"""
Core engine for model revision orchestration.

This module provides the top-level entry points for analyzing and revising
a network model for consistency.
"""

import logging
from typing import List

from network.inconsistency_solution import InconsistencySolution
from network.network import Network
from repair.consistency import check_consistency
from repair.topology import repair_inconsistencies
from configuration import config

logger = logging.getLogger(__name__)


def model_revision(
    network: Network,
    f_inconsistencies: List[InconsistencySolution],
    optimization: int) -> None:
    """
    Analyze and revise a given network model for consistency.
    Procedure:
        1st - tries to repair functions
        2nd - tries to flip the sign of the edges
        3rd - tries to add or remove edges
    """
    if optimization < 0:
        logger.error("It is not possible to repair this network for now.")
        logger.error("This may occur if there is at least one node for which from the same input two different outputs are expected (non-deterministic function).")
        return

    logger.debug(f"Found {len(f_inconsistencies)} solution(s) with {len(f_inconsistencies[0].inconsistent_nodes)} inconsistent node(s)")

    # At this point we have an inconsistent network with node candidates
    # to be repaired
    best_solution = None
    solutions2apply = set()
    for inconsistency in f_inconsistencies:
        repair_inconsistencies(network, inconsistency)

        # Check for valid solution
        if not inconsistency.has_impossibility:
            if best_solution is None \
                    or inconsistency.compare_repairs(best_solution) > 0:
                best_solution = inconsistency
                logger.debug(f"Found a solution with {best_solution.n_topology_changes} topology changes")
                if best_solution.n_topology_changes == 0 and not \
                        config.all_opt:
                    break
        else:
            logger.debug("Reached an impossibility")

    if best_solution is None:
        logger.info("It was not possible to repair the model.")
        return
    
    show_sub_opt = config.show_solution_for_each_inconsistency
    if config.all_opt:
        for inconsistency in f_inconsistencies:
            logger.debug(f"Checking for printing solution with {inconsistency.n_topology_changes} topology changes")
            if not inconsistency.has_impossibility \
                    and (inconsistency.compare_repairs(best_solution) >= 0
                         or show_sub_opt):
                if show_sub_opt \
                        and inconsistency.compare_repairs(best_solution) < 0:
                    if config.verbose < 2:
                        print("+", end="")
                    else:
                        print("(Sub-Optimal Solution)")
                if config.task == 'r':
                    inconsistency.print_solution(network=network)
                else:
                    solutions2apply.add(inconsistency)
    else:
        if config.task == 'r':
            best_solution.print_solution(network=network)
        else:
            solutions2apply.add(best_solution)

    return solutions2apply

def print_consistency(
        inconsistencies: List[InconsistencySolution],
        optimization: int) -> None:
    """
    Print the consistency status of the network in three verbose levels: 
    compact, json and human-readable.
    """
    if optimization == 0:
        # compact level
        if config.verbose == 0: print('Consistent!')
        # json level
        elif config.verbose == 1: print('{"consistent": true}')
        # human-readable level
        else: print("This network is consistent!")
        return
    # else, the network is inconsistent
    if config.verbose == 0:
        # compact level
        print('Inconsistent!')
        for inconsistency in inconsistencies:
            print(" " + inconsistency.print_inconsistency())
    elif config.verbose == 1:
        # json level
        print('{\n  "consistent": false,')
        print('  "inconsistencies": [')
        for inconsistency in inconsistencies:
            print("    {" + inconsistency.print_inconsistency() + "},")
        print("  ]\n}")
    # else, human-readable level
    else:
        print("This network is inconsistent!")
        for inconsistency in inconsistencies:
            print(inconsistency.print_inconsistency())
