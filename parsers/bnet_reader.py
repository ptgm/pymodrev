"""
BNet reader that parses arbitrary boolean expressions (with &, |, !, parentheses)
and (abusively) converts them into monotone non-degenerate boolean functions via
Quine-McCluskey minimisation.

Pipeline per expression:
  1. Tokenise + recursive-descent parse → AST
  2. Collect variables from AST
  3. Build truth table by evaluating AST over all 2^n assignments
  4. Quine-McCluskey: find all prime implicants, select minimal cover
  5. Convert to monotone non-degenerate form:
     - Variables absent from every implicant are degenerate → drop
     - Variables appearing both positive and negated → force positive (sign=1)
  6. Populate Network (nodes, edges, Function.regulators_by_term)
"""

import logging
from typing import List, Dict, Tuple, Set, Optional
from itertools import combinations

from network.network import Network
from parsers.network_reader import NetworkReader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------

class _ASTNode:
    """Base class for AST nodes."""
    pass


class _Var(_ASTNode):
    __slots__ = ('name',)

    def __init__(self, name: str):
        self.name = name

    def eval(self, env: Dict[str, bool]) -> bool:
        return env[self.name]

    def variables(self) -> Set[str]:
        return {self.name}


class _Not(_ASTNode):
    __slots__ = ('child',)

    def __init__(self, child: _ASTNode):
        self.child = child

    def eval(self, env: Dict[str, bool]) -> bool:
        return not self.child.eval(env)

    def variables(self) -> Set[str]:
        return self.child.variables()


class _BinOp(_ASTNode):
    __slots__ = ('op', 'left', 'right')

    def __init__(self, op: str, left: _ASTNode, right: _ASTNode):
        self.op = op
        self.left = left
        self.right = right

    def eval(self, env: Dict[str, bool]) -> bool:
        if self.op == '&':
            return self.left.eval(env) and self.right.eval(env)
        else:  # '|'
            return self.left.eval(env) or self.right.eval(env)

    def variables(self) -> Set[str]:
        return self.left.variables() | self.right.variables()


class _Const(_ASTNode):
    __slots__ = ('value',)

    def __init__(self, value: bool):
        self.value = value

    def eval(self, env: Dict[str, bool]) -> bool:
        return self.value

    def variables(self) -> Set[str]:
        return set()


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_TOKEN_LPAREN = 'LPAREN'
_TOKEN_RPAREN = 'RPAREN'
_TOKEN_NOT = 'NOT'
_TOKEN_AND = 'AND'
_TOKEN_OR = 'OR'
_TOKEN_VAR = 'VAR'
_TOKEN_CONST = 'CONST'
_TOKEN_EOF = 'EOF'


def _tokenise(expr: str) -> List[Tuple[str, str]]:
    """
    Tokenise a boolean expression string.
    Returns list of (token_type, value) tuples.
    """
    tokens = []
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch in (' ', '\t'):
            i += 1
            continue
        if ch == '(':
            tokens.append((_TOKEN_LPAREN, '('))
            i += 1
        elif ch == ')':
            tokens.append((_TOKEN_RPAREN, ')'))
            i += 1
        elif ch == '!':
            tokens.append((_TOKEN_NOT, '!'))
            i += 1
        elif ch == '&':
            tokens.append((_TOKEN_AND, '&'))
            i += 1
        elif ch == '|':
            tokens.append((_TOKEN_OR, '|'))
            i += 1
        else:
            # Variable name or constant (0 / 1)
            start = i
            while i < len(expr) and expr[i] not in ('(', ')', '!', '&', '|',
                                                      ' ', '\t'):
                i += 1
            name = expr[start:i]
            if name in ('0', '1'):
                tokens.append((_TOKEN_CONST, name))
            else:
                tokens.append((_TOKEN_VAR, name))
    tokens.append((_TOKEN_EOF, ''))
    return tokens


