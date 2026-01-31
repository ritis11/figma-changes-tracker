#!/usr/bin/env python3
"""
Figma Board Change Tracker

This module provides functionality to capture FigJam board snapshots via the Figma MCP API
and compare structural changes between snapshots.

USAGE:
    python -m figma_tracker.tracker --capture              # Capture new snapshot
    python -m figma_tracker.tracker --compare              # Compare with previous snapshot
    python -m figma_tracker.tracker --compare --from DATE  # Compare specific snapshots
    python -m figma_tracker.tracker --list                 # List all snapshots

NOTE: This module is designed to be called by an AI assistant that has access to
the Figma MCP tools. The capture functionality requires MCP tool invocation.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Pattern

from .config import config, FigmaConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class FigmaNode:
    """Represents a node in a Figma/FigJam board."""
    id: str
    node_type: str
    name: str = ""
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0
    text: str = ""
    color: str = ""
    author: str = ""
    # For connectors
    connector_start: str = ""
    connector_end: str = ""
    connector_start_cap: str = ""
    connector_end_cap: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding empty fields."""
        return {k: v for k, v in asdict(self).items() if v}


# =============================================================================
# Node Parsers - Extract Method pattern to reduce duplication
# =============================================================================

class NodeParser(ABC):
    """Abstract base class for parsing specific node types from FigJam XML."""
    
    @property
    @abstractmethod
    def node_type(self) -> str:
        """Return the type identifier for this node."""
        pass
    
    @property
    @abstractmethod
    def pattern(self) -> Pattern:
        """Return the compiled regex pattern for this node type."""
        pass
    
    @abstractmethod
    def create_node(self, match: re.Match) -> FigmaNode:
        """Create a FigmaNode from a regex match."""
        pass
    
    def parse(self, content: str) -> List[FigmaNode]:
        """Parse all nodes of this type from the content."""
        nodes = []
        for match in self.pattern.finditer(content):
            nodes.append(self.create_node(match))
        return nodes
    
    @staticmethod
    def safe_float(value: Optional[str], default: float = 0) -> float:
        """Safely convert a string to float, returning default on failure."""
        if value is None or value == "":
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default


class ShapeWithTextParser(NodeParser):
    """Parser for shape-with-text elements."""
    
    _pattern = re.compile(
        r'<shape-with-text\s+id="([^"]+)"'
        r'(?:\s+x="([^"]*)")?'
        r'(?:\s+y="([^"]*)")?'
        r'(?:\s+width="([^"]*)")?'
        r'(?:\s+height="([^"]*)")?'
        r'(?:\s+name="([^"]*)")?'
        r'[^>]*>([^<]*)</shape-with-text>',
        re.DOTALL
    )
    
    @property
    def node_type(self) -> str:
        return "shape-with-text"
    
    @property
    def pattern(self) -> Pattern:
        return self._pattern
    
    def create_node(self, match: re.Match) -> FigmaNode:
        return FigmaNode(
            id=match.group(1),
            node_type=self.node_type,
            x=self.safe_float(match.group(2)),
            y=self.safe_float(match.group(3)),
            width=self.safe_float(match.group(4)),
            height=self.safe_float(match.group(5)),
            name=match.group(6) or "",
            text=match.group(7).strip()
        )


class ConnectorParser(NodeParser):
    """Parser for connector elements."""
    
    _pattern = re.compile(
        r'<connector\s+id="([^"]+)"'
        r'(?:\s+x="([^"]*)")?'
        r'(?:\s+y="([^"]*)")?'
        r'(?:\s+connectorStart="([^"]*)")?'
        r'(?:\s+connectorStartCap="([^"]*)")?'
        r'(?:\s+connectorEnd="([^"]*)")?'
        r'(?:\s+connectorEndCap="([^"]*)")?'
        r'[^>]*>([^<]*)</connector>',
        re.DOTALL
    )
    
    @property
    def node_type(self) -> str:
        return "connector"
    
    @property
    def pattern(self) -> Pattern:
        return self._pattern
    
    def create_node(self, match: re.Match) -> FigmaNode:
        return FigmaNode(
            id=match.group(1),
            node_type=self.node_type,
            x=self.safe_float(match.group(2)),
            y=self.safe_float(match.group(3)),
            connector_start=match.group(4) or "",
            connector_start_cap=match.group(5) or "",
            connector_end=match.group(6) or "",
            connector_end_cap=match.group(7) or "",
            text=match.group(8).strip()
        )


