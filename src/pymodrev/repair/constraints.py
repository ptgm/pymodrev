"""
Row-based (bit-parallel) evaluation of candidate regulatory functions.

The repair search evaluates *thousands* of candidate functions for each
inconsistent node, always against the same labeling. The legacy evaluation
(``Updater.n_func_inconsistent_with_label_with_profile``) walks the time steps
of every profile, and for every step walks the clauses of the function, and for
every clause walks its regulators doing ``network.get_edge`` look-ups.

All of that can be compiled once per (labeling, node) into a small table of
"constraint rows"::

        state of the network at t   ->   value that node must take after the update

and a candidate function is then evaluated with a handful of Python big-int
operations (one bit per row), independently of the update scheme.

Every updater only has to say which rows it generates (see
``Updater.constraint_rows``); the classification of the result (consistent,
generalise, particularise, double inconsistency) is shared.
"""

from __future__ import annotations

from typing import Dict, Hashable, List, Optional, Sequence, Tuple, TYPE_CHECKING

from pymodrev.configuration import Inconsistencies

if TYPE_CHECKING:
    from pymodrev.network.function import Function
    from pymodrev.network.inconsistency_solution import InconsistencySolution
    from pymodrev.network.model import Model
    from pymodrev.network.observation_set import ObservationSet

CONSISTENT = Inconsistencies.CONSISTENT.value
SINGLE_INC_GEN = Inconsistencies.SINGLE_INC_GEN.value
SINGLE_INC_PART = Inconsistencies.SINGLE_INC_PART.value
DOUBLE_INC = Inconsistencies.DOUBLE_INC.value

# Kinds of segments (one segment per observation profile)
DYNAMIC = 'dynamic'   # (a)synchronous transitions: next value is observed
STEADY = 'steady'     # steady state: the node must keep its value


class ProfileRows:
    """
    The constraint rows a single profile imposes on a single node.

    ``states`` are the time maps (``{node_id: 0/1}``) in which the node is
    evaluated (they are *not* copied), ``outs`` the value the node must take
    right after.
    """
    __slots__ = ('kind', 'states', 'outs')

    def __init__(self, kind: str, states: List[Dict[str, int]], outs: List[int]):
        self.kind = kind
        self.states = states
        self.outs = outs


