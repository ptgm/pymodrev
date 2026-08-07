"""
This module contains the Updater class, which serves as an abstract base class
for applying update rules based on different update types. It provides utility
methods for consistency checks and loading appropriate update logic based on
the configuration.
"""

import sys
from abc import ABC, abstractmethod
from typing import List, Tuple, TYPE_CHECKING, Optional
import clingo
import os
from pymodrev.network.model import Model
from pymodrev.network.function import Function
from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.configuration import config
from pymodrev.parsers.asp_utils import asp_unquote

if TYPE_CHECKING:
    from pymodrev.network.observation_set import ObservationSet

class Updater(ABC):
    """
    The Updater class is the base class for all update-related logic. It
    defines the structure for applying update rules, checking consistency, and
    selecting the correct updater based on the update type. This class should
    be extended to implement specific update types such as synchronous,
    asynchronous, or complete updates.
    """

    @staticmethod
    @abstractmethod
    def get_type() -> str:
        """
        Subclasses must implement this method to return the update type
        (e.g., sync, async, etc.).
        This is used by the user to specify the updater.
        """

    @staticmethod
    @abstractmethod
    def get_name() -> str:
        """
        Subclasses should redifine this method to return a different updater name
        (e.g., reachasync, async, etc.).
        This is used when generating asp facts.
        """

    @staticmethod
    @abstractmethod
    def apply_update_rules(ctl: clingo.Control, updater) -> None:
        """
        Subclasses must implement this method to apply update rules based on
        the update type (e.g., synchronous, asynchronous, etc.).
        """

    @staticmethod
    @abstractmethod
    def is_func_consistent_with_label_with_profile(
            network: Model,
            labeling: InconsistencySolution,
            function: Function,
            profile: str) -> bool:
        """
        Evaluates whether the function's regulatory logic aligns with the
        expected dynamic behavior of the network. This implementation assumes a
        time series (i.e. multiple time points) and does not handle a
        steady-state scenario.
        """

    @staticmethod
    @abstractmethod
    def n_func_inconsistent_with_label_with_profile(
            network: Model,
            labeling: InconsistencySolution,
            function: Function,
            profile: str) -> int:
        """
        Checks the consistency of a function with a specific profile in a given
        labeling. It evaluates the function's clauses over time and returns the
        consistency status (consistent, single inconsistency, or double
        inconsistency) based on the profile.
        """

    @staticmethod
    def check_consistency(network: Model, observation_set: 'ObservationSet') -> Tuple[List[InconsistencySolution], int]:
        """
        This method loads the necessary rules, including base rules and network
        observation files, and applies consistency checks to the network. It
        also handles the logic for checking the optimization based on the
        update type.
        """
        result = []
        optimization = -2
        try:
            def logger(warning_code, message):
                if config.debug:
                    print(warning_code, file=sys.stderr)
                    print(message, file=sys.stderr)

            has_reach = any(
                updater.get_type() in ("reachasync", "reachsync")
                for updater in observation_set.updaters
            )

            if has_reach:
                max_bound = 2 * network.dimension # Heuristic: all nodes change twice in the worst case
                for reach_bound in range(1, max_bound + 1):
                    result, optimization = Updater._solve_with_optional_reach_bound(
                        network,
                        observation_set,
                        logger,
                        reach_bound=reach_bound,
                    )
                    if optimization != -1:
                        break
            else:
                result, optimization = Updater._solve_with_optional_reach_bound(
                    network,
                    observation_set,
                    logger,
                    reach_bound=None,
                )
        except Exception as e:
            print(f'Failed to check consistency: {e}')
            sys.exit(-1)
        return result, optimization

    @staticmethod
    def _solve_with_optional_reach_bound(
            network: Model,
            observation_set: 'ObservationSet',
            logger,
            reach_bound: Optional[int]) -> Tuple[List[InconsistencySolution], int]:
        """
        Solve one consistency instance, optionally fixing reachability to a
        specific bound for reachasync/reachsync observations.
        """
        result: List[InconsistencySolution] = []
        optimization = -1

        ctl = clingo.Control(['--opt-mode=optN'], logger, 20)

        base_lp = os.path.join(os.path.dirname(__file__), '..', 'asp_rules', 'base.lp')
        ctl.load(base_lp)

        for updater in observation_set.updaters:
            updater.apply_update_rules(ctl, updater)

        # Generate ASP facts from the internal Model representation
        asp_facts = network.to_asp_facts()
        ctl.add("base", [], asp_facts)

        for obs in observation_set.observations:
            obs_reach_bound = reach_bound if (
                reach_bound is not None
                and obs.updater is not None
                and obs.updater.get_type() in ("reachasync", "reachsync")
            ) else None
            ctl.add("base", [], obs.to_asp_facts(network.dimension, reach_bound=obs_reach_bound))

        ctl.ground([('base', [])])
        with ctl.solve(yield_=True) as handle:
            if handle.get().satisfiable:
                for model in handle:
                    if model and model.optimality_proven:
                        res, opt = Updater.parse_cc_model(model)
                        result.append(res)
                        optimization = opt
                        if config.solutions == 1:
                            break

        return result, optimization

    @staticmethod
    def parse_cc_model(model: clingo.Model) -> Tuple[InconsistencySolution, int]:
        """
        Parses a clingo model to extract inconsistency information.
        """
        inconsistency = InconsistencySolution()
        count = 0
        for atom in model.symbols(atoms=True):
            name = atom.name
            args = atom.arguments
            if name == 'vlabel':
                if len(args) > 3:
                    inconsistency.add_v_label(asp_unquote(str(args[0])),
                                              asp_unquote(str(args[2])),
                                              int(str(args[3])),
                                              int(str(args[1])))
                else:
                    inconsistency.add_v_label(asp_unquote(str(args[0])),
                                              asp_unquote(str(args[1])),
                                              int(str(args[2])), 0)
                continue
            if name == 'r_gen':
                inconsistency.add_generalization(asp_unquote(str(args[0])))
                continue
            if name == 'r_part':
                inconsistency.add_particularization(asp_unquote(str(args[0])))
                continue
            if name == 'repair':
                count += 1
                continue
            if name == 'update':
                inconsistency.add_update(int(str(args[1])),
                                         asp_unquote(str(args[0])),
                                         asp_unquote(str(args[2])))
                continue
            if name == 'topologicalerror':
                inconsistency.add_topological_error(asp_unquote(str(args[0])))
                continue
            if name == 'inc':
                inconsistency.add_inconsistent_profile(
                    asp_unquote(str(args[0])),
                    asp_unquote(str(args[1])))
                continue
            if name == 'incT':
                inconsistency.add_inconsistent_profile(
                    asp_unquote(str(args[0])),
                    asp_unquote(str(args[2])))
                inconsistency.add_inconsistent_profile(
                    asp_unquote(str(args[1])),
                    asp_unquote(str(args[2])))
                continue
        return inconsistency, count

    @staticmethod
    def is_clause_satisfiable(
            clause,
            network: Model,
            time_map,
            function: Function) -> bool:
        """
        Evaluates whether a clause is satisfiable given the network and current time mapping.
        """
        regulators = function.bitarray_to_regulators(clause)
        for var in regulators:
            edge = network.get_edge(var, function.node_id)
            if edge is not None:
                # The clause is unsatisfied if the edge sign contradicts the value in time_map.
                if (edge.sign > 0) == (time_map[var] == 0):
                    return False
            else:
                print(f"WARN: Missing edge from {var} to {function.node_id}")
                return False
        return True

