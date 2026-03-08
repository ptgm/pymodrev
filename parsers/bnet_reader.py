import logging
from network.network import Network
from parsers.network_reader import NetworkReader

logger = logging.getLogger(__name__)


class BnetReader(NetworkReader):
    """
    Reads Boolean Network (.bnet) models into a Network object.

    The bnet format defines one Boolean function per line:
        target, boolean_expression

    Operators: & (AND), | (OR), ! (NOT)
    The expression is parsed as a disjunctive normal form (DNF):
        term1 | term2 | ...   where each term is   lit1 & lit2 & ...
    """

    HEADER_TOKENS = {'targets', 'factors'}

    def read(self, network: Network, filepath: str) -> int:
        """
        Parses a .bnet file and populates the provided Network object.

        Returns:
            1 on success, -1 on warnings/partial parse, -2 on fatal error.
        """
        result = 1

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                bnet_content = f.read()
        except IOError as exc:
            raise ValueError(f"ERROR!\tCannot open file {filepath}") from exc

        for count_line, raw_line in enumerate(bnet_content.splitlines(), start=1):
            # Strip whitespace and skip empty lines
            line = raw_line.strip()
            if not line:
                continue

            # Skip comment lines
            if line.startswith('#'):
                continue

            # Skip header line ("targets, factors")
            if self._is_header_line(line):
                continue

            # Split on first comma: target, expression
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

            # Add the target node
            target_node = network.add_node(target)

            # Handle constant expressions (0 or 1): node with no regulators
            if expr in ('0', '1'):
                logger.info(
                    f'Line {count_line}: target "{target}" has constant '
                    f'value {expr}, no edges added.'
                )
                target_node.is_fixed = True
                continue

            if not expr:
                logger.warning(
                    f'WARN!\tEmpty expression for target "{target}" on '
                    f'line {count_line}: {raw_line}'
                )
                result = -1
                continue

            # Parse the boolean expression into DNF terms
            parse_result = self._parse_expression(
                network, target_node, target, expr, count_line
            )
            if parse_result < result:
                result = parse_result
            if result == -2:
                return result

        return result

    def _parse_expression(
        self, network: Network, target_node, target: str,
        expr: str, line_num: int
    ) -> int:
        """
        Parse a boolean expression in DNF form (terms separated by |,
        literals within a term separated by &) and populate the network.

        Returns 1 on success, -1 on warning, -2 on fatal error.
        """
        result = 1

        # Split into OR-terms
        or_terms = expr.split('|')

        for term_id, term_str in enumerate(or_terms, start=1):
            # Split into AND-literals
            literals = term_str.split('&')

            for lit_str in literals:
                lit = lit_str.strip()

                if not lit:
                    logger.warning(
                        f'WARN!\tEmpty literal in expression for target '
                        f'"{target}" on line {line_num}'
                    )
                    result = -1
                    continue

                # Detect negation
                negated = False
                if lit.startswith('!'):
                    negated = True
                    lit = lit[1:].strip()

                if not lit:
                    logger.warning(
                        f'WARN!\tEmpty variable after negation for target '
                        f'"{target}" on line {line_num}'
                    )
                    result = -1
                    continue

                regulator_name = lit
                sign = 0 if negated else 1

                # Add regulator node and edge
                regulator_node = network.add_node(regulator_name)
                network.add_edge(regulator_node, target_node, sign)

                # Register the regulator in the target's function
                target_node.function.add_regulator_to_term(
                    term_id, regulator_name
                )

        return result

    @staticmethod
    def _is_header_line(line: str) -> bool:
        """
        Detect the optional bnet header line: "targets, factors"
        """
        parts = [p.strip().lower() for p in line.split(',')]
        return set(parts) == BnetReader.HEADER_TOKENS
