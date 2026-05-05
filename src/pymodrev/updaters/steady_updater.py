"""
This module contains the SteadyStateUpdater class, which extends the Updater
class to handle steady-state updates while ensuring consistency constraints.
"""

import logging
import clingo
import os
from pymodrev.updaters.updater import Updater
from pymodrev.network.network import Network
from pymodrev.network.function import Function
from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.configuration import Inconsistencies

logger = logging.getLogger(__name__)

class SteadyUpdater(Updater):
    """
    This class extends Updater and applies specific rules to ensure
    consistent updates in a steady-state system.
    """

    @staticmethod
    def get_type() -> str:
        """
        This method to return the update type
        (e.g., sync, async, steady, etc.).
        """
        return "steady"


    @staticmethod
    def apply_update_rules(ctl: clingo.Control, updater) -> None:
        """
        This method loads configuration-defined rules into the control object
        (ctl) and applies consistency constraints based on the provided
        configuration.
        """
        steady_lp = os.path.join(os.path.dirname(__file__), '..', 'asp_rules', 'steady.lp')
        ctl.load(steady_lp)


    @staticmethod
    def is_func_consistent_with_label_with_profile(
            network: Network,
            labeling: InconsistencySolution,
            function: Function,
            profile: str) -> bool:
        """
        Evaluates whether the function's regulatory logic aligns with the
        expected steady-state behavior of the network. This method assumes a
        single time mapping is present in the label profile.
        """
        logger.debug(f"Checking consistency of node {function.node_id} with function: {function.print_function(network=network)}")

        profile_map = labeling.v_label[profile]

        # For steady state, we expect exactly one time mapping
        # if len(profile_map) != 1:
        #     # print("ERROR: SteadyStateUpdater expects a single time mapping.")
        #     return False

        # Retrieve the unique time mapping
        time_key = next(iter(profile_map))
        time_map = profile_map[time_key]
        found_sat = False
        n_clauses = function.get_n_clauses()

        if n_clauses:
            # Evaluate each clause until one is satisfiable.
            for clause in function.get_clauses():
                if Updater.is_clause_satisfiable(clause, network, time_map, function):
                    # In steady state, a satisfied clause means the function’s output should be 1.
                    found_sat = True
                    return time_map[function.node_id] == 1
        if not found_sat:
            return n_clauses == 0 or time_map[function.node_id] == 0
        return True


    @staticmethod
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
        logger.debug(f"Checking consistency of node {function.node_id} with function: {function.print_function(network=network)}")

        profile_map = labeling.v_label[profile]
        # For steady state, we expect exactly one time mapping
        # if len(profile_map) != 1:
        #     print("ERROR: SteadyUpdater expects a single time mapping.")
        #     return False

        result = Inconsistencies.CONSISTENT.value
        profile_map = labeling.v_label[profile]

        time_key = next(iter(profile_map))
        time_map = profile_map[time_key]
        found_sat = False
        n_clauses = function.get_n_clauses()

        if n_clauses:
            for clause in function.get_clauses():
                if Updater.is_clause_satisfiable(clause, network, time_map, function):
                    found_sat = True
                    if time_map[function.node_id] == 1:
                        return Inconsistencies.CONSISTENT.value
                    return Inconsistencies.SINGLE_INC_PART.value
        if not found_sat:
            if n_clauses == 0:
                return Inconsistencies.CONSISTENT.value
            if time_map[function.node_id] == 0:
                return Inconsistencies.CONSISTENT.value
            return Inconsistencies.SINGLE_INC_GEN.value
        return result
