# figma-changes-tracker
A lightweight utility that monitors Figma file changes and creates a summary of what all changed from previous snapshot

Track changes to Figma/FigJam boards by capturing snapshots and comparing them over time.

## Overview

This tool allows you to:
- **Capture snapshots** of FigJam boards (nodes, connectors, sticky notes, text)
- **Compare snapshots** to detect changes (added, modified, removed nodes)
- **Track history** of board evolution over time

Since user has view-only access to the Figma board, snapshots are captured via the AI assistant using **Figma's MCP integration**.

---

## Quick Start

### 1. Check Status & Get Capture Prompt

```bash
python -m figma_tracker.capture
```

**Output:**
```
============================================================
Figma Snapshot Status: Decision Tree
============================================================
  Last snapshot: 2025-12-17_221011 (2 hours ago)
  Nodes captured: 38
  Total snapshots: 2

------------------------------------------------------------
To capture a new snapshot, paste this in Cursor chat:
------------------------------------------------------------

  capture figma snapshot and compare

------------------------------------------------------------
```

### 2. Capture a Snapshot

Copy and paste in Cursor chat:
```
capture figma snapshot and compare
```

The AI will:
1. Fetch the current board state via Figma MCP
2. Parse and save the snapshot
3. Compare with the previous snapshot (if exists)
4. Show you what changed

---

## CLI Commands

### capture.py - Trigger Script

| Command | Description |
|---------|-------------|
| `python -m figma_tracker.capture` | Show status and capture prompt |
| `python -m figma_tracker.capture --status` | Show status only |
| `python -m figma_tracker.capture --list-boards` | List configured boards |
| `python -m figma_tracker.capture -b BOARD` | Use a specific board |

### tracker.py - Analysis Tools

| Command | Description |
|---------|-------------|
| `python -m figma_tracker.tracker --list` | List all snapshots |
| `python -m figma_tracker.tracker --summary` | Show latest snapshot summary |
| `python -m figma_tracker.tracker --compare` | Compare two most recent snapshots |
| `python -m figma_tracker.tracker --compare --from TIMESTAMP` | Compare from specific snapshot |
| `python -m figma_tracker.tracker --compare --json` | Output comparison as JSON |
| `python -m figma_tracker.tracker --boards` | List configured boards |

---

## Workflow Diagram

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  python -m          │     │  Paste in chat:     │     │  AI captures via    │
│  figma_tracker      │ --> │  "capture figma     │ --> │  Figma MCP and      │
│  .capture           │     │   snapshot"         │     │  saves JSON         │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
                                                                  │
                                                                  v
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  View change        │     │  python -m          │     │  Snapshot saved to  │
│  report             │ <-- │  figma_tracker      │ <-- │  data/raw/figma/    │
│                     │     │  .tracker --compare │     │  snapshots/         │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

---

## Data Storage

Snapshots are stored in:
```
data/raw/figma/snapshots/
  └── decision-tree/
      ├── 2025-12-17_143052.json    # Snapshot files
      ├── 2025-12-17_160230.json
      └── index.json                 # Metadata index
```

### Snapshot JSON Structure

Each snapshot contains:
```json
{
  "board_name": "decision-tree",
  "file_key": "XXXXXXXXX",
  "node_id": "2419:3646",
  "timestamp": "2025-12-17_143052",
  "section_name": "Section Name",
  "node_count": 38,
  "nodes": [
    {
      "id": "2420:3683",
      "node_type": "shape-with-text",
      "name": "SQUARE",
      "x": 1176,
      "y": 1064,
      "text": "Section text..."
    },
    {
      "id": "2420:3686",
      "node_type": "connector",
      "connector_start": "2420:3684",
      "connector_end": "2420:3685",
      "text": "No"
    }
  ]
}
```

---

## Change Report Example

```
============================================================
Figma Board Change Report
============================================================
Board: decision-tree
Comparing: 2025-12-17_143052 -> 2025-12-17_160230

ADDED NODES (2):
  + 2420:3700 [shape-with-text] "New charge type explanation..."
  + 2420:3701 [connector] ""

MODIFIED NODES (1):
  ~ 2420:3683 [shape-with-text]
    - "Older details..."
    + "Newer changes..."

REMOVED NODES (0):
  (none)

------------------------------------------------------------
Summary: 2 added, 1 modified, 0 removed
============================================================
```

---

## Configuration

Boards are configured in `figma_tracker/config.py`:

| Board Name | Figma File | Node |
|------------|------------|------|
| `decision-tree` (default) | UKiEtHKGhIDRnBGTVhsoL5 | 2419:3646 |

To add more boards, edit the `FIGMA_BOARDS` dict in `figma_tracker/config.py`.

---

## Node Types Tracked

| Type | Description |
|------|-------------|
| `shape-with-text` | Boxes, diamonds, rounded rectangles with text |
| `connector` | Lines/arrows connecting nodes |
| `sticky` | Sticky notes (with author info) |
| `text` | Standalone text labels |

---

## Python API

```python
from figma_tracker import FigmaTracker, capture_figma_snapshot

# Initialize tracker for a board
tracker = FigmaTracker("decision-tree")

# List snapshots
snapshots = tracker.list_snapshots()

# Compare recent snapshots
report = tracker.compare_snapshots()
print(report)

# Get summary
summary = tracker.get_snapshot_summary()

# Capture snapshot (after MCP call)
filepath, snapshot = capture_figma_snapshot(mcp_response_text)
```

---

## Troubleshooting

### "No snapshots found"
Run the capture prompt first: `capture figma snapshot`

### "Not enough snapshots to compare"
You need at least 2 snapshots to compare. Capture another one after making changes to the board.

### Snapshot not capturing all nodes
The MCP API returns content for the specified node ID. Make sure the node ID in config covers the section you want to track.

---

## Files

| File | Purpose |
|------|---------|
| `capture.py` | Trigger script - shows status and capture prompt |
| `tracker.py` | Core module - parsing, saving, comparing snapshots |
| `download.py` | Screenshot download helper |
| `config.py` | Board configuration and paths |

---

## Future Enhancements

- [ ] Email/Slack notifications on detected changes
- [ ] Visual diff (image comparison)
- [ ] Scheduled captures (requires Figma API token with Editor access)
- [ ] Export change reports to PDF/HTML

