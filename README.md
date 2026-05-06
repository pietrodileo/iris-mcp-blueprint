# IRIS MCP Blueprint

> ⚠️ **This repository is an example, not a finished product.** It's a *blueprint* showing **how to build an MCP server for InterSystems IRIS** that performs operations across several tool categories: **SQL**, **Globals**, **Class methods**, **Atelier API**, and **Interoperability** (see [`src/iris_mcp_blueprint/tools/`](src/iris_mcp_blueprint/tools/)), plus a handful of reusable **prompts** and **resources**. It is **not** meant to be a one-size-fits-all MCP server for every IRIS workload. Use it as a **starting point**: clone it, keep what you need, drop what you don't, and **adapt the tools, prompts, and resources to your own IRIS application** (namespaces, classes, productions, security model, business rules, and so on). The ObjectScript demo under `src/MCPTest/` is only there to give the included tools/prompts something to work against.

A **[FastMCP](https://gofastmcp.com/)** server that exposes tools, prompts, and resources to work with **InterSystems IRIS** with any MCP-compatible client (Cursor, Claude Desktop, and others). The Python package under `src/iris_mcp_blueprint/` connects to IRIS over the Native SDK and wraps the operations you tend to repeat by hand — running SQL, poking at globals, searching code through the Atelier API, driving an Interoperability production, calling class methods, and so on. The **ObjectScript** classes in `src/MCPTest/` (including `MCPTest.BP.QueryService`) are there as a concrete target so the tools and the guided **prompts** have something realistic to operate on.

---

## Prerequisites

| Tool | Why it’s needed | Source / version pin in this repo |
|---|---|---|
| **Python 3.12** | Runtime that satisfies `requires-python = ">=3.12"` in `pyproject.toml` | `.python-version` ⇒ `3.12` (read by `uv` to provision the venv) |
| **[uv](https://docs.astral.sh/uv/) ≥ 0.5** | Installs deps from `pyproject.toml` + `uv.lock`, runs the CLI (`uv run`) and remote builds (`uvx`) | Versions older than 0.5 may not understand the lockfile or `uv init --package` |
| **Docker** with `docker compose` v2 | Runs the IRIS database container described by `docker-compose.yml` | Image: `intersystems/iris-community:latest-cd` (see `Dockerfile`) |
| **Git** | Cloning this repo (and any `uvx --from git+...` install of remote forks) | — |
| **MCP-compatible client** *(at runtime)* | Drives the prompts and tools | Cursor, Claude Desktop, or anything that speaks MCP over stdio / SSE |

Notes:

- You don’t need to install Python yourself — `uv` will fetch the **3.12** interpreter pinned in `.python-version` if it’s not already on your system.
- The Docker container exposes IRIS on host ports **9091** (SuperServer) and **9092** (Web / Management Portal). Make sure those ports are free.

Install `uv` if you don't have it (via `pip`):

```bash
pip install uv
```

---

## Quick start

**Order matters here.** The MCP server opens its IRIS connection at startup, and if IRIS isn't reachable yet **every IRIS-backed tool will fail with a connection error**. Stick to this order:
  1. clone the repo
  2. start the IRIS Docker container
  3. set the IRIS env vars in your MCP client config
  4. start (or restart) the MCP server from the client.

### 1. Clone the repo

```bash
git clone https://github.com/pietrodileo/iris-mcp-blueprint.git
cd iris-mcp-blueprint
```

You can perform an optional smoke-check to ensure the MCP server starts at all (this also bootstraps `.venv/` from `pyproject.toml` + `uv.lock` on first run):

```bash
uv sync
uv run iris-mcp-blueprint --help
```

> This command is **only a sanity check** — it prints the CLI options and exits. You will **not** drive the server from the terminal; real usage happens through an MCP-compatible client such as **Cursor** or **Claude Desktop**, which spawns the server itself using the JSON config in steps 3–4.

> Running `uv sync` first is **optional**: it just pre-creates the venv (handy to surface install errors or to avoid MCP client startup timeouts).

### 2. Start the IRIS database (do this **before** launching the MCP server)

```bash
docker compose up -d
```

This starts IRIS with the SuperServer on port **9091** and the Management Portal on port **9092** (`http://localhost:9092/csp/sys/UtilHome.csp`). Wait until the container reports **`healthy`** (`docker ps`) before moving on — the MCP server cannot open a Native SDK connection until IRIS is accepting traffic on port 9091.

### 3. Set the IRIS connection env vars in your MCP client

Open your client's MCP config (`.cursor/mcp.json`, Claude Desktop's `claude_desktop_config.json`, etc.) and **fill in the `env` block** with the values listed in [IRIS connection environment variables](#iris-connection-environment-variables). Concrete JSON snippets for both clients are in [Configure Cursor or Claude Desktop](#configure-cursor-or-claude-desktop). Skipping or mistyping these values is the most common cause of `Connection refused` / `Login failed` errors at MCP startup.

### 4. Start (or restart) the MCP server from the client

Launch the server **from the MCP client** so it picks up the env block. In Cursor that means enabling/refreshing `iris-mcp-blueprint` in the MCP panel; in Claude Desktop, restart the app after editing the config. The first call goes through `uv run iris-mcp-blueprint` and provisions the venv on demand. If you started the server *before* IRIS was up, restart it now — connections are established at startup and not retried implicitly.

---

## MCP prompts and how to try them

Prompts are short, reusable **workflow instructions** returned by `@mcp.prompt` handlers in `src/iris_mcp_blueprint/prompts/prompts.py`. They don't run code on their own — they just tell the assistant which **tools** to call and in what order (for example `get_class_source`, then `add_production_item`, then `run_class_method`).

### Available prompts (quick reference)

| Prompt name | Purpose (summary) |
| --- | --- |
| `analyze-table` | Inspect a table’s structure, sample rows, and suggest indexes. |
| `explore-class` | Read a class with `get_class_source`, summarize methods, properties, and storage. |
| `import-csv-workflow` | Safe CSV import: validate name, call `import_csv_to_iris`, verify with `describe_table` / `fetch_data`. |
| `export-table` | Export an existing table to **JSON**, **CSV**, or **TXT** via the `export_table` tool, with optional `columns` / `where` / `limit` filters and a row-count safety check first. |
| `search-for-code` | Search class sources with `search_code`, then optionally deep-dive with `explore-class`. |
| `analyze-table-globals-content` | Map a persistent class / table to globals and explain how data is stored. |
| `create-rest-bp-endpoint` | Wire a Business Process to HTTP: production items (`EnsLib.REST.GenericService` + BP), `register_web_application`, `update_production`; for `MCPTest.BP.QueryService`, run `PopulateAndAssign` before testing. |

### What each prompt does (more detail)

Each entry below is collapsed by default — click to see arguments and the steps the prompt walks the assistant through.

<details>
<summary><code>analyze-table</code> — data-engineering review of a single SQL table</summary>

- **Arguments:** `table_name` (required); `schema_name` (optional — if empty the workflow asks you to pick a schema, defaulting to `SQLUser`).
- **What it does:** drives `res_tables_all` (when the schema is unknown), `describe_table` for columns and types, `fetch_data` for a small sample (first five rows), and finally writes a recommendation for **indexes** that would help typical access patterns.

</details>

<details>
<summary><code>explore-class</code> — source-level tour of one ObjectScript class</summary>

- **Arguments:** `query` = full class name (for example `MCPTest.BP.QueryService`).
- **What it does:** calls `get_class_source`, then summarizes **InstanceMethods / ClassMethods**, **properties**, and — when present — the `<Storage>` block and related **globals**.
- **Use it when:** you need a readable overview before editing or documenting code. Several other prompts chain into `explore-class` for deeper analysis.

</details>

<details>
<summary><code>import-csv-workflow</code> — end-to-end CSV → new IRIS table flow</summary>

- **Arguments:** `table_name`; a `csv_sample` string (headers plus a few rows are enough); optional `table_schema`.
- **What it does:** infers types from the sample, checks whether the target already exists via `res_tables_all`, refuses to overwrite blindly, then calls `import_csv_to_iris`. After load it uses `describe_table` and `fetch_data` (for example `SELECT COUNT(*)`) to verify shape and row counts, and may suggest `create_index` once you agree on names.
- **Try it with the bundled sample:** paste the first few lines of [`example_data/patients.csv`](example_data/patients.csv) (header + a handful of rows) into `csv_sample`, set `table_name` to a fresh name such as `Patients`, and optionally `table_schema` to `MCPTest` (or any schema you like). The workflow will create the table and load all rows.

</details>

<details>
<summary><code>export-table</code> — dump an existing IRIS table to JSON, CSV, or TXT</summary>

- **Arguments:** `table_name` (required); `format` = `json` (default), `csv`, or `txt`; optional `table_schema` (the workflow asks if empty, defaulting to `SQLUser`).
- **What it does:**
  1. Resolves the schema (via `res_tables_all` / `get_tables` if `table_schema` is empty).
  2. Calls `describe_table` to show the user the columns and types that will be exported.
  3. Runs `SELECT COUNT(*)` via `fetch_data` and warns if the table is large (>~10 000 rows).
  4. Asks the user whether to export everything (`limit=0`), apply a `WHERE` filter, restrict to a subset of `columns`, or keep the default `limit=1000`.
  5. Calls the **`export_table`** tool with the agreed scope and chosen format.
  6. Previews the first few lines/items and reports the total length, then explains how to save the output (e.g. `<table_name>.<format>`).
- **Tool details (`export_table`):**
  - `format` — `'json'` returns a list of objects (`null` for SQL `NULL`, `Decimal` and `datetime` serialized as strings); `'csv'` follows RFC 4180 with a comma delimiter and CRLF line terminator; `'txt'` reuses the pipe-separated table layout shared with the other SQL tools.
  - `columns` — optional list of column names. Each is validated as a SQL identifier (`[A-Za-z_][A-Za-z0-9_]*`) before being inlined.
  - `where` — optional SQL fragment **without** the leading `WHERE` keyword (e.g. `Age > 30 AND City = 'Rome'`). Caller is responsible for escaping; for untrusted input use `fetch_data` with parameters instead.
  - `limit` — defaults to `1000`. Pass `0` (or a negative value) to disable the cap. Implemented as IRIS `SELECT TOP N`, so it streams only the requested rows.
- **Try it with the demo data:** after `MCPTest.Employer.PopulateAndAssign()` has run (auto-seeded by `iris.script` on first start, or invoked via `run_class_method`), call the prompt with `table_name`: `Employer`, `table_schema`: `MCPTest`, `format`: `json` (or `csv` / `txt`).

</details>

<details>
<summary><code>search-for-code</code> — Atelier-style discovery across the namespace</summary>

- **Arguments:** `query` = any text to find in class sources (API name, method name, ObjectScript fragment).
- **Steps:** `search_code` → list of matching classes → you choose which hits matter → those classes are studied further (the prompt text tells the model to reuse `explore-class`) → short explanation of *how* the string appears in each chosen class.
- **Use it for:** refactors, security reviews, or learning how a pattern is used in your application.

</details>

<details>
<summary><code>analyze-table-globals-content</code> — goes below SQL to the global nodes backing a persistent class</summary>

- **Arguments:** `table_name`; optional `table_schema`. The class is treated as `{table_schema}.{table_name}` when that matches your persistent package.
- **What it does:** locates every distinct **global** and explains its role (data vs index vs stream) and may call `check_global` / `check_global_content` or `fetch_data` to verify their content.
- **Use it when:** you care about physical layout, not only column names.

</details>

<details>
<summary><code>create-rest-bp-endpoint</code> — expose an <code>Ens.BusinessProcess</code> subclass over HTTP via <code>EnsLib.REST.GenericService</code></summary>

- **Arguments:** `bp_class` (for example `MCPTest.BP.QueryService`); optional `bp_config_name`, `bs_config_name`, `web_app_path`, `production_name`.
- **What it does:**
  1. Verifies `OnRequest` / `EnsLib.HTTP.GenericMessage` on the BP.
  2. Ensures an **active production** exists.
  3. Calls `add_production_item` for the BP and for the REST BS (with `TargetConfigNames`).
  4. Calls `register_web_application`, then `update_production`, with optional `list_production_items`.
  5. For `MCPTest.BP.QueryService`, runs `MCPTest.Employer:PopulateAndAssign` via `run_class_method` to seed demo data.
  6. Applies the BS setting tweaks listed in the prompt.
  7. Documents the URL pattern `http://<host>:<webport><web_app_path>/<bs_config_name>` and runs an HTTP smoke test.
- **After running it:** validate with the curl examples in [How to test them (Cursor and similar clients)](#how-to-test-them-cursor-and-similar-clients).

</details>

### How to test them (Cursor and similar clients)

<details>
<summary>Click to expand — 4-step recipe + ready-to-use prompt arguments + curl smoke-tests for the QueryService demo</summary>

1. **Start IRIS** (`docker compose up -d`) and **configure the MCP server** using **Environment variables (IRIS connection)** and the JSON example under **Option A — Local** later in this README so the client can reach IRIS (`IRIS_PORT`, `IRIS_NAMESPACE`, credentials, etc.).
2. In the client, open the **MCP prompts** UI for `iris-mcp-blueprint` (wording varies: “Prompts”, slash command, or the model picker’s MCP prompt list).
3. **Select a prompt by name** (e.g. `explore-class`) and pass the **parameters** the prompt expects (e.g. class name `MCPTest.BP.QueryService`).
4. Send the message and **confirm** the assistant follows the steps: it should call the listed tools and report results. If a step returns `ERROR:`, fix IRIS connectivity or inputs and retry.

**Example inputs and full QueryService test** (after IRIS is up and MCP is configured):

- **`explore-class`** — `query`: `MCPTest.Employer` or `MCPTest.BP.QueryService`.
- **`analyze-table`** — `table_name`: `Employer`, `schema_name`: `MCPTest` (or your SQL schema; leave empty to exercise schema discovery).
- **`search-for-code`** — `query`: `PopulateAndAssign` or `EnsLib.REST.GenericService`.
- **`analyze-table-globals-content`** — same table/schema as `analyze-table`, for example `Employer` / `MCPTest`.
- **`import-csv-workflow`** — paste the first few lines of [`example_data/patients.csv`](example_data/patients.csv) into `csv_sample`, with `table_name`: `Patients` and an unused schema such as `MCPTest`. (You can also use any small fictional CSV and a **new** `table_name` that does not already exist.)
- **`export-table`** — `table_name`: `Employer`, `table_schema`: `MCPTest`, `format`: `json` (or `csv` / `txt`). The prompt previews the data and the underlying `export_table` tool returns the full payload as a single string ready to copy into `Employer.json` / `Employer.csv` / `Employer.txt`.
- **`create-rest-bp-endpoint`** — `bp_class`: `MCPTest.BP.QueryService`; leave other fields empty to accept the defaults the prompt proposes, or set them to match your existing production. With this repo's `docker compose`, the **web** port is mapped to **9092** on the host; a typical run of the prompt registers a CSP/REST web application under **`/rest/user/...`** and a production item **`QueryService-REST-BS`** (`EnsLib.REST.GenericService`) that forwards to the **`QueryService`** business process. Before calling it, ensure demo data exists by invoking the **`run_class_method`** tool with `class_name`: `MCPTest.Employer`, `method_name`: `PopulateAndAssign`, `args`: `[]` (or rely on `iris.script`, which populates only when the table is still empty after import). Then validate the endpoint from a shell (**`-i`** prints response headers; on macOS/Linux use `curl` instead of `curl.exe`):

  ```bash
  # Employees for one employer (employer-id is required for this mode)
  curl.exe -sS -i "http://localhost:9092/rest/user/queryservice-rest-bs/QueryService-REST-BS" -H "service: employees" -H "employer-id: 1"

  # All employers
  curl.exe -sS -i "http://localhost:9092/rest/user/queryservice-rest-bs/QueryService-REST-BS" -H "service: employers"
  ```

  Expected: **`HTTP/1.1 200 OK`** and **`Content-Type: application/json`**. The `service` header is matched case-insensitively; `employee` (singular) is accepted as an alias for `employees`. If your web path or business service **Name** in production differs, replace the URL segment after `/rest/user/` and the final path segment (`QueryService-REST-BS`) accordingly.

</details>

---

## Configuration

This section picks up where the **Quick start** left off: bootstrapping a brand-new MCP server from this layout, wiring the server into Cursor and Claude Desktop, and (optionally) publishing to PyPI so others can install it with `uvx`.

### Project layout

```
iris-mcp-blueprint/
├── pyproject.toml              # Package metadata + 3 runtime deps + CLI entry-point
├── uv.lock                     # Pinned transitive versions (committed)
├── docker-compose.yml          # IRIS Community container (web 9092, super 9091)
├── Dockerfile / iris.script    # Class import + optional demo data on first start
├── example_data/               # Sample CSV (e.g. patients.csv) for prompts
├── src/
│   ├── iris_mcp_blueprint/     # Python MCP server
│   │   ├── mcp_app.py          # FastMCP instance + IRIS connection lifespan
│   │   ├── entrypoint.py       # CLI entry-point (stdio / SSE transport)
│   │   ├── tools/              # @mcp.tool handlers (SQL, globals, Atelier, interop, …)
│   │   ├── prompts/            # @mcp.prompt handlers (workflows)
│   │   └── resources/          # @mcp.resource handlers (read-only data)
│   └── MCPTest/                # ObjectScript demo classes (Employer, BP/QueryService, …)
└── README.md
```

Only **three runtime dependencies** are pinned in `pyproject.toml` (`fastmcp`, `intersystems-irispython`, `requests`); the rest of the transitive graph lives in `uv.lock`. There's no `requirements.txt`.

### Initialize a new MCP project

The easiest route is to **clone this repo as a template** and rename the package, but you can also bootstrap from scratch with `uv`. Either way, the pieces are always the same: a `pyproject.toml` script entry, a FastMCP `mcp_app`, and one or more `@mcp.tool` / `@mcp.prompt` / `@mcp.resource` handlers.

<details>
<summary><strong>Option 1</strong> — fork / clone this repo and rename it</summary>

1. Clone, then rename the package directory `src/iris_mcp_blueprint/` and update the imports / entry point that reference it.
2. In `pyproject.toml`, change `name`, `description`, `authors`, and the `[project.scripts]` line so the CLI command and entry-point match the new package (`my-mcp = "my_mcp.entrypoint:main"`).
3. Adjust IRIS-specific defaults in `mcp_app.py` if your server should default to a different host/port/namespace.
4. Add or remove handlers under `tools/`, `prompts/`, `resources/`. Each new module must be **imported** from `entrypoint.py` (or wherever `mcp_app.run()` is invoked) so the decorators register before the server starts.
5. Run `uv sync` once to refresh the lockfile, then `uv run my-mcp --help` to smoke-test the new CLI name.

</details>

<details>
<summary><strong>Option 2</strong> — bootstrap a new package from scratch with <code>uv</code></summary>

```bash
uv init --package my-mcp           # creates pyproject.toml, src/my_mcp/, etc.
cd my-mcp
uv add fastmcp intersystems-irispython requests
```

Then, in `src/my_mcp/mcp_app.py`:

```python
from fastmcp import FastMCP

mcp = FastMCP("my-mcp")
```

Add a tool in `src/my_mcp/tools/echo.py`:

```python
from my_mcp.mcp_app import mcp

@mcp.tool()
def echo(message: str) -> str:
    """Return the message unchanged."""
    return message
```

Add an entry point in `src/my_mcp/entrypoint.py`:

```python
from my_mcp.mcp_app import mcp

def main() -> None:
    mcp.run()
```

Wire it up in `pyproject.toml`:

```toml
[project.scripts]
my-mcp = "my_mcp.entrypoint:main"
```

Then `uv run my-mcp` launches the server over stdio.

</details>

### IRIS connection environment variables

<details>
<summary>Click to expand — table of <code>IRIS_*</code> variables (host, port, namespace, credentials) the server reads at startup</summary>

The server reads these at startup with `os.getenv()`. Set them wherever you launch the server from (shell, `mcp.json` `env` block, Docker environment, CI secrets store). Note that there's **no** automatic `.env` file loading.

| Variable | Default | Description |
|---|---|---|
| `IRIS_HOSTNAME` | `localhost` | IRIS host |
| `IRIS_PORT` | `9091` | SuperServer TCP port (`1972` is the default value for the IRIS instance, while `9091` is the value of the example Docker mapping) |
| `IRIS_WEB_PORT` | `9092` | Management Portal / REST APIs port (`52773` is the default value for the IRIS instance, while `9092` is the value of the example Docker mapping) |
| `IRIS_NAMESPACE` | `USER` | IRIS namespace |
| `IRIS_USERNAME` | `_SYSTEM` | IRIS username |
| `IRIS_PASSWORD` | `SYS` | IRIS password |

For SSE / HTTP transport you can also set `MCP_TRANSPORT`, `FASTMCP_HOST`, and `FASTMCP_PORT` (see **Run the server from the terminal** below).

</details>

### Run the server from the terminal

<details>
<summary>Click to expand — choose between <code>stdio</code> (default, used by Cursor/Claude) and <code>sse</code> (HTTP for remote clients)</summary>

The server supports two transports. Pick the one that matches **how the MCP client will reach it**:

| Transport | When to use it | How the client connects |
|---|---|---|
| **`stdio`** *(default)* | The MCP client (Cursor, Claude Desktop, …) lives on the **same machine** and can spawn the server as a subprocess. This is what every example earlier in this README uses. | Client launches the `command` from its `mcp.json` and reads/writes JSON over `stdin`/`stdout`. |
| **`sse`** *(HTTP / Server-Sent Events)* | The client is **on a different machine**, in a sandbox, or otherwise can't spawn subprocesses. The server runs as a long-lived HTTP service and the client connects to a URL. | `GET http://<host>:<port>/sse` (the SSE endpoint exposed by FastMCP). |

#### `stdio` (default — what Cursor / Claude Desktop normally use)

You usually do **not** start `stdio` mode by hand — your MCP client launches it for you using the JSON config in [Configure Cursor or Claude Desktop](#configure-cursor-or-claude-desktop). The same command works in a terminal if you want to verify it manually:

```bash
uv run iris-mcp-blueprint
```

The process now waits for an MCP client on `stdin`. Press **Ctrl+C** to stop. There is nothing to "open" in a browser; this transport is meant for a parent process.

#### `sse` (remote / HTTP)

Use this when the client cannot spawn the server itself — for example a remote IDE, a hosted assistant, or you want several users to share one server instance.

1. Start the server explicitly in SSE mode and bind it to an interface and port reachable by the client. `0.0.0.0` listens on **all** network interfaces; `127.0.0.1` is loopback-only.

   ```bash
   uv run iris-mcp-blueprint --transport sse --host 0.0.0.0 --port 8000
   ```

   Equivalent using environment variables (handy in `docker run`, `systemd` units, etc.):

   ```bash
   MCP_TRANSPORT=sse FASTMCP_HOST=0.0.0.0 FASTMCP_PORT=8000 uv run iris-mcp-blueprint
   ```

   Defaults if you omit them: `--transport stdio`, `--host 127.0.0.1`, `--port 8000` (these are also the values returned when `--help` is invoked).

2. Make sure firewalls / Docker / cloud security groups allow inbound traffic to that port from the client.

3. Point the client at the SSE endpoint. Replace `<host>` with the address that is reachable from the client (`localhost` if it's the same machine, otherwise the public/LAN IP or DNS name); the path is always `/sse`:

   ```text
   http://<host>:8000/sse
   ```

   In Cursor, that goes in **Settings → MCP → Add server (SSE / URL)**. In Claude Desktop, use a JSON entry such as:

   ```json
   {
     "mcpServers": {
       "iris-mcp-blueprint": {
         "url": "http://<host>:8000/sse",
         "env": {
           "IRIS_HOSTNAME": "localhost",
           "IRIS_PORT": "9091",
           "IRIS_WEB_PORT": "9092",
           "IRIS_NAMESPACE": "USER",
           "IRIS_USERNAME": "_SYSTEM",
           "IRIS_PASSWORD": "SYS"
         }
       }
     }
   }
   ```

4. Quick smoke-test from any host that can reach the URL — the SSE endpoint should keep the connection open and stream events (you'll see `event:` / `data:` lines):

   ```bash
   curl -N http://<host>:8000/sse
   ```

> **Security note**: SSE mode does **not** add authentication on top — anyone who can reach the URL can call the tools (and therefore your IRIS instance). Bind to `127.0.0.1`, put a reverse proxy in front, or run it inside a private network.

</details>

### Configure Cursor or Claude Desktop

<details>
<summary>Click to expand — Local (<code>uv run</code>) vs Remote (<code>uvx</code>) JSON snippets for Cursor and Claude Desktop</summary>

There are two distribution modes for any MCP client config: **local** (`uv run` against a clone you maintain locally) and **remote** (`uvx` pulling the package from GitHub or PyPI on demand). Pick one per server — they're not meant to be combined.

| | Local (`uv run`) | Remote (`uvx`) |
|---|---|---|
| Requires cloning the repo | Yes | No |
| Reads `pyproject.toml` / `uv.lock` from | Local disk | GitHub / PyPI |
| Builds a wheel | No (editable source) | Yes (temporary, invisible) |
| Changes to `.py` files | Reflected immediately | Require a new commit + push (or republish) |
| Best for | Development | Sharing / distribution |

#### 1. Local: `uv run` against a cloned MCP

Clone this GitHub repository on a local folder and run the Docker container.

**Cursor** — create or edit `.cursor/mcp.json` in the repo root. Cursor uses the **workspace folder** as the MCP server's working directory, so a plain `uv` command works without any extra path:

<details>
<summary>Cursor JSON (local)</summary>

```json
{
  "mcpServers": {
    "iris-mcp-blueprint": {
      "command": "uv",
      "args": ["run", "iris-mcp-blueprint"],
      "env": {
        "IRIS_HOSTNAME": "localhost",
        "IRIS_PORT": "9091",
        "IRIS_WEB_PORT": "9092",
        "IRIS_NAMESPACE": "USER",
        "IRIS_USERNAME": "_SYSTEM",
        "IRIS_PASSWORD": "SYS"
      }
    }
  }
}
```

Other top-level keys you may already have in the `.json` file can stay alongside `mcpServers`.

</details>

**Claude Desktop** — Claude Desktop does **not** inherit a workspace folder, and on Windows the `uv` executable is often outside of Claude's `PATH`. To make a local launch reliable you usually have to:

1. Point `command` at the **absolute path to `uv.exe`** (or to the `uv` binary on macOS / Linux).
2. Pass `--directory <repo-root>` to `uv` so it finds `pyproject.toml`.

Config file locations:

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

<details>
<summary>Claude Desktop JSON (local, Windows)</summary>

Replace the two absolute paths with yours.

```json
{
  "mcpServers": {
    "iris-mcp-blueprint": {
      "command": "C:\\Users\\<you>\\.local\\bin\\uv.exe",
      "args": [
        "--directory",
        "C:\\path\\to\\iris-mcp-blueprint",
        "run",
        "iris-mcp-blueprint"
      ],
      "env": {
        "IRIS_HOSTNAME": "localhost",
        "IRIS_PORT": "9091",
        "IRIS_WEB_PORT": "9092",
        "IRIS_NAMESPACE": "USER",
        "IRIS_USERNAME": "_SYSTEM",
        "IRIS_PASSWORD": "SYS"
      }
    }
  }
}
```

Find your own `uv.exe` location with `where uv` in Windows Terminal (typically `C:\Users\<you>\.local\bin\uv.exe` after `pip install uv`).

On macOS / Linux a similar shape works. Just adjust the uv path and use a forward-slash repo path.

After editing the JSON, **fully quit Claude Desktop from the system tray** (closing the window is not enough) and relaunch. Cursor only needs the MCP server reload icon.

</details>

#### 2. Remote: `uvx` from GitHub or PyPI

`uvx` downloads the package, builds it in a temporary isolated environment, and runs it — no clone, no `uv sync`, no manual venv. The user only needs `uv` installed.

<details>
<summary>From GitHub (after the repository has been pushed)</summary>

Adjust `IRIS_*` for your environment.

**Cursor** — `.cursor/mcp.json` (uses just `uvx`; Cursor inherits `PATH` so this works on Windows, macOS, and Linux):

```json
{
  "mcpServers": {
    "iris-mcp-blueprint": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/pietrodileo/iris-mcp-blueprint.git",
        "iris-mcp-blueprint"
      ],
      "env": {
        "IRIS_HOSTNAME": "localhost",
        "IRIS_PORT": "9091",
        "IRIS_WEB_PORT": "9092",
        "IRIS_NAMESPACE": "USER",
        "IRIS_USERNAME": "_SYSTEM",
        "IRIS_PASSWORD": "SYS"
      }
    }
  }
}
```

**Claude Desktop on Windows** — `claude_desktop_config.json` (use the absolute path to `uvx.exe`):

```json
{
    "mcpServers": {
        "iris-mcp-blueprint": {
            "command": "C:\\Users\\p.dileo\\.local\\bin\\uvx.exe",
            "args": [
                "--from", "git+https://github.com/pietrodileo/iris-mcp-blueprint.git",
                "iris-mcp-blueprint"
            ],
            "env": {
                "IRIS_HOSTNAME": "localhost",
                "IRIS_PORT": "9091",
                "IRIS_WEB_PORT": "9092",
                "IRIS_NAMESPACE": "USER",
                "IRIS_USERNAME": "_SYSTEM",
                "IRIS_PASSWORD": "SYS"
            }
        }
    }
}
```

</details>

<details>
<summary>From PyPI (after publishing)</summary>

You can wire it into any client `mcp.json` using `uvx` and calling directly package name `iris-mcp-blueprint`:

```json
{
  "mcpServers": {
    "iris-mcp-blueprint": {
      "command": "uvx",
      "args": ["iris-mcp-blueprint"],
      "env": { "IRIS_HOSTNAME": "...", "IRIS_PORT": "1972" }
    }
  }
}
```

</details>

</details>

### Publish to PyPI

<details>
<summary>Click to expand — bump the version, <code>uv build</code>, then <code>uv publish</code> with a PyPI token exported as <code>UV_PUBLISH_TOKEN</code>, and verify with <code>uvx</code></summary>

Once the project is ready to share, build a wheel and upload it to PyPI so anyone with `uv` installed can run it via `uvx iris-mcp-blueprint` without cloning the repo first.

1. **Bump the version.** PyPI rejects re-uploads of an existing version, so every release needs a new number. Use `uv version` to update `pyproject.toml` (and `uv.lock`) in one step:

   ```bash
   uv version --bump patch    # 0.1.0 -> 0.1.1
   uv version --bump minor    # 0.1.0 -> 0.2.0
   uv version --bump major    # 0.1.0 -> 1.0.0
   uv version 1.2.3           # set an explicit version
   uv version                 # just print the current version
   ```

2. **Build distributable artifacts:**

   ```bash
   uv build      # writes sdist + wheel into dist/
   ```

3. **Get a PyPI token.** Log in to [PyPI](https://pypi.org/manage/account/token/) and create an API token (project-scoped is recommended once the project exists; otherwise use an account-wide token for the first upload). The token always starts with `pypi-`.

4. **Publish with the token.** Export the token as `UV_PUBLISH_TOKEN` so it does not end up in your shell history; `uv publish` reads it automatically:

   ```bash
   # Linux / macOS / Git Bash
   export UV_PUBLISH_TOKEN=pypi-<your-token>
   uv publish

   # PowerShell
   $env:UV_PUBLISH_TOKEN = "pypi-<your-token>"
   uv publish
   ```

5. **Verify the public install** (uses the freshly uploaded version, no `git` needed):

   ```bash
   uvx iris-mcp-blueprint --help
   ```

After a successful upload, switch any client `mcp.json` from the GitHub form to the simpler PyPI form shown above.

</details>
