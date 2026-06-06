import pytest

import pymodrev as mrev
from pymodrev.configuration import config
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


def test_model_from_dict_coerces_bool_and_int_constants():
    model = mrev.model_from_dict({"A": True, "B": 0})

    assert set(model.nodes.keys()) == {"A", "B"}
    # Constant true is encoded through positive autoregulation.
    assert model.get_edge("A", "A").sign == 1
    # Constant false should not introduce regulators.
    with pytest.raises(EdgeNotFoundError):
        model.get_edge("B", "B")


def test_model_to_file_round_trips_to_bnet(tmp_path):
    model = mrev.model_from_dict({"A": "B", "B": "A"})
    out_file = tmp_path / "nested" / "model.bnet"

    mrev.model_to_file(model, out_file)

    loaded = mrev.model_from_file(out_file)
    assert set(loaded.nodes.keys()) == {"A", "B"}
    assert loaded.get_edge("B", "A").sign == 1
    assert loaded.get_edge("A", "B").sign == 1


def test_is_consistent_returns_json_and_sets_solver_config():
    model = mrev.model_from_dict({"A": "A"})
    mrev.obs_steady("obs1", {"A": 0})

    res = mrev.is_consistent(model, ["obs1"])
    assert config.solutions == 1
    assert isinstance(res, dict)
    assert res.get("consistent") is True

    res_sol4 = mrev.is_consistent(model, ["obs1"], sol=4)
    assert config.solutions == 4
    assert res_sol4.get("consistent") is True


def test_is_consistent_accepts_single_observation_name_as_string():
    model = mrev.model_from_dict({"A": "A"})
    mrev.obs_steady("obs1", {"A": 1})

    res = mrev.is_consistent(model, "obs1")
    assert res.get("consistent") is True


def test_is_consistent_validates_inputs():
    model = mrev.model_from_dict({"A": "A"})
    mrev.obs_steady("obs1", {"A": 1})

    with pytest.raises(ValueError, match="sol must be one of"):
        mrev.is_consistent(model, ["obs1"], sol=5)

    with pytest.raises(ValueError, match="At least one observation name"):
        mrev.is_consistent(model, [])

    with pytest.raises(KeyError, match="is not registered"):
        mrev.is_consistent(model, ["missing_obs"])


def test_obs_sync_ts_rejects_invalid_time_keys():
    with pytest.raises(ValueError, match="Invalid observation time"):
        mrev.obs_sync_ts("obs1", {"0": {"A": 1}})


def test_obs_sync_ts_registers_valid_time_series():
    model = mrev.model_from_dict({"A": "A"})

    mrev.obs_sync_ts("ts_obs", {0: {"A": 1}, 1: {"A": 1}})

    res = mrev.is_consistent(model, ["ts_obs"])
    assert res.get("consistent") is True


def test_obs_async_ts_registers_valid_time_series():
    model = mrev.model_from_dict({"A": 0})

    mrev.obs_async_ts("ts_obs", {0: {"A": 0}, 1: {"A": 0}})

    res = mrev.is_consistent(model, ["ts_obs"])
    assert isinstance(res, dict)
    assert set(res) >= {"consistent", "inconsistencies"}


def test_obs_sync_reach_registers_valid_reachability_observation():
    model = mrev.model_from_dict({"A": "A"})

    mrev.obs_sync_reach("reach_obs", {"A": 1}, {"A": 1})

    res = mrev.is_consistent(model, ["reach_obs"])
    assert res.get("consistent") is True


def test_obs_async_reach_registers_valid_reachability_observation():
    model = mrev.model_from_dict({"A": 0})

    mrev.obs_async_reach("reach_obs", {"A": 0}, {"A": 0})

    res = mrev.is_consistent(model, ["reach_obs"])
    assert isinstance(res, dict)
    assert set(res) >= {"consistent", "inconsistencies"}


def test_repair_requires_is_consistent_first_when_no_obs_names():
    model = mrev.model_from_dict({"A": "A"})

    with pytest.raises(ValueError, match=r"is_consistent\(\) method must be run before"):
        mrev.repair(model)


def test_repair_returns_empty_for_consistent_model_after_is_consistent():
    model = mrev.model_from_dict({"A": "A"})
    mrev.obs_steady("obs1", {"A": 0})
    mrev.is_consistent(model, ["obs1"])

    repaired_models, details = mrev.repair(model)
    assert repaired_models == []
    assert details == {}


def test_repair_accepts_single_observation_name_as_string():
    model = mrev.model_from_dict({"A": "A"})
    mrev.obs_steady("obs1", {"A": 1})

    repaired_models, details = mrev.repair(model, "obs1")
    assert repaired_models == []
    assert details == {}


def test_repair_returns_repaired_model_variants():
    model = mrev.model_from_dict({"A": "A"})
    mrev.obs_notsteady("obs1", {"A": 0})

    repaired_models, details = mrev.repair(model, ["obs1"])
    assert len(repaired_models) >= 1
    assert all(repaired is not model for repaired in repaired_models)
    assert isinstance(details, dict)