class NodeConstraints:
    """
    All the constraint rows imposed by a labeling on one node, stored as
    per-node bit columns so that candidate functions can be evaluated with
    bitwise operations.
    """

    def __init__(self, node_id: str, segments: Sequence[ProfileRows],
                 node_ids: Sequence[str]):
        self.node_id = node_id
        self._node_ids = tuple(node_ids)
        self.segments = list(segments)

        states: List[Dict[str, int]] = []
        outs: List[int] = []
        # (start, end, kind, value of the node in the first row)
        self._spans: List[Tuple[int, int, str, int]] = []
        for seg in self.segments:
            start = len(states)
            states.extend(seg.states)
            outs.extend(seg.outs)
            first_cur = seg.states[0][node_id] if seg.states else -1
            self._spans.append((start, len(states), seg.kind, first_cur))
        self._states = states
        self.n_rows = len(states)
        self.all_mask = (1 << self.n_rows) - 1
        self.out_bits = 0
        for i, o in enumerate(outs):
            if o == 1:
                self.out_bits |= 1 << i
        self._cols: Dict[str, int] = {}
        self._signature: Optional[Hashable] = None

    # ------------------------------------------------------------------ #
    # columns
    # ------------------------------------------------------------------ #
    def column(self, node: str) -> int:
        """Bitset (one bit per row) with the rows where ``node`` is 1."""
        col = self._cols.get(node)
        if col is None:
            col = 0
            for i, state in enumerate(self._states):
                if state[node] == 1:
                    col |= 1 << i
            self._cols[node] = col
        return col

    def literal(self, node: str, sign: int) -> int:
        """Bitset with the rows in which the literal of ``node`` is true."""
        col = self.column(node)
        return col if sign else (~col & self.all_mask)

    # ------------------------------------------------------------------ #
    # evaluation
    # ------------------------------------------------------------------ #
    def prediction(self, function: 'Function', network: 'Model') -> int:
        """Bitset with the rows in which ``function`` evaluates to 1."""
        regs = function.regulators
        lits = []
        for reg in regs:
            edge = network.get_edge(reg, function.node_id)
            lits.append(self.literal(reg, edge.sign))
        pred = 0
        all_mask = self.all_mask
        for clause in function.get_clauses():
            sat = all_mask
            for idx, bit in enumerate(clause.get_signature()):
                if bit:
                    sat &= lits[idx]
                    if not sat:
                        break
            pred |= sat
        return pred

    def evaluate(self, function: 'Function', network: 'Model') -> int:
        """
        Returns one of ``Inconsistencies`` values with exactly the semantics of
        the legacy per-updater ``n_func_inconsistent_with_label_with_profile``
        aggregated over all the profiles.
        """
        if self.n_rows == 0:
            return CONSISTENT

        if function.get_n_clauses() == 0:
            return self._evaluate_constant()

        pred = self.prediction(function, network)
        too_general = pred & ~self.out_bits   # predicts 1, observed 0
        too_specific = ~pred & self.out_bits & self.all_mask  # predicts 0, observed 1
        if too_general and too_specific:
            return DOUBLE_INC
        if too_general:
            return SINGLE_INC_PART
        if too_specific:
            return SINGLE_INC_GEN
        return CONSISTENT

    def is_consistent(self, function: 'Function', network: 'Model') -> bool:
        if self.n_rows == 0:
            return True
        if function.get_n_clauses() == 0:
            return self._evaluate_constant() == CONSISTENT
        pred = self.prediction(function, network)
        return pred == self.out_bits

    def _evaluate_constant(self) -> int:
        """
        Function without regulators: in dynamic profiles the node must keep the
        value it had the first time it was evaluated, in steady states
        anything goes.
        """
        for start, end, kind, first_cur in self._spans:
            if kind != DYNAMIC or end == start:
                continue
            seg_mask = ((1 << (end - start)) - 1) << start
            want = seg_mask if first_cur == 1 else 0
            if (self.out_bits & seg_mask) != want:
                return DOUBLE_INC
        return CONSISTENT

    # ------------------------------------------------------------------ #
    # separability
    # ------------------------------------------------------------------ #
    def separable(self, regulators: Sequence[Tuple[str, int]]) -> bool:
        """
        Necessary condition for a monotone function of ``regulators`` (pairs
        regulator/edge sign) to be consistent with the rows: no row that must
        evaluate to 1 may be dominated by a row that must evaluate to 0, i.e.
        for every such pair of rows there must be a regulator whose literal is
        true in the first row and false in the second.

        When it does not hold no function (whatever its shape) can repair the
        node with these regulators and signs, so the (expensive) search for
        functions can be skipped.
        """
        positive = self.out_bits
        negative = self.all_mask & ~positive
        if not positive or not negative:
            return True
        lits = [self.literal(reg, sign) for reg, sign in regulators]
        while positive:
            low = positive & -positive
            positive ^= low
            distinguished = 0
            for lit in lits:
                if lit & low:
                    distinguished |= ~lit
            if negative & ~distinguished:
                return False
        return True

    # ------------------------------------------------------------------ #
    # signatures
    # ------------------------------------------------------------------ #
    @property
    def signature(self) -> Hashable:
        """
        A hashable value such that two NodeConstraints with the same signature
        accept exactly the same functions (used to share work between ASP
        solutions that only differ in irrelevant details of the trajectory).
        """
        if self._signature is None:
            order = self._node_ids
            segs = []
            for (start, end, kind, first_cur), seg in zip(self._spans, self.segments):
                rows = frozenset(
                    (tuple(state[n] for n in order), out)
                    for state, out in zip(seg.states, seg.outs))
                segs.append((kind, first_cur, rows))
            self._signature = frozenset(segs)
        return self._signature

    def row_values(self) -> List[Tuple[Dict[str, int], int]]:
        """(state, out) for every row (used by the topology pruning)."""
        outs = [(self.out_bits >> i) & 1 for i in range(self.n_rows)]
        return list(zip(self._states, outs))

    def split_positive_negative(self) -> Tuple[List[Dict[str, int]], List[Dict[str, int]]]:
        """
        Distinct states of the rows that require the node to be 1 / 0 after
        the update (only for non-constant functions).
        """
        pos: Dict[Tuple, Dict[str, int]] = {}
        neg: Dict[Tuple, Dict[str, int]] = {}
        order = self._node_ids
        for i, state in enumerate(self._states):
            key = tuple(state[n] for n in order)
            if (self.out_bits >> i) & 1:
                pos.setdefault(key, state)
            else:
                neg.setdefault(key, state)
        return list(pos.values()), list(neg.values())


def get_node_constraints(
        network: 'Model',
        observation_set: 'ObservationSet',
        labeling: 'InconsistencySolution',
        node_id: str) -> Optional[NodeConstraints]:
    """
    Builds (and caches in the labeling) the NodeConstraints of ``node_id``.

    Returns None when some profile belongs to an updater that does not support
    constraint rows (callers must then fall back to the legacy evaluation).
    """
    cache = labeling.constraint_cache
    if node_id in cache:
        return cache[node_id]
    segments: List[ProfileRows] = []
    result: Optional[NodeConstraints] = None
    supported = True
    for profile in labeling.v_label:
        updater = observation_set.get_observation_updater(profile)
        rows = None
        if updater is not None:
            rows = updater.constraint_rows(labeling, node_id, profile)
        if rows is None:
            supported = False
            break
        segments.append(rows)
    if supported:
        result = NodeConstraints(node_id, segments, sorted(network.nodes))
    cache[node_id] = result
    return result
