"""
MCP-Based Figma Board Snapshot Downloader

This module provides helper functions for capturing and managing snapshots
of Figma/FigJam boards using the MCP browser tools.

WORKFLOW:
1. Ask the AI assistant to capture a Figma board snapshot
2. AI navigates to the Figma board URL using MCP
3. AI takes a screenshot of the board
4. Screenshot is saved to data/raw/figma/ with timestamp

EXAMPLE PROMPTS FOR AI:
- "Take a snapshot of the Figma board"
- "Capture the current state of the Decision Tree board"
- "Download a screenshot of the FigJam board"
"""

import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

from .config import config, FigmaConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Default board to capture
DEFAULT_BOARD = config.DEFAULT_FIGMA_BOARD


def get_figma_snapshots_dir() -> Path:
    """
    Get the directory for storing Figma snapshots.
    
    Returns:
        Path to the Figma snapshots directory.
    """
    figma_dir = config.RAW_DATA_DIR / "figma"
    figma_dir.mkdir(parents=True, exist_ok=True)
    return figma_dir


def find_figma_snapshots(
    board_name: str = None,
    max_age_days: int = 30
) -> List[Tuple[Path, datetime]]:
    """
    Find existing Figma board snapshots.
    
    Args:
        board_name: Filter by board name (e.g., 'decision-tree'). None for all.
        max_age_days: Maximum age of snapshots to include (in days).
        
    Returns:
        List of tuples (file_path, modification_time) sorted by newest first.
    """
    figma_dir = get_figma_snapshots_dir()
    
    if not figma_dir.exists():
        return []
    
    cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)
    found_files = []
    
    # Pattern: YYYY-MM-DD_HHMMSS_board-name.png
    for file_path in figma_dir.glob("*.png"):
        if file_path.is_file():
            mtime = file_path.stat().st_mtime
            if mtime >= cutoff_time:
                # Filter by board name if specified
                if board_name and board_name not in file_path.name:
                    continue
                found_files.append((file_path, datetime.fromtimestamp(mtime)))
    
    # Sort by modification time (newest first)
    found_files.sort(key=lambda x: x[1], reverse=True)
    
    return found_files


def get_snapshot_filename(board_name: str = DEFAULT_BOARD) -> str:
    """
    Generate a timestamped filename for a new snapshot.
    
    Args:
        board_name: Name of the board (used in filename).
        
    Returns:
        Filename string like '2024-12-16_143052_decision-tree.png'
    """
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    return f"{timestamp}_{board_name}.png"


def save_snapshot(
    source_path: Path,
    board_name: str = DEFAULT_BOARD,
    keep_source: bool = False
) -> Optional[Path]:
    """
    Save a screenshot to the Figma snapshots directory.
    
    Args:
        source_path: Path to the screenshot file.
        board_name: Name of the board (used in filename).
        keep_source: Whether to keep the source file (copy vs move).
        
    Returns:
        Path to the saved snapshot, or None if save failed.
    """
    figma_dir = get_figma_snapshots_dir()
    filename = get_snapshot_filename(board_name)
    target_path = figma_dir / filename
    
    try:
        if keep_source:
            shutil.copy2(str(source_path), str(target_path))
            logger.info(f"Copied snapshot to {target_path}")
        else:
            shutil.move(str(source_path), str(target_path))
            logger.info(f"Moved snapshot to {target_path}")
        return target_path
    except Exception as e:
        logger.error(f"Failed to save snapshot: {e}")
        return None


def list_snapshots(board_name: str = None, max_age_days: int = 30) -> None:
    """
    Print a list of existing Figma board snapshots.
    
    Args:
        board_name: Filter by board name (e.g., 'decision-tree'). None for all.
        max_age_days: Maximum age of snapshots to show (in days).
    """
    found_files = find_figma_snapshots(board_name, max_age_days)
    
    if not found_files:
        print(f"\nNo snapshots found (last {max_age_days} days)")
        if board_name:
            print(f"  Board filter: {board_name}")
        return
    
    print(f"\n{'='*70}")
    print(f"Figma Board Snapshots in {get_figma_snapshots_dir()}")
    if board_name:
        print(f"  Filtered by: {board_name}")
    print(f"{'='*70}")
    
    for file_path, mod_time in found_files:
        size_kb = file_path.stat().st_size / 1024
        print(f"  {mod_time.strftime('%Y-%m-%d %H:%M')} | {size_kb:>8.1f} KB | {file_path.name}")
    
    print(f"{'='*70}")
    print(f"Total: {len(found_files)} snapshots")


def compare_snapshots(
    snapshot1: Path = None,
    snapshot2: Path = None,
    board_name: str = DEFAULT_BOARD
) -> dict:
    """
    Compare two snapshots by file size (basic change detection).
    
    If no snapshots are provided, compares the two most recent ones.
    
    Args:
        snapshot1: Path to first snapshot (older).
        snapshot2: Path to second snapshot (newer).
        board_name: Board name to filter when auto-selecting snapshots.
        
    Returns:
        Dictionary with comparison results:
        - 'snapshot1': Path to first snapshot
        - 'snapshot2': Path to second snapshot
        - 'size1': Size of first snapshot in bytes
        - 'size2': Size of second snapshot in bytes
        - 'size_diff': Size difference in bytes
        - 'size_diff_percent': Size difference as percentage
        - 'likely_changed': Boolean indicating if significant change detected
    """
    # If no snapshots provided, get the two most recent
    if snapshot1 is None or snapshot2 is None:
        recent = find_figma_snapshots(board_name)
        if len(recent) < 2:
            return {
                'error': 'Not enough snapshots to compare',
                'snapshots_found': len(recent)
            }
        snapshot2 = recent[0][0]  # newest
        snapshot1 = recent[1][0]  # second newest
    
    size1 = snapshot1.stat().st_size
    size2 = snapshot2.stat().st_size
    size_diff = size2 - size1
    size_diff_percent = (size_diff / size1 * 100) if size1 > 0 else 0
    
    # Consider >5% size change as significant
    likely_changed = abs(size_diff_percent) > 5
    
    return {
        'snapshot1': snapshot1,
        'snapshot2': snapshot2,
        'size1': size1,
        'size2': size2,
        'size_diff': size_diff,
        'size_diff_percent': round(size_diff_percent, 2),
        'likely_changed': likely_changed
    }


