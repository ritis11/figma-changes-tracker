"""
Unit tests for figma_tracker.tracker module.

Tests cover:
- Node parsing (all node types)
- Snapshot creation and serialization
- Snapshot comparison and change detection
- Edge cases and error handling
"""

import json
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from figma_tracker.tracker import (
    FigmaNode,
    FigmaSnapshot,
    NodeChange,
    ChangeReport,
    FigmaTracker,
    NodeParser,
    ShapeWithTextParser,
    ConnectorParser,
    StickyParser,
    TextParser,
    NODE_PARSERS,
    _truncate_text,
    capture_figma_snapshot,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_figjam_response():
    """Sample FigJam XML-like response for testing."""
    return '''
<section id="123:456" name="Test Section">
    <shape-with-text id="node1" x="100" y="200" width="150" height="80" name="Decision Box">Is this a test?</shape-with-text>
    <shape-with-text id="node2" x="300" y="200" width="150" height="80">Another node</shape-with-text>
    <connector id="conn1" x="150" y="240" connectorStart="node1" connectorStartCap="none" connectorEnd="node2" connectorEndCap="arrow">link</connector>
    <sticky id="sticky1" x="500" y="100" color="yellow" author="test@example.com" width="200" height="200">Important note!</sticky>
    <text id="text1" name="Label Text" x="600" y="300" width="100" height="30"/>
</section>
    '''


@pytest.fixture
def mock_board_config():
    """Mock board configuration."""
    return {
        "name": "Test Board",
        "file_key": "test_file_key",
        "node_id": "test_node_id",
        "url": "https://figma.com/board/test",
        "description": "Test board"
    }


@pytest.fixture
def temp_snapshot_dir(tmp_path):
    """Create a temporary snapshot directory."""
    snapshot_dir = tmp_path / "snapshots" / "test-board"
    snapshot_dir.mkdir(parents=True)
    return snapshot_dir


# =============================================================================
# FigmaNode Tests
# =============================================================================

class TestFigmaNode:
    """Tests for FigmaNode dataclass."""
    
    def test_create_node_minimal(self):
        """Test creating a node with minimal required fields."""
        node = FigmaNode(id="test1", node_type="shape-with-text")
        
        assert node.id == "test1"
        assert node.node_type == "shape-with-text"
        assert node.name == ""
        assert node.x == 0
        assert node.y == 0
    
    def test_create_node_full(self):
        """Test creating a node with all fields."""
        node = FigmaNode(
            id="test1",
            node_type="sticky",
            name="Test Note",
            x=100.5,
            y=200.5,
            width=150,
            height=100,
            text="Hello World",
            color="yellow",
            author="user@example.com"
        )
        
        assert node.id == "test1"
        assert node.text == "Hello World"
        assert node.color == "yellow"
    
    def test_to_dict_excludes_empty_fields(self):
        """Test that to_dict excludes empty fields."""
        node = FigmaNode(id="test1", node_type="text", text="Hello")
        result = node.to_dict()
        
        assert "id" in result
        assert "node_type" in result
        assert "text" in result
        assert "name" not in result  # Empty string excluded
        assert "x" not in result     # Zero excluded
    
    def test_to_dict_includes_zero_when_nonzero(self):
        """Test that to_dict includes non-zero numeric values."""
        node = FigmaNode(id="test1", node_type="shape", x=100)
        result = node.to_dict()
        
        assert result["x"] == 100


# =============================================================================
# FigmaSnapshot Tests
# =============================================================================

class TestFigmaSnapshot:
    """Tests for FigmaSnapshot dataclass."""
    
    def test_create_snapshot(self):
        """Test creating a snapshot."""
        snapshot = FigmaSnapshot(
            board_name="test-board",
            file_key="abc123",
            node_id="456:789",
            timestamp="2025-01-31_120000"
        )
        
        assert snapshot.board_name == "test-board"
        assert snapshot.nodes == []
    
    def test_to_dict(self):
        """Test snapshot serialization to dict."""
        node = FigmaNode(id="n1", node_type="text", text="Test")
        snapshot = FigmaSnapshot(
            board_name="test-board",
            file_key="abc123",
            node_id="456:789",
            timestamp="2025-01-31_120000",
            section_name="Test Section",
            nodes=[node]
        )
        
        result = snapshot.to_dict()
        
        assert result["board_name"] == "test-board"
        assert result["node_count"] == 1
        assert len(result["nodes"]) == 1
    
    def test_from_dict(self):
        """Test creating snapshot from dict."""
        data = {
            "board_name": "test-board",
            "file_key": "abc123",
            "node_id": "456:789",
            "timestamp": "2025-01-31_120000",
            "section_name": "Test Section",
            "nodes": [
                {"id": "n1", "node_type": "text", "text": "Hello"}
            ]
        }
        
        snapshot = FigmaSnapshot.from_dict(data)
        
        assert snapshot.board_name == "test-board"
        assert len(snapshot.nodes) == 1
        assert snapshot.nodes[0].text == "Hello"


# =============================================================================
# Node Parser Tests
# =============================================================================

class TestNodeParsers:
    """Tests for node parser classes."""
    
    def test_shape_with_text_parser(self):
        """Test parsing shape-with-text elements."""
        parser = ShapeWithTextParser()
        content = '<shape-with-text id="s1" x="100" y="200" width="150" height="80" name="Box">Content here</shape-with-text>'
        
        nodes = parser.parse(content)
        
        assert len(nodes) == 1
        assert nodes[0].id == "s1"
        assert nodes[0].node_type == "shape-with-text"
        assert nodes[0].x == 100
        assert nodes[0].y == 200
        assert nodes[0].name == "Box"
        assert nodes[0].text == "Content here"
    
    def test_shape_with_text_parser_missing_attributes(self):
        """Test parsing shape-with-text with missing optional attributes."""
        parser = ShapeWithTextParser()
        content = '<shape-with-text id="s1">Just text</shape-with-text>'
        
        nodes = parser.parse(content)
        
        assert len(nodes) == 1
        assert nodes[0].x == 0
        assert nodes[0].text == "Just text"
    
    def test_connector_parser(self):
        """Test parsing connector elements."""
        parser = ConnectorParser()
        content = '<connector id="c1" x="50" y="50" connectorStart="n1" connectorStartCap="none" connectorEnd="n2" connectorEndCap="arrow">label</connector>'
        
        nodes = parser.parse(content)
        
        assert len(nodes) == 1
        assert nodes[0].node_type == "connector"
        assert nodes[0].connector_start == "n1"
        assert nodes[0].connector_end == "n2"
        assert nodes[0].connector_end_cap == "arrow"
    
    def test_sticky_parser(self):
        """Test parsing sticky note elements."""
        parser = StickyParser()
        content = '<sticky id="st1" x="0" y="0" color="yellow" author="user@test.com" width="200" height="200">Note content</sticky>'
        
        nodes = parser.parse(content)
        
        assert len(nodes) == 1
        assert nodes[0].node_type == "sticky"
        assert nodes[0].color == "yellow"
        assert nodes[0].author == "user@test.com"
        assert nodes[0].text == "Note content"
    
    def test_text_parser(self):
        """Test parsing text elements."""
        parser = TextParser()
        content = '<text id="t1" name="Header Text" x="10" y="20" width="100" height="30"/>'
        
        nodes = parser.parse(content)
        
        assert len(nodes) == 1
        assert nodes[0].node_type == "text"
        assert nodes[0].name == "Header Text"
        assert nodes[0].text == "Header Text"  # Name used as text
    
    def test_safe_float_valid(self):
        """Test safe_float with valid values."""
        assert NodeParser.safe_float("100") == 100.0
        assert NodeParser.safe_float("100.5") == 100.5
    
    def test_safe_float_invalid(self):
        """Test safe_float with invalid values."""
        assert NodeParser.safe_float(None) == 0
        assert NodeParser.safe_float("") == 0
        assert NodeParser.safe_float("invalid") == 0
    
    def test_safe_float_custom_default(self):
        """Test safe_float with custom default."""
        assert NodeParser.safe_float(None, default=-1) == -1
    
    def test_multiple_nodes_same_type(self):
        """Test parsing multiple nodes of the same type."""
        parser = ShapeWithTextParser()
        content = '''
            <shape-with-text id="s1">First</shape-with-text>
            <shape-with-text id="s2">Second</shape-with-text>
            <shape-with-text id="s3">Third</shape-with-text>
        '''
        
        nodes = parser.parse(content)
        
        assert len(nodes) == 3
        assert [n.id for n in nodes] == ["s1", "s2", "s3"]


# =============================================================================
# NodeChange and ChangeReport Tests
# =============================================================================

class TestNodeChange:
    """Tests for NodeChange dataclass."""
    
    def test_added_node_str(self):
        """Test string representation of added node."""
        change = NodeChange(
            change_type="added",
            node_id="n1",
            node_type="sticky",
            new_text="New note"
        )
        
        result = str(change)
        
        assert "+ n1" in result
        assert "[sticky]" in result
        assert "New note" in result
    
    def test_removed_node_str(self):
        """Test string representation of removed node."""
        change = NodeChange(
            change_type="removed",
            node_id="n1",
            node_type="text",
            old_text="Old text"
        )
        
        result = str(change)
        
        assert "- n1" in result
        assert "[text]" in result
    
    def test_modified_node_str(self):
        """Test string representation of modified node."""
        change = NodeChange(
            change_type="modified",
            node_id="n1",
            node_type="shape-with-text",
            details="text changed"
        )
        
        result = str(change)
        
        assert "~ n1" in result
        assert "text changed" in result
    
    def test_long_text_truncation(self):
        """Test that long text is truncated in string output."""
        long_text = "A" * 100
        change = NodeChange(
            change_type="added",
            node_id="n1",
            node_type="sticky",
            new_text=long_text
        )
        
        result = str(change)
        
        assert "..." in result
        assert len(result) < len(long_text) + 50


class TestChangeReport:
    """Tests for ChangeReport dataclass."""
    
    def test_has_changes_empty(self):
        """Test has_changes returns False when empty."""
        report = ChangeReport(
            board_name="test",
            from_snapshot="t1",
            to_snapshot="t2"
        )
        
        assert not report.has_changes
    
    def test_has_changes_with_added(self):
        """Test has_changes returns True with additions."""
        report = ChangeReport(
            board_name="test",
            from_snapshot="t1",
            to_snapshot="t2",
            added=[NodeChange("added", "n1", "text")]
        )
        
        assert report.has_changes
    
    def test_to_dict(self):
        """Test change report serialization."""
        report = ChangeReport(
            board_name="test",
            from_snapshot="t1",
            to_snapshot="t2",
            added=[NodeChange("added", "n1", "text", new_text="Hi")],
            removed=[NodeChange("removed", "n2", "sticky", old_text="Bye")]
        )
        
        result = report.to_dict()
        
        assert result["summary"]["added"] == 1
        assert result["summary"]["removed"] == 1
        assert result["summary"]["modified"] == 0
        assert result["summary"]["total_changes"] == 2
    
    def test_str_format(self):
        """Test string representation includes all sections."""
        report = ChangeReport(
            board_name="Test Board",
            from_snapshot="2025-01-01",
            to_snapshot="2025-01-02"
        )
        
        result = str(report)
        
        assert "Test Board" in result
        assert "ADDED NODES" in result
        assert "MODIFIED NODES" in result
        assert "REMOVED NODES" in result
        assert "Summary" in result


# =============================================================================
# FigmaTracker Tests
# =============================================================================

class TestFigmaTracker:
    """Tests for FigmaTracker class."""
    
    @pytest.fixture
    def mock_config(self, mock_board_config, temp_snapshot_dir):
        """Create a mock config for testing."""
        with patch('figma_tracker.tracker.config') as mock:
            mock.DEFAULT_FIGMA_BOARD = "test-board"
            mock.get_figma_board_config.return_value = mock_board_config
            mock.get_figma_board_dir.return_value = temp_snapshot_dir
            yield mock
    
    def test_init_with_valid_board(self, mock_config):
        """Test tracker initialization with valid board."""
        tracker = FigmaTracker("test-board")
        
        assert tracker.board_name == "test-board"
        assert tracker.board_config is not None
    
    def test_init_with_invalid_board(self, mock_config):
        """Test tracker initialization with invalid board raises error."""
        mock_config.get_figma_board_config.return_value = None
        
        with pytest.raises(ValueError, match="Unknown board"):
            FigmaTracker("invalid-board")
    
    def test_parse_figjam_response(self, mock_config, sample_figjam_response):
        """Test parsing a complete FigJam response."""
        tracker = FigmaTracker("test-board")
        
        snapshot = tracker.parse_figjam_response(sample_figjam_response)
        
        assert snapshot.board_name == "test-board"
        assert snapshot.section_id == "123:456"
        assert snapshot.section_name == "Test Section"
        assert len(snapshot.nodes) == 5  # 2 shapes + 1 connector + 1 sticky + 1 text
    
    def test_parse_section_info(self, mock_config):
        """Test section info extraction."""
        tracker = FigmaTracker("test-board")
        snapshot = FigmaSnapshot(
            board_name="test",
            file_key="key",
            node_id="id",
            timestamp="now"
        )
        
        content = '<section id="sec-1" name="My Section">content</section>'
        tracker._parse_section_info(content, snapshot)
        
        assert snapshot.section_id == "sec-1"
        assert snapshot.section_name == "My Section"
    
    def test_save_and_load_snapshot(self, mock_config, temp_snapshot_dir, sample_figjam_response):
        """Test saving and loading a snapshot."""
        tracker = FigmaTracker("test-board")
        
        # Parse and save
        snapshot = tracker.parse_figjam_response(sample_figjam_response)
        filepath = tracker.save_snapshot(snapshot)
        
        assert filepath.exists()
        assert filepath.suffix == ".json"
        
        # Load and verify
        loaded = tracker.load_snapshot(snapshot.timestamp)
        
        assert loaded is not None
        assert loaded.board_name == snapshot.board_name
        assert len(loaded.nodes) == len(snapshot.nodes)
    
    def test_list_snapshots(self, mock_config, temp_snapshot_dir):
        """Test listing snapshots."""
        tracker = FigmaTracker("test-board")
        
        # Create index file with test data
        index_data = {
            "board_name": "test-board",
            "snapshots": [
                {"timestamp": "2025-01-31_100000", "filename": "2025-01-31_100000.json", "node_count": 5},
                {"timestamp": "2025-01-30_100000", "filename": "2025-01-30_100000.json", "node_count": 3}
            ]
        }
        index_file = temp_snapshot_dir / "index.json"
        with open(index_file, 'w') as f:
            json.dump(index_data, f)
        
        snapshots = tracker.list_snapshots()
        
        assert len(snapshots) == 2
        assert snapshots[0]["timestamp"] == "2025-01-31_100000"  # Sorted newest first
    
    def test_compare_snapshots_not_enough(self, mock_config, temp_snapshot_dir):
        """Test comparison when not enough snapshots exist."""
        tracker = FigmaTracker("test-board")
        
        report = tracker.compare_snapshots()
        
        assert not report.has_changes
        assert report.from_snapshot == "(none)"
    
    def test_compare_snapshots_added_nodes(self, mock_config, temp_snapshot_dir):
        """Test detecting added nodes."""
        tracker = FigmaTracker("test-board")
        
        # Create two snapshots
        old_snapshot = FigmaSnapshot(
            board_name="test-board",
            file_key="key",
            node_id="id",
            timestamp="2025-01-30_100000",
            nodes=[FigmaNode(id="n1", node_type="text", text="Original")]
        )
        
        new_snapshot = FigmaSnapshot(
            board_name="test-board",
            file_key="key",
            node_id="id",
            timestamp="2025-01-31_100000",
            nodes=[
                FigmaNode(id="n1", node_type="text", text="Original"),
                FigmaNode(id="n2", node_type="sticky", text="New note")
            ]
        )
        
        # Save both snapshots
        tracker.save_snapshot(old_snapshot)
        tracker.save_snapshot(new_snapshot)
        
        report = tracker.compare_snapshots()
        
        assert len(report.added) == 1
        assert report.added[0].node_id == "n2"
    
    def test_compare_snapshots_removed_nodes(self, mock_config, temp_snapshot_dir):
        """Test detecting removed nodes."""
        tracker = FigmaTracker("test-board")
        
        old_snapshot = FigmaSnapshot(
            board_name="test-board",
            file_key="key",
            node_id="id",
            timestamp="2025-01-30_100000",
            nodes=[
                FigmaNode(id="n1", node_type="text", text="Keep"),
                FigmaNode(id="n2", node_type="sticky", text="Remove me")
            ]
        )
        
        new_snapshot = FigmaSnapshot(
            board_name="test-board",
            file_key="key",
            node_id="id",
            timestamp="2025-01-31_100000",
            nodes=[FigmaNode(id="n1", node_type="text", text="Keep")]
        )
        
        tracker.save_snapshot(old_snapshot)
        tracker.save_snapshot(new_snapshot)
        
        report = tracker.compare_snapshots()
        
        assert len(report.removed) == 1
        assert report.removed[0].node_id == "n2"
    
    def test_compare_snapshots_modified_text(self, mock_config, temp_snapshot_dir):
        """Test detecting modified text content."""
        tracker = FigmaTracker("test-board")
        
        old_snapshot = FigmaSnapshot(
            board_name="test-board",
            file_key="key",
            node_id="id",
            timestamp="2025-01-30_100000",
            nodes=[FigmaNode(id="n1", node_type="text", text="Old text")]
        )
        
        new_snapshot = FigmaSnapshot(
            board_name="test-board",
            file_key="key",
            node_id="id",
            timestamp="2025-01-31_100000",
            nodes=[FigmaNode(id="n1", node_type="text", text="New text")]
        )
        
        tracker.save_snapshot(old_snapshot)
        tracker.save_snapshot(new_snapshot)
        
        report = tracker.compare_snapshots()
        
        assert len(report.modified) == 1
        assert report.modified[0].old_text == "Old text"
        assert report.modified[0].new_text == "New text"
    
    def test_compare_ignores_position_changes(self, mock_config, temp_snapshot_dir):
        """Test that position changes are ignored by default."""
        tracker = FigmaTracker("test-board")
        
        old_snapshot = FigmaSnapshot(
            board_name="test-board",
            file_key="key",
            node_id="id",
            timestamp="2025-01-30_100000",
            nodes=[FigmaNode(id="n1", node_type="text", text="Same", x=0, y=0)]
        )
        
        new_snapshot = FigmaSnapshot(
            board_name="test-board",
            file_key="key",
            node_id="id",
            timestamp="2025-01-31_100000",
            nodes=[FigmaNode(id="n1", node_type="text", text="Same", x=100, y=100)]
        )
        
        tracker.save_snapshot(old_snapshot)
        tracker.save_snapshot(new_snapshot)
        
        report = tracker.compare_snapshots(ignore_positions=True)
        
        assert not report.has_changes
    
    def test_compare_detects_position_changes_when_enabled(self, mock_config, temp_snapshot_dir):
        """Test that position changes are detected when enabled."""
        tracker = FigmaTracker("test-board")
        
        old_snapshot = FigmaSnapshot(
            board_name="test-board",
            file_key="key",
            node_id="id",
            timestamp="2025-01-30_100000",
            nodes=[FigmaNode(id="n1", node_type="text", text="Same", x=0, y=0)]
        )
        
        new_snapshot = FigmaSnapshot(
            board_name="test-board",
            file_key="key",
            node_id="id",
            timestamp="2025-01-31_100000",
            nodes=[FigmaNode(id="n1", node_type="text", text="Same", x=100, y=100)]
        )
        
        tracker.save_snapshot(old_snapshot)
        tracker.save_snapshot(new_snapshot)
        
        report = tracker.compare_snapshots(ignore_positions=False)
        
        assert len(report.modified) == 1


# =============================================================================
# Utility Function Tests
# =============================================================================

class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_truncate_text_short(self):
        """Test truncation doesn't affect short text."""
        result = _truncate_text("Short", 10)
        assert result == "Short"
    
    def test_truncate_text_long(self):
        """Test truncation of long text."""
        result = _truncate_text("This is a very long text", 10)
        assert result == "This is a ..."
        assert len(result) == 13  # 10 + 3 for "..."
    
    def test_truncate_text_exact_length(self):
        """Test text exactly at max length."""
        result = _truncate_text("1234567890", 10)
        assert result == "1234567890"


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the tracker module."""
    
    @pytest.fixture
    def mock_config(self, mock_board_config, temp_snapshot_dir):
        """Create a mock config for testing."""
        with patch('figma_tracker.tracker.config') as mock:
            mock.DEFAULT_FIGMA_BOARD = "test-board"
            mock.get_figma_board_config.return_value = mock_board_config
            mock.get_figma_board_dir.return_value = temp_snapshot_dir
            yield mock
    
    def test_full_workflow(self, mock_config, sample_figjam_response, temp_snapshot_dir):
        """Test complete capture -> save -> load -> compare workflow."""
        tracker = FigmaTracker("test-board")
        
        # First capture
        snapshot1 = tracker.parse_figjam_response(sample_figjam_response)
        # Manually set timestamp to ensure difference
        snapshot1.timestamp = "2025-01-30_100000"
        tracker.save_snapshot(snapshot1)
        
        # Modify response and capture again
        modified_response = sample_figjam_response.replace(
            "Is this a test?",
            "Yes, this is a test!"
        )
        
        snapshot2 = tracker.parse_figjam_response(modified_response)
        # Manually set different timestamp
        snapshot2.timestamp = "2025-01-31_100000"
        tracker.save_snapshot(snapshot2)
        
        # Compare
        report = tracker.compare_snapshots()
        
        assert report.has_changes
        assert len(report.modified) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
