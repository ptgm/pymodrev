"""
This module defines the Edge class, which represents a connection between two
nodes in a network.
The Edge class provides methods to manage and query the properties of the edge,
such as its start node, end node, sign, and whether it is fixed.
"""

from pymodrev.network.node import Node


class Edge:
    """
    Represents an edge in a network, connecting two nodes with a specific sign.
    Provides methods to manage and query the edge's properties.
    """

    def __init__(self, start_node: Node, end_node: Node, sign: int) -> None:
        """
        Initializes an edge with a start node, end node, and sign.
        """
        self._start_node = start_node
        self._end_node = end_node
        self._sign = sign
        self._is_fixed = False

    @property
    def start_node(self) -> Node:
        """Returns the start node of the edge."""
        return self._start_node

    @property
    def end_node(self) -> Node:
        """Returns the end node of the edge."""
        return self._end_node

    @property
    def sign(self) -> int:
        """Returns the sign of the edge."""
        return self._sign

    @sign.setter
    def sign(self, value: int):
        """Sets the sign of the edge."""
        self._sign = value

    @property
    def is_fixed(self) -> bool:
        """Returns whether the edge is fixed."""
        return self._is_fixed

    @is_fixed.setter
    def is_fixed(self, value: bool):
        """Sets whether the edge is fixed."""
        self._is_fixed = value

    def flip_sign(self) -> None:
        """
        Flips the sign of the edge (from 0 to 1 or from 1 to 0).
        """
        self.sign = 1 if self.sign == 0 else 0

    def __eq__(self, other) -> bool:
        if not isinstance(other, Edge):
            return False
        return self.start_node == other.start_node and \
               self.end_node == other.end_node and \
               self.sign == other.sign

    def __hash__(self) -> int:
        return hash((self.start_node, self.end_node, self.sign))
