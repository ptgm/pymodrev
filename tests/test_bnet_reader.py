"""
Unit tests for the BnetReader parser.

Tests cover: basic expressions, negation, AND, OR, mixed DNF,
header/comment/blank line handling, and constant expressions.
"""

import os
import tempfile
import pytest
from network.network import Network
from parsers.bnet_reader import BnetReader


@pytest.fixture
def reader():
    return BnetReader()


@pytest.fixture
def network():
    return Network()


def _write_bnet(content: str) -> str:
    """Write content to a temp .bnet file and return the path."""
    fd, path = tempfile.mkstemp(suffix='.bnet')
    with os.fdopen(fd, 'w') as f:
        f.write(content)
    return path


class TestBnetReaderBasic:
    """Basic parsing tests."""

    def test_identity(self, reader, network):
        """A, A  →  node A with self-loop, sign=1, one term with itself."""
        path = _write_bnet("A, A\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            assert 'A' in network.nodes
            # Edge A→A with sign 1
            edge = network.get_edge('A', 'A')
            assert edge.sign == 1
            # Function: 1 term with regulator A
            func = network.get_node('A').function
            assert func.regulators_by_term == {1: ['A']}
        finally:
            os.unlink(path)

    def test_negation(self, reader, network):
        """B, !A  →  nodes A, B; edge A→B sign=0; one term."""
        path = _write_bnet("B, !A\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            assert 'A' in network.nodes
            assert 'B' in network.nodes
            edge = network.get_edge('A', 'B')
            assert edge.sign == 0
            func = network.get_node('B').function
            assert func.regulators_by_term == {1: ['A']}
        finally:
            os.unlink(path)

    def test_and_expression(self, reader, network):
        """D, A & B  →  one term with regulators A and B."""
        path = _write_bnet("D, A & B\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            assert set(network.nodes.keys()) == {'A', 'B', 'D'}
            edge_a = network.get_edge('A', 'D')
            edge_b = network.get_edge('B', 'D')
            assert edge_a.sign == 1
            assert edge_b.sign == 1
            func = network.get_node('D').function
            assert func.regulators_by_term == {1: ['A', 'B']}
        finally:
            os.unlink(path)

    def test_or_expression(self, reader, network):
        """E, A | B  →  two terms, each with one regulator."""
        path = _write_bnet("E, A | B\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            func = network.get_node('E').function
            assert func.regulators_by_term == {1: ['A'], 2: ['B']}
        finally:
            os.unlink(path)

    def test_mixed_dnf(self, reader, network):
        """F, !A & B | A & !B  →  two terms (XOR-like)."""
        path = _write_bnet("F, !A & B | A & !B\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            func = network.get_node('F').function
            assert func.regulators_by_term == {1: ['A', 'B'], 2: ['A', 'B']}
            assert set(func.regulators) == {'A', 'B'}
        finally:
            os.unlink(path)


class TestBnetReaderEdgeCases:
    """Edge cases: headers, comments, blanks, constants."""

    def test_header_skipped(self, reader, network):
        """Header line 'targets, factors' should be skipped."""
        content = "targets, factors\nA, A\n"
        path = _write_bnet(content)
        try:
            result = reader.read(network, path)
            assert result == 1
            assert 'A' in network.nodes
            assert 'targets' not in network.nodes
        finally:
            os.unlink(path)

    def test_comment_skipped(self, reader, network):
        """Lines starting with # should be skipped."""
        content = "# this is a comment\nA, A\n"
        path = _write_bnet(content)
        try:
            result = reader.read(network, path)
            assert result == 1
            assert len(network.nodes) == 1
        finally:
            os.unlink(path)

    def test_blank_lines_skipped(self, reader, network):
        """Blank lines should be skipped."""
        content = "\n\nA, A\n\nB, !A\n\n"
        path = _write_bnet(content)
        try:
            result = reader.read(network, path)
            assert result == 1
            assert set(network.nodes.keys()) == {'A', 'B'}
        finally:
            os.unlink(path)

    def test_constant_zero(self, reader, network):
        """G, 0  →  node G exists but has no edges or function terms."""
        path = _write_bnet("G, 0\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            assert 'G' in network.nodes
            func = network.get_node('G').function
            assert func.regulators_by_term == {}
            assert func.regulators == []
        finally:
            os.unlink(path)

    def test_constant_one(self, reader, network):
        """H, 1  →  node H exists but has no edges or function terms."""
        path = _write_bnet("H, 1\n")
        try:
            result = reader.read(network, path)
            assert result == 1
            assert 'H' in network.nodes
            func = network.get_node('H').function
            assert func.regulators_by_term == {}
        finally:
            os.unlink(path)

