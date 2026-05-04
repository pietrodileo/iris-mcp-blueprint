# IRIS MCP Blueprint

> ⚠️ **This repository is an example, not a finished product.** It is a *blueprint* showing **how to build an MCP server for InterSystems IRIS** that performs operations across several tool categories — **SQL**, **Globals**, **Class methods**, **Atelier API**, and **Interoperability** (see [`src/iris_mcp_blueprint/tools/`](src/iris_mcp_blueprint/tools/)) — plus reusable **prompts** and **resources**. It is **not** intended to be a comprehensive, drop-in MCP server for any IRIS workload. Treat it as a **starting point**: clone it, keep what you need, remove what you don't, and **tailor the tools, prompts, and resources to your own IRIS application** (your namespaces, classes, productions, security model, business rules, etc.). The accompanying ObjectScript demo under `src/MCPTest/` exists only to give the included tools/prompts something to work against.

An **InterSystems IRIS**-backed **[FastMCP](https://gofastmcp.com/)** server that exposes IRIS tools, prompts, and resources to any MCP-compatible client (Cursor, Claude Desktop, and others). The Python package under `src/iris_mcp_blueprint/` connects to IRIS over the Native SDK and wraps common tasks (SQL, globals, Atelier search, production interoperability, class methods, and more). Example **ObjectScript** classes in `src/MCPTest/` (including `MCPTest.BP.QueryService`) demonstrate patterns you can drive from the MCP tools or from guided **prompts**.

---

## Prerequisites

| Tool | Why it’s needed | Source / version pin in this repo |
|---|---|---|
| **Python 3.12** | Runtime that satisfies `requires-python = ">=3.12"` in `pyproject.toml` | `.python-version` ⇒ `3.12` (read by `uv` to provision the venv) |
| **[uv](https://docs.astral.sh/uv/) ≥ 0.5** | Installs deps from `pyproject.toml` + `uv.lock`, runs the CLI (`uv run`) and remote builds (`uvx`) | Versions older than 0.5 may not understand the lockfile or `uv init --package` |
| **Docker** with `docker compose` v2 | Runs the IRIS database container described by `docker-compose.yml` | Image: `intersystems/iris-community:latest-cd` (see `Dockerfile`) |
| **Git** | Cloning this repo (and any `uvx --from git+...` install of remote forks) | — |
| **`curl`** *(optional)* | Smoke-test the demo REST endpoint exposed by `MCPTest.BP.QueryService` | On Windows, the bundled `curl.exe` is fine |
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

> **Order matters.** The MCP server connects to IRIS at startup. If you launch it before IRIS is reachable, **every IRIS-backed tool will fail with a connection error**. Always do the steps **in this order**: ① clone the repo → ② start the IRIS Docker container → ③ set the IRIS env vars in your MCP client config → ④ start (or restart) the MCP server from the client.

### 1. Clone the repo

```bash
git clone https://github.com/<you>/iris-mcp-blueprint.git
cd iris-mcp-blueprint
```

Optional smoke-check that the MCP server starts at all (this also bootstraps `.venv/` from `pyproject.toml` + `uv.lock` on first run):

```bash
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

Prompts are short, reusable **workflow instructions** returned by `@mcp.prompt` handlers in `src/iris_mcp_blueprint/prompts/prompts.py`. They do not run code by themselves; they tell the assistant which **tools** to call and in what order (for example: `get_class_source`, `add_production_item`, `run_class_method`).

### Available prompts (quick reference)

| Prompt name | Purpose (summary) |
| --- | --- |
| `analyze-table` | Inspect a table’s structure, sample rows, and suggest indexes. |
| `explore-class` | Read a class with `get_class_source`, summarize methods, properties, and storage. |
| `import-csv-workflow` | Safe CSV import: validate name, call `import_csv_to_iris`, verify with `describe_table` / `fetch_data`. |
| `search-for-code` | Search class sources with `search_code`, then optionally deep-dive with `explore-class`. |
| `analyze-table-globals-content` | Map a persistent class / table to globals and explain how data is stored. |
| `create-rest-bp-endpoint` | Wire a Business Process to HTTP: production items (`EnsLib.REST.GenericService` + BP), `register_web_application`, `update_production`; for `MCPTest.BP.QueryService`, run `PopulateAndAssign` before testing. |

### What each prompt does (more detail)

**`analyze-table`** — Data-engineering review of a single SQL table. Arguments: **`table_name`** (required), **`schema_name`** (optional; if empty the workflow asks you to pick a schema, defaulting to `SQLUser`). The embedded steps drive **`res_tables_all`** (when the schema is unknown), **`describe_table`** for columns and types, **`fetch_data`** for a small sample (first five rows), and finally a written recommendation for **indexes** that would help typical access patterns.

**`explore-class`** — Source-level tour of one **ObjectScript class**. Argument: **`query`** = full class name (for example `MCPTest.BP.QueryService`). The model uses **`get_class_source`**, then summarizes **InstanceMethods / ClassMethods**, **properties**, and—when present—the **`<Storage>`** block and related **globals**. Use it whenever you need a readable overview before editing or documenting code. Several other prompts chain into `explore-class` for deeper analysis.

**`import-csv-workflow`** — End-to-end **CSV → new IRIS table** flow. Arguments: **`table_name`**, a **`csv_sample`** string (headers plus a few rows are enough), and optional **`table_schema`**. The assistant infers types from the sample, checks whether the target already exists via **`res_tables_all`**, refuses to overwrite blindly, then calls **`import_csv_to_iris`**. After load, it uses **`describe_table`** and **`fetch_data`** (for example `SELECT COUNT(*)`) to verify shape and row counts, then may suggest **`create_index`** once you agree on index names. Ideal for ad hoc data loads separate from the packaged `MCPTest` classes. **You can try this prompt with the sample CSV shipped in [`example_data/patients.csv`](example_data/patients.csv)**: paste its first few lines (header + a handful of rows) into `csv_sample`, set **`table_name`** to a fresh name such as `Patients`, and optionally **`table_schema`** to `MCPTest` (or any schema you like) — the workflow will create the table and load all rows.

**`search-for-code`** — **Atelier-style** discovery across the namespace. Argument: **`query`** = any text to find in class sources (API name, method name, fragment of ObjectScript). Steps: **`search_code`** → list of matching classes → you choose which hits matter → those classes are studied further (the prompt text tells the model to reuse **`explore-class`**) → short explanation of *how* the string appears in each chosen class. Good for refactors, security reviews, or learning how a pattern is used in your application.

**`analyze-table-globals-content`** — Goes **below SQL** to the **global nodes** backing a persistent class. Arguments: **`table_name`**, optional **`table_schema`**; the class is treated as `{table_schema}.{table_name}` when that matches your persistent package. The workflow locates **DataLocation**, **IdLocation**, **IndexLocation**, **StreamLocation**, lists every **distinct global** and its role (data vs index vs stream), and may call **`check_global`** / **`check_global_content`** or **`fetch_data`** to correlate raw `$LIST` nodes with logical rows. Use it when you care about physical layout, replication, or backup scope—not only column names.

**`create-rest-bp-endpoint`** — **Interoperability** recipe: expose a **`Ens.BusinessProcess`** subclass over HTTP using **`EnsLib.REST.GenericService`**. Arguments include **`bp_class`** (for example `MCPTest.BP.QueryService`) and optional **`bp_config_name`**, **`bs_config_name`**, **`web_app_path`**, **`production_name`**. The scripted steps verify **`OnRequest`** / **`EnsLib.HTTP.GenericMessage`**, ensure an **active production**, **`add_production_item`** for the BP and the REST BS (with **`TargetConfigNames`**), **`register_web_application`**, **`update_production`**, optional **`list_production_items`**, demo data via **`run_class_method`** when the BP is `MCPTest.BP.QueryService`, BS setting tweaks as in the prompt, then documentation of the URL pattern **`http://<host>:<webport><web_app_path>/<bs_config_name>`** and an HTTP smoke test. After running it, validate with the **curl** examples in [Testing the demo REST service (QueryService)](#testing-the-demo-rest-service-queryservice).

### How to test them (Cursor and similar clients)

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
- **`create-rest-bp-endpoint`** — `bp_class`: `MCPTest.BP.QueryService`; leave other fields empty to accept the defaults the prompt proposes, or set them to match your existing production. With this repo's `docker compose`, the **web** port is mapped to **9092** on the host; a typical run of the prompt registers a CSP/REST web application under **`/rest/user/...`** and a production item **`QueryService-REST-BS`** (`EnsLib.REST.GenericService`) that forwards to the **`QueryService`** business process. Before calling it, ensure demo data exists by invoking the **`run_class_method`** tool with `class_name`: `MCPTest.Employer`, `method_name`: `PopulateAndAssign`, `args`: `[]` (or rely on `iris.script`, which populates only when the table is still empty after import). Then validate the endpoint from a shell (**`-i`** prints response headers; on macOS/Linux use `curl` instead of `curl.exe`):

  ```bash
  # Employees for one employer (employer-id is required for this mode)
  curl.exe -sS -i "http://localhost:9092/rest/user/queryservice-rest-bs/QueryService-REST-BS" -H "service: employees" -H "employer-id: 1"

  # All employers
  curl.exe -sS -i "http://localhost:9092/rest/user/queryservice-rest-bs/QueryService-REST-BS" -H "service: employers"
  ```

  Expected: **`HTTP/1.1 200 OK`** and **`Content-Type: application/json`**. The `service` header is matched case-insensitively; `employee` (singular) is accepted as an alias for `employees`. If your web path or business service **Name** in production differs, replace the URL segment after `/rest/user/` and the final path segment (`QueryService-REST-BS`) accordingly.

---

## Configuration

This section covers everything you need beyond the **Quick start**: bootstrapping a brand-new MCP server from this layout, wiring the server into Cursor and Claude Desktop, and (optionally) publishing to PyPI for `uvx`-style installs.

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

Only **three runtime dependencies** are pinned in `pyproject.toml` (`fastmcp`, `intersystems-irispython`, `requests`); transitive versions live in `uv.lock`. There is no `requirements.txt`.

### Initialize a new MCP project

The fastest path is to **clone this repo as a template** and rename the package, but you can also bootstrap from scratch with `uv`. Either way, the moving parts are the same: a `pyproject.toml` script entry, a FastMCP `mcp_app`, and one or more `@mcp.tool` / `@mcp.prompt` / `@mcp.resource` handlers.

**Option 1 — fork/clone this repo and rename it**

1. Clone, then rename the package directory `src/iris_mcp_blueprint/` and update the imports / entry point that reference it.
2. In `pyproject.toml`, change `name`, `description`, `authors`, and the `[project.scripts]` line so the CLI command and entry-point match the new package (`my-mcp = "my_mcp.entrypoint:main"`).
3. Adjust IRIS-specific defaults in `mcp_app.py` if your server should default to a different host/port/namespace.
4. Add or remove handlers under `tools/`, `prompts/`, `resources/`. Each new module must be **imported** from `entrypoint.py` (or wherever `mcp_app.run()` is invoked) so the decorators register before the server starts.
5. Run `uv sync` once to refresh the lockfile, then `uv run my-mcp --help` to smoke-test the new CLI name.

**Option 2 — bootstrap a new package from scratch**

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
import my_mcp.tools.echo  # noqa: F401  -- registers @mcp.tool

def main() -> None:
    mcp.run()
```

Wire it up in `pyproject.toml`:

```toml
[project.scripts]
my-mcp = "my_mcp.entrypoint:main"
```

Then `uv run my-mcp` launches the server over stdio.

### IRIS connection environment variables

The server reads these at startup with `os.getenv()`. Set them wherever you launch the server (shell, `mcp.json` `env` block, Docker environment, CI secrets store). There is **no** automatic `.env` file loading.

| Variable | Default | Description |
|---|---|---|
| `IRIS_HOSTNAME` | `localhost` | IRIS host |
| `IRIS_PORT` | `1972` | SuperServer TCP port (`9091` in the sample Docker mapping) |
| `IRIS_WEB_PORT` | `52773` | Management Portal / REST APIs port (`9092` in the sample Docker mapping) |
| `IRIS_NAMESPACE` | `USER` | IRIS namespace |
| `IRIS_USERNAME` | `_SYSTEM` | IRIS username |
| `IRIS_PASSWORD` | `SYS` | IRIS password |

For SSE / HTTP transport you can also set `MCP_TRANSPORT`, `FASTMCP_HOST`, and `FASTMCP_PORT` (see **Run the server from the terminal** below).

### Run the server from the terminal

**stdio** (default — for subprocess-based MCP clients like Cursor):

```bash
uv run iris-mcp-blueprint
```

**SSE / HTTP** (for remote clients that cannot spawn a subprocess):

```bash
uv run iris-mcp-blueprint --transport sse --host 0.0.0.0 --port 8000
```

Remote clients connect to `http://<host>:8000/sse`. The same options can be set via env vars:

```bash
MCP_TRANSPORT=sse FASTMCP_HOST=0.0.0.0 FASTMCP_PORT=8000 uv run iris-mcp-blueprint
```

### Configure Cursor or Claude Desktop

There are two distribution modes for any MCP client config: **local** (`uv run` against a clone you maintain) and **remote** (`uvx` pulling the package from GitHub or PyPI on demand). Pick one per server.

| | Local (`uv run`) | Remote (`uvx`) |
|---|---|---|
| Requires cloning the repo | Yes | No |
| Reads `pyproject.toml` / `uv.lock` from | Local disk | GitHub / PyPI |
| Builds a wheel | No (editable source) | Yes (temporary, invisible) |
| Changes to `.py` files | Reflected immediately | Require a new commit + push (or republish) |
| Best for | Development | Sharing / distribution |

#### Local: `uv run` against a clone

**Cursor** — create or edit `.cursor/mcp.json` in the repo root:

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

> **Windows note:** Cursor may not set the working directory to the repo root automatically. If `uv` cannot find `pyproject.toml`, add a `"cwd"` key:
>
> ```json
> "cwd": "C:\\path\\to\\iris-mcp-blueprint"
> ```

**Claude Desktop** — same `mcpServers` block, placed in the Claude config file. Always set `"cwd"` to the absolute path of the cloned repo so `uv` finds `pyproject.toml`.

Config file location:
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "iris-mcp-blueprint": {
      "command": "uv",
      "args": ["run", "iris-mcp-blueprint"],
      "cwd": "/path/to/iris-mcp-blueprint",
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

#### Remote: `uvx` from GitHub or PyPI

`uvx` downloads the package, builds it in a temporary isolated environment, and runs it — no clone, no `uv sync`, no manual venv. The user only needs `uv` installed.

**From GitHub** (works as soon as the repo is pushed; same JSON for Cursor and Claude Desktop):

```json
{
  "mcpServers": {
    "iris-mcp-blueprint": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/<you>/iris-mcp-blueprint",
        "iris-mcp-blueprint"
      ],
      "env": {
        "IRIS_HOSTNAME": "<your-iris-host>",
        "IRIS_PORT": "1972",
        "IRIS_WEB_PORT": "52773",
        "IRIS_NAMESPACE": "USER",
        "IRIS_USERNAME": "_SYSTEM",
        "IRIS_PASSWORD": "<your-password>"
      }
    }
  }
}
```

**From PyPI** (after publishing — see the next section):

```bash
uvx iris-mcp-blueprint
```

Or, in any client `mcp.json`:

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

### Publish to PyPI

Once the project is ready to share, build a wheel and upload it so anyone with `uv` installed can run it via `uvx iris-mcp-blueprint`.

1. Bump `version` in `pyproject.toml` (PyPI rejects re-uploads of an existing version).
2. Build distributable artifacts:

   ```bash
   uv build      # writes sdist + wheel into dist/
   ```

3. Publish:

   ```bash
   uv publish    # uses PYPI_TOKEN env var or credentials in ~/.pypirc
   ```

   For a dry run, target **TestPyPI** first:

   ```bash
   uv publish --publish-url https://test.pypi.org/legacy/
   uvx --index-url https://test.pypi.org/simple/ iris-mcp-blueprint
   ```

4. Verify the public install:

   ```bash
   uvx iris-mcp-blueprint --help
   ```

After a successful upload, switch any client `mcp.json` from the GitHub form to the simpler PyPI form shown above.
