import logging
from network.network import Network
from parsers.network_reader import NetworkReader

logger = logging.getLogger(__name__)

class ASPReader(NetworkReader):
    """
    Reads Answer Set Programming (.lp) model definitions into a Network object.
    """

    @staticmethod
    def validate_input_name(s: str) -> bool:
        """
        Checks if the input name follows the required ASP naming conventions.
        """
        if s[0] != '"' and not s[0].islower() and not s[0].isdigit():
            return False
        return True

    def read(self, network: Network, filepath: str) -> int:
        """
        Parses an ASP network file and populates the provided Network object.
        """
        result = 1
        try:
            with open(filepath, 'r', encoding="utf-8") as file:
                count_line = 0
                for line in file:
                    count_line += 1
                    line = ''.join(line.split())  # Remove all whitespace
                    if ').' in line:
                        predicates = line.split(')')
                        for i in range(len(predicates) - 1):
                            predicates[i] += ').'
                            if i > 0:
                                predicates[i] = predicates[i][1:]
                            split = predicates[i].split('(')

                            if split[0] == 'vertex':
                                node = split[1].split(')')[0]
                                network.add_node(node)
                                continue

                            elif split[0] == 'edge':
                                split = split[1].split(')')
                                split = split[0].split(',')

                                if len(split) != 3:
                                    logger.warning(f'WARN!\tEdge not recognized in line {str(count_line)}: {predicates[i]}')
                                    result = -1
                                    continue

                                if not self.validate_input_name(split[0]) or not self.validate_input_name(split[1]):
                                    logger.warning(f'WARN!\tInvalid node argument in line {str(count_line)}: {predicates[i]}')
                                    logger.warning('\t\tNode names must start with a lower case letter, a digit, or be surrounded by quotation marks.')
                                    return -2

                                start_id, end_id = split[0], split[1]
                                try:
                                    sign = int(split[2])
                                except ValueError:
                                    logger.warning(f'WARN!\tInvalid edge sign: {split[2]} on line {str(count_line)} in edge {predicates[i]}')
                                    return -2

                                if sign not in [0, 1]:
                                    logger.warning(f'WARN!\tInvalid edge sign on line {str(count_line)} in edge {predicates[i]}')
                                    return -2

                                start_node = network.add_node(start_id)
                                end_node = network.add_node(end_id)
                                network.add_edge(start_node, end_node, sign)
                                continue

                            elif split[0] == 'fixed':
                                split = split[1].split(')')
                                split = split[0].split(',')

                                if len(split) == 1:
                                    # Handle fixed(node)
                                    node_id = split[0]
                                    if not self.validate_input_name(node_id):
                                        logger.warning(f'WARN!\tInvalid node argument in line {count_line}: {predicates[i]}')
                                        return -2
                                    node = network.add_node(node_id)
                                    node.is_fixed = True
                                    continue

                                elif len(split) == 2:
                                    if not self.validate_input_name(split[0]) or not self.validate_input_name(split[1]):
                                        logger.warning(f'WARN!\tInvalid node argument in line {count_line}: {predicates[i]}')
                                        logger.warning('\t\tNodes names must start with a lower case letter, a digit, or be surrounded by quotation marks.')
                                        return -2

                                    start_id, end_id = split[0], split[1]
                                    edge = network.get_edge(start_id, end_id)

                                    if edge is not None:
                                        edge.fixed = True
                                    else:
                                        logger.warning(f'WARN!\tUnrecognized edge on line {count_line}: {predicates[i]} Ignoring...')
                                    continue

                            elif split[0] == 'functionOr':
                                split = split[1].split(')')
                                split = split[0].split(',')

                                if len(split) != 2:
                                    logger.warning(f'WARN!\tfunctionOr not recognized on line {str(count_line)}: {predicates[i]}')
                                    result = -1
                                    continue

                                if not self.validate_input_name(split[0]):
                                    logger.warning(f'WARN!\tInvalid node argument in line {str(count_line)}: {predicates[i]}')
                                    logger.warning('\t\tNodes names must start with a lower case letter, a digit, or be surrounded by quotation marks.')
                                    return -2

                                network.add_node(split[0])

                                if '..' in split[1]:
                                    split = split[1].split('.')
                                    try:
                                        range_limit = int(split[-1])
                                    except ValueError:
                                        logger.warning(f'WARN!\tInvalid range limit: {split[-1]} on line {count_line} in {predicates[i]}. It must be an integer greater than 0.')
                                        return -2
                                    if range_limit < 1:
                                        logger.warning(f'WARN!\tInvalid range limit: {range_limit} on line {count_line} in {predicates[i]}. It must be an integer greater than 0.')
                                        return -2

                                else:
                                    try:
                                        range_limit = int(split[1])
                                        if range_limit < 1:
                                            logger.warning(f'WARN!\tInvalid range limit: {range_limit} on line {count_line} in {predicates[i]}. It must be an integer greater than 0.')
                                            return -2
                                    except ValueError:
                                        logger.warning(f'WARN!\tInvalid functionOr range definition on line {count_line}: {predicates[i]}')
                                        return -2
                                continue

                            elif split[0] == 'functionAnd':
                                split = split[1].split(')')
                                split = split[0].split(',')

                                if len(split) != 3:
                                    logger.warning(f'WARN!\tfunctionAnd not recognized on line {count_line}: {predicates[i]}')
                                    result = -1
                                    continue

                                if not self.validate_input_name(split[0]) or not self.validate_input_name(split[2]):
                                    logger.warning(f'WARN!\tInvalid node argument on line {count_line}: {predicates[i]}')
                                    logger.warning('\t\tNodes names must start with a lower case letter, a digit, or be surrounded by quotation marks.')
                                    return -2

                                node = network.get_node(split[0])
                                if node is None:
                                    logger.warning(f'WARN!\tNode not recognized or not yet defined: {split[0]} on line {count_line} in {predicates[i]}')
                                    result = -1
                                    continue

                                node2 = network.get_node(split[2])
                                if node2 is None:
                                    logger.warning(f'WARN!\tNode not recognized or not yet defined: {split[2]} on line {count_line} in {predicates[i]}')
                                    result = -1
                                    continue

                                try:
                                    clause_id = int(split[1])
                                    if clause_id < 1:
                                        logger.warning(f'WARN!\tInvalid clause Id: {split[1]} on line {count_line} in {predicates[i]}')
                                        result = -1
                                        continue
                                except ValueError:
                                    logger.warning(f'WARN!\tInvalid clause Id: {split[1]} on line {count_line} in {predicates[i]}')
                                    result = -1
                                    continue
                                node.function.add_regulator_to_term(clause_id, split[2])
                                continue
        except IOError as exc:
            raise ValueError('ERROR!\tCannot open file ' + filepath) from exc
        return result
