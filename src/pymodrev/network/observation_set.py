"""
This module defines the ObservationSet class, which holds all observation
data associated with a model revision run, separately from the model topology.
"""

from typing import Dict, List, Set
from pymodrev.network.observation import Observation
from pymodrev.network.exceptions import ParseError


class ObservationSet:
    """
    Holds the collection of Observation objects for a model revision run.
    Provides methods to add observations and query their updaters.
    """

    def __init__(self) -> None:
        self._observations: Dict[str, Observation] = {}  # {'exp_id': obs, ...}
        self._updaters: Set = set()

    @property
    def observations_dictionary(self) -> Dict[str, Observation]:
        """Returns the dictionary of [profile, Observation objects]."""
        return self._observations

    @property
    def observations(self) -> List[Observation]:
        """Returns the list of unique Observation objects."""
        return list(set(self._observations.values()))

    @property
    def observation_files(self) -> List[str]:
        """Returns the list of observation file paths."""
        return list(set([obs.observation_path for obs in self._observations.values()]))

    @property
    def observation_files_with_updater(self) -> List:
        """Returns the list of (observation_path, updater) pairs."""
        return list(set([(obs.observation_path, obs.updater) for obs in self._observations.values()]))

    @property
    def updaters(self) -> Set:
        """Returns the set of updater objects."""
        return self._updaters

    def add_observation(self, observation: Observation) -> None:
        """
        Adds an Observation object to the set.
        Raises ParseError on duplicate experiment profile.
        """
        for exp in observation.experiments:
            if exp in self._observations:
                raise ParseError(f"Duplicated experimental profile {exp}")
            self._observations[exp] = observation
        self._updaters.add(observation.updater)

    def get_observation_updater(self, profile: str):
        """
        Returns the updater for the given experiment profile, or None.
        """
        obs = self._observations.get(profile)
        if obs is not None:
            return obs.updater
        return None
