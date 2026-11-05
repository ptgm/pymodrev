"""
This module contains the TimeSeriesUpdater class, which provides an abstract
base class for managing time series updates. The class enforces the
implementation of specific update rules and applies these rules based on the
configuration.
"""

from abc import abstractmethod
import clingo
import os
from typing import Optional
from pymodrev.updaters.updater import Updater
from pymodrev.network.function import Function
from pymodrev.network.inconsistency_solution import InconsistencySolution


class TimeSeriesUpdater(Updater):
    """
    This class extends the Updater class and defines the basic structure for
    time series update rules. It is meant to be subclassed and extended by
    specific update types (e.g., asynchronous, synchronous, complete)
    """

    @staticmethod
    @abstractmethod
    def add_specific_rules(ctl: clingo.Control):
        """
        Subclasses must implement this method to define rules that are specific
        to the type of update (e.g., async, sync, or complete).
        """

    @staticmethod
    def apply_update_rules(ctl: clingo.Control, updater) -> None:
        """
        This method applies general update rules and calls the specific update
        rules depending on the update type (asynchronous, synchronous, or
        complete). It loads the configuration and applies consistency checks as
        required.
        """
        time_series_lp = os.path.join(os.path.dirname(__file__), '..', 'asp_rules', 'time_series.lp')
        ctl.load(time_series_lp)

        updater.add_specific_rules(ctl)

    @staticmethod
    def should_update(
            time: int,
            labeling: InconsistencySolution,
            function: Function,
            profile: str) -> bool:
        """
        Determines if the function should be considered for an update at the
        given time. In a time series scenario, this method checks if the
        function's node ID is in the updates list.
        """
        updates = labeling.updates[time][profile]
        return any(update == function.node_id for update in updates)


    @staticmethod
    def transition_rows(
            labeling: InconsistencySolution,
            node_id: str,
            profile: str,
            only_when_updated: bool) -> Optional['ProfileRows']:
        """
        Rows of a time series: one per transition t -> t+1 (in which the node
        is updated, if ``only_when_updated``).
        """
        from pymodrev.repair.constraints import ProfileRows, DYNAMIC
        profile_map = labeling.v_label[profile]
        states = []
        outs = []
        time = 0
        while time in profile_map and (time + 1) in profile_map:
            if only_when_updated:
                updates = labeling.updates.get(time, {}).get(profile, ())
                if node_id not in updates:
                    time += 1
                    continue
            states.append(profile_map[time])
            outs.append(profile_map[time + 1][node_id])
            time += 1
        return ProfileRows(DYNAMIC, states, outs)
