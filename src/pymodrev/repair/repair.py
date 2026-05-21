"""
This module applies a valid repair to a network.
"""

import logging
from typing import List

from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.network.model import Model
from pymodrev.repair.consistency import check_consistency
from pymodrev.repair.topology import repair_inconsistencies
from pymodrev.configuration import config

logger = logging.getLogger(__name__)

def apply_repair(network: Model, repair: InconsistencySolution, node_repair_map: dict = {}) -> None:
    """
    This function applies a valid repair to a network.
    """
    for node_id, i_node in repair.inconsistent_nodes.items():
        if not i_node.repair_sets:
            continue

        # If a specific repair map is provided, use it; otherwise default to the first repair set
        if node_repair_map and node_id in node_repair_map:
            repair_set = node_repair_map[node_id]
        else:
            # Pick the first repair set for this node (they are all equally optimal)
            repair_set = i_node.repair_sets[0]

        # 1. Add edges
        for edge in repair_set.added_edges:
            start_node = network.get_node(edge.start_node.identifier)
            end_node = network.get_node(edge.end_node.identifier)
            network.add_edge(start_node, end_node, edge.sign)

        # 2. Remove edges
        for edge in repair_set.removed_edges:
            start_node = network.get_node(edge.start_node.identifier)
            end_node = network.get_node(edge.end_node.identifier)
            network.remove_edge(start_node, end_node)

        # 3. Flip edges
        for edge in repair_set.flipped_edges:
            target_edge = network.get_edge(edge.start_node.identifier,
                                           edge.end_node.identifier)
            target_edge.flip_sign()

        # 4. Update functions
        for func in repair_set.repaired_functions:
            node = network.get_node(func.node_id)
            node.function = func