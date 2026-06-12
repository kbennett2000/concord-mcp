"""concord-mcp — a read-only MCP server over Concord's /v1 Scripture API."""

from importlib.metadata import version

__version__ = version("concord-mcp")


def main() -> None:
    """Placeholder entry point. The MCP server lands in slice 1."""
    print(f"concord-mcp {__version__}")
