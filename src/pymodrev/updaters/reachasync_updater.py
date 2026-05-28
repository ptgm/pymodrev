"""
This module contains the ReachAsyncUpdater class, which extends the AsyncUpdater
to handle asynchronous updates with consistency checks to assess the reacheability of a given state.
"""

import clingo
import os
from pymodrev.updaters.async_updater import AsyncUpdater

class ReachasyncUpdater(AsyncUpdater):
    """
    This class extends AsyncUpdater and provides specific rules to ensure
    the consistency of updates to reach a given state.
    """


    @staticmethod
    def add_specific_rules(ctl: clingo.Control) -> None:
        """
        This method loads a configuration-defined rule set into the control
        object (ctl) and applies consistency constraints based on the provided
        configuration.
        """
        reach_lp = os.path.join(os.path.dirname(__file__), '..', 'asp_rules', 'reach.lp')
        ctl.load(reach_lp)
        #AsyncUpdater.add_specific_rules(ctl)
        super(ReachasyncUpdater,ReachasyncUpdater).add_specific_rules(ctl)

