"""
This module contains the Updater class, which serves as an abstract base class
for applying update rules based on different update types. It provides utility
methods for consistency checks and loading appropriate update logic based on
the configuration.
"""

import sys
from abc import ABC, abstractmethod
from typing import List, Tuple, TYPE_CHECKING, Optional, Sequence
import clingo
import os
from pymodrev.network.model import Model
from pymodrev.network.function import Function
from pymodrev.network.inconsistency_solution import InconsistencySolution
from pymodrev.configuration import config
from pymodrev.parsers.asp_utils import asp_unquote
from pymodrev.network.solution_stream import SolutionStream

if TYPE_CHECKING:
    from pymodrev.network.observation_set import ObservationSet
    from pymodrev.repair.constraints import ProfileRows

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
    def constraint_rows(
            labeling: InconsistencySolution,
            node_id: str,
            profile: str) -> Optional['ProfileRows']:
        """
        Returns the rows (network state -> value of ``node_id`` right after the
        update) this updater imposes on a node for the given profile, so that
        candidate functions can be evaluated with bit-parallel operations (see
        ``pymodrev.repair.constraints``).

        Updaters that do not implement it return None, and the legacy
        ``*_with_profile`` methods are used instead.
        """
        return None

    # ------------------------------------------------------------------ #
    # Consistency checking (ASP)
    # ------------------------------------------------------------------ #
    @staticmethod
    def check_consistency(
            network: Model,
            observation_set: 'ObservationSet',
            lazy: bool = False,
            consistency_only: Optional[bool] = None) -> Tuple[Sequence[InconsistencySolution], int]:
        """
        Loads the base rules, the update rules of every observation and the
        model/observation facts, solves the (optimisation) problem with clingo
        and returns the optimal inconsistency solutions together with the
        number of nodes that need to be repaired (0 = consistent, -1 = no
        solution).

        When ``lazy`` is True the returned sequence pulls solutions from the
        solver on demand (the first one is always computed, to know the
        optimum), so callers that only need the first few solutions do not pay
        for enumerating all of them.

        With ``consistency_only`` (default: when the task is to only check
        consistency) the solutions are not meant to be repaired afterwards, so
        only one solution per distinct (repaired nodes, inconsistent profiles)
        is produced for reachability observations.

        Reachability observations (reachasync / reachsync) are solved in two
        phases, see ``_solve_reach``.
        """
        if consistency_only is None:
            consistency_only = config.task == 'c'
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
                generator = Updater._solve_reach(network, observation_set, logger,
                                                 consistency_only)
            else:
                generator = Updater._solve_plain(network, observation_set, logger,
                                                 consistency_only)
            stream = SolutionStream(generator)
            optimization = stream.optimization
            if not lazy:
                stream.drain()
        except Exception as e:
            print(f'Failed to check consistency: {e}')
            sys.exit(-1)
        return (stream if lazy else list(stream)), optimization

    # clingo options. Core-guided optimisation (usc) is dramatically faster
    # than the default branch-and-bound on the "how many nodes must be
    # repaired" objective, in particular on reachability problems with long
    # horizons, where proving that fewer repairs are impossible is the
    # expensive part.
    _CLINGO_FAST = ['--opt-mode=optN', '--opt-strategy=usc', '--configuration=frumpy']
    _CLINGO_DEFAULT = ['--opt-mode=optN']

    @staticmethod
    def _clingo_args(*extra: str) -> List[str]:
        base = Updater._CLINGO_FAST if config.fast_asp else Updater._CLINGO_DEFAULT
        return list(base) + list(extra)

    @staticmethod
    def _build_control(
            network: Model,
            observation_set: 'ObservationSet',
            logger,
            args: List[str],
            extra_program: str = '') -> clingo.Control:
        """Creates and grounds a clingo control for the given observations."""
        ctl = clingo.Control(args, logger, 20)

        base_lp = os.path.join(os.path.dirname(__file__), '..', 'asp_rules', 'base.lp')
        ctl.load(base_lp)

        for updater in observation_set.updaters:
            updater.apply_update_rules(ctl, updater)

        # Generate ASP facts from the internal Model representation
        ctl.add("base", [], network.to_asp_facts())
        for obs in observation_set.observations:
            ctl.add("base", [], obs.to_asp_facts(network.dimension))
        if extra_program:
            ctl.add("base", [], extra_program)

        ctl.ground([('base', [])])
        return ctl

    @staticmethod
    def _solve_plain(network, observation_set, logger, consistency_only=False):
        """
        Generator of the optimal solutions of a problem without reachability
        observations (every optimal model is a solution).
        """
        if consistency_only:
            # only "which nodes, in which profiles" matters: do not enumerate
            # the (possibly many) completions of partial observations
            ctl = Updater._build_control(
                network, observation_set, logger,
                Updater._clingo_args('--project'),
                "#project r_gen/1. #project r_part/1. "
                "#project topologicalerror/1. #project inc/2. #project incT/3.")
        else:
            ctl = Updater._build_control(network, observation_set, logger,
                                         Updater._clingo_args())
        with ctl.solve(yield_=True) as handle:
            for model in handle:
                if model.optimality_proven:
                    solution, count = Updater.parse_cc_model(model)
                    yield solution, count
                    # consistent (nothing to repair) or only the first
                    # solution was asked: no need to enumerate the rest
                    if count == 0 or config.solutions == 1:
                        break

    # Atoms that identify "which nodes are repaired, and how"
    _REPAIR_ATOMS = ('r_gen', 'r_part', 'topologicalerror')

    @staticmethod
    def _solve_reach(network, observation_set, logger, consistency_only=False):
        """
        Generator of the optimal solutions of a problem with reachability
        observations.

        The reachability horizon is not part of the question the user asks
        ("can the model reach this state?"), but it is what blows up both the
        proof of optimality and the enumeration of optimal models: every
        interleaving of every path length up to the horizon is a different
        model. Therefore:

        * phase A finds the optimal number of nodes to repair, over the whole
          horizon (2*|nodes|), projecting on the repaired nodes, so every
          optimal *set of repaired nodes* is produced exactly once. This is
          also all that is needed to check consistency.
        * phase B (repair tasks only), for each optimal set of repaired nodes,
          enumerates the *shortest* witness paths. The repair search that
          follows only needs the observed transitions, and shorter paths
          impose fewer (and more meaningful) constraints on the functions.
          With ``config.reach_witnesses == 'all'`` every path within the
          horizon is enumerated instead (exponentially many).
        """
        project = ("#project r_gen/1. #project r_part/1. "
                   "#project topologicalerror/1.")
        if consistency_only:
            # distinct inconsistent profiles are part of the answer
            project += " #project inc/2."
        ctl = Updater._build_control(
            network, observation_set, logger,
            Updater._clingo_args('--project'), project)

        node_sets = []
        with ctl.solve(yield_=True) as handle:
            for model in handle:
                if not model.optimality_proven:
                    continue
                solution, count = Updater.parse_cc_model(model)
                if consistency_only or count == 0:
                    yield solution, count
                    continue
                node_sets.append(frozenset(
                    atom for atom in model.symbols(shown=True)
                    if atom.name in Updater._REPAIR_ATOMS))
                if config.solutions == 1:
                    break
        if consistency_only or not node_sets:
            return

        mode = config.reach_witnesses
        if mode == 'all':
            minimize_time = ''
        else:
            minimize_time = '#minimize{T@0,P : finalStateTime(P,T)}.'
        ctl = Updater._build_control(
            network, observation_set, logger, Updater._clingo_args(),
            minimize_time)
        # 'mixed': after the shortest witnesses of a node set, a few
        # arbitrary longer ones (the best repair depends on the witness and
        # is not always found on the shortest one)
        ctl_extra = None
        repair_atoms = [
            atom.symbol for atom in ctl.symbolic_atoms
            if atom.symbol.name in Updater._REPAIR_ATOMS]
        for node_set in node_sets:
            assumptions = [(symbol, symbol in node_set) for symbol in repair_atoms]
            produced = 0
            with ctl.solve(assumptions=assumptions, yield_=True) as handle:
                for model in handle:
                    if not model.optimality_proven:
                        continue
                    yield Updater.parse_cc_model(model)
                    produced += 1
                    if config.solutions == 1 or (
                            config.max_witnesses and produced >= config.max_witnesses):
                        break
            if config.solutions == 1:
                break
            if mode == 'mixed' and config.extra_witnesses > 0:
                if ctl_extra is None:
                    ctl_extra = Updater._build_control(
                        network, observation_set, logger,
                        Updater._clingo_args(), '')
                extra = 0
                with ctl_extra.solve(assumptions=assumptions, yield_=True) as handle:
                    for model in handle:
                        if not model.optimality_proven:
                            continue
                        yield Updater.parse_cc_model(model)
                        extra += 1
                        if extra >= config.extra_witnesses:
                            break

    @staticmethod
    def _symbol_name(symbol: clingo.Symbol) -> str:
        """Identifier of a (possibly quoted) symbol, without the quotes."""
        if symbol.type == clingo.SymbolType.String:
            return symbol.string
        return asp_unquote(str(symbol))

    @staticmethod
    def parse_cc_model(model: clingo.Model) -> Tuple[InconsistencySolution, int]:
        """
        Parses a clingo model to extract inconsistency information.
        """
        inconsistency = InconsistencySolution()
        count = 0
        name_of = Updater._symbol_name
        for atom in model.symbols(shown=True):
            name = atom.name
            args = atom.arguments
            if name == 'vlabel':
                if len(args) > 3:
                    inconsistency.add_v_label(name_of(args[0]),
                                              name_of(args[2]),
                                              args[3].number,
                                              args[1].number)
                else:
                    inconsistency.add_v_label(name_of(args[0]),
                                              name_of(args[1]),
                                              args[2].number, 0)
                continue
            if name == 'r_gen':
                inconsistency.add_generalization(name_of(args[0]))
                continue
            if name == 'r_part':
                inconsistency.add_particularization(name_of(args[0]))
                continue
            if name == 'repair':
                count += 1
                continue
            if name == 'update':
                inconsistency.add_update(args[1].number,
                                         name_of(args[0]),
                                         name_of(args[2]))
                continue
            if name == 'topologicalerror':
                inconsistency.add_topological_error(name_of(args[0]))
                continue
            if name == 'inc':
                inconsistency.add_inconsistent_profile(
                    name_of(args[0]),
                    name_of(args[1]))
                continue
            if name == 'incT':
                inconsistency.add_inconsistent_profile(
                    name_of(args[0]),
                    name_of(args[2]))
                inconsistency.add_inconsistent_profile(
                    name_of(args[1]),
                    name_of(args[2]))
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

