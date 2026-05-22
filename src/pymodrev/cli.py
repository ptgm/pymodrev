"""
This script analyzes a given network model to determine its consistency.
If inconsistencies are found, it attempts to compute the minimal set of repair
operations needed to restore consistency.
"""

import argparse
import sys
import os
import logging
import re

from pymodrev.network.model import Model
from pymodrev.network.observation_set import ObservationSet
from pymodrev.parsers.parser_factory import get_parser
from pymodrev.configuration import config
from pymodrev.repair.engine import model_revision
from pymodrev.repair.consistency import check_consistency, consistency_to_str
from pymodrev.repair.repair import apply_repair
from pymodrev.parsers.parser_observation import get_observation_parser
from pymodrev.network.exceptions import EdgeNotFoundError
from pymodrev.updaters.factory import get_updater, is_valid_updater_type

# Configure logger
logger = logging.getLogger(__name__)


def process_arguments(network: Model, observation_set: ObservationSet) -> None:
    """
    Process command-line arguments and configure the model and observation set.
    """
    arg_parser = argparse.ArgumentParser(
        description="""pyModRev - Python tool for model revision of Boolean networks.
Given a model and a set of observations, it determines if the model is consistent.
If not, it computes all the minimum number of repair operations in order to render it consistent.""",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=f"Version: {config.version}"
    )

    arg_parser.add_argument("-m", "--model",
                        required=True, help="Input model file")
    arg_parser.add_argument("-obs", "--observations", nargs='+', action='extend',
                        required=True, metavar=('OBS', 'UPDATER'),
                        help="""List of observation files and updater pairs.
Each observation *must* be followed by its updater type. 
Example: -obs obs1.lp async obs2.lp sync
Or: -obs obs1.lp async -obs obs2.lp sync""")
    arg_parser.add_argument('-t', '--task', choices=['c', 'r', 'm'], required=True,
                        help="""Specify the task to perform (default=r):
    c - check for consistency
    r - get repairs
    m - get repaired models""")
    arg_parser.add_argument("--exhaustive-search", action="store_true",
                        help="Force exhaustive search of function repair operations (default=false)")
    arg_parser.add_argument("-s", "--solutions", type=int, choices=[1,2,3,4], default=3,
                        help="""All solutions are optimal w.r.t. number of nodes needing repairs.
But a solution may be sub-optimal w.r.t. number of repair operations.
    1 - Show only the first ASP optimal solution, which may be 
        sup-optimal in terms of repairs (fastest)
    2 - Show only the first ASP&repairs optimal solution
    3 - Show all optimal solutions (default)
    4 - Show all optimal solutions, including sub-optimal repairs (slowest)
    """)
    arg_parser.add_argument("-f", "--format", type=str, choices=['c', 'j', 'h'], default='h',
                        help="""Specify output format (default=h):
    c - compact format
    j - json format
    h - human-readable format""")
    arg_parser.add_argument("--fixed-nodes", nargs='+', action='extend',
                        help="""List of nodes ids not to repair.
Example: --fixed-nodes A B C"""),
    arg_parser.add_argument("--fixed-edges", nargs='+', action='extend',
                        help="""List of edges ids not to repair.
Example: --fixed-edges A,B C;D E:F"""),
    arg_parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")

    args = arg_parser.parse_args()

    # Apply arguments to config and network
    network.input_file_network = args.model
    config.task = args.task
    config.force_optimum = args.exhaustive_search
    config.solutions = args.solutions
    config.format = args.format
    config.fixed_nodes = args.fixed_nodes
    config.fixed_edges = args.fixed_edges
    config.debug = args.debug

    # Activate debug mode
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s: %(message)s')
    
    obs_args = args.observations
    if len(obs_args) % 2 != 0:
        arg_parser.error("Expected an even number of arguments for -obs (pairs of obs_file and updater_name)")

    for i in range(0, len(obs_args), 2):
        obs_path = obs_args[i]
        updater_name = obs_args[i+1]

        try:
            if not is_valid_updater_type(updater_name):
                raise Exception(f"Updater '{updater_name}' not found in updaters directory")

            updater = get_updater(updater_name)
            obs_parser = get_observation_parser(obs_path)
            observation = obs_parser.read(obs_path, updater)
            observation_set.add_observation(observation)
        except Exception as e:
            arg_parser.error(str(e))

def main():
    network = Model()
    observation_set = ObservationSet()
    process_arguments(network, observation_set)
    
    # Delegate parsing to the correct reader based on file extension
    try:
        parser = get_parser(network.input_file_network)
        parse = parser.read(network, network.input_file_network)
        # Mark nodes and edges as fixed (not to be repaired)
        if config.fixed_nodes:
            for node_id in config.fixed_nodes:
                node = network.get_node(node_id)
                if not node:
                    raise ValueError(f'ERROR: Node {node_id} not found in the network.')
                node.is_fixed = True
        if config.fixed_edges:
            for edge_id in config.fixed_edges:
                nodes = re.split('[,;:]', edge_id)
                if len(nodes) != 2:
                    raise ValueError(f'ERROR: Edge {edge_id} incorrectly defined.')
                network.get_edge(nodes[0], nodes[1]).is_fixed = True
    except (ValueError, EdgeNotFoundError) as e:
        logger.error(str(e))
        sys.exit(1)

    if parse < 1 and not config.ignore_warnings:
        logger.error('Model definition with errors. Check documentation for input definition details.')
        sys.exit(1)

    # Check consistency
    f_inconsistencies, optimization = check_consistency(network, observation_set)
    if config.task == 'c' or optimization == 0:
        print(print_consistency(f_inconsistencies, optimization))
        sys.exit(0)

    # Model revision
    repairs_sols, output = model_revision(
        network, observation_set, f_inconsistencies, optimization)
    if config.task == 'r':
        print(output)
    else:
        import copy
        import itertools

        # 1. Collect all possible model combinations (Cartesian product of repair sets per solution)
        all_models_to_save = []
        for sol in repairs_sols:
            nodes_with_repairs = []
            # Sort node IDs for deterministic output order
            for node_id in sorted(sol.inconsistent_nodes.keys()):
                i_node = sol.inconsistent_nodes[node_id]
                if i_node.repair_sets:
                    node_options = [(node_id, rs) for rs in i_node.repair_sets]
                    nodes_with_repairs.append(node_options)
            
            # Cartesian product of options across all nodes for THIS solution
            for combination in itertools.product(*nodes_with_repairs):
                node_repair_map = dict(combination)
                all_models_to_save.append((sol, node_repair_map))

        # 2. Apply repairs and write files
        total_models = len(all_models_to_save)
        if total_models == 0:
            logger.info("No repaired models to generate.")
        else:
            padding = len(str(total_models))
            prefix, ext = os.path.splitext(network.input_file_network)
            for i, (repair_sol, node_repair_map) in enumerate(all_models_to_save):
                newNetwork = copy.deepcopy(network)
                apply_repair(newNetwork, repair_sol, node_repair_map)
                filename = f"{prefix}_{str(i+1).zfill(padding)}{ext}"
                parser.write(newNetwork, filename)
                print(f"Repaired model: {filename}")

if __name__ == '__main__':
    main()
