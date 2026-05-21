"""
This module defines the Model class, which represents a Boolean network of
nodes and edges.
The Model class provides methods to manage nodes, edges, and the input file.
Observations are managed separately via ObservationSet.
"""

from typing import Dict, List
from pymodrev.network.node import Node
from pymodrev.network.edge import Edge
from pymodrev.network.exceptions import EdgeNotFoundError


class Model:
    """
    Represents a Boolean network of nodes and edges.
    Provides methods to manage nodes, edges, and the input file path.
    """

    def __init__(self) -> None:
        """
        Initializes an empty model with no nodes or edges.
        """
        self._nodes: Dict[str, Node] = {}  # {'node_id': node, ...}
        self._graph = {}  # {'node_id': [edge_1, edge_2, ...], ...}
        self._regulators = {}  # Reverse of graph: {'node_id': ['reg_id', ...], ...}
        self._input_file_network = ''

    @property
    def nodes(self) -> Dict[str, Node]:
        """Returns all nodes in the model."""
        return self._nodes

    @property
    def graph(self) -> Dict[str, List[Edge]]:
        """Returns the graph representation of the model."""
        return self._graph

    @property
    def regulators(self) -> Dict[str, List[str]]:
        """Returns the regulators of each node in the model."""
        return self._regulators

    @property
    def input_file_network(self) -> str:
        """Returns the input file associated with the model."""
        return self._input_file_network

    @input_file_network.setter
    def input_file_network(self, value: str):
        self._input_file_network = value

    def get_node(self, node_id: str) -> Node | None:
        """
        Retrieves a node from the model by its identifier.
        """
        return self.nodes.get(node_id)

    def get_edge(self, start_node_id: str, end_node_id: str) -> Edge:
        """
        Retrieves an edge between two nodes by their identifiers.
        """
        if start_node_id in self.graph:
            for edge in self.graph[start_node_id]:
                if edge.end_node.identifier == end_node_id:
                    return edge
        raise EdgeNotFoundError(
            f"ERROR: Edge from {start_node_id} to {end_node_id} does not exist in the model!"
        )

    def add_node(self, node_id: str) -> Node:
        """
        Adds a new node to the model with the given identifier.
        """
        node = self.get_node(node_id)
        if node is None:
            node = Node(node_id)
            self.nodes[node_id] = node
            self.graph[node_id] = []
        return node

    def add_edge(self, start_node: Node, end_node: Node, sign: int) -> None:
        """
        Adds a new edge between two nodes with the specified sign.
        """
        try:
            self.get_edge(start_node.identifier, end_node.identifier)
        except EdgeNotFoundError:
            edge = Edge(start_node, end_node, sign)
            self.graph[edge.start_node.identifier].append(edge)
            if edge.end_node.identifier not in self.regulators:
                self.regulators[edge.end_node.identifier] = [edge.start_node.identifier]
            else:
                self.regulators[edge.end_node.identifier].append(edge.start_node.identifier)

    def remove_edge(self, start_node: Node, end_node: Node) -> None:
        """
        Removes an edge between two nodes from the model.
        """
        try:
            edge_to_remove = self.get_edge(start_node.identifier, end_node.identifier)
            self.graph[start_node.identifier].remove(edge_to_remove)
            self.regulators[end_node.identifier].remove(start_node.identifier)
            if not self.regulators[end_node.identifier]:
                del self.regulators[end_node.identifier]
        except ValueError:
            print(f"No edge exists between {start_node.identifier} and {end_node.identifier}")

    def to_asp_facts(self) -> str:
        """
        Encodes the model as ASP facts compatible with the clingo rules.
        Delegates to ASPParser.to_asp_facts().
        """
        from pymodrev.parsers.parser_asp import ASPParser
        return ASPParser.to_asp_facts(self)