class StickyParser(NodeParser):
    """Parser for sticky note elements."""
    
    _pattern = re.compile(
        r'<sticky\s+id="([^"]+)"'
        r'(?:\s+x="([^"]*)")?'
        r'(?:\s+y="([^"]*)")?'
        r'(?:\s+color="([^"]*)")?'
        r'(?:\s+author="([^"]*)")?'
        r'(?:\s+width="([^"]*)")?'
        r'(?:\s+height="([^"]*)")?'
        r'[^>]*>([^<]*)</sticky>',
        re.DOTALL
    )
    
    @property
    def node_type(self) -> str:
        return "sticky"
    
    @property
    def pattern(self) -> Pattern:
        return self._pattern
    
    def create_node(self, match: re.Match) -> FigmaNode:
        return FigmaNode(
            id=match.group(1),
            node_type=self.node_type,
            x=self.safe_float(match.group(2)),
            y=self.safe_float(match.group(3)),
            color=match.group(4) or "",
            author=match.group(5) or "",
            width=self.safe_float(match.group(6)),
            height=self.safe_float(match.group(7)),
            text=match.group(8).strip()
        )


class TextParser(NodeParser):
    """Parser for text elements."""
    
    _pattern = re.compile(
        r'<text\s+id="([^"]+)"'
        r'(?:\s+name="([^"]*)")?'
        r'(?:\s+x="([^"]*)")?'
        r'(?:\s+y="([^"]*)")?'
        r'(?:\s+width="([^"]*)")?'
        r'(?:\s+height="([^"]*)")?'
        r'[^>]*/?>',
        re.DOTALL
    )
    
    @property
    def node_type(self) -> str:
        return "text"
    
    @property
    def pattern(self) -> Pattern:
        return self._pattern
    
    def create_node(self, match: re.Match) -> FigmaNode:
        name = match.group(2) or ""
        return FigmaNode(
            id=match.group(1),
            node_type=self.node_type,
            name=name,
            x=self.safe_float(match.group(3)),
            y=self.safe_float(match.group(4)),
            width=self.safe_float(match.group(5)),
            height=self.safe_float(match.group(6)),
            text=name  # Use name as text for text elements
        )


# Registry of all node parsers
NODE_PARSERS: List[NodeParser] = [
    ShapeWithTextParser(),
    ConnectorParser(),
    StickyParser(),
    TextParser(),
]


@dataclass
class FigmaSnapshot:
    """Represents a complete snapshot of a Figma board."""
    board_name: str
    file_key: str
    node_id: str
    timestamp: str
    section_name: str = ""
    section_id: str = ""
    nodes: List[FigmaNode] = field(default_factory=list)
    raw_content: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "board_name": self.board_name,
            "file_key": self.file_key,
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "section_name": self.section_name,
            "section_id": self.section_id,
            "node_count": len(self.nodes),
            "nodes": [n.to_dict() for n in self.nodes],
            "raw_content": self.raw_content
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FigmaSnapshot":
        """Create a snapshot from a dictionary."""
        nodes = [FigmaNode(**n) for n in data.get("nodes", [])]
        return cls(
            board_name=data.get("board_name", ""),
            file_key=data.get("file_key", ""),
            node_id=data.get("node_id", ""),
            timestamp=data.get("timestamp", ""),
            section_name=data.get("section_name", ""),
            section_id=data.get("section_id", ""),
            nodes=nodes,
            raw_content=data.get("raw_content", "")
        )


