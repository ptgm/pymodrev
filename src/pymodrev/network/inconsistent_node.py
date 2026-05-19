"""
This module defines the Inconsistent_Node class, which represents a node in a
network that is inconsistent.
The class provides methods to manage and analyze repair sets and
inconsistencies for the node.
"""

from typing import List
from pymodrev.network.repair_set import RepairSet


class InconsistentNode:
    """
    Represents a node in a network that is inconsistent.
    Provides methods to manage repair sets, track repair operations, and
    determine if the node has been repaired.
    """
    def __init__(self, node_id: str, generalization: bool):
        """
        Initializes an inconsistent node with an identifier and a
        generalization flag.
        """
        self._identifier = node_id
        self._generalization = generalization
        self._repair_sets = []  # List of RepairSets
        self._n_topology_changes = 0
        self._n_repair_operations = 0
        self._n_add_remove_operations = 0
        self._n_flip_edges_operations = 0
        self._repaired = False
        self._topological_error = False
        self._repair_type = 1 if generalization else 2

    @property
    def identifier(self) -> str:
        """Returns the identifier of the node."""
        return self._identifier

    @property
    def generalization(self) -> bool:
        """Returns whether the node is a generalization."""
        return self._generalization

    @property
    def repair_sets(self) -> List[RepairSet]:
        """Returns the list of repair sets associated with the node."""
        return self._repair_sets

    @property
    def n_topology_changes(self) -> int:
        """Returns number of topology changes."""
        return self._n_topology_changes

    @n_topology_changes.setter
    def n_topology_changes(self, value: int):
        self._n_topology_changes = value

    @property
    def n_repair_operations(self) -> int:
        """Returns number of repair operations."""
        return self._n_repair_operations

    @n_repair_operations.setter
    def n_repair_operations(self, value: int):
        self._n_repair_operations = value

    @property
    def n_add_remove_operations(self) -> int:
        """Returns number of add/remove operations."""
        return self._n_add_remove_operations

    @n_add_remove_operations.setter
    def n_add_remove_operations(self, value: int):
        self._n_add_remove_operations = value

    @property
    def n_flip_edges_operations(self) -> int:
        """Returns number of flip edges operations."""
        return self._n_flip_edges_operations

    @n_flip_edges_operations.setter
    def n_flip_edges_operations(self, value: int):
        self._n_flip_edges_operations = value

    @property
    def repaired(self) -> bool:
        """Returns whether the node has been repaired."""
        return self._repaired

    @repaired.setter
    def repaired(self, value: bool):
        self._repaired = value

    @property
    def topological_error(self) -> bool:
        """Returns whether the node has a topological error."""
        return self._topological_error

    @topological_error.setter
    def topological_error(self, value: bool):
        self._topological_error = value

    @property
    def repair_type(self) -> int:
        """Returns the repair type."""
        return self._repair_type

    @repair_type.setter
    def repair_type(self, value: int):
        self._repair_type = value

    def is_repaired(self) -> bool:
        """
        Returns whether the node has been repaired.
        """
        return self.repaired

    def has_topological_error(self) -> bool:
        """
        Returns whether the node has a topological error.
        """
        return self.topological_error

    def add_repair_set(self, repair_set: RepairSet) -> None:
        """
        Adds a repair set to the node and updates repair statistics.
        If the new repair set is better than existing ones, it replaces them.
        """
        if not self.repaired:
            self.repaired = True
            self.n_topology_changes = repair_set.n_topology_changes
            self.n_repair_operations = repair_set.n_repair_operations
            self.n_flip_edges_operations = \
                repair_set.n_flip_edges_operations
            self.n_add_remove_operations = \
                repair_set.n_add_remove_operations
        else:
            # If new solutions is worse, ignore
            if (repair_set.n_add_remove_operations >
                    self.n_add_remove_operations):
                return
            if (repair_set.n_add_remove_operations ==
                    self.n_add_remove_operations and
                    repair_set.n_flip_edges_operations >
                    self.n_flip_edges_operations):
                return
            if (repair_set.n_add_remove_operations ==
                    self.n_add_remove_operations and
                    repair_set.n_flip_edges_operations ==
                    self.n_flip_edges_operations and
                    repair_set.n_repair_operations >
                    self.n_repair_operations):
                return

            # If new solution is better, remove all others before
            # At this point we know that the new repair is at least as good as
            # existing ones
            if repair_set.n_repair_operations < self.n_repair_operations:
                self.repair_sets.clear()
                self.n_topology_changes = repair_set.n_topology_changes
                self.n_repair_operations = repair_set.n_repair_operations
                self.n_add_remove_operations = \
                    repair_set.n_add_remove_operations
                self.n_flip_edges_operations = \
                    repair_set.n_flip_edges_operations
        self.repair_sets.append(repair_set)
