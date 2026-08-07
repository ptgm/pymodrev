"""High-level convenience API for pyModRev."""

from __future__ import annotations

import copy
import itertools
import os
import json
from pathlib import Path
from typing import Mapping, List, Tuple

from pymodrev.configuration import config
from pymodrev.network.model import Model
from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.network.observation import Observation
from pymodrev.network.observation_set import ObservationSet
from pymodrev.parsers.boolean_expression import parse_and_minimise_expression
from pymodrev.parsers.parser_factory import get_parser
from pymodrev.repair.consistency import check_consistency, consistency_to_str
from pymodrev.repair.engine import model_revision
from pymodrev.repair.repair import apply_repair as _apply_repair_in_place
from pymodrev.updaters.factory import get_updater

# This keeps the state between function calls between API function calls
_OBSERVATION_SET = ObservationSet()
_LAST_USED_OBSERVATION_NAMES: List[str] | None = None
_LAST_OPTIMIZATION: int | None = None
_LAST_INCONSISTENCIES: List[InconsistencySolution] | None = None

def clear_obs() -> None:
    """Remove all observations stored in the module-level registry."""
    global _OBSERVATION_SET, _LAST_USED_OBSERVATION_NAMES, _LAST_OPTIMIZATION, _LAST_INCONSISTENCIES
    _OBSERVATION_SET = ObservationSet()
    _LAST_USED_OBSERVATION_NAMES = None
    _LAST_OPTIMIZATION = None
    _LAST_INCONSISTENCIES = None


def _coerce_expression(expression) -> str:
    if isinstance(expression, (bool, int)):
        return "1" if expression else "0"
    return expression if isinstance(expression, str) else str(expression)