# ---------------------------------------------------------------------------
# Recursive-descent parser
#   Grammar (precedence low→high):
#     expr   := term (('|') term)*
#     term   := factor (('&') factor)*
#     factor := '!' factor | '(' expr ')' | VAR | CONST
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, tokens: List[Tuple[str, str]]):
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> Tuple[str, str]:
        return self._tokens[self._pos]

    def _consume(self, expected_type: Optional[str] = None) -> Tuple[str, str]:
        tok = self._tokens[self._pos]
        if expected_type is not None and tok[0] != expected_type:
            raise ValueError(
                f"Expected {expected_type} but got {tok[0]} ('{tok[1]}')"
            )
        self._pos += 1
        return tok

    def parse(self) -> _ASTNode:
        node = self._expr()
        if self._peek()[0] != _TOKEN_EOF:
            raise ValueError(
                f"Unexpected token after expression: {self._peek()}"
            )
        return node

    def _expr(self) -> _ASTNode:
        """expr := term ('|' term)*"""
        node = self._term()
        while self._peek()[0] == _TOKEN_OR:
            self._consume()
            right = self._term()
            node = _BinOp('|', node, right)
        return node

    def _term(self) -> _ASTNode:
        """term := factor ('&' factor)*"""
        node = self._factor()
        while self._peek()[0] == _TOKEN_AND:
            self._consume()
            right = self._factor()
            node = _BinOp('&', node, right)
        return node

    def _factor(self) -> _ASTNode:
        """factor := '!' factor | '(' expr ')' | VAR | CONST"""
        tok_type, tok_val = self._peek()

        if tok_type == _TOKEN_NOT:
            self._consume()
            child = self._factor()
            return _Not(child)

        if tok_type == _TOKEN_LPAREN:
            self._consume()
            node = self._expr()
            self._consume(_TOKEN_RPAREN)
            return node

        if tok_type == _TOKEN_VAR:
            self._consume()
            return _Var(tok_val)

        if tok_type == _TOKEN_CONST:
            self._consume()
            return _Const(tok_val == '1')

        raise ValueError(f"Unexpected token: {tok_type} ('{tok_val}')")


# ---------------------------------------------------------------------------
# Truth-table construction
# ---------------------------------------------------------------------------

def _build_truth_table(
    ast: _ASTNode, variables: List[str]
) -> Tuple[List[int], List[int]]:
    """
    Evaluate the AST over all 2^n assignments.

    Returns:
        on_set:   list of minterm indices where f=1
        dc_set:   always empty (no don't-cares for fully specified functions)
    """
    n = len(variables)
    on_set: List[int] = []
    for i in range(1 << n):
        env = {}
        for bit_pos, var in enumerate(variables):
            # MSB = first variable
            env[var] = bool((i >> (n - 1 - bit_pos)) & 1)
        if ast.eval(env):
            on_set.append(i)
    return on_set, []


# ---------------------------------------------------------------------------
# Quine–McCluskey minimisation
# ---------------------------------------------------------------------------

# An implicant is stored as a tuple (value, mask) where both are n-bit ints.
#   value: the literal pattern (1=true, 0=false for non-masked bits)
#   mask:  bits that are "don't care" in this implicant (1 = don't care)
# An implicant covers minterm m iff  (m & ~mask) == (value & ~mask).

Implicant = Tuple[int, int]  # (value, mask)


def _count_ones(x: int) -> int:
    return bin(x).count('1')


def _quine_mccluskey(
    n: int, on_set: List[int], dc_set: List[int]
) -> List[Implicant]:
    """
    Full Quine-McCluskey: find prime implicants then select minimal cover.

    Args:
        n:       number of variables
        on_set:  minterm indices where f=1
        dc_set:  don't-care minterm indices

    Returns:
        List of implicants (value, mask) forming a minimal cover of on_set.
    """
    if not on_set:
        return []

    all_minterms = set(on_set) | set(dc_set)

    # --- Step 1: find all prime implicants via iterated combining ----------

    # current set of implicants, keyed by number-of-ones in (value & ~mask)
    implicants: Set[Implicant] = {(m, 0) for m in all_minterms}
    prime_implicants: Set[Implicant] = set()

    while implicants:
        # Group by number of ones in value (ignoring masked bits)
        groups: Dict[int, Set[Implicant]] = {}
        for val, mask in implicants:
            ones = _count_ones(val & ~mask)
            groups.setdefault(ones, set()).add((val, mask))

        used: Set[Implicant] = set()
        new_implicants: Set[Implicant] = set()

        sorted_keys = sorted(groups.keys())
        for idx in range(len(sorted_keys) - 1):
            k = sorted_keys[idx]
            k1 = sorted_keys[idx + 1]
            if k1 != k + 1:
                continue
            for v1, m1 in groups[k]:
                for v2, m2 in groups[k1]:
                    if m1 != m2:
                        continue
                    diff = v1 ^ v2
                    # They must differ in exactly one non-masked bit
                    if _count_ones(diff) == 1 and (diff & m1) == 0:
                        merged = (v1 & ~diff, m1 | diff)
                        new_implicants.add(merged)
                        used.add((v1, m1))
                        used.add((v2, m2))

        # Implicants not used in any merge are prime
        prime_implicants |= (implicants - used)
        implicants = new_implicants

    # --- Step 2: select minimal cover of on_set ----------------------------

    return _select_minimal_cover(n, on_set, prime_implicants)


