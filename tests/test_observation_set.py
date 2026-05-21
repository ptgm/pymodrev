import pytest
from pymodrev.network.observation_set import ObservationSet
from pymodrev.network.observation import Observation
from pymodrev.updaters.steady_updater import SteadyUpdater
from pymodrev.network.exceptions import ParseError


@pytest.fixture
def observation_set():
    return ObservationSet()


def test_add_observation(observation_set):
    updater = SteadyUpdater()
    obs = Observation(updater)
    obs.experiments.add('exp1')
    observation_set.add_observation(obs)
    assert obs in observation_set.observations


def test_get_observation_updater(observation_set):
    updater = SteadyUpdater()
    obs = Observation(updater)
    obs.experiments.add('exp1')
    observation_set.add_observation(obs)
    assert updater == observation_set.get_observation_updater('exp1')


def test_duplicated_observation(observation_set):
    updater = SteadyUpdater()
    obs = Observation(updater)
    obs.experiments.add('exp1')
    observation_set.add_observation(obs)
    with pytest.raises(ParseError):
        observation_set.add_observation(obs)
