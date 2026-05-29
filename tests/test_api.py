import pytest

import pymodrev as mrev
from pymodrev import api
from pymodrev.configuration import config
from pymodrev.network import model
from pymodrev.network.exceptions import EdgeNotFoundError
from pymodrev.network.inconsistency_solution import InconsistencySolution


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


def test_save_model_round_trips_to_bnet(tmp_path):
    model = mrev.model_from_dict({"A": "B", "B": "A"})
    out_file = tmp_path / "model.bnet"

    mrev.model_to_file(model, out_file)

    loaded = mrev.model_from_file(out_file)
    assert set(loaded.nodes.keys()) == {"A", "B"}
    assert loaded.get_edge("B", "A").sign == 1
    assert loaded.get_edge("A", "B").sign == 1


def test_is_consistent():
    model = mrev.model_from_dict({"A": "A"})
    mrev.add_obs("obs1", {"A": 0}, "steady")

    res = mrev.is_consistent(model, ["obs1"])
    assert config.solutions == 1
    assert res == {"consistent": True }

    mrev.is_consistent(model, ["obs1"], sol=4)
    assert config.solutions == 4
    assert res == {"consistent": True }


def test_get_repairs_consistent():
    model = mrev.model_from_dict({"A": "A"})
    mrev.add_obs("obs1", {"A": 0}, "steady")
    mrev.is_consistent(model, ["obs1"])
    try:
        repairs = mrev.get_repairs(model)
        assert False, "Expected ValueError when model is consistent"
    except ValueError as e:
        assert str(e) == "Model is already consistent; no repairs to return"


def test_apply_repairs_accepts_single_solution():
    model = mrev.model_from_dict({"A": "A"})
    mrev.add_obs("obs1", {"A": 0}, "notsteady")
    mrev.is_consistent(model, ["obs1"])
    mrev.get_repairs(model)
    repaired_models = mrev.apply_repairs(model)
    assert len(repaired_models) == 1
    assert repaired_models[0] is not model

def test_apply_empty_repairs():
    model = mrev.model_from_dict({"A": "A"})
    mrev.add_obs("obs1", {"A": 0}, "notsteady")
    mrev.is_consistent(model, ["obs1"])
    try:
        mrev.apply_repairs(model)
        assert False, "Expected ValueError when no repairs are available"
    except ValueError as e:
        assert str(e) == "get_repairs() must be run before"
