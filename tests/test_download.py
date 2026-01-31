"""
Unit tests for figma_tracker.download module.

Tests cover:
- Snapshot directory management
- Finding and listing snapshots
- Filename generation
- Snapshot saving
- Snapshot comparison
- Board URL retrieval
"""

import pytest
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from figma_tracker.download import (
    get_figma_snapshots_dir,
    find_figma_snapshots,
    get_snapshot_filename,
    save_snapshot,
    list_snapshots,
    compare_snapshots,
    get_board_url,
    list_boards,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_figma_dir(tmp_path):
    """Create a temporary Figma snapshots directory."""
    figma_dir = tmp_path / "data" / "raw" / "figma"
    figma_dir.mkdir(parents=True)
    return figma_dir


@pytest.fixture
def mock_config(temp_figma_dir):
    """Mock the config module."""
    with patch('figma_tracker.download.config') as mock:
        mock.RAW_DATA_DIR = temp_figma_dir.parent
        mock.DEFAULT_FIGMA_BOARD = "decision-tree"
        mock.FIGMA_BOARDS = {
            "decision-tree": {
                "name": "Decision Tree",
                "file_key": "abc123",
                "node_id": "456:789",
                "url": "https://figma.com/board/abc123",
                "description": "Test board"
            },
            "other-board": {
                "name": "Other Board",
                "file_key": "xyz789",
                "node_id": "111:222",
                "url": "https://figma.com/board/xyz789"
            }
        }
        yield mock


# =============================================================================
# Directory Management Tests
# =============================================================================

class TestGetFigmaSnapshotsDir:
    """Tests for get_figma_snapshots_dir function."""
    
    def test_creates_directory(self, mock_config, temp_figma_dir):
        """Test that the function creates the directory if needed."""
        # Remove the directory first
        shutil.rmtree(temp_figma_dir, ignore_errors=True)
        
        result = get_figma_snapshots_dir()
        
        assert result.exists()
        assert result.is_dir()
    
    def test_returns_correct_path(self, mock_config, temp_figma_dir):
        """Test that the function returns the correct path."""
        result = get_figma_snapshots_dir()
        
        assert "figma" in str(result)


# =============================================================================
# Snapshot Finding Tests
# =============================================================================

class TestFindFigmaSnapshots:
    """Tests for find_figma_snapshots function."""
    
    def test_finds_png_files(self, mock_config, temp_figma_dir):
        """Test finding PNG snapshot files."""
        # Create test files
        (temp_figma_dir / "2025-01-31_120000_decision-tree.png").touch()
        (temp_figma_dir / "2025-01-30_100000_decision-tree.png").touch()
        
        results = find_figma_snapshots()
        
        assert len(results) == 2
    
    def test_filters_by_board_name(self, mock_config, temp_figma_dir):
        """Test filtering snapshots by board name."""
        (temp_figma_dir / "2025-01-31_120000_decision-tree.png").touch()
        (temp_figma_dir / "2025-01-31_110000_other-board.png").touch()
        
        results = find_figma_snapshots(board_name="decision-tree")
        
        assert len(results) == 1
        assert "decision-tree" in str(results[0][0])
    
    def test_filters_by_age(self, mock_config, temp_figma_dir):
        """Test filtering snapshots by age."""
        recent_file = temp_figma_dir / "recent.png"
        recent_file.touch()
        
        old_file = temp_figma_dir / "old.png"
        old_file.touch()
        # Set old file's mtime to 60 days ago
        import os
        old_mtime = datetime.now().timestamp() - (60 * 24 * 3600)
        os.utime(old_file, (old_mtime, old_mtime))
        
        results = find_figma_snapshots(max_age_days=30)
        
        assert len(results) == 1
    
    def test_empty_directory(self, mock_config, temp_figma_dir):
        """Test with empty directory."""
        results = find_figma_snapshots()
        
        assert len(results) == 0
    
    def test_sorted_newest_first(self, mock_config, temp_figma_dir):
        """Test that results are sorted newest first."""
        import os
        import time
        
        # Create files with different modification times
        file1 = temp_figma_dir / "file1.png"
        file1.touch()
        time.sleep(0.1)
        file2 = temp_figma_dir / "file2.png"
        file2.touch()
        
        results = find_figma_snapshots()
        
        assert len(results) == 2
        assert results[0][0].name == "file2.png"  # Newer file first


# =============================================================================
# Filename Generation Tests
# =============================================================================

class TestGetSnapshotFilename:
    """Tests for get_snapshot_filename function."""
    
    def test_includes_timestamp(self, mock_config):
        """Test that filename includes timestamp."""
        filename = get_snapshot_filename("test-board")
        
        # Should match format: YYYY-MM-DD_HHMMSS_board-name.png
        assert filename.endswith("_test-board.png")
        assert "-" in filename  # Date separators
    
    def test_includes_board_name(self, mock_config):
        """Test that filename includes board name."""
        filename = get_snapshot_filename("my-board")
        
        assert "my-board" in filename
    
    def test_default_board_name(self, mock_config):
        """Test using default board name."""
        filename = get_snapshot_filename()
        
        assert "decision-tree" in filename


# =============================================================================
# Snapshot Saving Tests
# =============================================================================

class TestSaveSnapshot:
    """Tests for save_snapshot function."""
    
    def test_copies_file(self, mock_config, temp_figma_dir, tmp_path):
        """Test saving with copy (keep_source=True)."""
        source = tmp_path / "source.png"
        source.write_bytes(b"test image data")
        
        result = save_snapshot(source, "test-board", keep_source=True)
        
        assert result is not None
        assert result.exists()
        assert source.exists()  # Source still exists
    
    def test_moves_file(self, mock_config, temp_figma_dir, tmp_path):
        """Test saving with move (keep_source=False)."""
        source = tmp_path / "source.png"
        source.write_bytes(b"test image data")
        
        result = save_snapshot(source, "test-board", keep_source=False)
        
        assert result is not None
        assert result.exists()
        assert not source.exists()  # Source removed
    
    def test_handles_missing_source(self, mock_config, temp_figma_dir, tmp_path):
        """Test handling of non-existent source file."""
        source = tmp_path / "nonexistent.png"
        
        result = save_snapshot(source, "test-board")
        
        assert result is None


# =============================================================================
# Snapshot Comparison Tests
# =============================================================================

class TestCompareSnapshots:
    """Tests for compare_snapshots function."""
    
    def test_compares_two_files(self, mock_config, temp_figma_dir):
        """Test comparing two snapshot files."""
        # Create two files with different sizes
        file1 = temp_figma_dir / "2025-01-30_decision-tree.png"
        file1.write_bytes(b"x" * 1000)
        
        file2 = temp_figma_dir / "2025-01-31_decision-tree.png"
        file2.write_bytes(b"x" * 1100)
        
        result = compare_snapshots(file1, file2)
        
        assert result["size1"] == 1000
        assert result["size2"] == 1100
        assert result["size_diff"] == 100
    
    def test_auto_selects_most_recent(self, mock_config, temp_figma_dir):
        """Test automatic selection of most recent snapshots."""
        import time
        
        file1 = temp_figma_dir / "2025-01-30_decision-tree.png"
        file1.write_bytes(b"x" * 1000)
        time.sleep(0.1)
        
        file2 = temp_figma_dir / "2025-01-31_decision-tree.png"
        file2.write_bytes(b"x" * 1000)
        
        result = compare_snapshots()
        
        assert "snapshot1" in result
        assert "snapshot2" in result
    
    def test_not_enough_snapshots(self, mock_config, temp_figma_dir):
        """Test with only one snapshot."""
        (temp_figma_dir / "only_one.png").write_bytes(b"data")
        
        result = compare_snapshots()
        
        assert "error" in result
    
    def test_likely_changed_significant(self, mock_config, temp_figma_dir):
        """Test detection of significant change (>5%)."""
        file1 = temp_figma_dir / "old.png"
        file1.write_bytes(b"x" * 1000)
        
        file2 = temp_figma_dir / "new.png"
        file2.write_bytes(b"x" * 1200)  # 20% increase
        
        result = compare_snapshots(file1, file2)
        
        assert result["likely_changed"] is True
    
    def test_likely_changed_insignificant(self, mock_config, temp_figma_dir):
        """Test detection of insignificant change (<5%)."""
        file1 = temp_figma_dir / "old.png"
        file1.write_bytes(b"x" * 1000)
        
        file2 = temp_figma_dir / "new.png"
        file2.write_bytes(b"x" * 1020)  # 2% increase
        
        result = compare_snapshots(file1, file2)
        
        assert result["likely_changed"] is False


# =============================================================================
# Board URL Tests
# =============================================================================

class TestGetBoardUrl:
    """Tests for get_board_url function."""
    
    def test_gets_valid_board_url(self, mock_config):
        """Test getting URL for valid board."""
        url = get_board_url("decision-tree")
        
        assert url == "https://figma.com/board/abc123"
    
    def test_returns_none_for_invalid_board(self, mock_config):
        """Test getting URL for invalid board."""
        url = get_board_url("nonexistent-board")
        
        assert url is None
    
    def test_default_board(self, mock_config):
        """Test using default board."""
        url = get_board_url()
        
        assert url is not None


# =============================================================================
# List Functions Tests
# =============================================================================

class TestListFunctions:
    """Tests for list output functions."""
    
    def test_list_snapshots_output(self, mock_config, temp_figma_dir, capsys):
        """Test list_snapshots output."""
        (temp_figma_dir / "2025-01-31_test.png").write_bytes(b"x" * 1024)
        
        list_snapshots()
        
        captured = capsys.readouterr()
        assert "Figma Board Snapshots" in captured.out
    
    def test_list_snapshots_empty(self, mock_config, temp_figma_dir, capsys):
        """Test list_snapshots with no files."""
        list_snapshots()
        
        captured = capsys.readouterr()
        assert "No snapshots found" in captured.out
    
    def test_list_boards_output(self, mock_config, capsys):
        """Test list_boards output."""
        list_boards()
        
        captured = capsys.readouterr()
        assert "Decision Tree" in captured.out
        assert "Other Board" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
