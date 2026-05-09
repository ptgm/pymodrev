"""
Topological repair operations for model revision.

This module provides functions that handle edge add/remove/flip operations
to repair inconsistencies in the network topology.
"""

import logging
from typing import List

from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.network.inconsistent_node import InconsistentNode
from pymodrev.network.repair_set import RepairSet
from pymodrev.network.network import Network
from pymodrev.network.function import Function
from pymodrev.network.edge import Edge
from pymodrev.repair.consistency import n_func_inconsistent_with_label
from pymodrev.repair.function_search import (
    search_comparable_functions,
    search_non_comparable_functions,
)
from pymodrev.configuration import config, Inconsistencies

logger = logging.getLogger(__name__)


def repair_inconsistencies(
        network: Network,
        inconsistency: InconsistencySolution) -> None:
    """
    This function receives an inconsistent model with a set of nodes to be
    repaired and tries to repair the target nodes making the model consistent
    returning the set of repair operations to be applied.
    """
    for node_id, node in inconsistency.inconsistent_nodes.items():
        repair_node_consistency(network, inconsistency, node)
        if inconsistency.has_impossibility:
            logger.debug(f"#Found a node with impossibility - {node_id}")
            return
        logger.debug(f"#Found a repair for node - {node_id}")


def repair_node_consistency(
        network: Network,
        inconsistency: InconsistencySolution,
        inconsistent_node: InconsistentNode) -> None:
    """
    This function repairs a given node and determines all possible solutions
    consider 0 .. N add/remove repair operations, starting with 0 repairs of
    this type
    """
    original_node = network.get_node(inconsistent_node.identifier)
    original_function = original_node.function
    original_regulators = original_function.regulators \
        if original_function is not None \
        else []
    list_edges_remove = []
    list_edges_add = []

    for regulator in original_regulators:
        edge = network.get_edge(regulator, original_function.node_id)
        if edge is not None and not edge.is_fixed:
            list_edges_remove.append(edge)

    max_n_remove = len(list_edges_remove)
    max_n_add = len(network.nodes) - max_n_remove

    for node_id, node in network.nodes.items():
        is_original_regulator = any(node_id == reg_id for reg_id in
                                    original_regulators)

        if not is_original_regulator:
            new_edge = Edge(node, original_node, 1)
            list_edges_add.append(new_edge)

    sol_found = False

    # Iterate through the number of add/remove operations
    for n_operations in range(max_n_remove + max_n_add + 1):
        for n_add in range(n_operations + 1):
            if n_add > max_n_add:
                break
            n_remove = n_operations - n_add
            if n_remove > max_n_remove:
                continue
            logger.debug(f"Testing {n_add} adds and {n_remove} removes")

            list_add_combination = get_edges_combinations(list_edges_add,
                                                          n_add)
            list_remove_combination = get_edges_combinations(list_edges_remove,
                                                             n_remove)

            for add_combination in list_add_combination:
                for remove_combination in list_remove_combination:
                    is_sol = False

                    # Remove and add edges
                    for edge in remove_combination:
                        logger.debug(f"Remove edge from {edge.start_node.identifier}")
                        network.remove_edge(edge.start_node,
                                            edge.end_node)

                    for edge in add_combination:
                        logger.debug(f"Add edge from {edge.start_node.identifier}")
                        network.add_edge(edge.start_node,
                                         edge.end_node, edge.sign)

                    # If n_operations > 0, the function must be changed
                    if n_operations > 0:
                        new_function = Function(original_node.identifier)
                        clause_id = 1

                        for regulator in original_regulators:
                            removed = any(regulator ==
                                          edge.start_node.identifier
                                          for edge in remove_combination)
                            if not removed:
                                # TODO try using add_regulator_to_term and only when needed add the clause
                                new_function.add_regulator_to_term(clause_id,
                                                                   regulator)
                                clause_id += 1

                        for edge in add_combination:
                            # TODO try using add_regulator_to_term and only when needed add the clause
                            new_function.add_regulator_to_term(
                                clause_id, edge.start_node.identifier)
                            clause_id += 1

                        # TODO does this makes sense? only creating the PFH function if the new function has regulators?
                        if new_function.regulators:
                            new_function.create_pfh_function()
                        original_node.function = new_function

                    # Test with edge flips starting with 0 edge flips
                    is_sol = repair_node_consistency_flipping_edges(
                        network, inconsistency, inconsistent_node,
                        add_combination, remove_combination)

                    # Add and remove edges for the original network
                    for edge in remove_combination:
                        network.add_edge(edge.start_node,
                                         edge.end_node, edge.sign)

                    for edge in add_combination:
                        network.remove_edge(edge.start_node,
                                            edge.end_node)

                    # Restore the original function
                    original_node.function = original_function

                    if is_sol:
                        sol_found = True
                        if config.solutions == 1:
                            logger.debug("No more solutions - showing only first ASP solution")
                            return
        if sol_found:
            break
    if not sol_found:
        inconsistency.has_impossibility = True
        logger.warning(f"Not possible to repair node {inconsistent_node.identifier}")
    return


