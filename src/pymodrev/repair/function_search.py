"""
Function search and replacement logic for model revision.

This module provides functions to search for comparable and non-comparable
replacement functions that can resolve inconsistencies in the network.
"""

import logging
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.network.inconsistent_node import InconsistentNode
from pymodrev.network.repair_set import RepairSet
from pymodrev.network.model import Model
from pymodrev.network.observation_set import ObservationSet
from pymodrev.network.function import Function
from pymodrev.network.edge import Edge
from pymodrev.repair.consistency import (
    n_func_inconsistent_with_label,
    is_func_consistent_with_label,
    is_function_in_bottom_half,
)
from pymodrev.configuration import config, Inconsistencies

logger = logging.getLogger(__name__)


def _function_eval_key(network: Model, function: Function) -> Tuple:
    """
    Build a stable key for caching function consistency evaluations.

    The key includes the function shape and the current signs of all edges
    from its regulators to the target node, because edge signs influence
    consistency checks.
    """
    edge_signature = []
    for regulator in function.regulators:
        edge = network.get_edge(regulator, function.node_id)
        edge_signature.append((regulator, edge.sign if edge is not None else None))
    return function.node_id, hash(function), tuple(edge_signature)


def _cached_is_func_consistent(
        network: Model,
        observation_set: ObservationSet,
        inconsistency: InconsistencySolution,
    function: Any,
    consistency_cache: Optional[Dict[Tuple, Any]]) -> bool:
    if consistency_cache is None:
        return is_func_consistent_with_label(network, observation_set, inconsistency, function)
    key = ("is", _function_eval_key(network, function))
    if key not in consistency_cache:
        consistency_cache[key] = is_func_consistent_with_label(
            network, observation_set, inconsistency, function)
    return consistency_cache[key]


def _cached_n_func_inconsistent(
        network: Model,
        observation_set: ObservationSet,
        inconsistency: InconsistencySolution,
    function: Any,
    consistency_cache: Optional[Dict[Tuple, Any]]) -> int:
    if consistency_cache is None:
        return n_func_inconsistent_with_label(network, observation_set, inconsistency, function)
    key = ("n", _function_eval_key(network, function))
    if key not in consistency_cache:
        consistency_cache[key] = n_func_inconsistent_with_label(
            network, observation_set, inconsistency, function)
    return consistency_cache[key]


def _add_repair_set_for_candidate(
        inconsistency: InconsistencySolution,
        inconsistent_node: InconsistentNode,
    candidate: Any,
        flipped_edges: List[Edge],
        added_edges: List[Edge],
        removed_edges: List[Edge]) -> None:
    repair_set = RepairSet()
    repair_set.add_repaired_function(candidate)
    for edge in flipped_edges:
        repair_set.add_flipped_edge(edge)
    for edge in removed_edges:
        repair_set.remove_edge(edge)
    for edge in added_edges:
        repair_set.add_edge(edge)
    inconsistency.add_repair_set(inconsistent_node.identifier, repair_set)


def _mode1_burst_probe_comparable(
        network: Model,
        observation_set: ObservationSet,
        inconsistency: InconsistencySolution,
    candidates: List[Any],
    consistency_cache: Optional[Dict[Tuple, Any]]) -> Tuple[set, Optional[Any]]:
    """
    Probe sparse candidate bursts for mode 1 before full traversal.

    This evaluates a small, distance-spread subset (including near and far
    candidates). If none is consistent, caller falls back to exhaustive
    traversal, preserving semantics.
    """
    tested_candidates = set()
    if not candidates:
        return tested_candidates, None

    ordered = sorted(candidates, key=lambda c: c.distance_from_original)
    n_candidates = len(ordered)

    probe_indexes = {0, n_candidates - 1}
    step = 1
    while step < n_candidates:
        probe_indexes.add(min(step, n_candidates - 1))
        probe_indexes.add(max(n_candidates - 1 - step, 0))
        step *= 2

    for idx in sorted(probe_indexes):
        candidate = ordered[idx]
        if candidate in tested_candidates:
            continue
        tested_candidates.add(candidate)
        if _cached_is_func_consistent(
                network,
                observation_set,
                inconsistency,
                candidate,
                consistency_cache):
            return tested_candidates, candidate

    return tested_candidates, None


