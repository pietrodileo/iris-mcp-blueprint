import re
from typing import Optional

from fastmcp import Context

from iris_mcp_blueprint.mcp_app import mcp
from iris_mcp_blueprint.tools.atelier_api import compile_documents, put_doc

WEBAPP_MANAGER_CLASS = "MCPTest.WebApplications.Manager"

_PRODUCTION_CLASS_RE = re.compile(r"^%?[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")

def _iris_status_error(iris, sc, action: str) -> Optional[str]:
    """Return an error string if 'sc' is an IRIS %Status failure, else None."""
    if sc is None or sc == 1 or sc == "1" or sc is True:
        return None
    try:
        ok = iris.classMethodInteger("%SYSTEM.Status", "IsOK", sc)
        if ok:
            return None
    except Exception:
        pass
    try:
        detail = iris.classMethodString("%SYSTEM.Status", "GetErrorText", sc)
    except Exception:
        detail = str(sc)[:400]
    return f"ERROR: {action} — {detail}"


def _resolve_production_name(iris, production_name: str) -> tuple[Optional[str], Optional[str]]:
    """Return (resolved production class name, error string)."""
    prod_name = (production_name or "").strip()
    if not prod_name:
        prod_name = (iris.classMethodString("Ens.Director", "GetActiveProductionName") or "").strip()
    if not prod_name:
        return None, "ERROR: no production specified and no active production."
    return prod_name, None


def _open_production(iris, prod_name: str):
    return iris.classMethodObject("Ens.Config.Production", "%OpenId", prod_name)


def _atelier_top_errors(data: dict) -> list[str]:
    lines: list[str] = []
    for err in (data.get("status") or {}).get("errors") or []:
        if isinstance(err, dict):
            lines.append(err.get("errorText") or err.get("message") or str(err))
        else:
            lines.append(str(err))
    return lines


def _atelier_compile_doc_issues(data: dict) -> list[str]:
    lines: list[str] = []
    content = (data.get("result") or {}).get("content") or []
    for doc in content:
        name = doc.get("name", "?")
        st = doc.get("status")
        if st:
            lines.append(f"{name}: {st}")
        for err in doc.get("errors") or []:
            if isinstance(err, dict):
                lines.append(f"{name}: {err.get('errorText') or err}")
            else:
                lines.append(f"{name}: {err}")
    return lines