@dataclass
class NodeChange:
    """Represents a change to a node between snapshots."""
    change_type: str  # 'added', 'removed', 'modified'
    node_id: str
    node_type: str
    name: str = ""
    old_text: str = ""
    new_text: str = ""
    details: str = ""
    
    def __str__(self) -> str:
        if self.change_type == "added":
            preview = self.new_text[:50] + "..." if len(self.new_text) > 50 else self.new_text
            return f"  + {self.node_id} [{self.node_type}] \"{preview}\""
        elif self.change_type == "removed":
            preview = self.old_text[:50] + "..." if len(self.old_text) > 50 else self.old_text
            return f"  - {self.node_id} [{self.node_type}] \"{preview}\""
        else:  # modified
            return f"  ~ {self.node_id} [{self.node_type}]\n    {self.details}"


@dataclass
class ChangeReport:
    """Report of changes between two snapshots."""
    board_name: str
    from_snapshot: str
    to_snapshot: str
    added: List[NodeChange] = field(default_factory=list)
    removed: List[NodeChange] = field(default_factory=list)
    modified: List[NodeChange] = field(default_factory=list)
    
    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.modified)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "board_name": self.board_name,
            "from_snapshot": self.from_snapshot,
            "to_snapshot": self.to_snapshot,
            "summary": {
                "added": len(self.added),
                "removed": len(self.removed),
                "modified": len(self.modified),
                "total_changes": len(self.added) + len(self.removed) + len(self.modified)
            },
            "changes": {
                "added": [asdict(c) for c in self.added],
                "removed": [asdict(c) for c in self.removed],
                "modified": [asdict(c) for c in self.modified]
            }
        }
    
    def __str__(self) -> str:
        lines = [
            "",
            "=" * 60,
            "Figma Board Change Report",
            "=" * 60,
            f"Board: {self.board_name}",
            f"Comparing: {self.from_snapshot} -> {self.to_snapshot}",
            ""
        ]
        
        lines.append(f"ADDED NODES ({len(self.added)}):")
        if self.added:
            for change in self.added:
                lines.append(str(change))
        else:
            lines.append("  (none)")
        lines.append("")
        
        lines.append(f"MODIFIED NODES ({len(self.modified)}):")
        if self.modified:
            for change in self.modified:
                lines.append(str(change))
        else:
            lines.append("  (none)")
        lines.append("")
        
        lines.append(f"REMOVED NODES ({len(self.removed)}):")
        if self.removed:
            for change in self.removed:
                lines.append(str(change))
        else:
            lines.append("  (none)")
        lines.append("")
        
        lines.append("-" * 60)
        lines.append(f"Summary: {len(self.added)} added, {len(self.modified)} modified, {len(self.removed)} removed")
        lines.append("=" * 60)
        
        return "\n".join(lines)


