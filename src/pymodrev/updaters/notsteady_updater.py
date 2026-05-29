"""
This module contains the NotSteadyStateUpdater class, which extends the AsyncUpdater
to handle asynchronous updates with consistency checks to avoid the corresponding given steady-state.
"""

import clingo
import os
from pymodrev.updaters.async_updater import AsyncUpdater

class NotsteadyUpdater(AsyncUpdater):
    """
    This class extends AsyncUpdater and provides specific rules to ensure
    the consistency of updates to avoid a steady-state.
    """

    @staticmethod
    def get_type() -> str:
        """
        This is used by the user to specify the updater.
        """
        return "notsteady"


    @staticmethod
    def get_name() -> str:
        """
        This is used when generating asp facts.
        """
        return NotsteadyUpdater.get_type()
    

    @staticmethod
    def add_specific_rules(ctl: clingo.Control) -> None:
        """
        This method loads a configuration-defined rule set into the control
        object (ctl) and applies consistency constraints based on the provided
        configuration.
        """
        avoid_ss_lp = os.path.join(os.path.dirname(__file__), '..', 'asp_rules', 'notsteady_state.lp')
        ctl.load(avoid_ss_lp)

