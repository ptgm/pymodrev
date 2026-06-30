"""
Core engine for model revision orchestration.

This module provides the top-level entry points for analyzing and revising
a network model for consistency.
"""

import logging
from typing import List, Tuple

from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.network.model import Model
from pymodrev.network.observation_set import ObservationSet
from pymodrev.repair.topology import repair_inconsistencies
from pymodrev.configuration import config

logger = logging.getLogger(__name__)


def model_revision(
    network: Model,
    observation_set: ObservationSet,
    f_inconsistencies: List[InconsistencySolution],
    optimization: int) -> Tuple[List[InconsistencySolution], str]:
    """
    Analyze and revise a given network model for consistency.
    Procedure:
        1st - tries to repair functions
        2nd - tries to flip the sign of the edges
        3rd - tries to add or remove edges
    """
    if optimization < 0:
        logger.error("Points of repair not found, probably due to fixed edges/nodes or node data expecting different outputs for the same input.")
        return [], ""

    logger.debug(f"Found {len(f_inconsistencies)} solution(s) with {len(f_inconsistencies[0].inconsistent_nodes)} inconsistent node(s)")

    # At this point we have an inconsistent network with node candidates
    # to be repaired
    best_solution = None
    solutions2apply = []
    s = ""
    for inconsistency in f_inconsistencies:
        repair_inconsistencies(network, observation_set, inconsistency)

        # Check for valid solution
        if not inconsistency.has_impossibility:
            if best_solution is None \
                    or inconsistency.compare_repairs(best_solution) > 0:
                best_solution = inconsistency
                logger.debug(f"Found a solution with {best_solution.n_topology_changes} topology changes")
                if best_solution.n_topology_changes == 0 and config.solutions <= 2:
                    break
        else:
            logger.debug("Reached an impossibility")

    if best_solution is None:
        logger.info("It was not possible to repair the model.")
        return [], ""
    
    if config.solutions > 2:
        for inconsistency in f_inconsistencies:
            logger.debug(f"Checking for printing solution with {inconsistency.n_topology_changes} topology changes")
            if not inconsistency.has_impossibility \
                    and (inconsistency.compare_repairs(best_solution) >= 0
                         or config.solutions == 4):
                subopt = config.solutions == 4 and config.task != 'm' \
                        and inconsistency.compare_repairs(best_solution) < 0
                s += inconsistency.solution_to_str(network, subopt)
                solutions2apply.append(inconsistency)
    else:
        s += best_solution.solution_to_str(network, config.solutions == 1)
        solutions2apply.append(best_solution)
    return solutions2apply, s
