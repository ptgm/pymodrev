"""
This module defines the InconsistencySolution class, which represents a
solution to inconsistencies in a network.
The class provides methods to manage and analyze inconsistent nodes, repair
sets, and other related properties.
"""

import json
from typing import Dict
from network.repair_set import RepairSet
from network.inconsistent_node import InconsistentNode
from configuration import config


class InconsistencySolution:
    """
    Represents a solution to inconsistencies in a network.
    Provides methods to manage inconsistent nodes, repair sets, and other
    properties related to the solution.
    """
    def __init__(self):
        """
        Initializes an empty inconsistency solution with no nodes, repairs,
        or observations.
        """
        # {'i_node_id_1': i_node_1, 'i_node_id_2': i_node_2, ...}
        # Minimum inconsistent node sets of a solution
        self._inconsistent_nodes = {}
        # Completed observations that are filled in; if an observation is not
        # complete, ASP fills it in and returns it (ASP tries all combinations)
        self._v_label = {}
        # Only for async, list of updates made for async at each point in time
        self._updates = {}
        # Which of the observations are inconsistent and the respective nodes,
        # used when the process is stopped midway
        self._inconsistent_profiles = {}
        self._inconsistent_nodes_profiles = {}  # Inconsistent nodes by observation
        self._n_topology_changes = 0
        self._n_ar_operations = 0
        self._n_e_operations = 0
        self._n_repair_operations = 0
        self._has_impossibility = False  # Solution is impossible to repair

    @property
    def inconsistent_nodes(self) -> Dict[str, InconsistentNode]:
        """Returns all inconsistent nodes in the solution."""
        return self._inconsistent_nodes

    @property
    def v_label(self) -> Dict:
        """Returns the completed observations."""
        return self._v_label

    @property
    def updates(self) -> Dict:
        """Returns the updates made for asynchronous operations."""
        return self._updates

    @property
    def inconsistent_profiles(self) -> Dict:
        """Returns the inconsistent profiles."""
        return self._inconsistent_profiles

    @property
    def inconsistent_nodes_profiles(self) -> Dict:
        """Returns the inconsistent nodes grouped by observation."""
        return self._inconsistent_nodes_profiles

    @property
    def n_topology_changes(self) -> int:
        """Returns the number of topology changes."""
        return self._n_topology_changes

    @n_topology_changes.setter
    def n_topology_changes(self, value: int):
        self._n_topology_changes = value

    @property
    def n_ar_operations(self) -> int:
        """Returns the number of add/remove operations."""
        return self._n_ar_operations

    @n_ar_operations.setter
    def n_ar_operations(self, value: int):
        self._n_ar_operations = value

    @property
    def n_e_operations(self) -> int:
        """Returns the number of edge flip operations."""
        return self._n_e_operations

    @n_e_operations.setter
    def n_e_operations(self, value: int):
        self._n_e_operations = value

    @property
    def n_repair_operations(self) -> int:
        """Returns the total number of repair operations."""
        return self._n_repair_operations

    @n_repair_operations.setter
    def n_repair_operations(self, value: int):
        self._n_repair_operations = value

    @property
    def has_impossibility(self) -> bool:
        """Returns whether the solution is impossible to repair."""
        return self._has_impossibility

    @has_impossibility.setter
    def has_impossibility(self, value: bool):
        self._has_impossibility = value

    def get_i_node(self, node_id: str) -> InconsistentNode:
        """
        Returns the inconsistent node with the given identifier.
        """
        return self.inconsistent_nodes[node_id]

    def compare_repairs(self, solution: "InconsistencySolution") -> int:
        """
        Compares the current solution with another solution to determine which
        is better.
        Returns:
            -1 if provided solution is better than current solution
            0 if provided solution is equal to current solution
            1 if provided solution is weaker than current solution
        """
        if (
            self.n_ar_operations < solution.n_ar_operations
            or self.n_e_operations < solution.n_e_operations
            or self.n_repair_operations < solution.n_repair_operations
        ):
            return 1
        if (
            self.n_ar_operations > solution.n_ar_operations
            or self.n_e_operations > solution.n_e_operations
            or self.n_repair_operations > solution.n_repair_operations
        ):
            return -1
        return 0

    def add_generalization(self, node_id: str) -> None:
        """
        Adds a generalization inconsistency for the node with the given
        identifier.
        """
        if node_id not in self.inconsistent_nodes:
            self.inconsistent_nodes[node_id] = InconsistentNode(node_id, True)
        else:
            i_node = self.inconsistent_nodes[node_id]
            if i_node.repair_type != 1:
                if i_node.repair_type == 0:
                    i_node.repair_type = 1
                else:
                    i_node.repair_type = 3

    def add_particularization(self, node_id: str) -> None:
        """
        Adds a particularization inconsistency for the node with the given
        identifier.
        """
        if node_id not in self.inconsistent_nodes:
            self.inconsistent_nodes[node_id] = InconsistentNode(node_id, False)
        else:
            i_node = self.inconsistent_nodes[node_id]
            if i_node.repair_type != 2:
                if i_node.repair_type == 0:
                    i_node.repair_type = 2
                else:
                    i_node.repair_type = 3

    def add_topological_error(self, node_id: str) -> None:
        """
        Adds a topological error for the node with the given identifier.
        """
        if node_id not in self.inconsistent_nodes:
            new_i_node = InconsistentNode(node_id, False)
            new_i_node.repair_type = 0
            new_i_node.topological_error = True
            self.inconsistent_nodes[node_id] = new_i_node
        else:
            self.inconsistent_nodes[node_id].topological_error = True

    def add_v_label(self, profile, node_id: str, value, time) -> None:
        """
        Adds a completed observation for the given profile, node, value, and
        time.
        """
        if profile not in self.v_label:
            self._v_label[profile] = {}
        profile_map = self.v_label[profile]
        if time not in profile_map:
            profile_map[time] = {}
        profile_map[time][node_id] = value

    def add_update(self, time, profile, node_id: str) -> None:
        """
        Adds an update for the given time, profile, and node.
        """
        if time not in self.updates:
            self._updates[time] = {}
        time_map = self.updates[time]
        if profile not in time_map:
            time_map[profile] = []
        time_map[profile].append(node_id)

    def add_inconsistent_profile(self, profile, node_id: str) -> None:
        """
        Adds an inconsistent profile for the given profile and node.
        """
        if profile not in self.inconsistent_profiles:
            self._inconsistent_profiles[profile] = []
        self.inconsistent_profiles[profile].append(node_id)
        if node_id not in self.inconsistent_nodes_profiles:
            self._inconsistent_nodes_profiles[node_id] = []
        self.inconsistent_nodes_profiles[node_id].append(profile)

    def add_repair_set(self, node_id: str, repair_set: RepairSet) -> None:
        """
        Adds a repair set for the node with the given identifier and updates
        repair statistics.
        """
        target = self.inconsistent_nodes[node_id]
        if target:
            if not target.repaired:
                self.n_topology_changes += repair_set.n_topology_changes
                self.n_ar_operations += repair_set.n_add_remove_operations
                self.n_e_operations += repair_set.n_flip_edges_operations
                self.n_repair_operations += repair_set.n_repair_operations
            else:
                if repair_set.n_add_remove_operations > target.n_add_remove_operations:
                    return
                if repair_set.n_add_remove_operations == target.n_add_remove_operations and \
                        repair_set.n_flip_edges_operations > target.n_flip_edges_operations:
                    return
                if repair_set.n_add_remove_operations == target.n_add_remove_operations and \
                        repair_set.n_flip_edges_operations == target.n_flip_edges_operations and \
                        repair_set.n_repair_operations > target.n_repair_operations:
                    return
                if repair_set.n_repair_operations < target.n_repair_operations:
                    self.n_topology_changes -= target.n_topology_changes
                    self.n_topology_changes += repair_set.n_topology_changes
                    self.n_ar_operations -= target.n_add_remove_operations
                    self.n_ar_operations += repair_set.n_add_remove_operations
                    self.n_e_operations -= target.n_flip_edges_operations
                    self.n_e_operations += repair_set.n_flip_edges_operations
                    self.n_repair_operations -= target.n_repair_operations
                    self.n_repair_operations += repair_set.n_repair_operations
            target.add_repair_set(repair_set)

    def print_solution(self, network=None) -> None:
        """
        Prints the solution based on the specified verbosity level.
        """
        if config.verbose == 0:
            self.print_compact_v0_solution(network=network)
        elif config.verbose == 1:
            self.print_json_v1_solution(network=network)
        else:
            self.print_human_v2_solution(network=network)

    def print_compact_v0_solution(self, network=None) -> None:
        """
        Prints the solution in a compact format.
        """
        first_node = True
        for i_node in self.inconsistent_nodes.values():
            if not first_node:
                print("/", end="")
            first_node = False
            print(i_node.identifier, end="")
            print("@", end="")
            first_repair = True
            for repair in i_node.repair_sets:
                if not first_repair:
                    print(";", end="")
                first_repair = False
                first = True
                for added_edge in repair.added_edges:
                    if not first:
                        print(":", end="")
                    first = False
                    print(f"A,{added_edge.start_node.identifier},{added_edge.end_node.identifier},{added_edge.sign}", end="")
                for removed_edge in repair.removed_edges:
                    if not first:
                        print(":", end="")
                    first = False
                    print(f"R,{removed_edge.start_node.identifier},{removed_edge.end_node.identifier}", end="")
                for flipped_edge in repair.flipped_edges:
                    if not first:
                        print(":", end="")
                    first = False
                    print(f"E,{flipped_edge.start_node.identifier},{flipped_edge.end_node.identifier}", end="")
                for repaired_function in repair.repaired_functions:
                    if not first:
                        print(":", end="")
                    first = False
                    print(f"F,{repaired_function.print_function(network=network, repair_set=repair)}", end="")
        print()

    def print_json_v1_solution(self, network=None):
        """
        Prints the solution in JSON format.
        """
        result = {
            "solution_repairs": self.n_repair_operations,
            "node_repairs": []
        }

        for node in self.inconsistent_nodes.values():
            node_data = {
                "node": node.identifier,
                "repair_set": []
            }
            first_repair_set = True
            i = 1
            for repair in node.repair_sets:
                if not first_repair_set:
                    node_data["repair_set"].append({})
                first_repair_set = False

                repair_data = {
                    "repair_id": i,
                    "repairs": []
                }
                i += 1
                # Adding function repairs
                for func in repair.repaired_functions:
                    repair_data["repairs"].append({
                        "type": "F",
                        "value": func.print_function(network=network, repair_set=repair)
                    })
                # Adding flipped edges
                for flipped_edge in repair.flipped_edges:
                    repair_data["repairs"].append({
                        "type": "E",
                        "value": f"({flipped_edge.start_node.identifier}, {flipped_edge.end_node.identifier})"
                    })
                # Adding removed edges
                for removed_edge in repair.removed_edges:
                    repair_data["repairs"].append({
                        "type": "R",
                        "value": f"({removed_edge.start_node.identifier}, {removed_edge.end_node.identifier})"
                    })
                # Adding added edges
                for added_edge in repair.added_edges:
                    repair_data["repairs"].append({
                        "type": "A",
                        "value": f"({added_edge.start_node.identifier}, {added_edge.end_node.identifier})",
                        "sign": added_edge.sign
                    })
                node_data["repair_set"].append(repair_data)
            result["node_repairs"].append(node_data)
        print(json.dumps(result, indent=4))

    def print_human_v2_solution(self, network=None) -> None:
        """
        Prints the solution in a human-readable format.
        """
        print(f"### Found solution with {self.n_repair_operations} repair operations.")
        for i_node in self.inconsistent_nodes.values():
            print(f"\tInconsistent node {i_node.identifier}.")
            i = 1
            for repair in i_node.repair_sets:
                print(f"\t\tRepair #{i}:")
                i += 1
                for repaired_function in repair.repaired_functions:
                    print(f"\t\t\tChange function of {repaired_function.node_id} to: " + \
                        f"{repaired_function.print_function(network=network, repair_set=repair)}")
                for flipped_edge in repair.flipped_edges:
                    print(f"\t\t\tFlip sign of edge ({flipped_edge.start_node.identifier}," + \
                        f"{flipped_edge.end_node.identifier}) to: " + \
                        ("negative" if flipped_edge.sign == 1 else "positive"))
                for removed_edge in repair.removed_edges:
                    print(f"\t\t\tRemove edge ({removed_edge.start_node.identifier}," + \
                        f"{removed_edge.end_node.identifier}).")
                for added_edge in repair.added_edges:
                    print(f"\t\t\tAdd edge ({added_edge.start_node.identifier}," + \
                        f"{added_edge.end_node.identifier}) with sign {added_edge.sign}.")
        if config.labelling:
            print("\t### Labelling for this solution:")
            multiple_profiles = config.multiple_profiles
            for profile, times in self.v_label.items():
                if multiple_profiles:
                    print(f"\t\tProfile: {profile}")
                for time, ids in times.items():
                    print(f"\t\t\tTime step: {time}")
                    for _id, value in ids.items():
                        print(f"\t\t\t\t{_id} => {value}")

    def print_inconsistency(self) -> str:
        """
        Returns the inconsistency details for the solution,
        based on the specified verbosity level (compact/json/human-readable).
        """
        result = ""
        if config.verbose == 0:
            # compact mode
            result += 'N[' + ",".join([f'{i_node.identifier.replace(chr(34), "")}' \
                    for i_node in self.inconsistent_nodes.values()]) + ']'
            result += ';P[' + ",".join([f'{i_profile.replace(chr(34), "")}' \
                for i_profile in self.inconsistent_profiles]) + ']'
        elif config.verbose == 1:
            # json mode
            result += '"nodes": [' + \
                ",".join([f'"{i_node.identifier.replace(chr(34), "")}"' \
                for i_node in self.inconsistent_nodes.values()]) + '], ' + \
                '"profiles": [' + \
                ",".join([f'"{i_profile.replace(chr(34), "")}"' \
                for i_profile in self.inconsistent_profiles]) + ']'
        else:
            # human mode
            result += '  node(s) needing repair: ' + \
                ", ".join([f'"{i_node.identifier.replace(chr(34), "")}"' \
                    for i_node in self.inconsistent_nodes.values()]) + '\n'
            result += '  present in profile(s): ' + \
                ", ".join([f'"{i_profile.replace(chr(34), "")}"' \
                    for i_profile in self.inconsistent_profiles])
        return result
