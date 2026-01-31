"""
Figma Tracker specific configuration.

This module extends the base Config with Figma-specific settings:
- Board definitions (file keys, node IDs, URLs)
- Snapshot directory configuration
- Default board selection
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class BaseConfig:
    """Base configuration with shared paths and utilities."""
    
    # Base paths - relative to project root (figma_tracker directory)
    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).parent)
    DATA_DIR: Path = field(default_factory=lambda: Path(__file__).parent / "data")
    RAW_DATA_DIR: Path = field(default_factory=lambda: Path(__file__).parent / "data" / "raw")
    PROCESSED_DATA_DIR: Path = field(default_factory=lambda: Path(__file__).parent / "data" / "processed")
    
    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist."""
        cls.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class FigmaConfig(BaseConfig):
    """Configuration for Figma board tracking."""
    
    # Figma snapshots directory
    FIGMA_SNAPSHOTS_DIR: Path = field(default_factory=lambda: Path(__file__).parent / "data" / "raw" / "figma" / "snapshots")
    
    # Figma Board Configuration
    FIGMA_BOARDS: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "decision-tree": {
            "name": "Decision Tree",
            "file_key": "UKiEtHKGhIDRnBGTVhsoL5",
            "node_id": "2419:3646",
            "url": "https://www.figma.com/board/UKiEtHKGhIDRnBGTVhsoL5/Decision-Tree?node-id=2419-3646",
            "description": "Description of the board"
        }
    })
    
    # Default board to track
    DEFAULT_FIGMA_BOARD: str = "decision-tree"
    
    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist, including Figma snapshot dir."""
        super().ensure_directories()
        cls.FIGMA_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    def get_figma_board_dir(self, board_name: str = None) -> Path:
        """
        Get the snapshot directory for a specific Figma board.
        
        Args:
            board_name: Name of the board. Defaults to DEFAULT_FIGMA_BOARD.
            
        Returns:
            Path to the board's snapshot directory.
        """
        if board_name is None:
            board_name = self.DEFAULT_FIGMA_BOARD
        board_dir = self.FIGMA_SNAPSHOTS_DIR / board_name
        board_dir.mkdir(parents=True, exist_ok=True)
        return board_dir
    
    def get_figma_board_config(self, board_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a Figma board.
        
        Args:
            board_name: Name of the board. Defaults to DEFAULT_FIGMA_BOARD.
            
        Returns:
            Board configuration dict, or None if not found.
        """
        if board_name is None:
            board_name = self.DEFAULT_FIGMA_BOARD
        return self.FIGMA_BOARDS.get(board_name)


# Default configuration instance
figma_config = FigmaConfig()

# Also export as 'config' for convenience within the package
config = figma_config