def repair_node_consistency_flipping_edges(
        network: Network,
        inconsistency: InconsistencySolution,
        inconsistent_node: InconsistentNode,
        added_edges: List[Edge],
        removed_edges: List[Edge]) -> bool:
    """
    Tries to repair a node's consistency by flipping edges in the network.
    It tests different combinations of edge flips and checks if the
    inconsistency is resolved.
    """
    function = network.get_node(inconsistent_node.identifier).function
    regulators = function.regulators if function is not None else []
    list_edges = []

    for regulator in regulators:
        edge = network.get_edge(regulator, function.node_id)
        if edge is not None and not edge.is_fixed:
            list_edges.append(edge)
    logger.debug(f"Searching solution flipping edges for {inconsistent_node.identifier}")

    sol_found = False
    iterations = len(list_edges)

    # Limit the number of flip edges if the node has already been repaired
    if inconsistent_node.is_repaired():
        iterations = inconsistent_node.n_flip_edges_operations
    for n_edges in range(iterations + 1):
        logger.debug(f"Testing with {n_edges} edge flips")

        edges_candidates = get_edges_combinations(list_edges, n_edges)

        # For each set of flipping edges
        for edge_set in edges_candidates:
            # Flip all edges
            for edge in edge_set:
                edge.flip_sign()
                logger.debug(f"Flip edge from {edge.start_node.identifier}")
            is_sol = repair_node_consistency_functions(network, inconsistency,
                                                       inconsistent_node,
                                                       edge_set, added_edges,
                                                       removed_edges)
            # Put network back to normal by flipping edges back
            for edge in edge_set:
                edge.flip_sign()
                logger.debug(f"Return flip edge from {edge.start_node.identifier}")
            if is_sol:
                logger.debug("Is solution by flipping edges")
                sol_found = True
                if config.solutions == 1:
                    logger.debug("No more solutions - showing only first ASP solution")
                    return True
        if sol_found:
            logger.debug(f"Ready to end with {n_edges} edges flipped")
            break

    return sol_found


def get_edges_combinations(
        edges: List[Edge],
        n: int,
        index_start: int = 0) -> List[List[Edge]]:
    """
    Generate all possible combinations of edges with specified size.
    """
    if n == 0:
        return [[]]
    result = []
    for i in range(index_start, len(edges) - n + 1):
        if n > 1:
            aux = get_edges_combinations(edges, n - 1, i + 1)
            for combination in aux:
                combination.append(edges[i])
                result.append(combination)
        else:
            result.append([edges[i]])
    return result


def repair_node_consistency_functions(
        network: Network,
        inconsistency: InconsistencySolution,
        inconsistent_node: InconsistentNode,
        flipped_edges: List[Edge],
        added_edges: List[Edge],
        removed_edges: List[Edge]) -> bool:
    """
    Repairs a node's function if needed by checking for consistency after
    topological changes, and if necessary, searches for a function change to
    resolve inconsistencies.
    """
    sol_found = False
    repair_type = inconsistent_node.repair_type

    # If any topological operation was performed, validate if the model
    # became consistent
    if flipped_edges or added_edges or removed_edges:
        repair_type = n_func_inconsistent_with_label(
            network, inconsistency,
            network.get_node(inconsistent_node.identifier).function)
        if repair_type == Inconsistencies.CONSISTENT.value:
            logger.debug("Node consistent with only topological changes")

            repair_set = RepairSet()

            for edge in flipped_edges:
                repair_set.add_flipped_edge(edge)

            # Add and remove edges in the solution repair set
            for edge in removed_edges:
                repair_set.remove_edge(edge)

            for edge in added_edges:
                repair_set.add_edge(edge)

            if added_edges or removed_edges:
                repair_set.add_repaired_function(network.get_node(
                    inconsistent_node.identifier).function)

            inconsistency.add_repair_set(inconsistent_node.identifier,
                                         repair_set)
            return True
    else:
        # No operation was performed yet, validate if it is a topological
        # change
        if inconsistent_node.has_topological_error():
            return False

    if repair_type == Inconsistencies.CONSISTENT.value:
        logger.warning(f"Found a consistent node before expected: {inconsistent_node.identifier}")

    # If a solution was already found, avoid searching for function changes
    if inconsistent_node.is_repaired():
        n_ra_op = inconsistent_node.n_add_remove_operations
        n_fe_op = inconsistent_node.n_flip_edges_operations
        n_op = inconsistent_node.n_repair_operations

        if (n_ra_op == len(added_edges) + len(removed_edges)) and (
                n_fe_op == len(flipped_edges)) and (n_op == n_ra_op + n_fe_op):
            logger.debug("Better solution already found. No function search.")
            return False

    # Model is not consistent and a function change is necessary
    if repair_type == Inconsistencies.DOUBLE_INC.value:
        if added_edges or removed_edges:
            # If we have a double inconsistency and at least one edge was
            # removed or added, it means that the function was changed to the
            # bottom function, and it's not repairable
            return False

        logger.debug(f"Searching for non-comparable functions for node {inconsistent_node.identifier}")

        # Case of double inconsistency
        sol_found = search_non_comparable_functions(network, inconsistency,
                                                    inconsistent_node,
                                                    flipped_edges, added_edges,
                                                    removed_edges)

        logger.debug(f"End searching for non-comparable functions for node {inconsistent_node.identifier}")

    else:
        logger.debug(f"Searching for comparable functions for node {inconsistent_node.identifier}")

        # Case of single inconsistency
        sol_found = search_comparable_functions(
            network, inconsistency, inconsistent_node, flipped_edges,
            added_edges, removed_edges,
            repair_type == Inconsistencies.SINGLE_INC_GEN.value)
        logger.debug(f"End searching for comparable functions for node {inconsistent_node.identifier}")

    return sol_found
