"""
This module defines the Node class, which represents a node in a network.
A node has an identifier and an associated function, and provides methods to
manage these properties.
"""

from network.function import Function


class Node:
    """
    Represents a node in a network.
    A node has an identifier and an associated function, which can be managed
    using the provided methods.
    """
    def __init__(self, node_id: str) -> None:
        """
        Initializes a node with a given identifier and a default function.
        """
        self._identifier = node_id
        self._function = Function(node_id)
        self._is_fixed = False

    @property
    def identifier(self) -> str:
        """Returns the identifier of the node."""
        return self._identifier

    @property
    def function(self) -> Function:
        """Returns the function associated with the node."""
        return self._function

    @function.setter
    def function(self, function: Function):
        """Sets the function associated with the node."""
        self._function = function

    @property
    def is_fixed(self) -> bool:
        """Returns whether the node is fixed."""
        return self._is_fixed

    @is_fixed.setter
    def is_fixed(self, value: bool):
        """Sets whether the node is fixed."""
        self._is_fixed = value
