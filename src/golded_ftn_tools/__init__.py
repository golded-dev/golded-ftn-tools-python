"""Command-line adapters and library operations for the GoldED FTN packages."""

from .api import catalog, create, decode, export, heads, read, repair, write
from .errors import ToolError

__all__ = [
    "ToolError",
    "catalog",
    "create",
    "decode",
    "export",
    "heads",
    "read",
    "repair",
    "write",
]
__version__ = "1.0.0"
