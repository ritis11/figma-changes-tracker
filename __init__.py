"""
Figma Board Change Tracker

This package provides tools for:
- Capturing FigJam board snapshots via Figma MCP API
- Comparing structural changes between snapshots
- Tracking board evolution over time
"""

# Lazy imports to avoid RuntimeWarning when running modules directly
def __getattr__(name):
    """Lazy load modules to avoid import issues."""
    if name == 'FigmaTracker':
        from .tracker import FigmaTracker
        return FigmaTracker
    elif name == 'capture_figma_snapshot':
        from .tracker import capture_figma_snapshot
        return capture_figma_snapshot
    elif name == 'FigmaSnapshot':
        from .tracker import FigmaSnapshot
        return FigmaSnapshot
    elif name == 'FigmaNode':
        from .tracker import FigmaNode
        return FigmaNode
    elif name == 'ChangeReport':
        from .tracker import ChangeReport
        return ChangeReport
    elif name == 'NodeChange':
        from .tracker import NodeChange
        return NodeChange
    elif name == 'show_status':
        from .capture import show_status
        return show_status
    elif name == 'print_capture_prompt':
        from .capture import print_capture_prompt
        return print_capture_prompt
    elif name == 'figma_config':
        from .config import figma_config
        return figma_config
    elif name == 'config':
        from .config import config
        return config
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'FigmaTracker',
    'capture_figma_snapshot',
    'FigmaSnapshot',
    'FigmaNode',
    'ChangeReport',
    'NodeChange',
    'show_status',
    'print_capture_prompt',
    'figma_config',
    'config',
]