def get_board_url(board_name: str = DEFAULT_BOARD) -> Optional[str]:
    """
    Get the URL for a registered Figma board.
    
    Args:
        board_name: Name of the board.
        
    Returns:
        URL string, or None if board not found.
    """
    board = config.FIGMA_BOARDS.get(board_name)
    return board['url'] if board else None


def list_boards() -> None:
    """Print a list of registered Figma boards."""
    print(f"\n{'='*60}")
    print("Registered Figma Boards")
    print(f"{'='*60}")
    
    for name, info in config.FIGMA_BOARDS.items():
        print(f"\n  {name}:")
        print(f"    Name: {info['name']}")
        print(f"    URL: {info['url']}")
        if info.get('description'):
            print(f"    Description: {info['description']}")
    
    print(f"\n{'='*60}")


# MCP Workflow Instructions (for AI reference)
MCP_WORKFLOW = """
## MCP Figma Snapshot Workflow

### Step 1: Navigate to Figma Board
Use MCP browser_navigate to go to the board URL:
```
https://www.figma.com/board/UKiEtHKGhIDRnBGTVhsoL5/Decision-Tree?node-id=526-987&p=f
```

### Step 2: Wait for Page Load
Use MCP browser_wait_for with time=3 to let the board fully render.

### Step 3: Check Login Status
Take a snapshot. If redirected to login page:
- Enter email in the login field
- Click "Log in" button
- Complete authentication (magic link or OAuth)
- Navigate back to the board URL

### Step 4: Take Screenshot
Use MCP browser_take_screenshot to capture the board:
- Set fullPage=true to capture the entire board
- Use a descriptive filename

### Step 5: Save Snapshot
The screenshot is saved to a temp location. Run:
```python
from figma_tracker.download import save_snapshot
from pathlib import Path

# Replace with actual temp path from MCP output
temp_path = Path("/path/to/temp/screenshot.png")
saved = save_snapshot(temp_path, board_name="decision-tree")
print(f"Saved to: {saved}")
```

Or manually copy to data/raw/figma/ with timestamp naming.

### Step 6: Compare with Previous (Optional)
```python
from figma_tracker.download import compare_snapshots
result = compare_snapshots()
print(f"Size changed by {result['size_diff_percent']}%")
print(f"Likely changed: {result['likely_changed']}")
```
"""


def print_workflow():
    """Print the MCP workflow instructions."""
    print(MCP_WORKFLOW)


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="MCP-based Figma Board Snapshot Helper"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List existing snapshots"
    )
    parser.add_argument(
        "--boards", "-b",
        action="store_true",
        help="List registered Figma boards"
    )
    parser.add_argument(
        "--compare", "-c",
        action="store_true",
        help="Compare the two most recent snapshots"
    )
    parser.add_argument(
        "--board",
        type=str,
        default=None,
        help="Filter by board name (e.g., 'decision-tree')"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Max age of snapshots to show (in days, default: 30)"
    )
    parser.add_argument(
        "--workflow", "-w",
        action="store_true",
        help="Print MCP workflow instructions"
    )
    
    args = parser.parse_args()
    
    if args.workflow:
        print_workflow()
    elif args.boards:
        list_boards()
    elif args.list:
        list_snapshots(args.board, args.days)
    elif args.compare:
        result = compare_snapshots(board_name=args.board or DEFAULT_BOARD)
        if 'error' in result:
            print(f"\n✗ {result['error']}")
            print(f"  Snapshots found: {result.get('snapshots_found', 0)}")
        else:
            print(f"\n{'='*60}")
            print("Snapshot Comparison")
            print(f"{'='*60}")
            print(f"  Older: {result['snapshot1'].name}")
            print(f"         Size: {result['size1'] / 1024:.1f} KB")
            print(f"  Newer: {result['snapshot2'].name}")
            print(f"         Size: {result['size2'] / 1024:.1f} KB")
            print(f"  Difference: {result['size_diff']:+d} bytes ({result['size_diff_percent']:+.2f}%)")
            print(f"  Likely changed: {'Yes' if result['likely_changed'] else 'No'}")
            print(f"{'='*60}")
    else:
        # Default: show help
        print("\nFigma Board Snapshot Helper")
        print("="*40)
        print("\nUsage:")
        print("  python -m figma_tracker.download --list       # List existing snapshots")
        print("  python -m figma_tracker.download --boards     # List registered boards")
        print("  python -m figma_tracker.download --compare    # Compare recent snapshots")
        print("  python -m figma_tracker.download --workflow   # Show MCP workflow")
        print("\nTo capture a snapshot:")
        print("  1. Ask AI: 'Take a snapshot of the Figma board'")
        print("  2. AI uses MCP to navigate and screenshot")
        print("  3. Screenshot is saved to data/raw/figma/")


if __name__ == "__main__":
    main()

