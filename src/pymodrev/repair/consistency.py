"""
Consistency checking utilities for model revision.

This module provides functions to evaluate whether a function or node
is consistent with a given labeling/profile.
"""

import logging
import math
from bitarray import bitarray
from typing import List, Dict, Tuple

from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.network.network import Network
from pymodrev.network.function import Function
from pymodrev.updaters.updater import Updater
from pymodrev.updaters.steady_updater import SteadyUpdater
from pymodrev.configuration import config, Inconsistencies

logger = logging.getLogger(__name__)


def check_consistency(network: Network) -> Tuple[List[InconsistencySolution], int]:
    """
    Check network consistency using ASP solver or alternative method.
    """
    result = []
    optimization = -2
    if config.check_asp:
        result, optimization = Updater.check_consistency(network)
    else:
        pass
    return result, optimization


def n_func_inconsistent_with_label(
        network: Network,
        labeling: InconsistencySolution,
        function: Function) -> int:
    """
    Checks the consistency of a function against a labeling. It verifies each
    profile and returns the consistency status (consistent, inconsistent, or
    double inconsistency).
    """
    result = Inconsistencies.CONSISTENT.value
    for key in labeling.v_label:
        ret = n_func_inconsistent_with_label_with_profile(network, labeling, function, key)
        logger.debug(f"Consistency value: {ret} for node {function.node_id} with function: {function.print_function(network=network)}")
        if result == Inconsistencies.CONSISTENT.value:
            result = ret
        else:
            if ret not in (result, Inconsistencies.CONSISTENT.value):
                result = Inconsistencies.DOUBLE_INC.value
                break
    return result


def n_func_inconsistent_with_label_with_profile(
        network: Network,
        labeling: InconsistencySolution,
        function: Function,
        profile: str) -> int:
    """
    Checks the consistency of a function with a specific profile in a given
    labeling. It evaluates the function's clauses over time and returns the
    consistency status (consistent, single inconsistency, or double
    inconsistency) based on the profile.
    """
    if len(labeling.v_label[profile]) == 1 and network.has_ss_obs:
        return SteadyUpdater.n_func_inconsistent_with_label_with_profile(network, labeling, function, profile)
    for updater in network.updaters:
        if len(labeling.v_label[profile]) != 1 and updater.__class__.__name__.lower() != SteadyUpdater.__name__.lower():
            return updater.n_func_inconsistent_with_label_with_profile(network, labeling, function, profile)


def is_func_consistent_with_label(
        network: Network,
        labeling: InconsistencySolution,
        function: Function) -> bool:
    """
    Checks if a function is consistent with a labeling across all profiles.
    """
    return all(
        is_func_consistent_with_label_with_profile(network, labeling, function, profile)
        for profile in labeling.v_label
    )


def is_func_consistent_with_label_with_profile(
        network: Network,
        labeling: InconsistencySolution,
        function: Function,
        profile: str) -> bool:
    """
    Evaluates whether the function's regulatory logic aligns with the expected
    time-dependent behavior of the network, ensuring that the function's
    clauses are satisfied at each time step. It considers both stable states
    and dynamic updates based on the profile's labeling.
    """
    obs = network.get_observation(profile)
    if obs is not None and obs.updater is not None:
        return obs.updater.is_func_consistent_with_label_with_profile(network, labeling, function, profile)
    else:
        # for backward compatibility but should be removed and never used
        # an error should be raised if an observation has no updater
        if len(labeling.v_label[profile]) == 1 and network.has_ss_obs:
            return SteadyUpdater.is_func_consistent_with_label_with_profile(network, labeling, function, profile)
        for updater in network.updaters:
            if len(labeling.v_label[profile]) != 1 and updater.__class__.__name__.lower() != SteadyUpdater.__name__.lower():
                return updater.is_func_consistent_with_label_with_profile(network, labeling, function, profile)

def get_function_value(
        network: Network,
        function: Function,
        input_map: Dict[str, int]):
    """
    Evaluates the value of a function based on the given input map. It checks
    the satisfaction of the function's clauses.
    """
    n_clauses = function.get_n_clauses()
    if n_clauses:
        clauses = function.get_clauses()
        for clause in clauses:
            is_clause_satisfiable = True
            _vars = function.bitarray_to_regulators(clause)
            for var in _vars:
                edge = network.get_edge(var, function.node_id)
                if edge is not None:
                    # Determine if clause is satisfiable based on edge sign
                    if (edge.sign > 0) == (input_map[var] == 0):
                        is_clause_satisfiable = False
                        # Stop checking if clause is already unsatisfiable
                        break
                else:
                    logger.warning(f"Missing edge from {var} to {function.node_id}")
                    return False
            if is_clause_satisfiable:
                return True
    return False


def is_function_in_bottom_half(
        network: Network,
        function: Function) -> bool:
    """
    Determines if a function is in the bottom half based on its regulators.
    If exact middle determination is enabled, it uses a different method.
    """
    if config.exact_middle_function_determination:
        logger.debug("Half determination by state")
        return is_function_in_bottom_half_by_state(network, function)
    n = function.get_n_regulators()
    n2 = n // 2
    mid_level = [n2 for _ in range(n)]
    return function.compare_level_list(mid_level) < 0


def is_function_in_bottom_half_by_state(
        network: Network,
        function: Function) -> bool:
    """
    Determines if a function is in the bottom half based on its state by
    evaluating its output across all possible input combinations.
    """
    regulators = function.regulators
    n_regulators = function.get_n_regulators()
    entries = int(math.pow(2, n_regulators))
    n_one = 0
    n_zero = 0
    for entry in range(entries):
        # Use bitarray to simulate the bitset, little-endian order
        bits = bitarray(bin(entry)[2:].zfill(16)[::-1])
        input_map = {}
        bit_index = 0
        for regulator in regulators:
            input_map[regulator] = 1 if bits[bit_index] else 0
            bit_index += 1
        if get_function_value(network, function, input_map):
            n_one += 1
            if n_one > (entries // 2):
                break
        else:
            n_zero += 1
            if n_zero > (entries // 2):
                break
    return n_zero > (entries // 2)
