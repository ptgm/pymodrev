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


def model_revision(network: Network) -> None:
    """
    Analyze and revise a given network model for consistency.
    Procedure:
        1st - tries to repair functions
        2nd - tries to flip the sign of the edges
        3rd - tries to add or remove edges
    """
    optimization = -2
    f_inconsistencies, optimization = check_consistency(network)
    if config.check_consistency:
        print_consistency(f_inconsistencies, optimization)
        return

    if optimization < 0:
        logger.error("It is not possible to repair this network for now.")
        logger.error("This may occur if there is at least one node for which from the same input two different outputs are expected (non-deterministic function).")
        return

    if optimization == 0:
        if config.verbose == 3:
            print_consistency(f_inconsistencies, optimization)
            return
        print("This network is consistent!")
        return

    logger.debug(f"Found {len(f_inconsistencies)} solution(s) with {len(f_inconsistencies[0].inconsistent_nodes)} inconsistent node(s)")

    # At this point we have an inconsistent network with node candidates
    # to be repaired
    best_solution = None
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
                inconsistency.print_solution(True)
    else:
        best_solution.print_solution(True)


def print_consistency(
        inconsistencies: List[InconsistencySolution],
        optimization: int) -> None:
    """
    Print the consistency status of the network in a structured JSON-like
    format.
    """
    print("{")
    print(f'\t"consistent": {"true" if optimization == 0 else "false,"}')
    if optimization != 0:
        print('\t"inconsistencies": [', end="")
        for i, inconsistency in enumerate(inconsistencies):
            if i > 0:
                print(",", end="")
            print("\n\t\t{", end="")
            inconsistency.print_inconsistency("\t\t\t")
            print("\n\t\t}", end="")
        print("\n\t]")
    print("}")