class FigmaTracker:
    """
    Track changes to Figma/FigJam boards.
    
    This class provides methods to:
    - Parse FigJam content from MCP API responses
    - Save snapshots to JSON files
    - Compare snapshots and generate change reports
    - List and manage snapshots
    """
    
    def __init__(self, board_name: str = None):
        """
        Initialize the tracker.
        
        Args:
            board_name: Name of the board to track. Defaults to config default.
        """
        self.board_name = board_name or config.DEFAULT_FIGMA_BOARD
        self.board_config = config.get_figma_board_config(self.board_name)
        
        if not self.board_config:
            raise ValueError(f"Unknown board: {self.board_name}")
        
        self.snapshot_dir = config.get_figma_board_dir(self.board_name)
        self.index_file = self.snapshot_dir / "index.json"
    
    def parse_figjam_response(self, response_text: str) -> FigmaSnapshot:
        """
        Parse the response from mcp_Figma_get_figjam into a FigmaSnapshot.
        
        Args:
            response_text: The XML-like text response from the MCP tool.
            
        Returns:
            A FigmaSnapshot object containing all parsed nodes.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        
        snapshot = FigmaSnapshot(
            board_name=self.board_name,
            file_key=self.board_config["file_key"],
            node_id=self.board_config["node_id"],
            timestamp=timestamp,
            raw_content=response_text
        )
        
        # Extract section info
        self._parse_section_info(response_text, snapshot)
        
        # Parse all node types using registered parsers
        snapshot.nodes = self._parse_all_nodes(response_text)
        
        logger.info(f"Parsed {len(snapshot.nodes)} nodes from FigJam response")
        return snapshot
    
    def _parse_section_info(self, content: str, snapshot: FigmaSnapshot) -> None:
        """Extract section information from the response."""
        section_match = re.search(
            r'<section\s+id="([^"]+)"\s+name="([^"]+)"',
            content
        )
        if section_match:
            snapshot.section_id = section_match.group(1)
            snapshot.section_name = section_match.group(2)
    
    def _parse_all_nodes(self, content: str) -> List[FigmaNode]:
        """Parse all nodes from content using registered parsers."""
        nodes = []
        for parser in NODE_PARSERS:
            nodes.extend(parser.parse(content))
        return nodes
    
    def save_snapshot(self, snapshot: FigmaSnapshot) -> Path:
        """
        Save a snapshot to disk.
        
        Args:
            snapshot: The snapshot to save.
            
        Returns:
            Path to the saved snapshot file.
        """
        # Ensure directory exists
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Save snapshot JSON
        filename = f"{snapshot.timestamp}.json"
        filepath = self.snapshot_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved snapshot to {filepath}")
        
        # Update index
        self._update_index(snapshot)
        
        return filepath
    
    def _update_index(self, snapshot: FigmaSnapshot) -> None:
        """Update the index file with the new snapshot."""
        index = self._load_index()
        
        index["snapshots"].append({
            "timestamp": snapshot.timestamp,
            "filename": f"{snapshot.timestamp}.json",
            "node_count": len(snapshot.nodes),
            "section_name": snapshot.section_name,
            "created_at": datetime.now().isoformat()
        })
        
        index["last_updated"] = datetime.now().isoformat()
        index["total_snapshots"] = len(index["snapshots"])
        
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2)
    
    def _load_index(self) -> Dict[str, Any]:
        """Load the index file, creating if necessary."""
        if self.index_file.exists():
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return {
            "board_name": self.board_name,
            "file_key": self.board_config["file_key"],
            "node_id": self.board_config["node_id"],
            "snapshots": [],
            "total_snapshots": 0,
            "last_updated": None
        }
    
    def load_snapshot(self, timestamp: str = None) -> Optional[FigmaSnapshot]:
        """
        Load a snapshot from disk.
        
        Args:
            timestamp: Timestamp of the snapshot. If None, loads the latest.
            
        Returns:
            The loaded snapshot, or None if not found.
        """
        if timestamp is None:
            # Get latest snapshot
            snapshots = self.list_snapshots()
            if not snapshots:
                return None
            timestamp = snapshots[0]["timestamp"]
        
        filepath = self.snapshot_dir / f"{timestamp}.json"
        
        if not filepath.exists():
            logger.warning(f"Snapshot not found: {filepath}")
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return FigmaSnapshot.from_dict(data)
    
    def list_snapshots(self) -> List[Dict[str, Any]]:
        """
        List all snapshots for this board.
        
        Returns:
            List of snapshot metadata, sorted by timestamp (newest first).
        """
        index = self._load_index()
        snapshots = index.get("snapshots", [])
        
        # Sort by timestamp descending
        snapshots.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return snapshots
    
    def compare_snapshots(
        self,
        from_timestamp: str = None,
        to_timestamp: str = None,
        ignore_positions: bool = True
    ) -> ChangeReport:
        """
        Compare two snapshots and generate a change report.
        
        Args:
            from_timestamp: Older snapshot timestamp. If None, uses second-latest.
            to_timestamp: Newer snapshot timestamp. If None, uses latest.
            ignore_positions: If True, don't report position-only changes.
            
        Returns:
            A ChangeReport object detailing the differences.
        """
        # Resolve timestamps
        from_timestamp, to_timestamp = self._resolve_comparison_timestamps(
            from_timestamp, to_timestamp
        )
        
        if from_timestamp is None or to_timestamp is None:
            return self._empty_change_report(from_timestamp, to_timestamp)
        
        # Load snapshots
        old_snapshot = self.load_snapshot(from_timestamp)
        new_snapshot = self.load_snapshot(to_timestamp)
        
        if not old_snapshot or not new_snapshot:
            logger.error("Could not load snapshots for comparison")
            return self._empty_change_report(from_timestamp, to_timestamp)
        
        # Build node maps and compute differences
        old_nodes = {n.id: n for n in old_snapshot.nodes}
        new_nodes = {n.id: n for n in new_snapshot.nodes}
        
        report = ChangeReport(
            board_name=self.board_name,
            from_snapshot=from_timestamp,
            to_snapshot=to_timestamp
        )
        
        # Populate report with changes
        self._find_added_nodes(old_nodes, new_nodes, report)
        self._find_removed_nodes(old_nodes, new_nodes, report)
        self._find_modified_nodes(old_nodes, new_nodes, report, ignore_positions)
        
        return report
    
    def _resolve_comparison_timestamps(
        self, 
        from_timestamp: Optional[str], 
        to_timestamp: Optional[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Resolve default timestamps for comparison."""
        snapshots = self.list_snapshots()
        
        if len(snapshots) < 2:
            logger.warning("Not enough snapshots to compare")
            return None, None
        
        if to_timestamp is None:
            to_timestamp = snapshots[0]["timestamp"]
        if from_timestamp is None:
            from_timestamp = snapshots[1]["timestamp"]
        
        return from_timestamp, to_timestamp
    
    def _empty_change_report(
        self, 
        from_snapshot: Optional[str], 
        to_snapshot: Optional[str]
    ) -> ChangeReport:
        """Create an empty change report."""
        return ChangeReport(
            board_name=self.board_name,
            from_snapshot=from_snapshot or "(none)",
            to_snapshot=to_snapshot or "(none)"
        )
    
    def _find_added_nodes(
        self,
        old_nodes: Dict[str, FigmaNode],
        new_nodes: Dict[str, FigmaNode],
        report: ChangeReport
    ) -> None:
        """Find nodes that were added in the new snapshot."""
        added_ids = set(new_nodes.keys()) - set(old_nodes.keys())
        for node_id in added_ids:
            node = new_nodes[node_id]
            report.added.append(NodeChange(
                change_type="added",
                node_id=node_id,
                node_type=node.node_type,
                name=node.name,
                new_text=node.text
            ))
    
    def _find_removed_nodes(
        self,
        old_nodes: Dict[str, FigmaNode],
        new_nodes: Dict[str, FigmaNode],
        report: ChangeReport
    ) -> None:
        """Find nodes that were removed from the old snapshot."""
        removed_ids = set(old_nodes.keys()) - set(new_nodes.keys())
        for node_id in removed_ids:
            node = old_nodes[node_id]
            report.removed.append(NodeChange(
                change_type="removed",
                node_id=node_id,
                node_type=node.node_type,
                name=node.name,
                old_text=node.text
            ))
    
    def _find_modified_nodes(
        self,
        old_nodes: Dict[str, FigmaNode],
        new_nodes: Dict[str, FigmaNode],
        report: ChangeReport,
        ignore_positions: bool
    ) -> None:
        """Find nodes that were modified between snapshots."""
        common_ids = set(old_nodes.keys()) & set(new_nodes.keys())
        
        for node_id in common_ids:
            old_node = old_nodes[node_id]
            new_node = new_nodes[node_id]
            
            changes = self._detect_node_changes(old_node, new_node, ignore_positions)
            
            if changes:
                details = self._format_change_details(old_node, new_node, changes)
                report.modified.append(NodeChange(
                    change_type="modified",
                    node_id=node_id,
                    node_type=new_node.node_type,
                    name=new_node.name,
                    old_text=old_node.text,
                    new_text=new_node.text,
                    details=details
                ))
    
    def _detect_node_changes(
        self,
        old_node: FigmaNode,
        new_node: FigmaNode,
        ignore_positions: bool
    ) -> List[str]:
        """Detect what changed between two versions of a node."""
        changes = []
        
        if old_node.text != new_node.text:
            changes.append("text changed")
        
        if old_node.name != new_node.name:
            changes.append(f"name: '{old_node.name}' -> '{new_node.name}'")
        
        if old_node.node_type == "connector":
            if old_node.connector_start != new_node.connector_start:
                changes.append(f"start: {old_node.connector_start} -> {new_node.connector_start}")
            if old_node.connector_end != new_node.connector_end:
                changes.append(f"end: {old_node.connector_end} -> {new_node.connector_end}")
        
        if not ignore_positions:
            if old_node.x != new_node.x or old_node.y != new_node.y:
                changes.append(
                    f"moved from ({old_node.x}, {old_node.y}) to ({new_node.x}, {new_node.y})"
                )
        
        return changes
    
    @staticmethod
    def _format_change_details(
        old_node: FigmaNode,
        new_node: FigmaNode,
        changes: List[str]
    ) -> str:
        """Format the details of node changes for display."""
        details_parts = []
        
        if old_node.text != new_node.text:
            old_preview = _truncate_text(old_node.text, 40)
            new_preview = _truncate_text(new_node.text, 40)
            details_parts.append(f'- "{old_preview}"')
            details_parts.append(f'+ "{new_preview}"')
        else:
            details_parts.append(", ".join(changes))
        
        return "\n    ".join(details_parts)


    def get_snapshot_summary(self, timestamp: str = None) -> Optional[Dict[str, Any]]:
        """
        Get a summary of a snapshot.
        
        Args:
            timestamp: Timestamp of the snapshot. If None, uses latest.
            
        Returns:
            Summary dict, or None if not found.
        """
        snapshot = self.load_snapshot(timestamp)
        if not snapshot:
            return None
        
        # Count node types
        type_counts = {}
        for node in snapshot.nodes:
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1
        
        return {
            "board_name": snapshot.board_name,
            "timestamp": snapshot.timestamp,
            "section_name": snapshot.section_name,
            "total_nodes": len(snapshot.nodes),
            "node_types": type_counts
        }


