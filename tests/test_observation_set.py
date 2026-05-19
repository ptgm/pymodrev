import pytest
from pymodrev.network.observation_set import ObservationSet
from pymodrev.network.observation import Observation
from pymodrev.updaters.steady_updater import SteadyUpdater
from pymodrev.network.exceptions import ParseError


@pytest.fixture
def observation_set():
    return ObservationSet()


def test_observation_set_flags(observation_set):
    observation_set.has_ss_obs = True
    assert observation_set.has_ss_obs
    observation_set.has_ss_obs = False
    assert not observation_set.has_ss_obs

    observation_set.has_ts_obs = True
    assert observation_set.has_ts_obs
    observation_set.has_ts_obs = False
    assert not observation_set.has_ts_obs


def test_add_observation(observation_set):
    obs = Observation('obs1.lp', None)
    obs.experiments.add('exp1')
    observation_set.add_observation(obs)
    assert obs in observation_set.observations


def test_get_observation_updater(observation_set):
    updater = SteadyUpdater()
    obs = Observation('obs1.lp', updater)
    obs.experiments.add('exp1')
    observation_set.add_observation(obs)
    assert updater == observation_set.get_observation_updater('exp1')


def test_duplicated_observation(observation_set):
    obs = Observation('obs1.lp', None)
    obs.experiments.add('exp1')
    observation_set.add_observation(obs)
    with pytest.raises(ParseError):
        observation_set.add_observation(obs)
