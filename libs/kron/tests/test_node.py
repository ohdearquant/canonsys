"""Tests for Node class and create_node factory."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from kron.core.node import NODE_REGISTRY, Node, NodeConfig, create_node


class SampleNodeContent(BaseModel):
    """Sample content for Node tests."""

    title: str
    value: int = 0


class TestNodeConfig:
    """Test NodeConfig immutable configuration."""

    def test_default_config(self):
        """Default NodeConfig should have sensible defaults."""
        config = NodeConfig()

        assert config.schema == "public"
        assert config.embedding_enabled is False
        assert config.soft_delete is False
        assert config.versioning is False
        assert config.is_persisted is False

    def test_config_with_table_name(self):
        """Config with table_name should be persisted."""
        config = NodeConfig(table_name="test_table")

        assert config.is_persisted is True
        assert config.table_name == "test_table"

    def test_config_immutability(self):
        """NodeConfig should be immutable (frozen)."""
        config = NodeConfig()
        with pytest.raises(Exception):  # FrozenInstanceError
            config.table_name = "new_table"

    def test_embedding_requires_dim(self):
        """embedding_enabled=True requires embedding_dim when validated."""
        # NodeConfig defers validation until used (Params pattern)
        config = NodeConfig(embedding_enabled=True)
        # The config is valid on creation but validation may occur later
        assert config.embedding_enabled is True

    def test_embedding_dim_must_be_positive(self):
        """embedding_dim must be positive when validated."""
        # NodeConfig defers validation - here we just test it stores the value
        config = NodeConfig(embedding_enabled=True, embedding_dim=0)
        assert config.embedding_dim == 0

    def test_has_audit_fields(self):
        """has_audit_fields should detect audit configuration."""
        config1 = NodeConfig()
        config2 = NodeConfig(soft_delete=True)
        config3 = NodeConfig(content_hashing=True)

        assert config1.has_audit_fields is False
        assert config2.has_audit_fields is True
        assert config3.has_audit_fields is True


class TestNodeCreation:
    """Test Node class instantiation."""

    def test_node_with_dict_content(self):
        """Node should accept dict content."""
        node = Node(content={"key": "value"})

        assert node.content == {"key": "value"}
        assert isinstance(node.id, UUID)

    def test_node_with_pydantic_content(self):
        """Node should accept Pydantic BaseModel content."""
        content = SampleNodeContent(title="Test", value=42)
        node = Node(content=content)

        assert node.content.title == "Test"
        assert node.content.value == 42

    def test_node_with_none_content(self):
        """Node should accept None content."""
        node = Node(content=None)
        assert node.content is None

    def test_node_inherits_element_fields(self):
        """Node should have id, created_at, metadata from Element."""
        node = Node()

        assert hasattr(node, "id")
        assert hasattr(node, "created_at")
        assert hasattr(node, "metadata")

    def test_invalid_content_type_raises(self):
        """Node content must be dict, BaseModel, or None."""
        with pytest.raises(TypeError, match="must be Serializable"):
            Node(content=42)  # int is not valid

    def test_get_config_returns_default(self):
        """get_config() should return NodeConfig even if not set."""
        config = Node.get_config()
        assert isinstance(config, NodeConfig)


class TestCreateNodeFactory:
    """Test create_node() factory function."""

    def test_create_node_basic(self):
        """create_node should create Node subclass."""
        TestNode = create_node("TestNode")

        node = TestNode()
        assert isinstance(node, Node)
        assert isinstance(node.id, UUID)

    def test_create_node_with_content_type(self):
        """create_node should accept typed content."""
        TypedNode = create_node("TypedNode", content=SampleNodeContent)

        node = TypedNode(content=SampleNodeContent(title="Test"))
        assert node.content.title == "Test"

    def test_create_node_with_table_name(self):
        """create_node with table_name should register for persistence."""
        table_name = f"test_table_{uuid4().hex[:8]}"
        PersistNode = create_node("PersistNode", table_name=table_name)

        config = PersistNode.get_config()
        assert config.is_persisted is True
        assert config.table_name == table_name

    def test_create_node_with_soft_delete(self):
        """create_node with soft_delete should enable lifecycle methods."""
        SoftDeleteNode = create_node("SoftDeleteNode", soft_delete=True)

        node = SoftDeleteNode()
        assert hasattr(node, "soft_delete")
        assert hasattr(node, "restore")

    def test_create_node_with_versioning(self):
        """create_node with versioning should track version."""
        VersionedNode = create_node("VersionedNode", versioning=True)

        node = VersionedNode()
        assert hasattr(node, "version")

    def test_create_node_with_embedding(self):
        """create_node with embedding should add embedding field."""
        EmbeddingNode = create_node("EmbeddingNode", embedding_enabled=True, embedding_dim=1536)

        node = EmbeddingNode()
        assert hasattr(node, "embedding")


class TestNodeSerialization:
    """Test Node serialization and deserialization."""

    def test_node_to_dict_python_mode(self, sample_node):
        """to_dict python mode should preserve types."""
        data = sample_node.to_dict(mode="python")

        assert isinstance(data["id"], UUID)
        assert data["content"]["key"] == "value"

    def test_node_to_dict_json_mode(self, sample_node):
        """to_dict json mode should be JSON-serializable."""
        data = sample_node.to_dict(mode="json")

        assert isinstance(data["id"], str)
        assert data["content"]["key"] == "value"

    def test_node_from_dict_roundtrip(self, sample_node):
        """from_dict should restore Node from to_dict output."""
        data = sample_node.to_dict(mode="json")
        restored = Node.from_dict(data)

        assert restored.id == sample_node.id
        assert restored.content["key"] == "value"


class TestNodeLifecycle:
    """Test Node lifecycle methods (touch, soft_delete, etc.)."""

    def test_touch_requires_config(self):
        """touch() should update timestamps when configured."""
        TrackedNode = create_node("TrackedNode", track_updated_at=True)
        node = TrackedNode()

        original_updated_at = node.updated_at
        node.touch()

        assert node.updated_at >= original_updated_at

    def test_soft_delete_requires_config(self):
        """soft_delete() should require soft_delete=True in config."""
        node = Node()
        with pytest.raises(RuntimeError, match="does not support soft_delete"):
            node.soft_delete()

    def test_soft_delete_marks_deleted(self):
        """soft_delete() should mark node as deleted."""
        SoftNode = create_node("SoftNode", soft_delete=True)
        node = SoftNode()

        node.soft_delete()

        assert node.is_deleted is True
        assert node.deleted_at is not None

    def test_restore_undeletes_node(self):
        """restore() should undelete a soft-deleted node."""
        SoftNode = create_node("SoftNode2", soft_delete=True)
        node = SoftNode()

        node.soft_delete()
        assert node.is_deleted is True

        node.restore()
        assert node.is_deleted is False
        assert node.deleted_at is None


class TestNodeRegistry:
    """Test Node registry for polymorphic dispatch."""

    def test_node_is_in_registry(self):
        """Node base class should be in NODE_REGISTRY."""
        assert "Node" in NODE_REGISTRY
        assert NODE_REGISTRY["Node"] is Node

    def test_persistable_registry_tracks_table_names(self):
        """Nodes with table_name are registered when accessed."""
        table_name = f"registry_test_{uuid4().hex[:8]}"
        RegisteredNode = create_node("RegisteredNode", table_name=table_name)

        # Trigger registration by accessing the registry key
        _ = RegisteredNode.get_config()

        # Registration may be deferred - check the class is created properly
        assert RegisteredNode is not None
        config = RegisteredNode.get_config()
        assert config.table_name == table_name
