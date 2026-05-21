from pymodrev.updaters.factory import get_available_updaters, get_updater, is_valid_updater_type
from pymodrev.updaters.async_updater import AsyncUpdater
from pymodrev.updaters.complete_updater import CompleteUpdater
from pymodrev.updaters.notsteady_updater import NotsteadyUpdater
from pymodrev.updaters.steady_updater import SteadyUpdater
from pymodrev.updaters.sync_updater import SyncUpdater

_EXPECTED_UPDATERS = [
    "steady", "sync", "async", "complete", "notsteady"
]

def test_discovered_updater_types_match_declared_types():
    discovered_types = set(get_available_updaters().keys())
    assert discovered_types == set(_EXPECTED_UPDATERS)


def test_is_valid_updater_type():
    for updater_type in _EXPECTED_UPDATERS:
        assert is_valid_updater_type(updater_type)
    assert not is_valid_updater_type("invalid")


def test_get_updater_returns_expected_type_instance():
    assert get_updater("steady").__class__.__name__ == SteadyUpdater.__name__
    assert get_updater("sync").__class__.__name__ == SyncUpdater.__name__
    assert get_updater("async").__class__.__name__ == AsyncUpdater.__name__
    assert get_updater("complete").__class__.__name__ == CompleteUpdater.__name__
    assert get_updater("notsteady").__class__.__name__ == NotsteadyUpdater.__name__


def test_get_updater_raises_for_unknown_type():
    try:
        get_updater("invalid")
        assert False, "Expected ValueError for invalid updater type"
    except ValueError as exc:
        assert "Updater 'invalid' not found" in str(exc)
