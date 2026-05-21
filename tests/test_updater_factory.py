from pymodrev.updaters.factory import get_available_updaters, get_updater, is_valid_updater_type
from pymodrev.updaters.async_updater import AsyncUpdater
from pymodrev.updaters.complete_updater import CompleteUpdater
from pymodrev.updaters.notsteady_updater import NotsteadyUpdater
from pymodrev.updaters.steady_updater import SteadyUpdater
from pymodrev.updaters.sync_updater import SyncUpdater


def test_discovered_updater_types_match_declared_types():
    updaters = get_available_updaters()
    discovered_types = set(updaters.keys())

    expected_types = {
        AsyncUpdater.get_type(),
        CompleteUpdater.get_type(),
        NotsteadyUpdater.get_type(),
        SteadyUpdater.get_type(),
        SyncUpdater.get_type(),
    }

    assert discovered_types == expected_types


def test_is_valid_updater_type():
    assert is_valid_updater_type("steady")
    assert is_valid_updater_type("sync")
    assert is_valid_updater_type("async")
    assert is_valid_updater_type("complete")
    assert is_valid_updater_type("not_ss")
    assert not is_valid_updater_type("invalid")


def test_get_updater_returns_expected_type_instance():
    assert isinstance(get_updater("steady"), SteadyUpdater)
    assert isinstance(get_updater("sync"), SyncUpdater)
    assert isinstance(get_updater("async"), AsyncUpdater)
    assert isinstance(get_updater("complete"), CompleteUpdater)
    assert isinstance(get_updater("not_ss"), NotsteadyUpdater)


def test_get_updater_raises_for_unknown_type():
    try:
        get_updater("invalid")
        assert False, "Expected ValueError for invalid updater type"
    except ValueError as exc:
        assert "Updater 'invalid' not found" in str(exc)
