"""
Unit tests for figma_tracker.capture module.

Tests cover:
- Time ago formatting
- Status display
- Board listing
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from figma_tracker.capture import (
    get_time_ago,
    show_status,
    print_capture_prompt,
    print_status_only,
)


# =============================================================================
# Time Formatting Tests
# =============================================================================

class TestGetTimeAgo:
    """Tests for get_time_ago function."""
    
    def test_just_now(self):
        """Test timestamp from a few seconds ago."""
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d_%H%M%S")
        
        result = get_time_ago(timestamp)
        
        assert result == "just now"
    
    def test_minutes_ago(self):
        """Test timestamp from minutes ago."""
        past = datetime.now() - timedelta(minutes=5)
        timestamp = past.strftime("%Y-%m-%d_%H%M%S")
        
        result = get_time_ago(timestamp)
        
        assert "minute" in result
        assert "5" in result
    
    def test_one_minute_ago(self):
        """Test singular minute."""
        past = datetime.now() - timedelta(minutes=1, seconds=30)
        timestamp = past.strftime("%Y-%m-%d_%H%M%S")
        
        result = get_time_ago(timestamp)
        
        # Should be "1 minute ago" not "1 minutes ago"
        assert "minute" in result
    
    def test_hours_ago(self):
        """Test timestamp from hours ago."""
        past = datetime.now() - timedelta(hours=3)
        timestamp = past.strftime("%Y-%m-%d_%H%M%S")
        
        result = get_time_ago(timestamp)
        
        assert "hour" in result
        assert "3" in result
    
    def test_one_hour_ago(self):
        """Test singular hour."""
        past = datetime.now() - timedelta(hours=1, minutes=30)
        timestamp = past.strftime("%Y-%m-%d_%H%M%S")
        
        result = get_time_ago(timestamp)
        
        assert "hour" in result
    
    def test_days_ago(self):
        """Test timestamp from days ago."""
        past = datetime.now() - timedelta(days=5)
        timestamp = past.strftime("%Y-%m-%d_%H%M%S")
        
        result = get_time_ago(timestamp)
        
        assert "day" in result
        assert "5" in result
    
    def test_one_day_ago(self):
        """Test singular day."""
        past = datetime.now() - timedelta(days=1, hours=12)
        timestamp = past.strftime("%Y-%m-%d_%H%M%S")
        
        result = get_time_ago(timestamp)
        
        assert "1 day ago" in result
    
    def test_invalid_timestamp(self):
        """Test handling of invalid timestamp."""
        result = get_time_ago("invalid-timestamp")
        
        assert result == "unknown"
    
    def test_empty_timestamp(self):
        """Test handling of empty timestamp."""
        result = get_time_ago("")
        
        assert result == "unknown"


# =============================================================================
# Status Display Tests
# =============================================================================

class TestShowStatus:
    """Tests for show_status function."""
    
    @pytest.fixture
    def mock_tracker(self):
        """Create a mock tracker."""
        tracker = MagicMock()
        tracker.board_name = "test-board"
        tracker.board_config = {
            "name": "Test Board",
            "file_key": "abc123",
            "node_id": "456:789"
        }
        tracker.snapshot_dir = "/path/to/snapshots"
        return tracker
    
    def test_status_no_snapshots(self, mock_tracker):
        """Test status when no snapshots exist."""
        mock_tracker.list_snapshots.return_value = []
        
        status = show_status(mock_tracker)
        
        assert status["board_name"] == "test-board"
        assert status["total_snapshots"] == 0
        assert status["last_snapshot"] is None
    
    def test_status_with_snapshots(self, mock_tracker):
        """Test status when snapshots exist."""
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d_%H%M%S")
        
        mock_tracker.list_snapshots.return_value = [
            {"timestamp": timestamp, "node_count": 10}
        ]
        
        status = show_status(mock_tracker)
        
        assert status["total_snapshots"] == 1
        assert status["last_snapshot"] == timestamp
        assert status["last_node_count"] == 10


# =============================================================================
# Print Function Tests
# =============================================================================

class TestPrintFunctions:
    """Tests for print output functions."""
    
    def test_print_capture_prompt(self, capsys):
        """Test capture prompt output."""
        status = {
            "board_name": "test-board",
            "board_display_name": "Test Board",
            "total_snapshots": 5,
            "last_snapshot": "2025-01-31_120000",
            "last_snapshot_ago": "2 hours ago",
            "last_node_count": 15,
            "snapshot_dir": "/path/to/snapshots"
        }
        
        print_capture_prompt(status)
        
        captured = capsys.readouterr()
        assert "Test Board" in captured.out
        assert "2025-01-31_120000" in captured.out
        assert "2 hours ago" in captured.out
        assert "capture figma snapshot" in captured.out
    
    def test_print_capture_prompt_no_snapshots(self, capsys):
        """Test capture prompt when no snapshots exist."""
        status = {
            "board_name": "test-board",
            "board_display_name": "Test Board",
            "total_snapshots": 0,
            "last_snapshot": None,
            "snapshot_dir": "/path/to/snapshots"
        }
        
        print_capture_prompt(status)
        
        captured = capsys.readouterr()
        assert "No snapshots yet" in captured.out
    
    def test_print_status_only(self, capsys):
        """Test status-only output."""
        status = {
            "board_name": "test-board",
            "board_display_name": "Test Board",
            "total_snapshots": 3,
            "last_snapshot": "2025-01-31_100000",
            "last_snapshot_ago": "1 hour ago",
            "last_node_count": 10,
            "snapshot_dir": "/path/to/snapshots"
        }
        
        print_status_only(status)
        
        captured = capsys.readouterr()
        assert "Test Board" in captured.out
        assert "capture figma snapshot" not in captured.out  # No prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
