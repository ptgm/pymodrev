"""
Differential tests: the bit-parallel evaluation of candidate functions
(pymodrev.repair.constraints) must agree with the legacy per-updater walk for
every update scheme, on every candidate function visited by the Hasse search.
"""

from collections import deque
from pathlib import Path

import pytest

from pymodrev.configuration import config
from pymodrev.network.function import Function
from pymodrev.network.observation_set import ObservationSet
from pymodrev.parsers.parser_factory import get_parser
from pymodrev.parsers.parser_observation import get_observation_parser
from pymodrev.network.model import Model
from pymodrev.repair.consistency import (
    check_consistency,
    is_func_consistent_with_label,
    n_func_inconsistent_with_label,
)
from pymodrev.updaters.factory import get_updater

ROOT = Path(__file__).parent.parent
EX = ROOT / "examples"

# (model, [(observation file, updater)])
CASES = [
    ("toy/00/model.bnet", [("toy/00/sync.csv", "sync")]),
    ("boolean_cell_cycle/03/model.bnet", [("boolean_cell_cycle/03/steady.csv", "steady")]),
    ("boolean_cell_cycle/05/model.bnet", [("boolean_cell_cycle/05/async.csv", "async")]),
    ("boolean_cell_cycle/08/model.bnet", [("boolean_cell_cycle/08/sync.csv", "sync")]),
    ("boolean_cell_cycle/10/model.lp", [("boolean_cell_cycle/10/async.lp", "async"),
                                        ("boolean_cell_cycle/10/sync.lp", "sync")]),
    ("fissionYeastDavidich2008/02/model.bnet", [("fissionYeastDavidich2008/02/async.csv", "async"),
                                                ("fissionYeastDavidich2008/02/steady.csv", "steady")]),
    ("fissionYeastDavidich2008/04/model.bnet", [("fissionYeastDavidich2008/04/notsteady.csv", "notsteady")]),
    ("toy/01/model.bnet", [("toy/01/reachasync_02.csv", "reachasync")]),
    ("toy/02/model.bnet", [("toy/02/reachsync_02.csv", "reachsync")]),
    ("../hsc.zginml", [("../hsc_preDiff_2_pLymph_reach.xlsx", "reachasync")]),
    ("../hsc.zginml", [("../hsc_iHSC_2_pLymph_reach.xlsx", "reachasync")]),
]


def _load(model_path, observations):
    network = Model()
    get_parser(str(EX / model_path)).read(network, str(EX / model_path))
    obs_set = ObservationSet()
    for obs_path, updater_name in observations:
        updater = get_updater(updater_name)
        obs_set.add_observation(
            get_observation_parser(str(EX / obs_path)).read(str(EX / obs_path), updater))
    return network, obs_set


def _candidates(node, limit=150):
    """A few functions around the original one (both directions)."""
    original = node.function
    out = [original]
    if original.get_n_regulators() < 2:
        return out
    for generalize in (True, False):
        queue = deque([original])
        seen = {original}
        while queue and len(out) < limit * (1 if generalize else 2):
            current = queue.popleft()
            for cand in current.get_replacements(generalize):
                if cand not in seen:
                    seen.add(cand)
                    queue.append(cand)
                    out.append(cand)
    return out


@pytest.mark.parametrize("model_path,observations", CASES,
                         ids=[c[0] + "|" + "+".join(o[1] for o in c[1]) for c in CASES])
def test_fast_evaluation_matches_legacy(model_path, observations):
    old_solutions, old_format = config.solutions, config.format
    config.solutions = 3
    try:
        network, obs_set = _load(model_path, observations)
        solutions, optimization = check_consistency(network, obs_set)
        if optimization <= 0:
            pytest.skip("consistent model: nothing to compare")
        checked = 0
        for solution in list(solutions)[:20]:
            for node_id in network.nodes:
                node = network.nodes[node_id]
                for cand in _candidates(node):
                    config.fast_consistency = True
                    fast_n = n_func_inconsistent_with_label(network, obs_set, solution, cand)
                    fast_is = is_func_consistent_with_label(network, obs_set, solution, cand)
                    config.fast_consistency = False
                    slow_n = n_func_inconsistent_with_label(network, obs_set, solution, cand)
                    slow_is = is_func_consistent_with_label(network, obs_set, solution, cand)
                    assert fast_n == slow_n, (node_id, cand.print_function(network=network))
                    assert fast_is == slow_is, (node_id, cand.print_function(network=network))
                    checked += 1
        assert checked > 0
    finally:
        config.fast_consistency = True
        config.solutions, config.format = old_solutions, old_format
