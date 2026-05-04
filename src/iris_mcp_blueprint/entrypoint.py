"""
MCP entrypoint: register tools, prompts, and resources, then run the server.
The FastMCP instance and IRIS lifespan live in iris_mcp_blueprint.mcp_app so tool modules can import mcp.
"""

import argparse
import os
from typing import Any, Literal

from iris_mcp_blueprint.mcp_app import logger, mcp

import iris_mcp_blueprint.tools.sql as sql_tools
import iris_mcp_blueprint.tools.globals as global_tools
import iris_mcp_blueprint.tools.class_methods as class_method_tools
import iris_mcp_blueprint.tools.atelier_api as atelier_api_tools
import iris_mcp_blueprint.tools.interoperability as interoperability_tools
import iris_mcp_blueprint.prompts.prompts as prompts
import iris_mcp_blueprint.resources.resources as resources

TransportChoice = Literal["stdio", "sse"]

def run_server(
    transport: TransportChoice = "stdio",
    *,
    host: str | None = None,
    port: int | None = None,
    **kwargs: Any,
) -> None:
    """Run the MCP server over stdio (local) or SSE (remote HTTP).

    Args:
        transport: ``stdio`` for subprocess/IDE mode (e.g. Cursor); ``sse`` for HTTP/SSE.
        host: Bind address when using SSE (default: FASTMCP_HOST or 127.0.0.1).
        port: TCP port when using SSE (default: FASTMCP_PORT or 8000).
    """
    logger.info("Running server with transport: %s", transport)
    allowed: tuple[str, ...] = ("stdio", "sse")
    if transport not in allowed:
        raise ValueError(f"Unknown transport: {transport!r}; expected one of {allowed}")

    if transport == "stdio":
        mcp.run(transport="stdio", **kwargs)
        return

    resolved_host = host if host is not None else os.getenv("FASTMCP_HOST", "127.0.0.1")
    resolved_port = port if port is not None else int(os.getenv("FASTMCP_PORT", "8000"))
    mcp.run(transport="sse", host=resolved_host, port=resolved_port, **kwargs)


def main() -> None:
    parser = argparse.ArgumentParser(description="IRIS MCP Blueprint server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse"),
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="stdio: local subprocess; sse: HTTP/SSE for remote clients. Env: MCP_TRANSPORT.",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("FASTMCP_HOST", "127.0.0.1"),
        help="Bind address for SSE (use 0.0.0.0 for all interfaces). Env: FASTMCP_HOST.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("FASTMCP_PORT", "8000")),
        help="TCP port for SSE. Env: FASTMCP_PORT.",
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Disable FastMCP startup banner.",
    )
    args = parser.parse_args()
    run_server(
        transport=args.transport,
        host=args.host,
        port=args.port,
        show_banner=not args.no_banner,
    )

if __name__ == "__main__":
    main()
