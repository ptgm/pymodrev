"""High-level convenience API for pyModRev."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from pymodrev.network.model import Model
from pymodrev.network.observation import Observation
from pymodrev.network.observation_set import ObservationSet
from pymodrev.parsers.boolean_expression import parse_and_minimise_expression
from pymodrev.parsers.parser_factory import get_parser
from pymodrev.repair.consistency import check_consistency
from pymodrev.repair.engine import model_revision
from pymodrev.repair.repair import apply_repair as _apply_repair_in_place
from pymodrev.updaters.factory import get_updater


_OBSERVATION_SET = ObservationSet()
_LAST_USED_OBSERVATION_NAMES: list[str] | None = None
_LAST_OPTIMIZATION: int | None = None


def clear_obs() -> None:
    """Remove all observations stored in the module-level registry."""
    global _OBSERVATION_SET, _LAST_USED_OBSERVATION_NAMES, _LAST_OPTIMIZATION
    _OBSERVATION_SET = ObservationSet()
    _LAST_USED_OBSERVATION_NAMES = None
    _LAST_OPTIMIZATION = None


def get_observation_set() -> ObservationSet:
    """Return the module-level observation registry."""
    return _OBSERVATION_SET


def _coerce_expression(expression) -> str:
    if isinstance(expression, str):
        return expression
    if isinstance(expression, bool):
        return "1" if expression else "0"
    if isinstance(expression, int):
        return "1" if expression else "0"
    return str(expression)


def model_from_dict(model_definition: Mapping[str, object]) -> Model:
    """Build a model from a node-to-expression mapping.

    The expressions are parsed with the same boolean-expression pipeline used
    by the file parsers, so they are simplified and converted to signed edges
    before being stored in the network.
    """
    network = Model()

    for node_id in model_definition.keys():
        network.add_node(str(node_id))

    for node_id, expression in model_definition.items():
        target = str(node_id)
        target_node = network.get_node(target)
        if target_node is None:
            target_node = network.add_node(target)

        expression_text = _coerce_expression(expression).strip()
        if expression_text in {"0", "1"}:
            from pymodrev.parsers.boolean_expression import add_positive_autoregulation

            if expression_text == "1":
                add_positive_autoregulation(network, target_node, target)
            continue

        parse_and_minimise_expression(network, target_node, target, expression_text)

    return network


def _build_observation_from_data(name: str, data: Mapping, updater_type: str) -> Observation:
    updater = get_updater(updater_type)
    observation = Observation(updater)

    if data and all(isinstance(value, Mapping) for value in data.values()):
        for time, values in data.items():
            try:
                time_value = int(time)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid observation time '{time}' for '{name}'")
            for node_id, value in values.items():
                _add_observation_value(observation, name, time_value, str(node_id), value)
    else:
        for node_id, value in data.items():
            _add_observation_value(observation, name, None, str(node_id), value)

    return observation


def _add_observation_value(
    observation: Observation,
    exp_id: str,
    time,
    node_id: str,
    value,
) -> None:
    if value is None:
        return
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"", "na", "n/a", "nan", "*", "-"}:
            return
    observation.add_data(exp_id, time, node_id, int(value))


def add_obs(name: str, data: Mapping, updater_type: str) -> Observation:
    """Create and register an observation from a dictionary."""
    observation = _build_observation_from_data(name, data, updater_type)
    _OBSERVATION_SET.add_observation(observation)
    return observation


def _subset_observations(observation_names: Iterable[str] | None) -> ObservationSet:
    if observation_names is None:
        return _OBSERVATION_SET

    subset = ObservationSet()
    for observation_name in observation_names:
        observation = _OBSERVATION_SET.observations_dictionary.get(observation_name)
        if observation is None:
            raise KeyError(f"Observation '{observation_name}' is not registered")
        subset.add_observation(observation)
    return subset


def is_consistent(
    model: Model,
    observation_names: Sequence[str] | None = None,
) -> tuple[bool, list]:
    """Check whether a model is consistent with the selected observations."""
    global _LAST_USED_OBSERVATION_NAMES, _LAST_OPTIMIZATION
    selected_names = list(observation_names) if observation_names is not None else None
    observation_set = _subset_observations(selected_names)
    inconsistencies, optimization = check_consistency(model, observation_set)
    _LAST_USED_OBSERVATION_NAMES = selected_names
    _LAST_OPTIMIZATION = optimization
    return optimization == 0, inconsistencies


def get_repairs(
    model: Model,
    inconsistencies,
    observation_names: Sequence[str] | None = None,
):
    """Compute repair solutions for the provided inconsistencies."""
    selected_names = list(observation_names) if observation_names is not None else _LAST_USED_OBSERVATION_NAMES
    observation_set = _subset_observations(selected_names)

    optimization = _LAST_OPTIMIZATION if _LAST_OPTIMIZATION is not None else (1 if inconsistencies else 0)
    return model_revision(model, observation_set, inconsistencies, optimization)


def apply_repair(model: Model, repair, node_repair_map: dict | None = None) -> Model:
    """Apply a repair to a copy of the given model and return the copy."""
    repaired_model = copy.deepcopy(model)
    _apply_repair_in_place(repaired_model, repair, node_repair_map or {})
    return repaired_model


def load_model(filepath: os.PathLike[str] | str) -> Model:
    """Load a model from a supported file format."""
    filename = os.fspath(filepath)
    network = Model()
    parser = get_parser(filename)
    parser.read(network, filename)
    return network


def save_model(model: Model, filepath: os.PathLike[str] | str) -> None:
    """Write a model to disk using the parser that matches the file extension."""
    filename = os.fspath(filepath)
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    parser = get_parser(filename)
    parser.write(model, filename)