def _truncate_text(text: str, max_length: int) -> str:
    """Truncate text with ellipsis if it exceeds max_length."""
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def print_snapshots(tracker: FigmaTracker) -> None:
    """Print a formatted list of snapshots."""
    snapshots = tracker.list_snapshots()
    
    if not snapshots:
        print(f"\nNo snapshots found for board: {tracker.board_name}")
        print(f"  Snapshot directory: {tracker.snapshot_dir}")
        return
    
    print(f"\n{'=' * 60}")
    print(f"Figma Board Snapshots: {tracker.board_name}")
    print(f"{'=' * 60}")
    print(f"  Directory: {tracker.snapshot_dir}")
    print(f"  Total snapshots: {len(snapshots)}")
    print(f"{'=' * 60}")
    
    for snap in snapshots:
        print(f"  {snap['timestamp']} | {snap['node_count']:>4} nodes | {snap.get('section_name', 'N/A')}")
    
    print(f"{'=' * 60}")


def print_boards() -> None:
    """Print a list of configured Figma boards."""
    print(f"\n{'=' * 60}")
    print("Configured Figma Boards")
    print(f"{'=' * 60}")
    
    for name, info in config.FIGMA_BOARDS.items():
        print(f"\n  {name}:")
        print(f"    Name: {info['name']}")
        print(f"    File Key: {info['file_key']}")
        print(f"    Node ID: {info['node_id']}")
        if info.get('description'):
            print(f"    Description: {info['description']}")
    
    print(f"\n{'=' * 60}")