def model_from_dict(model_definition: Mapping[str, object]) -> Model:
    """Build a model from a node-to-expression mapping.

    The Boolean expressions are parsed and simplified to extract the 
    edges and corresponding signs, before being stored in the model.
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
        if expression_text in ("0", "1"):
            from pymodrev.parsers.boolean_expression import add_positive_autoregulation
            if expression_text == "1":
                add_positive_autoregulation(network, target_node, target)
            continue

        parse_and_minimise_expression(network, target_node, target, expression_text)

    return network


def model_from_file(filepath: os.PathLike[str] | str) -> Model:
    """Load a model from a supported file format (.bnet, .zginml, .lp)."""
    filename = os.fspath(filepath)
    network = Model()
    parser = get_parser(filename)
    parser.read(network, filename)
    return network


def _add_observation_value(observation: Observation, obs_id: str,
    time, node_id: str, value: str | int) -> None:
    if value is None:
        return
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("", "na", "n/a", "nan", "*", "-"):
            return # ignore: no restriction on this (obs_id,node_id)
        elif normalized in ("1", "true", "t", "yes", "y"):
            value = 1
        elif normalized in ("0", "false", "f", "no", "n"):
            value = 0
        else:
            raise ValueError(f"Invalid observation '{obs_id}' value: '{node_id}' = '{value}'")
    observation.add_data(obs_id, time, node_id, value)

def _add_single_state_obs(obs_id: str, data: Mapping[str, str | int], updater_type: str) -> Observation:
    updater = get_updater(updater_type)
    observation = Observation(updater)
    for node_id, value in data.items():
        _add_observation_value(observation, obs_id, None, node_id, value)
    return observation

def _add_multiple_state_obs(obs_id: str, data: Mapping, updater_type: str) -> Observation:
    updater = get_updater(updater_type)
    observation = Observation(updater)

    if data and all(isinstance(value, Mapping) for value in data.values()):
        for time, values in data.items():
            if not isinstance(time, int) and (not isinstance(time, str) or time not in {"init", "final"}):
                raise ValueError(f"Invalid observation time '{time}' for '{obs_id}'")
            for node_id, value in values.items():
                _add_observation_value(observation, obs_id, time, node_id, value)
    else:
        for node_id, value in data.items():
            _add_observation_value(observation, obs_id, None, node_id, value)

    return observation


def obs_steady(obs_id: str, state: Mapping[str, str | int]) -> None:
    """Register a named steady-state observation from a dictionary of nodes and their values."""
    observation = _add_single_state_obs(obs_id, state, "steady")
    global _OBSERVATION_SET
    _OBSERVATION_SET.add_observation(observation)

def obs_notsteady(obs_id: str, state: Mapping[str, int]) -> None:
    """Register a named notsteady-state observation from a dictionary of nodes and their values."""
    observation = _add_single_state_obs(obs_id, state, "notsteady")
    global _OBSERVATION_SET
    _OBSERVATION_SET.add_observation(observation)


def obs_sync_ts(obs_id: str, data: Mapping[str|int, Mapping[str, int]]) -> None:
    """Register a named synchronous time-series observation from a dictionary of time points to node-value mappings."""
    observation = _add_multiple_state_obs(obs_id, data, "sync")
    global _OBSERVATION_SET
    _OBSERVATION_SET.add_observation(observation)

def obs_async_ts(obs_id: str, data: Mapping[str|int, Mapping[str, int]]) -> None:
    """Register a named asynchronous time-series observation from a dictionary of time points to node-value mappings."""
    observation = _add_multiple_state_obs(obs_id, data, "async")
    global _OBSERVATION_SET
    _OBSERVATION_SET.add_observation(observation)


def obs_sync_reach(obs_id: str, data_init: Mapping[str, int], data_final: Mapping[str, int]) -> None:
    """Register a named synchronous reachability observation from two dictionaries of nodes and their values."""
    data = {"init": data_init, "final": data_final}
    observation = _add_multiple_state_obs(obs_id, data, "reachsync")
    global _OBSERVATION_SET
    _OBSERVATION_SET.add_observation(observation)

def obs_async_reach(obs_id: str, data_init: Mapping[str, int], data_final: Mapping[str, int]) -> None:
    """Register a named asynchronous reachability observation from two dictionaries of nodes and their values."""
    data = {"init": data_init, "final": data_final}
    observation = _add_multiple_state_obs(obs_id, data, "reachasync")
    global _OBSERVATION_SET
    _OBSERVATION_SET.add_observation(observation)


def _subset_observations(observation_names: List[str] | None) -> ObservationSet:
    global _OBSERVATION_SET
    if observation_names is None:
        return _OBSERVATION_SET

    subset = ObservationSet()
    for observation_name in observation_names:
        observation = _OBSERVATION_SET.observations_dictionary.get(observation_name)
        if observation is None:
            raise KeyError(f"Observation '{observation_name}' is not registered")
        subset.add_observation(observation)
    return subset


def is_consistent(model: Model, observation_names: List[str] | str,
                  sol: int = 1) -> dict:
    """Check whether a model is consistent with the selected observations."""
    if sol not in (1, 2, 3, 4):
        raise ValueError("sol must be one of: 1, 2, 3, 4")

    # Keep API defaults focused on speed unless the caller requests otherwise.
    config.solutions = sol # default 1st solution for API context
    config.format = 'j' # default JSON format for API context

    if not observation_names:
        raise ValueError("At least one observation name must be provided")
    if isinstance(observation_names, str):
        observation_names = [observation_names]
    observation_set = _subset_observations(observation_names)

    inconsistencies, optimization = check_consistency(model, observation_set)
    global _LAST_USED_OBSERVATION_NAMES, _LAST_INCONSISTENCIES, _LAST_OPTIMIZATION
    _LAST_USED_OBSERVATION_NAMES = observation_names
    _LAST_INCONSISTENCIES = inconsistencies
    _LAST_OPTIMIZATION = optimization
    return json.loads(consistency_to_str(inconsistencies, optimization))


def repair(model: Model, obs_names: List[str] | str | None = None) -> Tuple[List[Model], dict]:
    """Computes all possible repair solutions from the previous is_consistent()
    call, applies the repairs, and returns the repaired model(s)."""
    global _LAST_USED_OBSERVATION_NAMES, _LAST_INCONSISTENCIES, _LAST_OPTIMIZATION
    if not obs_names: # default behavior. user called is_consistent() before
        if not _LAST_USED_OBSERVATION_NAMES or not _LAST_INCONSISTENCIES or _LAST_OPTIMIZATION is None:
            raise ValueError("is_consistent() method must be run before")
        if _LAST_OPTIMIZATION == 0:
            return [], {}
        observation_set = _subset_observations(_LAST_USED_OBSERVATION_NAMES)
    else: # user called repair() directly with explicit observation names
        if isinstance(obs_names, str):
            obs_names = [obs_names]
        _LAST_USED_OBSERVATION_NAMES = obs_names
        observation_set = _subset_observations(_LAST_USED_OBSERVATION_NAMES)
        _LAST_INCONSISTENCIES, _LAST_OPTIMIZATION = check_consistency(model, observation_set)
        if _LAST_OPTIMIZATION == 0:
            return [], {}

    config.task = 'r'
    config.format = 'j'
    repairs, s = model_revision(model, observation_set, _LAST_INCONSISTENCIES, _LAST_OPTIMIZATION)


    repaired_models: list[Model] = []
    for repair_solution in repairs:
        nodes_with_repairs = []
        for node_id in sorted(repair_solution.inconsistent_nodes.keys()):
            i_node = repair_solution.inconsistent_nodes[node_id]
            if i_node.repair_sets:
                nodes_with_repairs.append([(node_id, rs) for rs in i_node.repair_sets])

        if not nodes_with_repairs:
            continue

        for combination in itertools.product(*nodes_with_repairs):
            node_repair_map = dict(combination)
            repaired_model = copy.deepcopy(model)
            _apply_repair_in_place(repaired_model, repair_solution, node_repair_map)
            repaired_models.append(repaired_model)

    return repaired_models, json.loads(s)


def model_to_file(model: Model, filepath: os.PathLike[str] | str) -> None:
    """Write a model to disk."""
    path = Path(filepath)
    # Ensure the parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    # Remove the file if it already exists to avoid issues with overwriting
    path.unlink(missing_ok=True)
    # write the model to file
    parser = get_parser(str(path))
    parser.write(model, str(path))
