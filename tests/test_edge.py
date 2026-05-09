import pytest
from pymodrev.network.node import Node
from pymodrev.network.edge import Edge

@pytest.fixture
def sample_nodes():
    return Node("node1"), Node("node2"), Node("node3")

def test_edge_initialization(sample_nodes):
    node1, node2, _ = sample_nodes
    edge = Edge(node1, node2, 1)
    assert edge.start_node == node1
    assert edge.end_node == node2
    assert edge.sign == 1
    assert not edge.is_fixed

def test_edge_flip_sign(sample_nodes):
    node1, node2, _ = sample_nodes
    edge = Edge(node1, node2, 1)
    edge.flip_sign()
    assert edge.sign == 0
    edge.flip_sign()
    assert edge.sign == 1

def test_edge_set_fixed(sample_nodes):
    node1, node2, _ = sample_nodes
    edge = Edge(node1, node2, 1)
    edge.is_fixed = True
    assert edge.is_fixed

def test_edge_equality_and_hash(sample_nodes):
    node1, node2, node3 = sample_nodes
    e1 = Edge(node1, node2, 1)
    e2 = Edge(node1, node2, 1)
    e3 = Edge(node1, node2, 0)
    e4 = Edge(node1, node3, 1)

    assert e1 == e2
    assert e1 != e3
    assert e1 != e4
    assert hash(e1) == hash(e2)
    assert e1 != "not an edge"