@mcp.tool()
def get_active_production(ctx: Context) -> str:
    """
    Return the name of the currently active Interoperability production on the current namespace.
    """
    iris = ctx.request_context.lifespan_context["iris"]
    if iris is None:
        return "ERROR: IRIS connection is not available."
    try:
        name = iris.classMethodString("Ens.Director", "GetActiveProductionName")
        return name if name else "(no active production)"
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def start_production(ctx: Context, production_class_name: str, synchronous: int = 1) -> str:
    """
    Start an Interoperability production by class name (must already exist and be compiled).

    Calls `##class(Ens.Director).StartProduction(productionName)` (single-argument form
    compatible with the IRIS Native SDK and servers where the two-argument `sync` overload
    is not exposed to Python). It does **not** create the production class; use
    `create_empty_production` or deploy a class from source, then call this tool.

    Args:
        production_class_name: Full production class name (e.g. `MCPTest.EmptyProduction`).
        synchronous: Reserved for future use; start mode follows the server's single-arg API.
    """
    _ = synchronous
    iris = ctx.request_context.lifespan_context["iris"]
    if iris is None:
        return "ERROR: IRIS connection is not available."
    try:
        sc = iris.classMethodValue(
            "Ens.Director", "StartProduction", production_class_name
        )
        err = _iris_status_error(iris, sc, f"StartProduction({production_class_name})")
        if err:
            return err
        return f"OK: started production '{production_class_name}'."
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def stop_production(ctx: Context) -> str:
    """
    Stop the currently running Interoperability production in this namespace.

    Calls `##class(Ens.Director).StopProduction()`.
    """
    iris = ctx.request_context.lifespan_context["iris"]
    if iris is None:
        return "ERROR: IRIS connection is not available."
    try:
        sc = iris.classMethodValue("Ens.Director", "StopProduction")
        err = _iris_status_error(iris, sc, "StopProduction()")
        if err:
            return err
        return "OK: production stopped."
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def create_empty_production(ctx: Context, production_class_name: str) -> str:
    """
    Create and compile a new empty `Ens.Production` subclass in the current namespace.

    Uses the Atelier REST API (`PutDoc` + `action/compile`) — same web host/credentials as
    other Atelier tools (`IRIS_WEB_PORT`, `IRIS_ATELIER_API_VERSION`).

    Args:
        production_class_name: Full class name (e.g. `MyPkg.MyProduction`). Must contain
            at least one package segment. The `ProductionDefinition` XData will use this
            exact name as the production name.

    Returns a status string starting with `OK:` or `ERROR:`.
    """
    raw = (production_class_name or "").strip()
    if not _PRODUCTION_CLASS_RE.match(raw):
        return (
            "ERROR: production_class_name must look like a valid IRIS class name "
            "with a package (e.g. `MCPTest.MyEmptyProd`)."
        )
    doc = raw if raw.endswith(".cls") else f"{raw}.cls"
    cls = doc[:-4] if doc.endswith(".cls") else doc

    lines = [
        f"Class {cls} Extends Ens.Production",
        "{",
        "",
        "XData ProductionDefinition",
        "{",
        f'<Production Name="{cls}" LogGeneralTraceEvents="false">',
        "</Production>",
        "}",
        "",
        "}",
    ]
    try:
        put_resp = put_doc(ctx, doc, lines, ignore_conflict=True)
        top = _atelier_top_errors(put_resp)
        if top:
            return "ERROR: Atelier PutDoc — " + "; ".join(top)

        comp = compile_documents(ctx, [doc], flags="cuk")
        issues = _atelier_top_errors(comp) + _atelier_compile_doc_issues(comp)
        if issues:
            return "ERROR: compile — " + "; ".join(issues)

        return (
            f"OK: created and compiled empty production class '{cls}'. "
            f"Start it with `start_production` using that class name."
        )
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def list_production_items(ctx: Context, production_name: str = "") -> str:
    """
    List the items currently configured in a production on the current namespace.

    Args:
        production_name: Production class name. If empty, the active production is used.
    """
    iris = ctx.request_context.lifespan_context["iris"]
    if iris is None:
        return "ERROR: IRIS connection is not available."
    try:
        prod_name, err = _resolve_production_name(iris, production_name)
        if err:
            return err
        prod = _open_production(iris, prod_name)
        if prod is None:
            return f"ERROR: production '{prod_name}' not found."
        items = prod.get("Items")
        n = items.invokeInteger("Count")
        out_lines = ["ConfigName | ClassName | Enabled | PoolSize"]
        for i in range(1, n + 1):
            item = items.invokeObject("GetAt", i)
            line = " | ".join(
                [
                    str(item.get("Name") or ""),
                    str(item.get("ClassName") or ""),
                    str(item.get("Enabled") or ""),
                    str(item.get("PoolSize") or ""),
                ]
            )
            out_lines.append(line)
        return "\n".join(out_lines)
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def add_production_item(
    ctx: Context,
    class_name: str,
    config_name: str,
    production_name: str = "",
    comment: str = "",
    pool_size: int = 1,
    enabled: bool = True,
    settings: Optional[dict] = None,
) -> str:
    """
    Add a Business Host (Service / Process / Operation) to a production on the current namespace.

    Args:
        class_name: Full class name of the host (e.g. 'EnsLib.REST.GenericService',
            'MCPTest.BP.QueryService').
        config_name: Config name of the new item inside the production.
        production_name: Production class name. If empty, the active production is used.
        comment: Optional comment shown in the production page.
        pool_size: Pool size (jobs). Use 0 for on-demand BPL processes.
        enabled: Whether the item is enabled at startup.
        settings: Optional dict of {SettingName: value} pairs applied as Host
            settings. Typical example for a BS routing to a BP:
                {"TargetConfigNames": "MyBP"}

    Returns a status string starting with "OK:" or "ERROR:".
    """
    iris = ctx.request_context.lifespan_context["iris"]
    if iris is None:
        return "ERROR: IRIS connection is not available."
    try:
        prod_name, err = _resolve_production_name(iris, production_name)
        if err:
            return err
        prod = _open_production(iris, prod_name)
        if prod is None:
            return f"ERROR: production '{prod_name}' not found."

        items = prod.get("Items")
        n = items.invokeInteger("Count")
        for i in range(1, n + 1):
            it = items.invokeObject("GetAt", i)
            if (it.get("Name") or "") == config_name:
                return f"ERROR: an item named '{config_name}' already exists in '{prod_name}'."

        item = iris.classMethodObject("Ens.Config.Item", "%New")
        item.set("ClassName", class_name)
        item.set("Name", config_name)
        item.set("Comment", comment or "")
        item.set("PoolSize", int(pool_size))
        item.set("Enabled", 1 if enabled else 0)

        for k, v in (settings or {}).items():
            setting = iris.classMethodObject("Ens.Config.Setting", "%New")
            setting.set("Name", str(k))
            setting.set("Value", "" if v is None else str(v))
            setting.set("Target", "Host")
            sc_ins = item.get("Settings").invoke("Insert", setting)
            e = _iris_status_error(iris, sc_ins, f"Settings.Insert({k})")
            if e:
                return e

        sc = item.invoke("%Save")
        e = _iris_status_error(iris, sc, "Ens.Config.Item.%Save")
        if e:
            return e

        sc = items.invoke("Insert", item)
        e = _iris_status_error(iris, sc, "Items.Insert")
        if e:
            return e

        sc = prod.invoke("SaveToClass", item)
        e = _iris_status_error(iris, sc, "SaveToClass(item)")
        if e:
            return e

        sc = prod.invoke("%Save")
        e = _iris_status_error(iris, sc, "Ens.Config.Production.%Save")
        if e:
            return e

        return f"OK: added '{config_name}' ({class_name}) to '{prod_name}'."
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def remove_production_item(ctx: Context, config_name: str, production_name: str = "") -> str:
    """
    Remove a Business Host from a production.

    Args:
        config_name: Config name of the item to remove.
        production_name: Production class name. If empty, the active production is used.
    """
    iris = ctx.request_context.lifespan_context["iris"]
    if iris is None:
        return "ERROR: IRIS connection is not available."
    try:
        prod_name, err = _resolve_production_name(iris, production_name)
        if err:
            return err
        prod = _open_production(iris, prod_name)
        if prod is None:
            return f"ERROR: production '{prod_name}' not found."

        items = prod.get("Items")
        n = items.invokeInteger("Count")
        remove_at: Optional[int] = None
        for i in range(1, n + 1):
            it = items.invokeObject("GetAt", i)
            if (it.get("Name") or "") == config_name:
                remove_at = i
                break
        if remove_at is None:
            return f"ERROR: item '{config_name}' not found in '{prod_name}'."

        items.invoke("RemoveAt", remove_at)

        sc = prod.invoke("SaveToClass")
        e = _iris_status_error(iris, sc, "SaveToClass()")
        if e:
            return e
        sc = prod.invoke("%Save")
        e = _iris_status_error(iris, sc, "Ens.Config.Production.%Save")
        if e:
            return e

        return f"OK: removed '{config_name}' from '{prod_name}'."
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def update_production(ctx: Context, production_name: str = "") -> str:
    """
    Apply pending configuration changes to the running production
    (equivalent to clicking 'Update' in the Management Portal).

    Calls `##class(Ens.Director).UpdateProduction()`. Only the active production is updated;
    `production_name` is reserved for future use and ignored.
    """
    _ = production_name
    iris = ctx.request_context.lifespan_context["iris"]
    if iris is None:
        return "ERROR: IRIS connection is not available."
    try:
        active = (iris.classMethodString("Ens.Director", "GetActiveProductionName") or "").strip()
        if not active:
            return "ERROR: no active production."
        sc = iris.classMethodValue("Ens.Director", "UpdateProduction")
        err = _iris_status_error(iris, sc, "UpdateProduction()")
        if err:
            return err
        return f"OK: production '{active}' updated."
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def register_web_application(
    ctx: Context,
    path: str,
    dispatch_class: str = "EnsLib.REST.GenericService",
    description: str = "REST endpoint exposed via the MCP blueprint",
    namespace: str = "",
) -> str:
    """
    Create or update a CSP web application that exposes an HTTP-based Business
    Service (typically EnsLib.REST.GenericService) to the outside world.

    Delegates to the ObjectScript helper because 'Security.Applications'
    requires switching to the %SYS namespace, which is cleaner to do in
    ObjectScript than over the Native SDK.

    Authentication is set to *Unauthenticated* for development convenience.
    Tighten this before going to production.

    Args:
        path: URL path of the web app (must start with '/'), e.g. '/rest/user/queryservice-rest-bs'
            or '/csp/myapp/api' depending on Security.Applications registration.
        dispatch_class: Class that handles incoming requests. Defaults to
            'EnsLib.REST.GenericService' which forwards everything to the
            Business Service whose config name appears next in the URL.
        description: Free-text description shown in the Management Portal.
        namespace: Target namespace. If empty, uses the namespace of the
            current MCP connection.
    """
    iris = ctx.request_context.lifespan_context["iris"]
    if iris is None:
        return "ERROR: IRIS connection is not available."
    if not path.startswith("/"):
        return "ERROR: 'path' must start with '/' (e.g. '/rest/user/queryservice-rest-bs')."
    cfg = ctx.request_context.lifespan_context.get("config", {})
    ns = namespace or cfg.get("namespace") or "USER"
    try:
        return iris.classMethodValue(
            WEBAPP_MANAGER_CLASS,
            "RegisterWebApplication",
            ns,
            path,
            dispatch_class,
            description,
        )
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def remove_web_application(ctx: Context, path: str) -> str:
    """
    Delete a CSP web application by URL path (delegates to ObjectScript).

    Args:
        path: URL path of the web app (must start with '/'), e.g. '/rest/user/queryservice-rest-bs'.
    """
    iris = ctx.request_context.lifespan_context["iris"]
    if iris is None:
        return "ERROR: IRIS connection is not available."
    if not path.startswith("/"):
        return "ERROR: 'path' must start with '/'."
    try:
        return iris.classMethodValue(
            WEBAPP_MANAGER_CLASS,
            "RemoveWebApplication",
            path,
        )
    except Exception as e:
        return f"ERROR: {e}"
