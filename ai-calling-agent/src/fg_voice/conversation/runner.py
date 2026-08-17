"""Conversation orchestrator (spec §8.4).

Ties the graph, prompt bank, audio bank, extractor dispatch, interrupt
controller, backchannel picker, DTMF buffer, safety tripwire, and Redis
CallState store into a single async loop that drives one call from
START to a terminal node.

Lives in `conversation/` (not `pipeline/`) because the import-linter
layered contract puts conversation ABOVE pipeline — i.e. conversation
may reach down into pipeline for interrupt/backchannel/Flux helpers,
but not the other way around. Orchestrating the graph is a
conversation-layer concern.

I/O boundaries are two abstract protocols:

- `TurnInput` — source of caller-side events. The production impl
  reads Flux WebSocket frames + Twilio DTMF events; the test double
  emits a scripted sequence so integration tests are deterministic.
- `AudioSink` — destination for outbound audio frames + Twilio control
  messages. Production impl writes to the Twilio Media Streams WS;
  the test double records every clip played.

Keeping the runner protocol-driven means we can prove the full call
flow end to end without a phone or a Deepgram key, and swap in the
real transports without touching this file."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from typing import Final, Literal, Protocol

from fg_voice.audio.bank import AudioBank, Clip
from fg_voice.conversation.confidence import (
    extraction_confidence_gate,
    stt_confidence_gate,
)
from fg_voice.conversation.graph import EotConfig, ExtractorId, Graph, Node
from fg_voice.conversation.nodes import dtmf_slot_value, run_extractor
from fg_voice.conversation.policies import (
    CATEGORICAL_NODES,
    MAX_ATTEMPTS_CATEGORICAL,
    MAX_ATTEMPTS_FREE_TEXT,
    MAX_CALL_DURATION_SEC,
    reprompt_id_for,
    timing_for,
)
from fg_voice.conversation.prompt_bank import PromptBank
from fg_voice.conversation.safety import check_transcript
from fg_voice.conversation.state import TERMINAL_NODES, CallState, NodeId, SlotSource
from fg_voice.conversation.state_store import CallStateStore
from fg_voice.pipeline.backchannel import BackchannelPicker
from fg_voice.pipeline.eager_eot import EagerEotCoordinator, EagerEotStats
from fg_voice.pipeline.interrupt import InterruptController
from fg_voice.pipeline.stt_flux import FluxAction, FluxEvent, FluxEventKind, action_for
from fg_voice.telephony.dtmf import DtmfBuffer, map_digit

log = logging.getLogger(__name__)

# Sentinel returned from a turn collection when we didn't get a fillable answer.
_NO_ANSWER: Final[None] = None


class Hangup(Exception):
    """Raised by TurnInput.next_event when the transport closed. The
    runner catches this at the outer loop, persists final state, and
    returns without playing a further prompt."""


@dataclass(frozen=True, slots=True)
class InputEvent:
    """One event from the caller side. Only one of the payload fields
    is populated per event; `kind` disambiguates."""

    kind: Literal["flux", "dtmf"]
    flux_event: FluxEvent | None = None
    dtmf_digit: str | None = None


class TurnInput(Protocol):
    """Source of caller events. Returns None on no-input timeout.
    Raises `Hangup` if the transport closed."""

    async def next_event(self, timeout_ms: int) -> InputEvent | None: ...


class AudioSink(Protocol):
    """Destination for outbound audio + Twilio control frames."""

    async def play_clip(self, clip: Clip) -> None: ...
    async def send_clear(self, message: str) -> None: ...


class FluxReconfigurer(Protocol):
    """Push per-node EOT config to the live Flux WS. Production impl
    wraps `FluxClient.send_config`; the test double just records the
    values so tests can assert the runner emitted the correct pair
    on each prompted-node entry."""

    async def reconfigure(self, config: EotConfig) -> None: ...


@dataclass(slots=True)
class _NoopFluxReconfigurer:
    """Default when no Flux WS is wired (e.g. Gather-mode tests, P2.5
    integration tests). Silently drops the reconfigure — the runner
    still walks the graph; no Flux traffic gets emitted."""

    calls: list[EotConfig] = field(default_factory=list)

    async def reconfigure(self, config: EotConfig) -> None:
        self.calls.append(config)


@dataclass(frozen=True, slots=True)
class RunnerConfig:
    """All knobs the runner reads. Kept out of `Settings` so the test
    harness can pass a tiny config without touching env vars."""

    stream_sid: str = "MZfake"
    max_call_duration_sec: int = MAX_CALL_DURATION_SEC
    # Defaults pushed to Flux via `reconfigure(...)` when a per-node
    # override is absent. Mirror the `Settings.stt_eot_*` fields; kept
    # here so the runner works standalone in tests without touching
    # env vars.
    default_eot_threshold: float = 0.7
    default_eot_timeout_ms: int = 1200
    # Toggle eager-EOT speculative extraction. When True, the runner
    # instantiates an `EagerEotCoordinator` per turn and routes Flux
    # events through it so `EagerEndOfTurn` starts speculation and
    # `TurnResumed` cancels it. When False (the P2.5 default) the
    # runner treats those events as no-ops, matching prior behaviour.
    enable_eager_eot: bool = False


@dataclass(slots=True)
class RunResult:
    """Return value of `ConversationRunner.run`. `terminated_via` is
    the reason the loop exited — for dashboards + tests."""

    state: CallState
    terminated_via: Literal["terminal_node", "hangup", "max_call_duration"] = "terminal_node"


class ConversationRunner:
    """One instance per call. Not reusable — the state, backchannel
    picker, and interrupt controller are all per-call."""

    def __init__(
        self,
        *,
        call_state: CallState,
        graph: Graph,
        prompt_bank: PromptBank,
        audio_bank: AudioBank,
        turn_input: TurnInput,
        audio_sink: AudioSink,
        state_store: CallStateStore,
        config: RunnerConfig | None = None,
        flux_reconfigurer: FluxReconfigurer | None = None,
    ) -> None:
        self.state = call_state
        self.graph = graph
        self.prompt_bank = prompt_bank
        self.audio_bank = audio_bank
        self.turn_input = turn_input
        self.audio_sink = audio_sink
        self.state_store = state_store
        self.config = config or RunnerConfig()
        self.interrupt = InterruptController(
            stream_sid=self.config.stream_sid,
            send_clear=self.audio_sink.send_clear,
        )
        self.backchannel = BackchannelPicker()
        self.dtmf_buf = DtmfBuffer()
        # Prompt IDs the runner has played this call, in order — useful
        # for tests to assert the reprompt ladder actually played.
        self._prompt_trail: list[str] = []
        # Optional Flux reconfigurer. Defaults to a recording no-op so
        # tests can peek at what would have been pushed to Flux without
        # standing up a real WS.
        self.flux_reconfigurer: FluxReconfigurer = flux_reconfigurer or _NoopFluxReconfigurer()
        # Per-call eager-EOT stats aggregator. Populated only when
        # config.enable_eager_eot is True. Exposed so /metrics + tests
        # can assert hit_rate on the coordinator.
        self.eager_eot_stats: EagerEotStats = EagerEotStats()

    @property
    def prompt_trail(self) -> tuple[str, ...]:
        return tuple(self._prompt_trail)

    # ─── Main loop ───────────────────────────────────────────────────

    async def run(self) -> RunResult:
        try:
            return await asyncio.wait_for(
                self._run_loop(),
                timeout=self.config.max_call_duration_sec,
            )
        except TimeoutError:
            # Max call duration hit — transition to TIMEOUT_EXIT and
            # play its notice before returning. Persist so the post-call
            # DAG sees the final state.
            self.state.current_node = NodeId.TIMEOUT_EXIT
            await self._play_prompt_if_any(self.graph.node(NodeId.TIMEOUT_EXIT))
            await self._save()
            return RunResult(state=self.state, terminated_via="max_call_duration")
        except Hangup:
            await self._save()
            return RunResult(state=self.state, terminated_via="hangup")

    async def _run_loop(self) -> RunResult:
        while True:
            node = self.graph.node(self.state.current_node)
            if self._is_terminal(node):
                await self._play_prompt_if_any(node)
                await self._save()
                return RunResult(state=self.state, terminated_via="terminal_node")
            if node.is_machine:
                await self._advance_machine(node)
                continue
            await self._one_turn(node)

    # ─── Per-turn ────────────────────────────────────────────────────

    async def _one_turn(self, node: Node) -> None:
        prompt_id = self._current_prompt_id(node)
        await self._play_prompt(prompt_id)
        await self._save()

        # Prompted-but-no-extractor node (e.g. CONSENT) plays its
        # notice, then advances unconditionally. There is no caller
        # turn to collect.
        if node.extractor is ExtractorId.NONE:
            self._transition_to(self._first_matching_edge(node))
            return

        # Push per-node EOT knobs to Flux before we start listening
        # (§9.2). Nodes with per-node overrides (ASK_LOCATION,
        # CONFIRM_SUMMARY, etc.) get their tuned values; the rest fall
        # back to the runner defaults. NoopFluxReconfigurer records
        # the calls but sends nothing, so tests remain deterministic.
        eot = self.graph.effective_eot(
            node.id,
            default_threshold=self.config.default_eot_threshold,
            default_timeout_ms=self.config.default_eot_timeout_ms,
        )
        with contextlib.suppress(Exception):
            await self.flux_reconfigurer.reconfigure(eot)

        result = await self._collect_turn(node)
        if result is _NO_ANSWER:
            self._advance_ladder(node)
            return

        assert result is not None
        transcript, source = result

        # Safety tripwire runs BEFORE extraction so an "I'm bleeding"
        # utterance short-circuits to EMERGENCY_REDIRECT even if the
        # extractor would otherwise classify some other slot.
        if source == "asr":
            verdict = check_transcript(transcript)
            if verdict.triggered:
                self.state.add_flag("life_safety")
                # Remember where to resume so the post-emergency
                # re-entry (P3+) can pick up mid-conversation.
                self.state.resume_after_emergency = self.state.current_node
                self._transition_to(NodeId.EMERGENCY_REDIRECT)
                return

        # DTMF path bypasses the LLM/rule extractor entirely — the digit
        # maps through the prompt's dtmf_map to a canonical slot value.
        if source == "dtmf":
            prompt = self.prompt_bank.get(prompt_id)
            canonical = map_digit(transcript, prompt.dtmf)
            if canonical is None or node.slot is None:
                self._advance_ladder(node)
                return
            self.state.set_slot(node.slot, dtmf_slot_value(node.slot, canonical))
        else:
            slot_value = run_extractor(node.extractor, transcript, source="asr")
            # Extraction confidence gate (§9.4). Below the threshold,
            # the extractor produced a value but not confidently — the
            # reprompt ladder is safer than persisting a guess. The
            # gate returns fail for both None and low-confidence so a
            # single check covers both branches.
            extraction_gate = extraction_confidence_gate(slot_value)
            if not extraction_gate.pass_ or node.slot is None:
                log.info(
                    "runner.extraction_gate.dropped",
                    extra={
                        "reason": extraction_gate.reason,
                        "confidence": slot_value.confidence if slot_value else None,
                        "node_id": node.id,
                    },
                )
                self._advance_ladder(node)
                return
            assert slot_value is not None
            self.state.set_slot(node.slot, slot_value)

        target = self._first_matching_edge_or_none(node)
        if target is None:
            # Extractor filled the slot but no guard passed — treat as
            # unclear (defensive; the graph is defined so this shouldn't
            # normally happen, but a spec change could leave a gap).
            self._advance_ladder(node)
            return
        self._transition_to(target)

    async def _collect_turn(self, node: Node) -> tuple[str, SlotSource] | None:
        timing = timing_for(node.id)
        # Per-turn eager-EOT coordinator (if enabled). The extractor
        # here is an identity — the coordinator returns the transcript
        # verbatim, and the runner does the real extraction later in
        # `_one_turn`. That keeps the safety tripwire firing BEFORE
        # extraction (CLAUDE.md invariant #8) while still gaining the
        # coordinator's transcript-match reuse + TurnResumed cancel.
        eager: EagerEotCoordinator[str] | None = None
        if self.config.enable_eager_eot:

            async def _identity(transcript: str) -> str:
                return transcript

            eager = EagerEotCoordinator[str](extractor=_identity)

        while True:
            event = await self.turn_input.next_event(timeout_ms=timing.no_input_timeout_ms)
            if event is None:
                return _NO_ANSWER

            if event.kind == "dtmf":
                if event.dtmf_digit is None:
                    continue
                self.dtmf_buf.push(event.dtmf_digit)
                return (self.dtmf_buf.take(), "dtmf")

            # Flux event
            flux = event.flux_event
            if flux is None:
                continue
            action = action_for(flux)

            if action is FluxAction.BARGE_IN:
                await self.interrupt.on_start_of_turn()
                # Also let the eager coordinator reset its per-turn
                # state so a mid-flight speculation is cancelled at
                # the graph-level barge-in as well.
                if eager is not None:
                    eager.reset()
                continue

            if eager is not None and action in (
                FluxAction.SPECULATE,
                FluxAction.CANCEL_SPECULATION,
            ):
                # Fire-and-forget: the coordinator handles the async
                # speculation lifecycle. We don't await a return value
                # here — the speculation task lives on until END_OF_TURN.
                await eager.handle_event(flux)
                continue

            if action is FluxAction.COMMIT_TURN:
                # STT confidence gate (§9.4). Below the threshold, the
                # transcript is too uncertain to bother extracting —
                # treat as no-answer and let the ladder advance to
                # `reprompt_*_1`.
                stt_gate = stt_confidence_gate(flux.confidence)
                if not stt_gate.pass_:
                    log.info(
                        "runner.stt_gate.dropped",
                        extra={
                            "reason": stt_gate.reason,
                            "confidence": flux.confidence,
                            "node_id": node.id,
                        },
                    )
                    return _NO_ANSWER

                transcript = flux.transcript or ""
                if eager is not None:
                    # Route through the coordinator so it can reuse a
                    # matching speculation OR run a fresh identity
                    # "extraction" on the final transcript. Either way
                    # we get the transcript back as `result`.
                    result = await eager.handle_event(flux)
                    self._absorb_eager_stats(eager)
                    if result is None or not result.strip():
                        return _NO_ANSWER
                    transcript = result
                elif not transcript.strip():
                    return _NO_ANSWER
                # Play a short backchannel to mask the extractor pause.
                bc = self.backchannel.next(self.audio_bank)
                if bc is not None:
                    with contextlib.suppress(Exception):
                        await self.audio_sink.play_clip(bc)
                return (transcript, "asr")

            if action is FluxAction.NOOP or flux.kind is FluxEventKind.TURN_INFO:
                # Metadata / draft transcript updates — observability
                # only, no state change. Continue polling.
                continue

    def _absorb_eager_stats(self, eager: EagerEotCoordinator[str]) -> None:
        """Copy the per-turn coordinator's counters onto the per-call
        aggregate. Called on COMMIT_TURN so the runner-level stats
        reflect every turn that ran through the coordinator."""
        self.eager_eot_stats.speculations_started += eager.stats.speculations_started
        self.eager_eot_stats.speculations_reused += eager.stats.speculations_reused
        self.eager_eot_stats.speculations_cancelled += eager.stats.speculations_cancelled
        self.eager_eot_stats.speculations_discarded += eager.stats.speculations_discarded
        self.eager_eot_stats.final_extractions += eager.stats.final_extractions

    # ─── Reprompt ladder + transitions ───────────────────────────────

    def _current_prompt_id(self, node: Node) -> str:
        """Which prompt to play right now: the initial ask on attempt 0,
        or the next rung of the reprompt ladder."""
        if self.state.attempt == 0:
            assert node.prompt_id is not None, f"prompted node {node.id} has no prompt_id"
            return node.prompt_id
        reprompt = reprompt_id_for(node.id, self.state.attempt)
        if reprompt is not None:
            return reprompt
        assert node.prompt_id is not None
        return node.prompt_id

    def _advance_ladder(self, node: Node) -> None:
        """Called when the caller failed to fill the slot on this attempt."""
        self.state.attempt += 1
        max_att = (
            MAX_ATTEMPTS_CATEGORICAL if node.id in CATEGORICAL_NODES else MAX_ATTEMPTS_FREE_TEXT
        )
        if self.state.attempt > max_att:
            # Ladder exhausted. Exit gracefully (§7.3 row 4).
            self._transition_to(NodeId.TIMEOUT_EXIT)

    def _transition_to(self, target: NodeId) -> None:
        self.state.current_node = target
        self.state.attempt = 0

    async def _advance_machine(self, node: Node) -> None:
        self._transition_to(self._first_matching_edge(node))
        await self._save()

    def _first_matching_edge(self, node: Node) -> NodeId:
        for edge in node.transitions:
            if edge.guard(self.state):
                return edge.target
        raise AssertionError(f"machine/consent node {node.id} had no matching edge")

    def _first_matching_edge_or_none(self, node: Node) -> NodeId | None:
        for edge in node.transitions:
            if edge.guard(self.state):
                return edge.target
        return None

    # ─── Prompt playback ─────────────────────────────────────────────

    async def _play_prompt(self, prompt_id: str) -> None:
        self._prompt_trail.append(prompt_id)
        prompt = self.prompt_bank.get(prompt_id)
        clip = self.audio_bank.get(prompt_id)
        if clip is None:
            # Dynamic prompt with variables — live TTS lands in P3.
            # In P2.5 the runner is expected to advance regardless
            # so the graph reaches its terminal; the missing audio
            # shows up in the sink recording (nothing played) so
            # tests can detect the gap.
            log.debug(
                "runner: no audio bank clip for prompt_id=%s (dynamic prompt, needs live TTS)",
                prompt_id,
            )
            return
        await self._play_clip_with_interrupt(clip, barge_in=prompt.barge_in)

    async def _play_prompt_if_any(self, node: Node) -> None:
        if node.prompt_id is None:
            return
        await self._play_prompt(node.prompt_id)

    async def _play_clip_with_interrupt(self, clip: Clip, *, barge_in: bool) -> None:
        """Play a clip, tracking it on the interrupt controller so a
        Flux StartOfTurn during playback can cancel it. `barge_in=False`
        prompts (consent, emergency_redirect) still play through — the
        controller ignores mid-play interrupt requests for these because
        we never track them."""
        if not barge_in:
            with contextlib.suppress(Exception):
                await self.audio_sink.play_clip(clip)
            return

        task: asyncio.Task[None] = asyncio.create_task(self._play_and_swallow(clip))
        self.interrupt.track(task)
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            self.interrupt.release()

    async def _play_and_swallow(self, clip: Clip) -> None:
        with contextlib.suppress(Exception):
            await self.audio_sink.play_clip(clip)

    # ─── Helpers ─────────────────────────────────────────────────────

    def _is_terminal(self, node: Node) -> bool:
        return node.is_terminal or node.id in TERMINAL_NODES

    async def _save(self) -> None:
        await self.state_store.save(self.state)


__all__ = [
    "AudioSink",
    "ConversationRunner",
    "FluxReconfigurer",
    "Hangup",
    "InputEvent",
    "RunResult",
    "RunnerConfig",
    "TurnInput",
]
