"""
Function search and replacement logic for model revision.

This module provides functions to search for comparable and non-comparable
replacement functions that can resolve inconsistencies in the network.
"""

import logging
from typing import List

from network.inconsistency_solution import InconsistencySolution
from network.inconsistent_node import InconsistentNode
from network.repair_set import RepairSet
from network.network import Network
from network.function import Function
from network.edge import Edge
from repair.consistency import (
    n_func_inconsistent_with_label,
    is_func_consistent_with_label,
    is_function_in_bottom_half,
)
from configuration import config, Inconsistencies

logger = logging.getLogger(__name__)


def search_comparable_functions(
        network: Network,
        inconsistency: InconsistencySolution,
        inconsistent_node: InconsistentNode,
        flipped_edges: List[Edge],
        added_edges: List[Edge],
        removed_edges: List[Edge],
        generalize: bool) -> bool:
    """
    Searches for comparable functions that can repair the inconsistency of a
    node. It evaluates potential replacement functions and applies the
    necessary edges to resolve the inconsistency.
    """
    sol_found = False
    original_f = network.get_node(inconsistent_node.identifier).function

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
    t_candidates = original_f.pfh_get_replacements(generalize)

    while t_candidates:
        candidate_sol = False
        candidate = t_candidates.pop(0)
        if function_repaired and candidate.distance_from_original > \
                repaired_function_level:
            continue
        if is_func_consistent_with_label(network, inconsistency, candidate):
            candidate_sol = True
            repair_set = RepairSet()
            repair_set.add_repaired_function(candidate)
            for edge in flipped_edges:
                repair_set.add_flipped_edge(edge)
            for edge in removed_edges:
                repair_set.remove_edge(edge)
            for edge in added_edges:
                repair_set.add_edge(edge)
            inconsistency.add_repair_set(inconsistent_node.identifier,
                                         repair_set)
            function_repaired = True
            sol_found = True
            repaired_function_level = candidate.distance_from_original

            if not config.show_all_functions:
                break

        taux_candidates = candidate.pfh_get_replacements(generalize)
        if taux_candidates:
            for taux_candidate in taux_candidates:
                if taux_candidate not in t_candidates:
                    t_candidates.append(taux_candidate)

        if not candidate_sol:
            del candidate
    if not sol_found and config.force_optimum:
        return search_non_comparable_functions(network, inconsistency,
                                               inconsistent_node,
                                               flipped_edges, added_edges,
                                               removed_edges)
    return sol_found


def search_non_comparable_functions(
        network: Network,
        inconsistency: InconsistencySolution,
        inconsistent_node: InconsistentNode,
        flipped_edges: List[Edge],
        added_edges: List[Edge],
        removed_edges: List[Edge]) -> bool:
    """
    Searches for non-comparable functions to resolve inconsistencies in the
    given network. Attempts to replace an inconsistent function with a
    consistent alternative.
    """
    sol_found, function_repaired = False, False
    candidates, consistent_functions = [], []
    best_below, best_above, equal_level = [], [], []
    level_compare = config.compare_level_function

    # Each function must have a list of replacement candidates and each must
    # be tested until it works
    original_f = network.get_node(inconsistent_node.identifier).function
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

    logger.debug(f"Finding functions for double inconsistency in {original_f.print_function(network=network)}")

    counter = 0
    while candidates:
        counter += 1
        candidate = candidates.pop(0)
        is_consistent = False

        if candidate not in consistent_functions:
            continue

        inc_type = n_func_inconsistent_with_label(network, inconsistency,
                                                  candidate)
        if inc_type == Inconsistencies.CONSISTENT.value:
            is_consistent = True
            consistent_functions.append(candidate)
            if not function_repaired:
                logger.debug(f"Found first function at level {candidate.distance_from_original} {candidate.print_function(network=network)}")
            function_repaired, sol_found = True, True
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
            if new_candidate not in candidates:
                candidates.append(new_candidate)
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
                repair_set = RepairSet()
                repair_set.add_repaired_function(candidate_set)
                for edge in flipped_edges:
                    repair_set.add_flipped_edge(edge)
                for edge in removed_edges:
                    repair_set.remove_edge(edge)
                for edge in added_edges:
                    repair_set.add_edge(edge)
                inconsistency.add_repair_set(inconsistent_node.identifier,
                                             repair_set)
        else:
            for candidate in consistent_functions:
                repair_set = RepairSet()
                repair_set.add_repaired_function(candidate)
                for edge in flipped_edges:
                    repair_set.add_flipped_edge(edge)
                for edge in removed_edges:
                    repair_set.remove_edge(edge)
                for edge in added_edges:
                    repair_set.add_edge(edge)
                inconsistency.add_repair_set(inconsistent_node.identifier,
                                             repair_set)
    return sol_found
