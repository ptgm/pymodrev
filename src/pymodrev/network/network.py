"""
This module defines the Network class, which represents a network of nodes and
edges.
The Network class provides methods to manage nodes, edges, and network-related
properties such as input files and observations.
"""

from typing import Dict, List, Set
from pymodrev.network.node import Node
from pymodrev.network.edge import Edge
from pymodrev.network.exceptions import EdgeNotFoundError, ParseError

class Network:
    """
    Represents a network of nodes and edges.
    Provides methods to manage nodes, edges, and network-related properties
    such as input files and observations.
    """
    def __init__(self) -> None:
        """
        Initializes an empty network with no nodes, edges, or input files.
        """
        self._nodes = {}  # {'node_id_1': node_1, 'node_id_2': node_2, ...}
        self._graph = {}  # {'node_id_1': [edge_1_2, edge_1_3], 'node_id_2': [edge_2_1], ...}
        self._regulators = {}  # Reverse of graph {'node_id_1': ['node_id_2'], 'node_id_2': ['node_id_1'], 'node_id_3': ['node_id_1'], ...}
        self._input_file_network = ''
        self._observations = {}  # {'exp_id_1': obs_1, 'exp_id_2': obs_1, 'exp_id_3': obs_2,...}
        self._updaters_name = set()
        self._updaters = set()
        self._has_ss_obs = False
        self._has_ts_obs = False

    @property
    def nodes(self) -> Dict[str, Node]:
        """Returns all nodes in the network."""
        return self._nodes

    @property
    def graph(self) -> Dict[str, List[Edge]]:
        """Returns the graph representation of the network."""
        return self._graph

    @property
    def regulators(self) -> Dict[str, List[str]]:
        """Returns the regulators of each node in the network."""
        return self._regulators

    @property
    def input_file_network(self) -> str:
        """Returns the input file associated with the network."""
        return self._input_file_network

    @input_file_network.setter
    def input_file_network(self, value: str):
        self._input_file_network = value

    @property
    def observation_files(self) -> List[str]:
        """Returns the list of observation file paths."""
        return list(set([obs.observation_path for obs in self._observations.values()]))

    @property
    def observations_dictionary(self) -> Dict[str, "Observation"]:
        """Returns the dictionary of [profile, Observation objects]."""
        return self._observations
    
    @property
    def observations(self) -> List:
        """Returns the list of Observation objects."""
        return list(set(self._observations.values()))

    @property
    def observation_files_with_updater(self) -> List:
        """Returns the list of observation files with their updaters (for compatibility)."""
        return list(set([(obs.observation_path, obs.updater) for obs in self._observations.values()]))

    @property
    def updaters_name(self) -> Set:
        """Returns the set of updater names."""
        return self._updaters_name

    @property
    def updaters(self) -> Set:
        """Returns the set of updater objects."""
        return self._updaters

    @property
    def has_ss_obs(self) -> bool:
        """Returns whether the network has steady-state observations."""
        return self._has_ss_obs

    @has_ss_obs.setter
    def has_ss_obs(self, value: bool):
        self._has_ss_obs = value

    @property
    def has_ts_obs(self) -> bool:
        """Returns whether the network has time-series observations."""
        return self._has_ts_obs

    @has_ts_obs.setter
    def has_ts_obs(self, value: bool):
        self._has_ts_obs = value

    def add_updater(self, updater) -> None:
        self.updaters.add(updater)

    def add_updater_name(self, updater_name: str) -> None:
        self.updaters_name.add(updater_name)

    def get_node(self, node_id: str) -> Node:
        """
        Retrieves a node from the network by its identifier.
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
        raise EdgeNotFoundError(f"ERROR: Edge from {start_node_id} to {end_node_id} does not exist in the network!")

    def add_node(self, node_id: str) -> Node:
        """
        Adds a new node to the network with the given identifier.
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
            return self.get_edge(start_node.identifier, end_node.identifier)
        except EdgeNotFoundError:
            edge = Edge(start_node, end_node, sign)
            # self.edges.append(edge)
            self.graph[edge.start_node.identifier].append(edge)
            if edge.end_node.identifier not in self.regulators:
                self.regulators[edge.end_node.identifier] = \
                    [edge.start_node.identifier]
            else:
                self.regulators[edge.end_node.identifier].append(
                    edge.start_node.identifier)
            # return edge

    def remove_edge(self, start_node: Node, end_node: Node) -> None:
        """
        Removes an edge between two nodes from the network.
        """
        try:
            edge_to_remove = self.get_edge(start_node.identifier,
                                           end_node.identifier)  # Find the edge to remove
            self.graph[start_node.identifier].remove(edge_to_remove)  # Remove the edge from the graph
            self.regulators[end_node.identifier].remove(start_node.identifier)  # Remove the start_node from the list of regulators for the end_node
            if not self.regulators[end_node.identifier]:  # If there are no more regulators for the end_node, remove the key from the regulators dictionary
                del self.regulators[end_node.identifier]
        except ValueError:
            print(f"No edge exists between {start_node.identifier} and {end_node.identifier}")

    def add_observation(self, observation) -> None:
        """
        Adds an Observation object to the network.
        """
        for exp in observation.experiments:
            if exp in self._observations:
                raise ParseError(f"Duplicated experimental profile {exp}")
            else:
                self._observations[exp] = observation

    def to_asp_facts(self) -> str:
        """
        Encodes the network as ASP facts compatible with the clingo rules.
        Delegates to ASPParser.to_asp_facts().
        """
        from pymodrev.parsers.parser_asp import ASPParser
        return ASPParser.to_asp_facts(self)
    
    def get_observation_updater(self, profile: str) -> "Updater":
        """
        Gets the observation with a given profile name or expid if it exists
        """
        obs = self._observations[profile]
        if obs is not None:
            return obs.updater
        return None


