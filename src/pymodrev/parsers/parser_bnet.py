"""
BNet parser that delegates boolean expression parsing to the shared
boolean_expression module.
"""

import logging

from pymodrev.network.model import Model
from pymodrev.parsers.network_parser import NetworkParser
from pymodrev.parsers.boolean_expression import (
    parse_and_minimise_expression,
    add_positive_autoregulation
)

logger = logging.getLogger(__name__)


class BnetParser(NetworkParser):
    """
    Reads and writes .bnet files. Converts each boolean expression into a
    monotone non-degenerate form using Quine-McCluskey minimisation (via
    shared parser).
    """

    HEADER_TOKENS = {'targets', 'factors'}

    def read(self, network: Model, filepath: str) -> int:
        """
        Parse a .bnet file and populate the provided Model object.

        Returns:
            1 on success, -1 on warnings, -2 on fatal error.
        """
        result = 1

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                bnet_content = f.read()
        except IOError as exc:
            raise ValueError(f"ERROR!\tCannot open file {filepath}") from exc

        for count_line, raw_line in enumerate(bnet_content.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            if self._is_header_line(line):
                continue

            if ',' not in line:
                logger.warning(
                    f'WARN!\tLine {count_line} has no comma separator, '
                    f'skipping: {raw_line}'
                )
                result = -1
                continue

            target_str, expr_str = line.split(',', 1)
            target = target_str.strip()
            expr = expr_str.strip()

            if not target:
                logger.warning(
                    f'WARN!\tEmpty target name on line {count_line}: '
                    f'{raw_line}'
                )
                result = -1
                continue

            target_node = network.add_node(target)

            # Handle constant expressions
            if expr in ('0', '1'):
                logger.info(
                    f'Line {count_line}: target "{target}" has constant '
                    f'value {expr}, adding positive auto-regulation.'
                )
                add_positive_autoregulation(network, target_node, target)
                continue

            if not expr:
                logger.warning(
                    f'WARN!\tEmpty expression for target "{target}" on '
                    f'line {count_line}: {raw_line}'
                )
                result = -1
                continue

            # Parse, minimise, and populate using shared module
            parse_result = parse_and_minimise_expression(
                network, 
                target_node, 
                target, 
                expr,
                location_info=f"on line {count_line}"
            )
            
            if parse_result < result:
                result = parse_result
            if result == -2:
                return result

        return result

    @staticmethod
    def _is_header_line(line: str) -> bool:
        """Detect the optional bnet header line: 'targets, factors'."""
        parts = [p.strip().lower() for p in line.split(',')]
        return set(parts) == BnetParser.HEADER_TOKENS

    def write(self, network: Model, filename: str) -> None:
        """
        Write the provided Model object to a .bnet file.
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("targets, factors\n")
                # Sort nodes by identifier for deterministic output
                for node_id in sorted(network.nodes.keys()):
                    node = network.nodes[node_id]
                    func = node.function
                    
                    if not func.regulators_by_term:
                        # If no regulators, it might be a constant but 
                        # BnetParser.read maps constants to self-loops.
                        # However, for robustness, we handle empty terms.
                        # Usually, every node in this system has at least 
                        # one term (even if it's just a self-loop).
                        continue
                        
                    terms_str = []
                    # regulators_by_term is {term_id: [reg1, reg2, ...]}
                    # term_id starts from 1
                    for term_id in sorted(func.regulators_by_term.keys()):
                        regulators = func.regulators_by_term[term_id]
                        reg_strs = []
                        for reg in regulators:
                            # Determine sign from the edge in the network
                            try:
                                edge = network.get_edge(reg, node_id)
                                prefix = "!" if edge.sign == 0 else ""
                            except Exception:
                                # Fallback if edge not found (shouldn't happen)
                                prefix = ""
                            reg_strs.append(f"{prefix}{reg}")
                        
                        terms_str.append(" & ".join(reg_strs))
                    
                    expression = " | ".join(terms_str)
                    f.write(f"{node_id}, {expression}\n")
                    
        except IOError as exc:
            raise ValueError(f"ERROR!\tCannot write to file {filename}") from exc
