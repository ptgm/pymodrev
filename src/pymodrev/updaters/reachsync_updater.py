"""
This module contains the ReachSyncUpdater class, which extends the SyncUpdater
to handle Synchronous updates with consistency checks to assess the reacheability of a given state.
"""

import clingo
import os
from pymodrev.updaters.sync_updater import SyncUpdater

class ReachsyncUpdater(SyncUpdater):
    """
    This class extends SyncUpdater and provides specific rules to ensure
    the consistency of updates to reach a given state.
    """

    @staticmethod
    def get_type() -> str:
        """
        This is used by the user to specify the updater.
        """
        return "reachsync"

    @staticmethod
    def get_name() -> str:
        """
        This is used when generating asp facts.
        """
        return "sync"

    @staticmethod
    def add_specific_rules(ctl: clingo.Control) -> None:
        """
        This method loads a configuration-defined rule set into the control
        object (ctl) and applies consistency constraints based on the provided
        configuration.
        """
        reach_lp = os.path.join(os.path.dirname(__file__), '..', 'asp_rules', 'reach.lp')
        ctl.load(reach_lp)
        #SyncUpdater.add_specific_rules(ctl)
        super(ReachsyncUpdater,ReachsyncUpdater).add_specific_rules(ctl)

