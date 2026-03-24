"""
This module contains the MultiAsyncUpdater class, which extends
TimeSeriesUpdater to handle multiple asynchronous updates while ensuring
consistency.
"""

import logging
import clingo
import os
from updaters.time_series_updater import TimeSeriesUpdater
from updaters.updater import Updater
from network.network import Network
from network.function import Function
from network.inconsistency_solution import InconsistencySolution
from configuration import Inconsistencies

logger = logging.getLogger(__name__)

class CompleteUpdater(TimeSeriesUpdater):
    """
    This class extends TimeSeriesUpdater and applies additional rules
    to handle complete updates while enforcing consistency checks.
    """

    @staticmethod
    def add_specific_rules(ctl: clingo.Control) -> None:
        """
        This method loads a configuration-defined rule set into the control
        object (ctl) and applies consistency constraints if enabled.
        """
        complete_lp = os.path.join(os.path.dirname(__file__), '..', 'asp_rules', 'complete.lp')
        ctl.load(complete_lp)


    @staticmethod
    def is_func_consistent_with_label_with_profile(
            network: Network,
            labeling: InconsistencySolution,
            function: Function,
            profile: str) -> bool:
        """
        Evaluates whether the function's regulatory logic aligns with the
        expected dynamic behavior of the network. This implementation assumes a
        time series (i.e. multiple time points) and does not handle a
        steady-state scenario.
        """
        logger.debug(f"Checking consistency of node {function.node_id} with function: {function.print_function(network=network)}")

        profile_map = labeling.v_label[profile]
        time = 0
        last_val = -1

        while time in profile_map:
            # For dynamic updates, ensure there is a next time point
            if time + 1 not in profile_map:
                break

            time_map = profile_map[time]

            # Always check update condition for time series (no steady state branch)
            if not TimeSeriesUpdater.should_update(time, labeling,function, profile):
                time += 1
                continue

            found_sat = False
            n_clauses = function.get_n_clauses()

            if n_clauses:
                for clause in function.get_clauses():
                    if Updater.is_clause_satisfiable(clause, network, time_map, function):
                        found_sat = True
                        # In a dynamic update, require a transition to a 1-label at the next time step.
                        if profile_map[time + 1][function.node_id] != 1:
                            return False
                        break

            if not found_sat:
                if n_clauses == 0:
                    if last_val < 0:
                        last_val = time_map[function.node_id]
                    if profile_map[time + 1][function.node_id] != last_val:
                        return False
                else:
                    if profile_map[time + 1][function.node_id] != 0:
                        return False
            time += 1
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
        result = Inconsistencies.CONSISTENT.value
        profile_map = labeling.v_label[profile]
        time = 0
        last_val = -1

        while time in profile_map:
            # If it's not a steady state, the following time must exist
            if (time + 1) not in profile_map:
                break

            time_map = profile_map[time]

            # Always check update condition for time series (no steady state branch)
            if not TimeSeriesUpdater.should_update(time, labeling, function, profile):
                time += 1
                continue

            found_sat = False
            n_clauses = function.get_n_clauses()

            if n_clauses:
                for clause in function.get_clauses():
                    if Updater.is_clause_satisfiable(clause, network, time_map, function):
                        found_sat = True
                        # In a dynamic update, require a transition to a 1-label at the next time step.
                        if profile_map[time + 1][function.node_id] != 1:
                            if result in (Inconsistencies.CONSISTENT.value,
                                          Inconsistencies.SINGLE_INC_PART.value):
                                result = Inconsistencies.SINGLE_INC_PART.value
                            else:
                                return Inconsistencies.DOUBLE_INC.value
                        break
            if not found_sat:
                if n_clauses == 0:
                    if last_val < 0:
                        last_val = time_map[function.node_id]
                    if profile_map[time + 1][function.node_id] != \
                            last_val:
                        return Inconsistencies.DOUBLE_INC.value
                else:
                    if profile_map[time + 1][function.node_id] != 0:
                        if result in (Inconsistencies.CONSISTENT.value,
                                      Inconsistencies.SINGLE_INC_GEN.value):
                            result = Inconsistencies.SINGLE_INC_GEN.value
                        else:
                            return Inconsistencies.DOUBLE_INC.value
            time += 1
        return result

