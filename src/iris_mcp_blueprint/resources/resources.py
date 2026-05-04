from fastmcp import Context

from iris_mcp_blueprint.mcp_app import mcp
from iris_mcp_blueprint.tools.sql import execute_sql_query
from iris_mcp_blueprint.tools.atelier_api import get_atelier_info

@mcp.resource("resource://iris/version")
def res_version(ctx: Context) -> str:
    """
    Return the system metrics.
    Args:
        ctx: The context of the resource call.
    """
    iris = ctx.request_context.lifespan_context["iris"] 
    return f"""System Metrics:
    IRIS OS Version: {iris.classMethodValue('%SYSTEM.Version', 'GetVersion')}
    Namespace: {iris.classMethodValue('%SYSTEM.SYS', 'NameSpace')}
    Disk: {iris.classMethodValue('%File', 'GetDirectorySpace', '/')}
    """

_BASE_TABLES_SQL = (
    "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
    "WHERE TABLE_TYPE = 'BASE TABLE'"
)


@mcp.resource("resource://iris/tables")
def res_tables_all(ctx: Context) -> str:
    """
    Return every base table across all SQL schemas.

    Read this resource via ``resource://iris/tables``. To restrict to a
    single schema, use the template ``resource://iris/tables/{table_schema}``
    (e.g. ``resource://iris/tables/SQLUser``).

    Args:
        ctx: The context of the resource call.
    """
    db = ctx.request_context.lifespan_context["db"]
    return execute_sql_query(db, _BASE_TABLES_SQL, [])

@mcp.resource("resource://iris/atelier_info")
def res_atelier_info(ctx: Context) -> str:
    """
    Return Atelier REST API server info: highest supported API version,
    IRIS build, available namespaces, and feature flags.

    Useful to decide which value to set for the `IRIS_ATELIER_API_VERSION`
    env var. The MCP server's URLs are built as
    `/api/atelier/<IRIS_ATELIER_API_VERSION>/<namespace>/...`, so picking
    the highest version reported here unlocks the newest endpoints.

    Args:
        ctx: The context of the resource call.
    """
    cfg = ctx.request_context.lifespan_context["config"]
    try:
        info = get_atelier_info(ctx)
    except Exception as e:
        return f"Atelier info request failed: {e}"

    api_max = info.get("api")
    iris_build = info.get("version", "unknown")
    iris_id = info.get("id", "unknown")
    namespaces = ", ".join(info.get("namespaces", [])) or "(none)"
    features = info.get("features", []) or []
    features_lines = "\n".join(
        f"  - {f.get('name')}: {'enabled' if f.get('enabled') else 'disabled'}"
        for f in features
    ) or "  (none)"

    configured = cfg.get("atelier_api_version", "v3")
    suggested = f"v{api_max}" if isinstance(api_max, int) else "unknown"

    return (
        "IRIS Atelier REST API\n"
        "=====================\n"
        f"Server URL: http://{cfg['hostname']}:{cfg['web_port']}/api/atelier/\n"
        f"IRIS Build: {iris_build}\n"
        f"IRIS ID:    {iris_id}\n"
        f"Highest supported API version: {suggested} (max integer: {api_max})\n"
        f"Currently configured by this MCP server: {configured} "
        f"(env IRIS_ATELIER_API_VERSION)\n"
        f"Namespaces: {namespaces}\n"
        "Features:\n"
        f"{features_lines}\n"
    )
