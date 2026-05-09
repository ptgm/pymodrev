"""
This module contains the NotSteadyStateUpdater class, which extends the SyncUpdater
to handle synchronous updates with consistency checks to avoid the corresponding given steady-state.
"""

import logging
import clingo
import os
from pymodrev.updaters.async_updater import AsyncUpdater

logger = logging.getLogger(__name__)

class NotsteadyUpdater(AsyncUpdater):
    """
    This class extends SyncUpdater and provides specific rules to ensure
    the consistency of updates to avoid a steady-state.
    """

    @staticmethod
    def get_type() -> str:
        """
        This method to return the update type
        (e.g., sync, async, etc.).
        """
        return "not_ss"


    @staticmethod
    def add_specific_rules(ctl: clingo.Control) -> None:
        """
        This method loads a configuration-defined rule set into the control
        object (ctl) and applies consistency constraints based on the provided
        configuration.
        """
        avoid_ss_lp = os.path.join(os.path.dirname(__file__), '..', 'asp_rules', 'avoid_steady_state.lp')
        ctl.load(avoid_ss_lp)