def _mode1_burst_probe_non_comparable(
        network: Model,
        observation_set: ObservationSet,
        inconsistency: InconsistencySolution,
    seed_candidate: Any,
        is_generalize: bool,
        consistency_cache: Optional[Dict[Tuple, Any]],
        max_bursts: int = 3):
    """
    Probe sparse bursts of the non-comparable space for mode 1.

    It expands candidates in exponentially larger bursts and evaluates only
    representative functions from each burst. If no solution is found, caller
    falls back to the full traversal.
    """
    queue = deque([seed_candidate])
    queued_candidates = {seed_candidate}
    tested_candidates = set()
    burst_size = 1
    for _ in range(max_bursts):
        if not queue:
            break

        burst_window = []
        while queue and len(burst_window) < burst_size:
            candidate = queue.popleft()
            queued_candidates.discard(candidate)
            if candidate in tested_candidates:
                continue
            tested_candidates.add(candidate)
            burst_window.append(candidate)

            for new_candidate in candidate.get_replacements(is_generalize):
                if new_candidate not in queued_candidates and new_candidate not in tested_candidates:
                    queue.append(new_candidate)
                    queued_candidates.add(new_candidate)

        if not burst_window:
            burst_size *= 2
            continue

        probe_candidates = [burst_window[0]]
        if len(burst_window) > 1:
            probe_candidates.append(burst_window[-1])

        for candidate in probe_candidates:
            inc_type = _cached_n_func_inconsistent(
                network,
                observation_set,
                inconsistency,
                candidate,
                consistency_cache,
            )
            if inc_type == Inconsistencies.CONSISTENT.value:
                return candidate

        burst_size *= 2

    return None


def search_comparable_functions(
        network: Model,
        observation_set: ObservationSet,
        inconsistency: InconsistencySolution,
        inconsistent_node: InconsistentNode,
        flipped_edges: List[Edge],
        added_edges: List[Edge],
        removed_edges: List[Edge],
    generalize: bool,
        consistency_cache: Optional[Dict[Tuple, Any]] = None) -> bool:
    """
    Searches for comparable functions that can repair the inconsistency of a
    node. It evaluates potential replacement functions and applies the
    necessary edges to resolve the inconsistency.
    """
    sol_found = False
    original_node = network.get_node(inconsistent_node.identifier)
    if original_node is None:
        logger.warning(f"Inconsistent node {inconsistent_node.identifier} not found in network")
        inconsistency.has_impossibility = True
        return False
    original_f = original_node.function

    if original_f is None:
        logger.warning(f"Inconsistent node {inconsistent_node.identifier} without regulatory function")
        inconsistency.has_impossibility = True
        return False

    if original_f.get_n_regulators() < 2:
        return False

    logger.debug(f"Searching for comparable functions of dimension {original_f.get_n_regulators()} going {'down' if generalize else 'up'}")

    # Get the replacement candidates
    function_repaired = False
    repaired_function_level = -1
    initial_candidates: List[Any] = list(original_f.pfh_get_replacements(generalize))

    tested_candidates = set()
    if config.solutions == 1 and initial_candidates:
        tested_candidates, burst_candidate = _mode1_burst_probe_comparable(
            network,
            observation_set,
            inconsistency,
            initial_candidates,
            consistency_cache,
        )
        if burst_candidate is not None:
            _add_repair_set_for_candidate(
                inconsistency,
                inconsistent_node,
                burst_candidate,
                flipped_edges,
                added_edges,
                removed_edges,
            )
            return True

    t_candidates = deque(initial_candidates)
    queued_candidates = set(t_candidates)

    while t_candidates:
        candidate: Any = t_candidates.popleft()
        queued_candidates.discard(candidate)
        if candidate in tested_candidates:
            continue
        tested_candidates.add(candidate)
        # Already found a good function, but will still search for more equally good
        if function_repaired and candidate.distance_from_original > \
                repaired_function_level:
            continue
        if _cached_is_func_consistent(
            network,
            observation_set,
            inconsistency,
            candidate,
            consistency_cache):
            _add_repair_set_for_candidate(
                inconsistency,
                inconsistent_node,
                candidate,
                flipped_edges,
                added_edges,
                removed_edges,
            )
            function_repaired = True
            sol_found = True
            repaired_function_level = candidate.distance_from_original
            if config.solutions <= 2:
                break
        else:
            taux_candidates = candidate.pfh_get_replacements(generalize)
            if taux_candidates:
                for taux_candidate in taux_candidates:
                    if taux_candidate not in queued_candidates and taux_candidate not in tested_candidates:
                        t_candidates.append(taux_candidate)
                        queued_candidates.add(taux_candidate)

    return sol_found