def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Figma Board Change Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m figma_tracker.tracker --capture           # Capture new snapshot (requires MCP)
  python -m figma_tracker.tracker --compare           # Compare two most recent snapshots
  python -m figma_tracker.tracker --compare --from 2024-12-16_143052
  python -m figma_tracker.tracker --list              # List all snapshots
  python -m figma_tracker.tracker --boards            # List configured boards
  python -m figma_tracker.tracker --summary           # Show latest snapshot summary

Note: The --capture command outputs instructions for using MCP tools.
      Run this in a context where an AI assistant can invoke the Figma MCP API.
        """
    )
    parser.add_argument(
        "--capture",
        action="store_true",
        help="Capture a new snapshot (outputs MCP instructions)"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare snapshots"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all snapshots"
    )
    parser.add_argument(
        "--boards",
        action="store_true",
        help="List configured Figma boards"
    )
    parser.add_argument(
        "--summary", "-s",
        action="store_true",
        help="Show summary of latest snapshot"
    )
    parser.add_argument(
        "--board", "-b",
        type=str,
        default=None,
        help=f"Board name (default: {config.DEFAULT_FIGMA_BOARD})"
    )
    parser.add_argument(
        "--from",
        dest="from_timestamp",
        type=str,
        default=None,
        help="From timestamp for comparison"
    )
    parser.add_argument(
        "--to",
        dest="to_timestamp",
        type=str,
        default=None,
        help="To timestamp for comparison"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    
    args = parser.parse_args()
    
    if args.boards:
        print_boards()
        return
    
    try:
        tracker = FigmaTracker(args.board)
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    if args.capture:
        board_config = tracker.board_config
        print(f"\n{'=' * 60}")
        print("Figma Snapshot Capture")
        print(f"{'=' * 60}")
        print(f"\nBoard: {board_config['name']}")
        print(f"File Key: {board_config['file_key']}")
        print(f"Node ID: {board_config['node_id']}")
        print(f"\nTo capture a snapshot, ask the AI assistant to:")
        print(f"  1. Call mcp_Figma_get_figjam with:")
        print(f"     - fileKey: {board_config['file_key']}")
        print(f"     - nodeId: {board_config['node_id']}")
        print(f"  2. Pass the response to FigmaTracker.parse_figjam_response()")
        print(f"  3. Call FigmaTracker.save_snapshot() with the result")
        print(f"\nOr use the capture_figma_snapshot() helper function.")
        print(f"{'=' * 60}")
    
    elif args.compare:
        report = tracker.compare_snapshots(
            from_timestamp=args.from_timestamp,
            to_timestamp=args.to_timestamp
        )
        
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(report)
    
    elif args.list:
        if args.json:
            snapshots = tracker.list_snapshots()
            print(json.dumps(snapshots, indent=2))
        else:
            print_snapshots(tracker)
    
    elif args.summary:
        summary = tracker.get_snapshot_summary()
        if summary:
            if args.json:
                print(json.dumps(summary, indent=2))
            else:
                print(f"\n{'=' * 60}")
                print("Latest Snapshot Summary")
                print(f"{'=' * 60}")
                print(f"  Board: {summary['board_name']}")
                print(f"  Timestamp: {summary['timestamp']}")
                print(f"  Section: {summary['section_name']}")
                print(f"  Total Nodes: {summary['total_nodes']}")
                print(f"  Node Types:")
                for ntype, count in summary['node_types'].items():
                    print(f"    - {ntype}: {count}")
                print(f"{'=' * 60}")
        else:
            print("No snapshots found")
    
    else:
        # Default: show help
        print("\nFigma Board Change Tracker")
        print("=" * 40)
        print("\nUsage:")
        print("  python -m figma_tracker.tracker --capture    # Capture new snapshot")
        print("  python -m figma_tracker.tracker --compare    # Compare recent snapshots")
        print("  python -m figma_tracker.tracker --list       # List all snapshots")
        print("  python -m figma_tracker.tracker --boards     # List configured boards")
        print("  python -m figma_tracker.tracker --summary    # Show snapshot summary")
        print("\nFor detailed help: python -m figma_tracker.tracker --help")


# Helper function for AI assistant to capture snapshots
def capture_figma_snapshot(
    mcp_response: str,
    board_name: str = None
) -> Tuple[Path, FigmaSnapshot]:
    """
    Helper function to capture and save a Figma snapshot.
    
    This is designed to be called by an AI assistant after invoking
    the mcp_Figma_get_figjam tool.
    
    Args:
        mcp_response: The text response from mcp_Figma_get_figjam tool.
        board_name: Board name. Defaults to config default.
        
    Returns:
        Tuple of (filepath, snapshot)
    
    Example:
        # After calling mcp_Figma_get_figjam and getting response
        filepath, snapshot = capture_figma_snapshot(response_text)
        print(f"Saved {snapshot.node_count} nodes to {filepath}")
    """
    tracker = FigmaTracker(board_name)
    snapshot = tracker.parse_figjam_response(mcp_response)
    filepath = tracker.save_snapshot(snapshot)
    return filepath, snapshot


if __name__ == "__main__":
    main()

