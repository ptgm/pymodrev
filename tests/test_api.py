import pytest

import pymodrev as mrev
from pymodrev.network.exceptions import EdgeNotFoundError


@pytest.fixture(autouse=True)
def clean_observations():
    mrev.clear_obs()
    yield
    mrev.clear_obs()


def test_model_from_dict_simplifies_expression_and_builds_edges():
    model = mrev.model_from_dict({"A": "B | (B & C)", "B": "A", "C": "C"})

    assert set(model.nodes.keys()) == {"A", "B", "C"}
    assert model.get_edge("B", "A").sign == 1
    with pytest.raises(EdgeNotFoundError):
        model.get_edge("C", "A")


def test_add_obs_registers_steady_observation():
    observation = mrev.add_obs("apoptosis", {"A": 0, "B": "na", "C": 1}, "steady")

    assert observation.experiments == {"apoptosis"}
    assert ("apoptosis", None, "A", 0) in observation.data
    assert ("apoptosis", None, "C", 1) in observation.data
    assert ("apoptosis", None, "B", 0) not in observation.data
    assert "apoptosis" in mrev.get_observation_set().observations_dictionary


def test_add_obs_registers_time_series_observation():
    observation = mrev.add_obs(
        "exp2",
        {0: {"A": 0, "B": "na"}, 2: {"A": 1, "B": 1}},
        "async",
    )

    assert observation.experiments == {"exp2"}
    assert ("exp2", 0, "A", 0) in observation.data
    assert ("exp2", 2, "A", 1) in observation.data
    assert ("exp2", 2, "B", 1) in observation.data


def test_save_model_round_trips_to_bnet(tmp_path):
    model = mrev.model_from_dict({"A": "B", "B": "A"})
    out_file = tmp_path / "model.bnet"

    mrev.save_model(model, out_file)

    loaded = mrev.load_model(out_file)
    assert set(loaded.nodes.keys()) == {"A", "B"}
    assert loaded.get_edge("B", "A").sign == 1
    assert loaded.get_edge("A", "B").sign == 1