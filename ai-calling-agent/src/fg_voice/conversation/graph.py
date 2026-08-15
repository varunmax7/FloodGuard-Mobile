"""Static definition of the conversation DAG (spec §8.1, §8.2).

The graph is data, not code: nodes and edges are declared once, the
runner walks them. No guard performs I/O; extraction results already
sit on `CallState.slots` when a guard is evaluated. This is what makes
the graph deterministically testable and replayable — see §18.1."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from fg_voice.conversation.state import TERMINAL_NODES, CallState, NodeId, Slot


class ExtractorId(StrEnum):
    """Which extractor a node's turn should invoke. Kept as an enum so
    the graph can be validated statically before any extractor code is
    imported (avoids a hard dep from the graph on `extraction/`)."""

    NONE = "none"
    INTENT = "intent"
    HAZARD_TYPE = "hazard_type"
    DESCRIPTION = "description"
    LOCATION = "location"
    SEVERITY = "severity"
    DEPTH = "depth"
    CONFIRMATION = "confirmation"


Guard = Callable[[CallState], bool]


@dataclass(frozen=True, slots=True)
class Edge:
    """First edge whose guard returns True wins. `label` is only for
    logs / graph diagrams — never shown to the caller."""

    guard: Guard
    target: NodeId
    label: str


@dataclass(frozen=True, slots=True)
class Node:
    id: NodeId
    prompt_id: str | None
    slot: Slot | None
    extractor: ExtractorId
    transitions: tuple[Edge, ...]
    is_terminal: bool = False
    # `is_machine` nodes require no caller input — their single edge fires
    # as soon as the runner enters them. Used for START, RESOLVE_LOCATION,
    # SUBMIT, and START_OVER.
    is_machine: bool = False


@dataclass(frozen=True, slots=True)
class Graph:
    nodes: dict[NodeId, Node] = field(default_factory=dict)
    start: NodeId = NodeId.START
    # Nodes reachable via out-of-band paths (tripwire, timeout, fatal).
    # The runner enters them by calling `escalate_to(...)` on the state,
    # not by following a declared edge. Listed here so reachability
    # tests know they aren't orphans.
    global_interrupt_targets: frozenset[NodeId] = frozenset(
        {NodeId.EMERGENCY_REDIRECT, NodeId.TIMEOUT_EXIT, NodeId.FATAL_FALLBACK}
    )

    def node(self, node_id: NodeId) -> Node:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise UnknownNodeError(node_id) from exc

    def reachable_from_start(self) -> frozenset[NodeId]:
        """BFS from START plus global_interrupt_targets. Every declared
        node must be in the result — otherwise the graph has an orphan
        and boot fails."""
        seen: set[NodeId] = set()
        queue: deque[NodeId] = deque([self.start, *self.global_interrupt_targets])
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            for edge in self.node(current).transitions:
                if edge.target not in seen:
                    queue.append(edge.target)
        return frozenset(seen)


class UnknownNodeError(KeyError):
    def __init__(self, node_id: NodeId) -> None:
        super().__init__(f"unknown node_id: {node_id!r}")


# ─── Guard primitives (pure) ─────────────────────────────────────────
# Named module-level closures so `dataclass(frozen=True)` can hash the
# graph and pytest can pretty-print the failing edge. Lambdas would work
# for the runner but destroy the stack traces.


def _always(_: CallState) -> bool:
    return True


def _slot_equals(slot: Slot, expected: str) -> Guard:
    def guard(state: CallState) -> bool:
        v = state.get_slot(slot)
        return v is not None and v.value == expected

    guard.__name__ = f"_slot_equals[{slot.value}={expected}]"
    return guard


def _slot_in(slot: Slot, expected: frozenset[str]) -> Guard:
    def guard(state: CallState) -> bool:
        v = state.get_slot(slot)
        return v is not None and isinstance(v.value, str) and v.value in expected

    guard.__name__ = f"_slot_in[{slot.value} in {sorted(expected)}]"
    return guard


def _hazard_is_flood_class(state: CallState) -> bool:
    return state.hazard_is_flood_class()


# ─── Node factory helpers ────────────────────────────────────────────


def _leaf(node_id: NodeId, prompt_id: str, terminal: bool = True) -> Node:
    return Node(
        id=node_id,
        prompt_id=prompt_id,
        slot=None,
        extractor=ExtractorId.NONE,
        transitions=(Edge(_always, NodeId.END, "→END"),),
        is_terminal=terminal,
    )


def _machine(node_id: NodeId, target: NodeId, label: str) -> Node:
    return Node(
        id=node_id,
        prompt_id=None,
        slot=None,
        extractor=ExtractorId.NONE,
        transitions=(Edge(_always, target, label),),
        is_machine=True,
    )


# ─── The actual graph ────────────────────────────────────────────────


def build_graph() -> Graph:
    nodes: dict[NodeId, Node] = {}

    # START → CONSENT (machine)
    nodes[NodeId.START] = _machine(NodeId.START, NodeId.CONSENT, "boot→consent")

    # CONSENT plays a non-interruptible notice, then unconditionally
    # advances to ASK_INTENT.
    nodes[NodeId.CONSENT] = Node(
        id=NodeId.CONSENT,
        prompt_id="consent_notice",
        slot=None,
        extractor=ExtractorId.NONE,
        transitions=(Edge(_always, NodeId.ASK_INTENT, "consent→ask_intent"),),
    )

    nodes[NodeId.ASK_INTENT] = Node(
        id=NodeId.ASK_INTENT,
        prompt_id="ask_intent",
        slot=Slot.INTENT,
        extractor=ExtractorId.INTENT,
        transitions=(
            Edge(_slot_equals(Slot.INTENT, "yes"), NodeId.ASK_HAZARD_TYPE, "intent=yes"),
            Edge(_slot_equals(Slot.INTENT, "no"), NodeId.NOT_REPORTING, "intent=no"),
        ),
    )

    nodes[NodeId.NOT_REPORTING] = _leaf(NodeId.NOT_REPORTING, "not_reporting")

    nodes[NodeId.ASK_HAZARD_TYPE] = Node(
        id=NodeId.ASK_HAZARD_TYPE,
        prompt_id="ask_hazard_type",
        slot=Slot.HAZARD_TYPE,
        extractor=ExtractorId.HAZARD_TYPE,
        transitions=(
            Edge(
                _slot_in(
                    Slot.HAZARD_TYPE,
                    frozenset({"storm", "sludge_oil", "abnormal_tide", "erosion", "other"}),
                ),
                NodeId.ASK_DESCRIPTION,
                "hazard=resolved",
            ),
        ),
    )

    nodes[NodeId.ASK_DESCRIPTION] = Node(
        id=NodeId.ASK_DESCRIPTION,
        prompt_id="ask_description",
        slot=Slot.DESCRIPTION,
        extractor=ExtractorId.DESCRIPTION,
        transitions=(Edge(_always, NodeId.ASK_LOCATION, "description→ask_location"),),
    )

    nodes[NodeId.ASK_LOCATION] = Node(
        id=NodeId.ASK_LOCATION,
        prompt_id="ask_location",
        slot=Slot.LOCATION,
        extractor=ExtractorId.LOCATION,
        transitions=(Edge(_always, NodeId.RESOLVE_LOCATION, "location→resolve"),),
    )

    # RESOLVE_LOCATION is a machine node that fans out based on the
    # gazetteer confidence tracked on the LOCATION slot. In P2 the
    # confidence is a passthrough from the free-text extractor, so
    # the low-confidence branch is normally taken; P4 replaces this
    # with the real gazetteer.
    nodes[NodeId.RESOLVE_LOCATION] = Node(
        id=NodeId.RESOLVE_LOCATION,
        prompt_id=None,
        slot=None,
        extractor=ExtractorId.NONE,
        transitions=(
            Edge(_location_confidently_resolved, NodeId.ASK_SEVERITY, "geo≥0.85"),
            Edge(_location_ambiguous, NodeId.DISAMBIGUATE_LOCATION, "geo margin<0.10"),
            Edge(_location_needs_confirm, NodeId.CONFIRM_LOCATION_LOW_CONF, "geo∈[0.60,0.85)"),
            Edge(_always, NodeId.ASK_LOCATION, "geo<0.60→retry"),
        ),
        is_machine=True,
    )

    nodes[NodeId.CONFIRM_LOCATION_LOW_CONF] = Node(
        id=NodeId.CONFIRM_LOCATION_LOW_CONF,
        prompt_id="confirm_location_low_conf",
        slot=Slot.CONFIRMATION,
        extractor=ExtractorId.CONFIRMATION,
        transitions=(
            Edge(_slot_equals(Slot.CONFIRMATION, "yes"), NodeId.ASK_SEVERITY, "confirmed"),
            Edge(_always, NodeId.ASK_LOCATION, "reject→ask_location"),
        ),
    )

    nodes[NodeId.DISAMBIGUATE_LOCATION] = Node(
        id=NodeId.DISAMBIGUATE_LOCATION,
        prompt_id="disambiguate_location",
        slot=Slot.LOCATION,
        extractor=ExtractorId.LOCATION,
        transitions=(Edge(_always, NodeId.ASK_SEVERITY, "picked→ask_severity"),),
    )

    nodes[NodeId.ASK_SEVERITY] = Node(
        id=NodeId.ASK_SEVERITY,
        prompt_id="ask_severity",
        slot=Slot.SEVERITY,
        extractor=ExtractorId.SEVERITY,
        transitions=(
            Edge(_hazard_is_flood_class, NodeId.ASK_DEPTH, "flood-class→ask_depth"),
            Edge(_always, NodeId.CONFIRM_SUMMARY, "→confirm"),
        ),
    )

    nodes[NodeId.ASK_DEPTH] = Node(
        id=NodeId.ASK_DEPTH,
        prompt_id="ask_depth",
        slot=Slot.WATER_DEPTH_CM,
        extractor=ExtractorId.DEPTH,
        transitions=(Edge(_always, NodeId.CONFIRM_SUMMARY, "→confirm"),),
    )

    nodes[NodeId.CONFIRM_SUMMARY] = Node(
        id=NodeId.CONFIRM_SUMMARY,
        prompt_id="confirm_summary",
        slot=Slot.CONFIRMATION,
        extractor=ExtractorId.CONFIRMATION,
        transitions=(
            Edge(_slot_equals(Slot.CONFIRMATION, "yes"), NodeId.SUBMIT, "confirmed→submit"),
            Edge(_slot_equals(Slot.CONFIRMATION, "restart"), NodeId.START_OVER, "restart"),
            Edge(_slot_equals(Slot.CONFIRMATION, "no"), NodeId.START_OVER, "no→restart"),
        ),
    )

    nodes[NodeId.START_OVER] = Node(
        id=NodeId.START_OVER,
        prompt_id="start_over",
        slot=None,
        extractor=ExtractorId.NONE,
        transitions=(Edge(_always, NodeId.ASK_HAZARD_TYPE, "restart→ask_hazard"),),
        is_machine=True,
    )

    nodes[NodeId.SUBMIT] = _machine(NodeId.SUBMIT, NodeId.SUBMITTED, "submit→submitted")
    nodes[NodeId.SUBMITTED] = _leaf(NodeId.SUBMITTED, "submitted", terminal=True)

    # Global interrupt destinations. Their `transitions` route to END
    # so the reachability test passes; the runner may instead just hang
    # up on entering these (e.g. FATAL_FALLBACK), which is fine.
    nodes[NodeId.EMERGENCY_REDIRECT] = Node(
        id=NodeId.EMERGENCY_REDIRECT,
        prompt_id="emergency_redirect",
        slot=None,
        extractor=ExtractorId.NONE,
        transitions=(Edge(_always, NodeId.END, "emergency→end"),),
    )
    nodes[NodeId.TIMEOUT_EXIT] = _leaf(NodeId.TIMEOUT_EXIT, "timeout_exit", terminal=True)
    nodes[NodeId.FATAL_FALLBACK] = _leaf(NodeId.FATAL_FALLBACK, "fatal_fallback", terminal=True)

    # END has no prompt and no outgoing edges — its own terminal marker.
    nodes[NodeId.END] = Node(
        id=NodeId.END,
        prompt_id=None,
        slot=None,
        extractor=ExtractorId.NONE,
        transitions=(),
        is_terminal=True,
    )

    return Graph(nodes=nodes)


# ─── Location confidence guards (P2 stubs; P4 replaces backing data) ─
# In P2 the free-text extractor stores confidence=0.6 for any non-empty
# LOCATION utterance. That places us in the "confirm" branch by default,
# which matches the spec's low-confidence path.


def _location_confidence(state: CallState) -> float:
    v = state.get_slot(Slot.LOCATION)
    return v.confidence if v is not None else 0.0


def _location_confidently_resolved(state: CallState) -> bool:
    return _location_confidence(state) >= 0.85


def _location_needs_confirm(state: CallState) -> bool:
    c = _location_confidence(state)
    return 0.60 <= c < 0.85


def _location_ambiguous(state: CallState) -> bool:
    # Placeholder: the P4 gazetteer will set a `location_ambiguous` flag
    # on the CallState when the top-1/top-2 margin is < 0.10. Until then
    # we never take this branch.
    return "location_ambiguous" in state.flags


# ─── Terminal check helper ───────────────────────────────────────────


TERMINAL_CAP_HOPS: Final[int] = 20


def is_terminal_node(node: Node) -> bool:
    return node.is_terminal or node.id in TERMINAL_NODES


__all__ = [
    "TERMINAL_CAP_HOPS",
    "Edge",
    "ExtractorId",
    "Graph",
    "Guard",
    "Node",
    "UnknownNodeError",
    "build_graph",
    "is_terminal_node",
]
