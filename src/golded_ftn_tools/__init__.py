"""Command-line adapters and library operations for the GoldED FTN packages."""

from .api import create, decode, export, read, repair, write
from .errors import ToolError

__all__ = [
    "ToolError",
    "create",
    "decode",
    "export",
    "read",
    "repair",
    "write",
]
__version__ = "0.1.0"
