#!/usr/bin/env python3
"""
Figma Snapshot Capture Trigger

A simple script that displays snapshot status and provides a ready-to-paste
prompt for the AI assistant to capture a new Figma snapshot.

USAGE:
    python -m figma_tracker.capture              # Show status and capture prompt
    python -m figma_tracker.capture --status     # Show status only
    python -m figma_tracker.capture --board NAME # Use a specific board

WORKFLOW:
    1. Run this script
    2. Copy the displayed prompt
    3. Paste it in the Cursor chat
    4. AI captures the snapshot and shows comparison
"""

import argparse
from datetime import datetime
from pathlib import Path

from .config import config
from .tracker import FigmaTracker


def get_time_ago(timestamp_str: str) -> str:
    """Convert a timestamp string to a human-readable 'time ago' format."""
    try:
        # Parse timestamp like "2025-12-17_221011"
        dt = datetime.strptime(timestamp_str, "%Y-%m-%d_%H%M%S")
        now = datetime.now()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        
        hours = diff.seconds // 3600
        if hours > 0:
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        
        minutes = diff.seconds // 60
        if minutes > 0:
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        
        return "just now"
    except:
        return "unknown"


def show_status(tracker: FigmaTracker) -> dict:
    """Display current snapshot status and return status info."""
    snapshots = tracker.list_snapshots()
    board_config = tracker.board_config
    
    status = {
        "board_name": tracker.board_name,
        "board_display_name": board_config.get("name", tracker.board_name),
        "total_snapshots": len(snapshots),
        "last_snapshot": None,
        "last_snapshot_ago": None,
        "snapshot_dir": str(tracker.snapshot_dir)
    }
    
    if snapshots:
        latest = snapshots[0]
        status["last_snapshot"] = latest["timestamp"]
        status["last_snapshot_ago"] = get_time_ago(latest["timestamp"])
        status["last_node_count"] = latest.get("node_count", 0)
    
    return status


def print_capture_prompt(status: dict) -> None:
    """Print the status and capture prompt."""
    print()
    print("=" * 60)
    print(f"Figma Snapshot Status: {status['board_display_name']}")
    print("=" * 60)
    
    if status["last_snapshot"]:
        print(f"  Last snapshot: {status['last_snapshot']} ({status['last_snapshot_ago']})")
        print(f"  Nodes captured: {status.get('last_node_count', 'N/A')}")
    else:
        print("  No snapshots yet - this will be the first!")
    
    print(f"  Total snapshots: {status['total_snapshots']}")
    print(f"  Storage: {status['snapshot_dir']}")
    print()
    print("-" * 60)
    print("To capture a new snapshot, paste this in Cursor chat:")
    print("-" * 60)
    print()
    print("  capture figma snapshot and compare")
    print()
    print("-" * 60)
    print("=" * 60)
    print()


def print_status_only(status: dict) -> None:
    """Print just the status without capture prompt."""
    print()
    print("=" * 60)
    print(f"Figma Snapshot Status: {status['board_display_name']}")
    print("=" * 60)
    
    if status["last_snapshot"]:
        print(f"  Last snapshot: {status['last_snapshot']} ({status['last_snapshot_ago']})")
        print(f"  Nodes captured: {status.get('last_node_count', 'N/A')}")
    else:
        print("  No snapshots yet")
    
    print(f"  Total snapshots: {status['total_snapshots']}")
    print(f"  Storage: {status['snapshot_dir']}")
    print("=" * 60)
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Figma Snapshot Capture Trigger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflow:
  1. Run: python -m figma_tracker.capture
  2. Copy the displayed prompt
  3. Paste it in Cursor chat
  4. AI captures snapshot and shows comparison

Examples:
  python -m figma_tracker.capture              # Show prompt for default board
  python -m figma_tracker.capture --status     # Just show status
  python -m figma_tracker.capture -b my-board  # Use different board
        """
    )
    parser.add_argument(
        "--board", "-b",
        type=str,
        default=None,
        help=f"Board name (default: {config.DEFAULT_FIGMA_BOARD})"
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show status only (no capture prompt)"
    )
    parser.add_argument(
        "--list-boards",
        action="store_true",
        help="List all configured boards"
    )
    
    args = parser.parse_args()
    
    # List boards
    if args.list_boards:
        print("\nConfigured Figma Boards:")
        print("-" * 40)
        for name, info in config.FIGMA_BOARDS.items():
            marker = " (default)" if name == config.DEFAULT_FIGMA_BOARD else ""
            print(f"  {name}{marker}: {info.get('name', 'N/A')}")
        print()
        return
    
    # Initialize tracker
    try:
        tracker = FigmaTracker(args.board)
    except ValueError as e:
        print(f"\nError: {e}")
        print(f"Available boards: {', '.join(config.FIGMA_BOARDS.keys())}")
        return
    
    # Get status
    status = show_status(tracker)
    
    # Print output
    if args.status:
        print_status_only(status)
    else:
        print_capture_prompt(status)


if __name__ == "__main__":
    main()

