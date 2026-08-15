"""Step-based conversation driver — one turn per invocation.

`ConversationRunner` (runner.py) drives a persistent async loop over a
Media Streams WebSocket. That model doesn't fit Twilio's `<Gather>`
verb, which is fundamentally HTTP: one webhook POST per caller turn,
Twilio does the STT itself, we return TwiML with the next prompt.

This driver is the same state machine expressed as a pure function:
given a `CallState` + one caller input, walk forward through the graph
until we either need to gather again or hit a terminal, and return a
`TurnStepResult` describing what TwiML to render. No `asyncio`, no
long-running coroutines, no persistent connection.

Shares three pieces of logic with the runner — reprompt-ladder
selection, machine-node advance, safety tripwire — but keeps its own
copy so a bug in one path never silently poisons the other. The graph,
prompt bank, extractors, and state store are all shared."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fg_voice.conversation.graph import ExtractorId, Graph, Node
from fg_voice.conversation.nodes import dtmf_slot_value, run_extractor
from fg_voice.conversation.policies import (
    CATEGORICAL_NODES,
    MAX_ATTEMPTS_CATEGORICAL,
    MAX_ATTEMPTS_FREE_TEXT,
    reprompt_id_for,
)
from fg_voice.conversation.prompt_bank import PromptBank
from fg_voice.conversation.safety import check_transcript
from fg_voice.conversation.state import (
    TERMINAL_NODES,
    CallState,
    NodeId,
    SlotSource,
)
from fg_voice.conversation.state_store import CallStateStore
from fg_voice.telephony.dtmf import map_digit

CallerInputKind = Literal["asr", "dtmf", "timeout"]


class DriverError(Exception):
    """Base for driver-level errors surfaced to the HTTP handler."""


class CallStateMissing(DriverError):
    def __init__(self, call_sid: str) -> None:
        super().__init__(f"no CallState for call_sid={call_sid!r}")


@dataclass(frozen=True, slots=True)
class CallerInput:
    """One caller turn as delivered by Twilio Gather. Only one of
    `transcript` / `digit` is populated per turn; a `timeout` kind
    means no caller input was collected."""

    kind: CallerInputKind
    transcript: str = ""
    digit: str = ""

    @classmethod
    def speech(cls, transcript: str) -> CallerInput:
        return cls(kind="asr", transcript=transcript)

    @classmethod
    def dtmf(cls, digit: str) -> CallerInput:
        return cls(kind="dtmf", digit=digit)

    @classmethod
    def timeout(cls) -> CallerInput:
        return cls(kind="timeout")


@dataclass(frozen=True, slots=True)
class TurnStepResult:
    """What the HTTP handler should render as TwiML this turn.

    - `prompts_to_play`: prompt_ids in order. All but the last are
      pure Say clips; the final entry is either (a) inside a Gather
      if `action="gather"`, or (b) followed by Hangup if
      `action="hangup"`.
    - `prompt_variables`: per-prompt template substitutions for the
      few dynamic prompts (confirm_summary, confirm_location_low_conf,
      submitted). Prompts absent from this dict take no variables.
    - `dtmf_map`: passed through to the Gather so Twilio knows a
      one-digit press is enough to submit. `None` means speech-only.
    - `hangup_after`: true when we should render a `<Hangup>` — always
      set when the state machine reached a terminal node."""

    prompts_to_play: tuple[str, ...]
    action: Literal["gather", "hangup"]
    prompt_variables: dict[str, dict[str, str]] = field(default_factory=dict)
    dtmf_map: dict[str, str] | None = None
    hangup_after: bool = False


class TurnDriver:
    """Stateless — every method loads CallState from the store, mutates
    it, saves it back. Safe to instantiate per-request."""

    def __init__(
        self,
        *,
        graph: Graph,
        prompt_bank: PromptBank,
        state_store: CallStateStore,
    ) -> None:
        self.graph = graph
        self.prompt_bank = prompt_bank
        self.state_store = state_store

    # ─── Public API ──────────────────────────────────────────────────

    async def start_call(
        self,
        *,
        call_sid: str,
        caller_hash: str,
    ) -> tuple[CallState, TurnStepResult]:
        """Fresh call. Creates a CallState at START and walks forward
        to the first Gather-worthy prompt."""
        state = CallState(call_sid=call_sid, caller_hash=caller_hash)
        result = await self._advance(state, caller_input=None)
        return state, result

    async def step(
        self,
        *,
        call_sid: str,
        caller_input: CallerInput,
    ) -> tuple[CallState, TurnStepResult]:
        """Continuation of an in-flight call. Loads the CallState,
        applies the caller's turn to the current node, then walks
        forward. Raises `CallStateMissing` if the state expired."""
        state = await self.state_store.load(call_sid)
        if state is None:
            raise CallStateMissing(call_sid)
        result = await self._advance(state, caller_input=caller_input)
        return state, result

    # ─── Core: one HTTP-turn worth of state-machine advance ──────────

    async def _advance(
        self,
        state: CallState,
        *,
        caller_input: CallerInput | None,
    ) -> TurnStepResult:
        prompts: list[str] = []
        variables: dict[str, dict[str, str]] = {}

        # Step 1: apply the caller's answer (if any) to the current node.
        if caller_input is not None:
            self._apply_input(state, caller_input)

        # Step 2: walk forward until we either need to gather again or
        # hit a terminal. Each iteration handles one node.
        while True:
            node = self.graph.node(state.current_node)

            if self._is_terminal(node):
                if node.prompt_id is not None:
                    prompts.append(node.prompt_id)
                    self._maybe_add_variables(node.prompt_id, state, variables)
                await self.state_store.save(state)
                return TurnStepResult(
                    prompts_to_play=tuple(prompts),
                    action="hangup",
                    prompt_variables=variables,
                    hangup_after=True,
                )

            if node.is_machine:
                state.current_node = _first_matching_edge(node, state)
                continue

            # Prompted node. Pick the right rung of the ladder.
            prompt_id = self._current_prompt_id(state, node)
            prompts.append(prompt_id)
            self._maybe_add_variables(prompt_id, state, variables)

            # Prompted-but-no-extractor (CONSENT, START_OVER) — play
            # the notice, then advance unconditionally in the same
            # HTTP response.
            if node.extractor is ExtractorId.NONE:
                state.current_node = _first_matching_edge(node, state)
                continue

            # Prompted with extractor — we need caller input. Save
            # and return, letting Twilio Gather do the collection.
            await self.state_store.save(state)
            return TurnStepResult(
                prompts_to_play=tuple(prompts),
                action="gather",
                prompt_variables=variables,
                dtmf_map=self.prompt_bank.get(prompt_id).dtmf,
                hangup_after=False,
            )

    # ─── Applying one caller answer to the current node ──────────────

    def _apply_input(self, state: CallState, caller_input: CallerInput) -> None:
        node = self.graph.node(state.current_node)
        if node.extractor is ExtractorId.NONE:
            # Caller input on a play-and-advance node is discarded —
            # not their fault, we shouldn't have been listening.
            return

        if caller_input.kind == "timeout":
            self._advance_ladder(state, node)
            return

        transcript = caller_input.transcript if caller_input.kind == "asr" else caller_input.digit
        if not transcript:
            self._advance_ladder(state, node)
            return

        # Safety tripwire on ASR turns — an "I'm bleeding" utterance
        # short-circuits to EMERGENCY_REDIRECT no matter which slot
        # we thought we were collecting.
        if caller_input.kind == "asr":
            verdict = check_transcript(transcript)
            if verdict.triggered:
                state.add_flag("life_safety")
                state.resume_after_emergency = state.current_node
                state.current_node = NodeId.EMERGENCY_REDIRECT
                state.attempt = 0
                return

        if caller_input.kind == "dtmf":
            prompt_id = self._current_prompt_id(state, node)
            prompt = self.prompt_bank.get(prompt_id)
            canonical = map_digit(caller_input.digit, prompt.dtmf)
            if canonical is None or node.slot is None:
                self._advance_ladder(state, node)
                return
            state.set_slot(node.slot, dtmf_slot_value(node.slot, canonical))
        else:
            source: SlotSource = "asr"
            slot_value = run_extractor(node.extractor, transcript, source=source)
            if slot_value is None or node.slot is None:
                self._advance_ladder(state, node)
                return
            state.set_slot(node.slot, slot_value)

        target = _first_matching_edge_or_none(node, state)
        if target is None:
            self._advance_ladder(state, node)
            return
        state.current_node = target
        state.attempt = 0

    # ─── Helpers (mirrored from runner.py; kept local on purpose) ────

    def _current_prompt_id(self, state: CallState, node: Node) -> str:
        if state.attempt == 0:
            assert node.prompt_id is not None, f"prompted node {node.id} has no prompt_id"
            return node.prompt_id
        reprompt = reprompt_id_for(node.id, state.attempt)
        if reprompt is not None:
            return reprompt
        assert node.prompt_id is not None
        return node.prompt_id

    def _advance_ladder(self, state: CallState, node: Node) -> None:
        state.attempt += 1
        max_att = (
            MAX_ATTEMPTS_CATEGORICAL if node.id in CATEGORICAL_NODES else MAX_ATTEMPTS_FREE_TEXT
        )
        if state.attempt > max_att:
            state.current_node = NodeId.TIMEOUT_EXIT
            state.attempt = 0

    # ─── Utilities ──────────────────────────────────────────────────

    def _is_terminal(self, node: Node) -> bool:
        return node.is_terminal or node.id in TERMINAL_NODES

    def _maybe_add_variables(
        self,
        prompt_id: str,
        state: CallState,
        variables: dict[str, dict[str, str]],
    ) -> None:
        """Fill dynamic template variables for the three prompts that
        take them in v1. Dynamic prompts without a data source in P2.5
        (confirm_location_low_conf, disambiguate_location) get whatever
        substitutions are available; the P4 RAG layer will populate the
        rest."""
        prompt = self.prompt_bank.get(prompt_id)
        if not prompt.variables:
            return
        subs: dict[str, str] = {}
        if "hazard_type_spoken" in prompt.variables:
            hz = state.slots.get(NODE_SLOT_MAP["hazard"])
            subs["hazard_type_spoken"] = _spoken_hazard(hz.value if hz else "the hazard")
        if "location_spoken" in prompt.variables:
            loc = state.slots.get(NODE_SLOT_MAP["location"])
            subs["location_spoken"] = str(loc.value) if loc else "the location you mentioned"
        if "severity_spoken" in prompt.variables:
            sv = state.slots.get(NODE_SLOT_MAP["severity"])
            subs["severity_spoken"] = _spoken_severity(sv.value if sv else "moderate")
        if "short_ref" in prompt.variables:
            subs["short_ref"] = _short_ref_for(state)
        if "location_candidate" in prompt.variables:
            loc = state.slots.get(NODE_SLOT_MAP["location"])
            subs["location_candidate"] = str(loc.value) if loc else "that location"
        if "option_a" in prompt.variables:
            subs["option_a"] = "the first one"
        if "option_b" in prompt.variables:
            subs["option_b"] = "the second one"
        variables[prompt_id] = subs


# ─── Small pure helpers ──────────────────────────────────────────────


from fg_voice.conversation.state import Slot  # noqa: E402 — placed after class to keep import light

NODE_SLOT_MAP = {
    "hazard": Slot.HAZARD_TYPE,
    "location": Slot.LOCATION,
    "severity": Slot.SEVERITY,
}


_HAZARD_SPOKEN: dict[str, str] = {
    "storm": "storm damage",
    "sludge_oil": "sludge or oil",
    "abnormal_tide": "unusual tides",
    "erosion": "erosion",
    "other": "a coastal hazard",
}
_SEVERITY_SPOKEN: dict[str, str] = {
    "light": "light",
    "moderate": "moderate",
    "extreme": "extreme",
}


def _spoken_hazard(value: object) -> str:
    return _HAZARD_SPOKEN.get(str(value), "a coastal hazard")


def _spoken_severity(value: object) -> str:
    return _SEVERITY_SPOKEN.get(str(value), "moderate")


def _short_ref_for(state: CallState) -> str:
    """Deterministic FG-XXXX from the report_id. Unambiguous alphabet
    (no 0/O/1/I) so callers reading it back over a noisy line don't
    trip on look-alikes. The real generator lands in P5 with the
    reports table; this is enough to render the terminal prompt in
    Gather mode."""
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    n = state.report_id.int
    out = []
    for _ in range(4):
        out.append(alphabet[n % len(alphabet)])
        n //= len(alphabet)
    return "FG-" + "".join(out)


def _first_matching_edge(node: Node, state: CallState) -> NodeId:
    for edge in node.transitions:
        if edge.guard(state):
            return edge.target
    raise AssertionError(f"machine/consent node {node.id} had no matching edge")


def _first_matching_edge_or_none(node: Node, state: CallState) -> NodeId | None:
    for edge in node.transitions:
        if edge.guard(state):
            return edge.target
    return None


__all__ = [
    "CallStateMissing",
    "CallerInput",
    "DriverError",
    "TurnDriver",
    "TurnStepResult",
]
