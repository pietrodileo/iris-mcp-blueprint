from fastmcp import Context
import irisnative
from typing import Any, Optional
import logging

from iris_mcp_blueprint.mcp_app import mcp

logger = logging.getLogger(__name__)

# --- GLOBAL MANAGEMENT TOOLS HELPERS ---

def _format_global_path(global_name: str, subscripts: tuple) -> str:
    """
    Format a global path for display.
    Args:
        global_name: The name of the global to format.
        subscripts: The subscripts of the global to format.
    """
    if not subscripts:
        return f"^{global_name}"
    parts = ", ".join(
        str(s) if isinstance(s, (int, float)) else repr(s) for s in subscripts
    )
    return f"^{global_name}({parts})"

# --- GLOBAL MANAGEMENT TOOLS ---

@mcp.tool()
def check_global(ctx: Context, global_name: str) -> str:
    """
    Check if a global exists (e.g., 'MCPData').
    Args:
        ctx: The context of the tool call.
        global_name: The name of the global to check.
    """
    iris = ctx.request_context.lifespan_context["iris"]
    state = iris.isDefined(global_name)
    return f"Global ^{global_name} state: {state} (0=Empty, >0=Exists)"

@mcp.tool()
def save_global(ctx: Context, global_name: str,value: str,subscripts: list[Any] | None = None,) -> str:
    """
    Save a value to a global node. Use subscripts for ^g(1,\"a\") style paths (e.g. [1, \"Prova\"]).
    Args:
        ctx: The context of the tool call.
        global_name: The name of the global to save the value to.
        value: The value to save to the global.
        subscripts: The subscripts of the global to save the value to.
    """
    iris = ctx.request_context.lifespan_context["iris"]
    subs = subscripts or []
    iris.set(value, global_name, *subs)
    sub_fmt = ",".join(str(s) if isinstance(s, int) else repr(s) for s in subs)
    tail = f"({sub_fmt})" if subs else ""
    return f"Set ^{global_name}{tail} = {value!r}"

@mcp.tool()
def check_global_content(ctx: Context, global_name: str, subscripts: list[Any] | None = None) -> str:
    """
    Read a global node (same subscript rules as save_global).
    Args:
        ctx: The context of the tool call.
        global_name: The name of the global to read.
        subscripts: The subscripts of the global to read.
    """
    iris = ctx.request_context.lifespan_context["iris"]
    subs = subscripts or []
    content = iris.get(global_name, *subs)
    sub_fmt = ",".join(str(s) if isinstance(s, int) else repr(s) for s in subs)
    tail = f"({sub_fmt})" if subs else ""
    return f"^{global_name}{tail} = {content!r}"

@mcp.tool()
def list_global_subscripts(
    ctx: Context,
    global_name: str,
    subscripts: list[Any] | None = None,
    recursive: bool = False,
    max_depth: int = 10,
    max_nodes: int = 2000,
    include_values: bool = False,
) -> str:
    """
    List subscript keys under a global path using the IRIS node iterator (ZORDER-style).
    Args:
        ctx: The context of the tool call.
        global_name: top global without ^ (e.g. BTHo).
        subscripts: path into the global, e.g. ["DufT", 3] for ^BTHo("DufT",3,...
        recursive: if True, each line is a full path from the start node; max_depth is how many
        subscript levels to descend below the starting path (1 = only immediate children).
        max_depth: how many subscript levels to descend below the starting path (1 = only immediate children).
        max_nodes: maximum number of nodes to return (default: 2000).
        include_values: if True, include the values of the nodes.
    """
    iris = ctx.request_context.lifespan_context["iris"]
    base_subs: tuple = tuple(subscripts or [])
 
    if max_depth < 1:
        return "Error: max_depth must be at least 1 (use 1 for immediate children only)."
    if max_nodes < 1:
        return "Error: max_nodes must be at least 1."
 
    def child_keys(subs: tuple) -> list:
        try:
            it = iris.iterator(global_name, *subs)
            return list(it.subscripts())
        except Exception:
            return []
 
    def fmt(subs: tuple) -> str:
        if not subs:
            return f"^{global_name}"
        parts = ",".join(repr(s) if isinstance(s, str) else str(s) for s in subs)
        return f"^{global_name}({parts})"
 
    lines: list[str] = []
    stop_note: Optional[str] = None
 
    if not recursive:
        for s in child_keys(base_subs):
            if len(lines) >= max_nodes:
                lines.append(f"(truncated to {max_nodes} keys)")
                break
            lines.append(str(s) if isinstance(s, (int, float)) else repr(s))
 
        if not lines:
            return f"No subscripts (or not defined) under {fmt(base_subs)}."
 
        blurb = f" (truncated to {max_nodes} keys)" if len(lines) > max_nodes else ""
        return (
            f"Subscripts at {fmt(base_subs)} (count={len(lines)}{blurb}):\n"
            + "\n".join(lines)
        )
 
    def visit(current_subs: tuple, levels_below: int) -> None:
        nonlocal stop_note
        if len(lines) >= max_nodes or stop_note:
            return
 
        for s in child_keys(current_subs):
            if len(lines) >= max_nodes:
                stop_note = f"max_nodes={max_nodes}"
                return
 
            path_subs = current_subs + (s,)
            path_str = fmt(path_subs)
 
            if include_values:
                try:
                    v = iris.get(global_name, *path_subs)
                except Exception as ex:
                    v = f"<read error: {ex}>"
                lines.append(f"{path_str} = {v!r}")
            else:
                lines.append(path_str)
 
            if levels_below > 1 and len(lines) < max_nodes and not stop_note:
                visit(path_subs, levels_below - 1)
 
            if len(lines) >= max_nodes and not stop_note:
                stop_note = f"max_nodes={max_nodes}"
                return
 
    visit(base_subs, max_depth)
 
    if not lines and not stop_note:
        return f"No subscripts (or not defined) under {fmt(base_subs)}."
    if stop_note:
        lines.append(f"(Stopped: {stop_note}.)")
 
    return (
        f"Global paths from {fmt(base_subs)} (recursive, levels_below_start={max_depth}):\n"
        + "\n".join(lines)
    )
