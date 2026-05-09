"""
Core engine for model revision orchestration.

This module provides the top-level entry points for analyzing and revising
a network model for consistency.
"""

import logging
from typing import List

from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.network.network import Network
from pymodrev.repair.consistency import check_consistency
from pymodrev.repair.topology import repair_inconsistencies
from pymodrev.configuration import config

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
        logger.error("Points of repair not found, probably due to fixed edges/nodes or node data expecting different outputs for the same input.")
        return

    logger.debug(f"Found {len(f_inconsistencies)} solution(s) with {len(f_inconsistencies[0].inconsistent_nodes)} inconsistent node(s)")

    # At this point we have an inconsistent network with node candidates
    # to be repaired
    best_solution = None
    solutions2apply = []
    for inconsistency in f_inconsistencies:
        repair_inconsistencies(network, inconsistency)

        # Check for valid solution
        if not inconsistency.has_impossibility:
            if best_solution is None \
                    or inconsistency.compare_repairs(best_solution) > 0:
                best_solution = inconsistency
                logger.debug(f"Found a solution with {best_solution.n_topology_changes} topology changes")
                if best_solution.n_topology_changes == 0 and config.sol <= 2:
                    break
        else:
            logger.debug("Reached an impossibility")

    if best_solution is None:
        logger.info("It was not possible to repair the model.")
        return
    
    if config.sol > 2:
        for inconsistency in f_inconsistencies:
            logger.debug(f"Checking for printing solution with {inconsistency.n_topology_changes} topology changes")
            if not inconsistency.has_impossibility \
                    and (inconsistency.compare_repairs(best_solution) >= 0
                         or config.sol == 4):
                if config.sol == 4 and config.task != 'm' \
                        and inconsistency.compare_repairs(best_solution) < 0:
                    if config.format != 'h':
                        print("+", end="")
                    else:
                        print("(Sub-Optimal Solution)")
                if config.task == 'r':
                    inconsistency.print_solution(network=network)
                else:
                    solutions2apply.append(inconsistency)
    else:
        if config.task == 'r':
            if config.sol == 1:
                if config.format != 'h':
                    print("+", end="")
                else:
                    print("(Potential Sub-Optimal Solution)")
            best_solution.print_solution(network=network)
        else:
            solutions2apply.append(best_solution)
    return solutions2apply

def print_consistency(
        inconsistencies: List[InconsistencySolution],
        optimization: int) -> None:
    """
    Print the consistency of the model in three formats: 
    compact, json and human-readable.
    """
    if optimization == 0:
        # compact format
        if config.format == 'c': print('Consistent!')
        # json format
        elif config.format == 'j': print('{"consistent": true}')
        # human-readable format
        else: print("This model is consistent!")
        return

    # else, the model is inconsistent
    # Not really printing all the inconsistency solutions
    # Only the unique inconsistency solutions with respect to:
    # . inconsistent nodes
    # . inconsistent profiles
    unique_inconsistencies = set(inconsistencies)
    if config.format == 'c':
        # compact format
        print('Inconsistent!')
        if optimization < 0 and not unique_inconsistencies:
            print(' Points of repair not found, probably due to fixed edges/nodes')
        for inconsistency in unique_inconsistencies:
            print(" " + inconsistency.print_inconsistency())
    elif config.format == 'j':
        # json format
        print('{\n  "consistent": false,')
        print('  "inconsistencies": [')
        for inconsistency in unique_inconsistencies:
            print("    {" + inconsistency.print_inconsistency() + "},")
        print("  ]\n}")
    # else, human-readable format
    else:
        print("This model is inconsistent!")
        for inconsistency in unique_inconsistencies:
            print(inconsistency.print_inconsistency())
