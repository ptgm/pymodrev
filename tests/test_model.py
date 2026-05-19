import pytest
from pymodrev.network.model import Model
from pymodrev.network.exceptions import EdgeNotFoundError

@pytest.fixture
def model():
    return Model()

def test_get_node(model):
    node = model.add_node('node_1')
    retrieved_node = model.get_node('node_1')
    assert retrieved_node == node
    assert model.get_node('non_existing_node') is None

def test_get_nodes(model):
    model.add_node('node_1')
    model.add_node('node_2')
    nodes = model.nodes
    assert len(nodes) == 2
    assert 'node_1' in nodes
    assert 'node_2' in nodes

def test_add_edge(model):
    node_1 = model.add_node('node_1')
    node_2 = model.add_node('node_2')
    model.add_edge(node_1, node_2, 1)

    edge = model.get_edge('node_1', 'node_2')
    assert edge.start_node == node_1
    assert edge.end_node == node_2
    assert 'node_1' in model.regulators['node_2']

def test_get_edge_not_found(model):
    model.add_node('node_1')
    with pytest.raises(EdgeNotFoundError):
        model.get_edge('node_1', 'node_2')

def test_remove_edge(model):
    node_1 = model.add_node('node_1')
    node_2 = model.add_node('node_2')
    model.add_edge(node_1, node_2, 1)
    model.remove_edge(node_1, node_2)

    with pytest.raises(EdgeNotFoundError):
        model.get_edge('node_1', 'node_2')
    assert 'node_2' not in model.regulators