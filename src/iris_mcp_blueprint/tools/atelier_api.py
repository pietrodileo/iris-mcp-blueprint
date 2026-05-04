from fastmcp import Context
import requests
from requests.auth import HTTPBasicAuth
import logging

from iris_mcp_blueprint.mcp_app import mcp

logger = logging.getLogger(__name__)

def _call_atelier_api(ctx: Context, method: str, endpoint: str, body=None, params=None):
    """
    Internal helper for the Atelier REST API.

    Args:
        ctx: The context of the tool call.
        method: The HTTP method to use.
        endpoint: The endpoint to call.
        body: The body of the request.
        params: The parameters of the request.
    """
    cfg = ctx.request_context.lifespan_context["config"]

    # Standard URL: /api/atelier/<version>/:namespace/:resource
    # Note: 'endpoint' should not start with a slash
    api_version = cfg.get("atelier_api_version", "v3")
    url = f"http://{cfg['hostname']}:{cfg['web_port']}/api/atelier/{api_version}/{cfg['namespace']}/{endpoint}"

    auth = HTTPBasicAuth(cfg['username'], cfg['password'])

    response = requests.request(method, url, auth=auth, json=body, params=params, timeout=15)

    if response.status_code == 404:
        logger.error(f"Atelier 404 at URL: {url}")

    response.raise_for_status()
    return response.json()


def put_doc(
    ctx: Context,
    doc_name: str,
    content_lines: list[str],
    ignore_conflict: bool = True,
) -> dict:
    """
    Save or create a source document via Atelier `PutDoc` (PUT `doc/...`).

    `doc_name` must include the extension (e.g. `My.Pkg.Class.cls`).
    """
    if "/" in doc_name or "\\" in doc_name:
        raise ValueError("doc_name must be a single document name, not a path")
    params = {"ignoreConflict": 1} if ignore_conflict else None
    body = {"enc": False, "content": content_lines}
    return _call_atelier_api(ctx, "PUT", f"doc/{doc_name}", body=body, params=params)


def compile_documents(
    ctx: Context, documents: list[str], flags: str = "cuk"
) -> dict:
    """
    Compile one or more documents (Atelier `action/compile`).

    Args:
        documents: Document names including extension, e.g. `["My.Class.cls"]`.
        flags: Compiler flags (default `cuk`).
    """
    return _call_atelier_api(
        ctx, "POST", "action/compile", body=documents, params={"flags": flags}
    )


def get_atelier_info(ctx: Context) -> dict:
    """
    Query the unversioned Atelier root endpoint (`GET /api/atelier/`) to
    discover server metadata: highest supported API version, IRIS build,
    namespaces, and feature flags. Available on every IRIS version.

    Returns the parsed `result.content` dict, e.g.::

        {
            "version": "IRIS for UNIX ... 2025.3 ...",
            "id": "F75640E7-...",
            "api": 8,
            "features": [{"name": "DEEPSEE", "enabled": true}, ...],
            "namespaces": ["%SYS", "USER"]
        }
    """
    cfg = ctx.request_context.lifespan_context["config"]
    url = f"http://{cfg['hostname']}:{cfg['web_port']}/api/atelier/"
    auth = HTTPBasicAuth(cfg['username'], cfg['password'])
    response = requests.get(url, auth=auth, timeout=15)
    response.raise_for_status()
    return response.json().get("result", {}).get("content", {})

@mcp.tool()
def search_code(
    ctx: Context,
    query: str,
    documents: str = "*.cls,*.mac,*.int,*.inc",
    regex: int = 0,
    case_sensitive: int = 0,
    include_system: int = 0,
    include_generated: int = 0,
    max_results: int = 50,
) -> str:
    """
    Search for a string across IRIS source documents (Atelier `action/search`).

    Calls `GET /api/atelier/<ver>/<ns>/action/search` (v2+). Both `query` and
    `documents` are required by the server; missing `documents` returns HTTP 400.

    Args:
        query: Text (or regex) to search for.
        documents: Comma-separated file mask (default `*.cls,*.mac,*.int,*.inc`).
        regex: 1 = treat `query` as a regex, 0 = plain-text (default).
        case_sensitive: 1 = case-sensitive, 0 = case-insensitive (default).
            Only honoured when `regex=0`.
        include_system: 1 = include system docs (e.g. `%Api.*`), 0 = skip (default).
        include_generated: 1 = include generated docs, 0 = skip (default).
        max_results: Max number of hits to return (default 50).
    """
    try:
        params = {
            "query": query,
            "documents": documents,
            "regex": regex,
            "case": case_sensitive,
            "sys": include_system,
            "gen": include_generated,
            "max": max_results,
        }
        data = _call_atelier_api(ctx, "GET", "action/search", params=params)

        # Atelier returns `result` either as a list of {doc, matches[]} or as
        # an object with a `content` array (older variants). Normalise here.
        result = data.get("result")
        if isinstance(result, list):
            items = result
        elif isinstance(result, dict):
            items = result.get("content", [])
        else:
            items = []

        if not items:
            return f"No matches found for '{query}'."

        lines: list[str] = []
        for it in items:
            doc = it.get("doc", "?")
            for m in it.get("matches", []) or []:
                location = m.get("line") or m.get("member") or "?"
                text = (m.get("text") or "").strip()
                lines.append(f"{doc}:{location}: {text}")
        return "\n".join(lines) if lines else f"No matches found for '{query}'."
    except Exception as e:
        return f"Search failed: {e}"

@mcp.tool()
def get_class_source(ctx: Context, class_name: str) -> str:
    """
    Read .cls source code using Atelier REST API.

    Args:
        class_name: The name of the class to get the source code for.
    """
    # validate the class name
    if not class_name.endswith(".cls"):
        class_name = f"{class_name}.cls"
    data = _call_atelier_api(ctx, "GET", f"doc/{class_name}")
    return "\n".join(data.get("result", {}).get("content", []))
