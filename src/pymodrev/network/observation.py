"""
This module provides the Observation class for pyModRev. The Observation class
encapsulates information about an observation, including the updater specified
via the command line. It also performs a basic check to ensure the provided 
observation file exists.
"""

import os
from pymodrev.updaters.updater import Updater
from pymodrev.parsers.asp_utils import asp_quote


from typing import List, Tuple, Set, Optional


class Observation:
    """
    Represents an observation for the network model, including the updater (as 
    specified via the command line). It stores the internal structure of 
    observations and can generate ASP facts.
    """

    def __init__(self, updater: Updater):
        """
        Initializes an Observation instance.
        """
        self.updater = updater
        self.experiments: Set[str] = set()
        # Data format: (experiment_id, time, node_id, value)
        # where time is None for steady-state observations
        self.data: List[Tuple[str, Optional[int], str, int]] = []

    def add_data(self, exp_id: str, time: Optional[int], node_id: str, value: int):
        """
        Adds an observation data point.
        """
        self.experiments.add(exp_id)
        self.data.append((exp_id, time, node_id, value))

    def to_asp_facts(self) -> str:
        """
        Generates ASP facts from the internal observation data.
        """
        facts = []
        for exp_id in sorted(list(self.experiments)):
            facts.append(f"exp({asp_quote(exp_id)}).")
            if self.updater is not None:
                facts.append(f"exp({asp_quote(exp_id)},{self.updater.get_name()}).")
        
        for exp_id, time, node_id, value in self.data:
            if time is None:
                facts.append(f"obs_vlabel({asp_quote(exp_id)},{asp_quote(node_id)},{value}).")
            else:
                facts.append(f"obs_vlabel({asp_quote(exp_id)},{time},{asp_quote(node_id)},{value}).")
        
        return "\n".join(facts) + "\n"

    def __str__(self):
        return f"Observation(updater='{self.updater}', n_points={len(self.data)})"

    def __repr__(self):
        return (f"Observation(updater={self.updater!r}, n_points={len(self.data)})")