def _implicant_covers(imp: Implicant, minterm: int) -> bool:
    """Check whether an implicant covers a given minterm."""
    val, mask = imp
    return (minterm & ~mask) == (val & ~mask)


def _select_minimal_cover(
    n: int, on_set: List[int], primes: Set[Implicant]
) -> List[Implicant]:
    """
    Greedy minimal-cover selection with essential prime implicant extraction.
    """
    # Build coverage map: minterm → set of prime implicants that cover it
    coverage: Dict[int, Set[Implicant]] = {
        m: set() for m in on_set
    }
    for imp in primes:
        for m in on_set:
            if _implicant_covers(imp, m):
                coverage[m].add(imp)

    selected: List[Implicant] = []
    remaining = set(on_set)

    # Extract essential prime implicants (minterms covered by exactly one PI)
    changed = True
    while changed:
        changed = False
        for m in list(remaining):
            covering = coverage[m] & set(primes)
            if len(covering) == 1:
                essential = next(iter(covering))
                if essential not in selected:
                    selected.append(essential)
                    # Remove all minterms covered by this essential PI
                    covered = {
                        mt for mt in remaining
                        if _implicant_covers(essential, mt)
                    }
                    remaining -= covered
                    changed = True

    # Greedy cover for remaining minterms
    while remaining:
        # Pick the PI that covers the most remaining minterms
        best_imp = None
        best_count = -1
        for imp in primes:
            if imp in selected:
                continue
            count = sum(1 for m in remaining if _implicant_covers(imp, m))
            if count > best_count:
                best_count = count
                best_imp = imp
        if best_imp is None or best_count == 0:
            break
        selected.append(best_imp)
        remaining -= {m for m in remaining if _implicant_covers(best_imp, m)}

    return selected


# ---------------------------------------------------------------------------
# Implicant → regulator info conversion
# ---------------------------------------------------------------------------

def _implicant_to_literals(
    imp: Implicant, variables: List[str]
) -> List[Tuple[str, int]]:
    """
    Convert an implicant (value, mask) to a list of (variable_name, sign)
    pairs where sign is 1 (positive) or 0 (negated).
    Masked-out variables are omitted (they are don't-cares).
    """
    val, mask = imp
    n = len(variables)
    literals: List[Tuple[str, int]] = []
    for bit_pos, var in enumerate(variables):
        bit = 1 << (n - 1 - bit_pos)
        if mask & bit:
            # Don't care — variable not relevant for this implicant
            continue
        sign = 1 if (val & bit) else 0
        literals.append((var, sign))
    return literals


# ---------------------------------------------------------------------------
# Main reader
# ---------------------------------------------------------------------------