def search_non_comparable_functions(
        network: Model,
        observation_set: ObservationSet,
        inconsistency: InconsistencySolution,
        inconsistent_node: InconsistentNode,
        flipped_edges: List[Edge],
        added_edges: List[Edge],
        removed_edges: List[Edge],
        consistency_cache: Optional[Dict[Tuple, Any]] = None) -> bool:
    """
    Searches for non-comparable functions to resolve inconsistencies in the
    given network. Attempts to replace an inconsistent function with a
    consistent alternative.
    """
    sol_found, function_repaired = False, False
    candidates = deque()
    queued_candidates = set()
    tested_candidates = set()
    consistent_functions = []
    consistent_functions_set = set()
    best_below, best_above, equal_level = [], [], []
    level_compare = config.compare_level_function

    # Each function must have a list of replacement candidates and each must
    # be tested until it works
    original_node = network.get_node(inconsistent_node.identifier)
    if original_node is None:
        logger.warning(f"Inconsistent node {inconsistent_node.identifier} not found in network")
        inconsistency.has_impossibility = True
        return False
    original_f = original_node.function
    original_map = original_f.regulators_by_term

    if original_f.get_n_regulators() < 2:
        return False

    logger.debug(f"Searching for non-comparable functions of dimension {original_f.get_n_regulators()}")

    # Construction of new function to start search
    # TODO is missing the copy of the other attributes, might lead to error
    new_f = Function(original_f.node_id)

    # If the function is in the lower half of the Hasse diagram, start search
    # at the most specific function and generalize
    is_generalize = True
    if level_compare:
        logger.debug("Starting half determination")
        is_generalize = is_function_in_bottom_half(network, original_f)
        logger.debug("End half determination")
        logger.debug(f"Performing a search going {'up' if is_generalize else 'down'}")

    cindex = 1
    for _, _vars in original_map.items():
        for var in _vars:
            new_f.add_regulator_to_term(cindex, var)
            if not is_generalize:
                cindex += 1

    candidates.append(new_f)
    queued_candidates.add(new_f)

    if config.solutions == 1:
        burst_skip_key = ("burst", "non-comparable-skip", inconsistent_node.identifier)
        should_probe_burst = not (consistency_cache is not None and consistency_cache.get(burst_skip_key, False))

        if should_probe_burst:
            burst_candidate = _mode1_burst_probe_non_comparable(
                network,
                observation_set,
                inconsistency,
                new_f,
                is_generalize,
                consistency_cache,
            )
            if burst_candidate is not None:
                _add_repair_set_for_candidate(
                    inconsistency,
                    inconsistent_node,
                    burst_candidate,
                    flipped_edges,
                    added_edges,
                    removed_edges,
                )
                return True

            # Adaptive cutoff: after the first miss for this node in mode 1,
            # skip future non-comparable burst probes and go straight to full search.
            if consistency_cache is not None:
                consistency_cache[burst_skip_key] = True

    logger.debug(f"Finding functions for double inconsistency in {original_f.print_function(network=network)}")

    counter = 0
    while candidates:
        counter += 1
        candidate = candidates.popleft()
        queued_candidates.discard(candidate)
        is_consistent = False

        # Skip candidates that were already evaluated.
        if candidate in tested_candidates:
            continue
        tested_candidates.add(candidate)

        inc_type = _cached_n_func_inconsistent(
            network,
            observation_set,
            inconsistency,
            candidate,
            consistency_cache,
        )
        if inc_type == Inconsistencies.CONSISTENT.value:
            is_consistent = True
            if candidate not in consistent_functions_set:
                consistent_functions.append(candidate)
                consistent_functions_set.add(candidate)
            if not function_repaired:
                logger.debug(f"Found first function at level {candidate.distance_from_original} {candidate.print_function(network=network)}")
            function_repaired, sol_found = True, True

            # Mode 1 only needs the first valid repair candidate.
            # Short-circuiting here avoids unnecessary exploration aimed at
            # collecting equivalent/alternative candidates for richer modes.
            if config.solutions == 1:
                _add_repair_set_for_candidate(
                    inconsistency,
                    inconsistent_node,
                    candidate,
                    flipped_edges,
                    added_edges,
                    removed_edges,
                )
                return True

            if level_compare:
                cmp = original_f.compare_level(candidate)
                if cmp == 0:
                    equal_level.append(candidate)
                    continue
                if (is_generalize and cmp < 0 and equal_level) \
                        or (not is_generalize and cmp > 0 and equal_level):
                    continue
                if cmp > 0 and not equal_level:
                    if not best_below:
                        best_below.append(candidate)
                    else:
                        rep_cmp = best_below[0].compare_level(candidate)
                        if rep_cmp == 0:
                            best_below.append(candidate)
                        elif rep_cmp < 0:
                            best_below = [candidate]
                    if not is_generalize:
                        continue
                if cmp < 0 and not equal_level:
                    if not best_above:
                        best_above.append(candidate)
                    else:
                        rep_cmp = best_above[0].compare_level(candidate)
                        if rep_cmp == 0:
                            best_above.append(candidate)
                        elif rep_cmp > 0:
                            best_above = [candidate]
                    if is_generalize:
                        continue
        else:
            if candidate.son_consistent:
                del candidate
                continue

            if inc_type == Inconsistencies.DOUBLE_INC.value or \
                    (is_generalize
                     and inc_type == Inconsistencies.SINGLE_INC_PART.value) \
                    or (not is_generalize
                        and inc_type == Inconsistencies.SINGLE_INC_GEN.value):
                del candidate
                continue

            if level_compare:
                if is_generalize and equal_level \
                        and candidate.compare_level(original_f) > 0:
                    del candidate
                    continue
                if not is_generalize and equal_level \
                        and candidate.compare_level(original_f) < 0:
                    del candidate
                    continue
                if is_generalize and best_above:
                    if best_above[0].compare_level(candidate) < 0:
                        del candidate
                        continue
                if not is_generalize and best_below:
                    if best_below[0].compare_level(candidate) > 0:
                        del candidate
                        continue

        new_candidates = candidate.get_replacements(is_generalize)
        for new_candidate in new_candidates:
            new_candidate.son_consistent = is_consistent
            if new_candidate not in queued_candidates and new_candidate not in tested_candidates:
                candidates.append(new_candidate)
                queued_candidates.add(new_candidate)
        if not is_consistent:
            del candidate

    if function_repaired:
        if level_compare:
            logger.debug("Printing consistent functions found using level comparison")
            if equal_level:
                logger.debug(f"Looked at {counter} functions. Found {len(consistent_functions)} consistent. Returning {len(equal_level)} functions of same level\n")
            else:
                logger.debug(f"Looked at {counter} functions. Found {len(consistent_functions)} consistent. Returning {len(best_below) + len(best_above)} functions")
        else:
            logger.debug(f"Looked at {counter} functions. Found {len(consistent_functions)} functions")
    else:
        logger.debug(f"No consistent functions found - {counter}")

    # Add repair sets to the solution
    if sol_found:
        if level_compare:
            for candidate_set in (equal_level if equal_level else best_below +
                                  best_above):
                _add_repair_set_for_candidate(
                    inconsistency,
                    inconsistent_node,
                    candidate_set,
                    flipped_edges,
                    added_edges,
                    removed_edges,
                )
        else:
            for candidate in consistent_functions:
                _add_repair_set_for_candidate(
                    inconsistency,
                    inconsistent_node,
                    candidate,
                    flipped_edges,
                    added_edges,
                    removed_edges,
                )
    return sol_found
