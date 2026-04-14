"""
This module contains the Updater class, which serves as an abstract base class
for applying update rules based on different update types. It provides utility
methods for consistency checks and loading appropriate update logic based on
the configuration.
"""

import sys
from abc import ABC, abstractmethod
from typing import List, Tuple
import clingo
import os
from pymodrev.network.network import Network
from pymodrev.network.function import Function
from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.configuration import config
from pymodrev.parsers.asp_utils import asp_unquote

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
    def apply_update_rules(ctl: clingo.Control, updater) -> None:
        """
        Subclasses must implement this method to apply update rules based on
        the update type (e.g., synchronous, asynchronous, etc.).
        """

    @staticmethod
    @abstractmethod
    def is_func_consistent_with_label_with_profile(
            network: Network,
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
            network: Network,
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
    def check_consistency(network: Network) -> Tuple[List, int]:
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
            ctl = clingo.Control(['--opt-mode=optN'], logger, 20)

            base_lp = os.path.join(os.path.dirname(__file__), '..', 'asp_rules', 'base.lp')
            ctl.load(base_lp)

            for updater in network.updaters:
                updater.apply_update_rules(ctl, updater)

            # Generate ASP facts from the internal Network representation
            asp_facts = network.to_asp_facts()
            ctl.add("base", [], asp_facts)
            for obs in network.observations:
                ctl.add("base", [], obs.to_asp_facts())
            ctl.ground([('base', [])])
            with ctl.solve(yield_=True) as handle:
                if handle.get().satisfiable:
                    for model in handle:
                        if model and model.optimality_proven:
                            res, opt = Updater.parse_cc_model(model)
                            result.append(res)
                            optimization = opt
                            if config.sol == 1:
                                break
                else:
                    optimization = -1
        except Exception as e:
            print(f'Failed to check consistency: {e}')
            sys.exit(-1)
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
            network: Network,
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

