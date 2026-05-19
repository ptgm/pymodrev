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
        self._updaters_name: Set = set()
        self._updaters: Set = set()
        self._has_ss_obs: bool = False
        self._has_ts_obs: bool = False

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
    def updaters_name(self) -> Set:
        """Returns the set of updater names."""
        return self._updaters_name

    @property
    def updaters(self) -> Set:
        """Returns the set of updater objects."""
        return self._updaters

    @property
    def has_ss_obs(self) -> bool:
        """Returns whether there are steady-state observations."""
        return self._has_ss_obs

    @has_ss_obs.setter
    def has_ss_obs(self, value: bool):
        self._has_ss_obs = value

    @property
    def has_ts_obs(self) -> bool:
        """Returns whether there are time-series observations."""
        return self._has_ts_obs

    @has_ts_obs.setter
    def has_ts_obs(self, value: bool):
        self._has_ts_obs = value

    def add_updater(self, updater) -> None:
        self._updaters.add(updater)

    def add_updater_name(self, updater_name: str) -> None:
        self._updaters_name.add(updater_name)

    def add_observation(self, observation: Observation) -> None:
        """
        Adds an Observation object to the set.
        Raises ParseError on duplicate experiment profile.
        """
        for exp in observation.experiments:
            if exp in self._observations:
                raise ParseError(f"Duplicated experimental profile {exp}")
            self._observations[exp] = observation

    def get_observation_updater(self, profile: str):
        """
        Returns the updater for the given experiment profile, or None.
        """
        obs = self._observations.get(profile)
        if obs is not None:
            return obs.updater
        return None