class BnetReader(NetworkReader):
    """
    Reads .bnet files and converts each boolean expression into a monotone
    non-degenerate form using Quine-McCluskey minimisation.

    Monotone conversion rules:
      • Variables that disappear during minimisation are degenerate → removed.
      • Variables that appear with opposing signs across implicants are forced
        to positive (sign=1).
    """

    HEADER_TOKENS = {'targets', 'factors'}

    def read(self, network: Network, filepath: str) -> int:
        """
        Parse a .bnet file and populate the provided Network object.

        Returns:
            1 on success, -1 on warnings, -2 on fatal error.
        """
        result = 1

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                bnet_content = f.read()
        except IOError as exc:
            raise ValueError(f"ERROR!\tCannot open file {filepath}") from exc

        for count_line, raw_line in enumerate(bnet_content.splitlines(),
                                              start=1):
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
                self._add_positive_autoregulation(
                    network, target_node, target
                )
                continue

            if not expr:
                logger.warning(
                    f'WARN!\tEmpty expression for target "{target}" on '
                    f'line {count_line}: {raw_line}'
                )
                result = -1
                continue

            # Parse, minimise, and populate
            parse_result = self._parse_and_minimise(
                network, target_node, target, expr, count_line
            )
            if parse_result < result:
                result = parse_result
            if result == -2:
                return result

        return result

    # -----------------------------------------------------------------------
    # Core pipeline
    # -----------------------------------------------------------------------

    def _parse_and_minimise(
        self, network: Network, target_node, target: str,
        expr: str, line_num: int
    ) -> int:
        """
        Full pipeline: parse → truth table → QMC → monotone → populate.
        """
        # 1. Parse
        try:
            tokens = _tokenise(expr)
            ast = _Parser(tokens).parse()
        except ValueError as exc:
            logger.warning(
                f'WARN!\tFailed to parse expression for "{target}" on '
                f'line {line_num}: {exc}'
            )
            return -1

        # 2. Collect variables (sorted for deterministic bit ordering)
        variables = sorted(ast.variables())

        if not variables:
            # Expression is a constant (tautology or contradiction)
            try:
                val = ast.eval({})
            except Exception:
                val = False
            if val:
                logger.info(f'Line {line_num}: target "{target}" evaluates to constant 1.')
            else:
                logger.info(f'Line {line_num}: target "{target}" evaluates to constant 0.')
            self._add_positive_autoregulation(
                network, target_node, target
            )
            return 1

        # 3. Truth table
        on_set, dc_set = _build_truth_table(ast, variables)

        if not on_set:
            # Function is identically 0
            logger.info(
                f'Line {line_num}: target "{target}" is identically 0 '
                f'after evaluation.'
            )
            self._add_positive_autoregulation(
                network, target_node, target
            )
            return 1

        if len(on_set) == (1 << len(variables)):
            # Function is identically 1 (tautology)
            logger.info(
                f'Line {line_num}: target "{target}" is identically 1 '
                f'(tautology) after evaluation.'
            )
            self._add_positive_autoregulation(
                network, target_node, target
            )
            return 1

        # 4. Quine-McCluskey minimisation
        n = len(variables)
        implicants = _quine_mccluskey(n, on_set, dc_set)

        if not implicants:
            logger.warning(
                f'WARN!\tQMC produced no implicants for "{target}" on '
                f'line {line_num}.'
            )
            return -1

        # 5. Determine per-variable sign and which variables survive
        var_signs = self._determine_monotone_signs(implicants, variables)

        # 6. Populate network
        self._populate_network(
            network, target_node, target, implicants, variables, var_signs
        )

        return 1

    # -----------------------------------------------------------------------
    # Monotone sign determination
    # -----------------------------------------------------------------------

    @staticmethod
    def _determine_monotone_signs(
        implicants: List[Implicant], variables: List[str]
    ) -> Dict[str, int]:
        """
        For each variable, decide its sign in the monotone function.

        Rules:
          - If a variable appears only positive → sign=1
          - If a variable appears only negative → sign=0
          - If a variable appears with **both** signs → sign=1 (forced positive)
          - If a variable never appears (all implicants mask it) → it is
            degenerate and excluded from the result dict.

        Returns:
            dict mapping variable_name → sign (only for non-degenerate vars).
        """
        # Track which signs each variable takes across all implicants
        seen_signs: Dict[str, Set[int]] = {}

        for imp in implicants:
            for var, sign in _implicant_to_literals(imp, variables):
                seen_signs.setdefault(var, set()).add(sign)

        result: Dict[str, int] = {}
        for var in variables:
            if var not in seen_signs:
                # Degenerate — variable masked out in every implicant
                continue
            signs = seen_signs[var]
            if signs == {0}:
                result[var] = 0
            else:
                # Either {1} or {0,1}: force positive
                result[var] = 1

        return result

    # -----------------------------------------------------------------------
    # Network population
    # -----------------------------------------------------------------------

    @staticmethod
    def _populate_network(
        network: Network, target_node, target: str,
        implicants: List[Implicant], variables: List[str],
        var_signs: Dict[str, int]
    ) -> None:
        """
        Add edges and function terms for the target node based on the
        minimised, monotone implicants.
        """
        # Add edges for each surviving variable
        for var_name, sign in var_signs.items():
            reg_node = network.add_node(var_name)
            network.add_edge(reg_node, target_node, sign)

        # Populate function terms
        for term_id, imp in enumerate(implicants, start=1):
            for var, _original_sign in _implicant_to_literals(imp, variables):
                if var in var_signs:
                    target_node.function.add_regulator_to_term(term_id, var)

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------

    @staticmethod
    def _add_positive_autoregulation(
        network: Network, target_node, target: str
    ) -> None:
        """
        Add a positive self-loop for a constant function: the target node
        becomes its own regulator with sign=1 and a single term.
        """
        reg_node = network.add_node(target)
        network.add_edge(reg_node, target_node, 1)
        target_node.function.add_regulator_to_term(1, target)

    @staticmethod
    def _is_header_line(line: str) -> bool:
        """Detect the optional bnet header line: 'targets, factors'."""
        parts = [p.strip().lower() for p in line.split(',')]
        return set(parts) == BnetReader.HEADER_TOKENS
