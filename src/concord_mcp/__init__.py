"""concord-mcp — a read-only MCP server over Concord's /v1 Scripture API."""

from importlib.metadata import version

__version__ = version("concord-mcp")


def main() -> None:
    """Console-script entry point: run the MCP server on stdio."""
    from concord_mcp.server import main as run_server

    run_server()
