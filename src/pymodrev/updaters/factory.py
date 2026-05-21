"""Dynamic discovery and lookup utilities for updater implementations."""

import inspect
import os
from functools import lru_cache
from importlib import util
from typing import Dict

from pymodrev.updaters.updater import Updater


def _load_module(module_name: str, module_path: str):
    spec = util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load updater module '{module_name}'")

    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _discover_updaters() -> Dict[str, Updater]:
    updaters: Dict[str, Updater] = {}
    updater_dir = os.path.dirname(__file__)
    ignored = {
        "__init__.py",
        "updater.py",
        "time_series_updater.py",
        "factory.py",
    }

    for filename in os.listdir(updater_dir):
        if not filename.endswith(".py") or filename in ignored:
            continue

        module_basename = os.path.splitext(filename)[0]
        module_name = f"pymodrev.updaters.{module_basename}"
        module_path = os.path.join(updater_dir, filename)
        module = _load_module(module_name, module_path)

        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            if not issubclass(cls, Updater) or cls is Updater:
                continue
            if inspect.isabstract(cls):
                continue

            updater = cls()
            updater_type = updater.get_type()
            if updater_type in updaters and type(updaters[updater_type]) is not type(updater):
                raise ValueError(f"Duplicate updater type discovered: '{updater_type}'")
            updaters[updater_type] = updater

    return updaters


def get_available_updaters() -> Dict[str, Updater]:
    """Return all discovered updaters keyed by their declared updater type."""
    return dict(_discover_updaters())


def is_valid_updater_type(updater_type: str) -> bool:
    """Check whether an updater type string can be resolved to an updater."""
    return updater_type in _discover_updaters()


def get_updater(updater_type: str) -> Updater:
    """Return the updater instance for a type or raise ValueError if unknown."""
    updater = _discover_updaters().get(updater_type)
    if updater is None:
        raise ValueError(f"Updater '{updater_type}' not found in updaters directory")
    return updater
