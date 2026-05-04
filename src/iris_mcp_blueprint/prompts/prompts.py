from fastmcp import Context

from iris_mcp_blueprint.mcp_app import mcp

# --- PROMPTS FOR DATA ENGINEERING ---

@mcp.prompt("analyze-table") 
def analyze_table_prompt(table_name: str, schema_name: str = ""):
    """
    Creates a prompt that tells the AI to investigate a table's structure
    and suggest optimizations.
    Args:
        table_name: The name of the table to analyze.
        schema_name: The name of the schema to analyze.
    """
    return f"""I need you to analyze the InterSystems IRIS table: {schema_name}.{table_name}.
    Please perform the following steps:
    1. If table schema is not provided, use the 'res_tables_all' resource to get the list of tables and ask the user to select the schema. Default is 'SQLUser'.
    2. Use the 'describe_table' tool to see the columns and data types.
    3. Use 'fetch_data' to look at the first 5 rows.
    4. Suggest any indexes that might improve performance for this table.
    """

@mcp.prompt("explore-class")
def explore_class_prompt(query: str):
    """
    Creates a prompt that tells the AI to study a class and suggest a new method for it.
    Args:
        query: The name of the class to analyze.
    """
    return f"""I need you to explore the InterSystems IRIS class: {query}.
    Please perform the following steps:
    1. Use 'get_class_source' to read the current implementation of {query}.
    2. Identify the existing ClassMethods and properties.
    3. If a storage is present, analyze the globals associated with the class.
    4. Explain what the class does."""

@mcp.prompt("import-csv-workflow")
def import_csv_workflow(table_name: str, csv_sample: str, table_schema: str = ""):
    """
    A guided workflow for the AI to handle CSV imports securely.
    Args:
        table_name: The name of the table to import data into.
        csv_sample: A sample of the CSV data to import.
        table_schema: The name of the schema to import data into.
    """
    return f"""You are an IRIS Data Engineer. I need to import data into a new table named '{table_schema}.{table_name}'.

    Here is a sample of the CSV data:
    {csv_sample}

    Please follow these steps:
    1. Analyze the headers and data types in the sample.
    2. Check if a table with that name already exists using 'res_tables_all' resource. If exists, stop the process and inform the user. If not exist, inform the user that table name will be {table_schema}.{table_name}.
    3. Use the 'import_csv_to_iris' tool to create the table and perform the batch insert.
    4. After the import, use 'describe_table' to verify the schema was created correctly.
    5. If table schema is not provided, ask the user to select the schema. Default is 'SQLUser'.
    6. Run a 'fetch_data' query (SELECT COUNT(*) FROM {table_schema}.{table_name}) to confirm the row count matches the input.
    7. Use the 'analyze_table_prompt' to analyze the class and suggest possible improvements.
    8. If the user agrees with your proposal, create indexes on the proper columns using the 'create_index' tool, asking for index names.
    """

@mcp.prompt("export-table")
def export_table_prompt(table_name: str, format: str = "json", table_schema: str = ""):
    """
    Guided workflow that helps the AI export an existing IRIS table to JSON, CSV,
    or TXT. The AI inspects the table first, helps the user pick a sensible scope
    (full table vs. filtered subset), then calls the 'export_table' tool and
    previews the result.

    Args:
        table_name: The name of the table to export (no schema).
        format: The output format — 'json' (list of objects), 'csv' (RFC 4180),
            or 'txt' (pipe-separated table). Default is 'json'.
        table_schema: The schema of the table (optional; if empty the AI will
            help select one, defaulting to 'SQLUser').
    """
    fmt = (format or "json").strip().lower()
    fqn = f"{table_schema}.{table_name}" if table_schema else table_name
    return f"""You are an IRIS Data Engineer. The user wants to export the table '{fqn}' as {fmt.upper()}.
    Please follow these steps:
    1. If 'table_schema' is empty, list candidates with the 'res_tables_all' resource (or the 'get_tables' tool) and ask the user to choose. Default is 'SQLUser'. Once chosen, use '<chosen_schema>.{table_name}' as the fully-qualified name from now on.
    2. Use 'describe_table' with table_name='{table_name}' and the chosen schema to confirm the columns and types so the user knows what will be exported.
    3. Use 'fetch_data' with the SQL `SELECT COUNT(*) FROM <chosen_schema>.{table_name}` to report the total row count. If it exceeds ~10000 rows, warn the user that exporting everything in chat may be unreadable.
    4. Ask the user whether to:
       - export all rows (set 'limit' to 0 to disable the cap), OR
       - apply a 'WHERE' filter (passed as the 'where' argument, no leading 'WHERE' keyword), OR
       - select a subset of 'columns' (list of column names), OR
       - keep the default 'limit=1000' (recommended for chat preview).
    5. Confirm the requested 'format' is one of 'json', 'csv', 'txt'. Default to '{fmt}' otherwise.
    6. Call the 'export_table' tool with table_name='{table_name}', table_schema=<chosen_schema>, format='{fmt}', plus any agreed columns / where / limit.
    7. Show the user a short preview (first ~10 lines for csv/txt, or first ~5 items for json) and report the total length of the returned content.
    8. Tell the user how to persist the output (e.g. save to '<table_name>.{fmt}'). The exact mechanism depends on the host — Cursor users can copy the content into a new file; clients with file-write capability can write the file directly.
    9. If the tool returns a string starting with 'Export Error:' or 'Export failed', stop, surface the error verbatim, and ask the user how to proceed.
    """

# --- PROMPTS FOR ATELIER API ---

@mcp.prompt("search-for-code")
def search_for_code(query: str):
    """
    Creates a prompt that tells the AI to search for a particular string all across the classes and to analyze the classes that match the research.
    Args:
        query: The string to search for.
    """
    return f"""I need you to search for the following string all across the InterSystems IRIS classes content: {query}.
    Please perform the following steps:
    1. Use 'search_code' tool to search for the requested string across all classes.
    2. Provide the user a list of all the matching classes
    3. Ask the user if he wants to analyze some of the extracted classes.
    4. Collect user response and analyze the source code of the requested classes using the 'explore-class' prompt.
    5. Explain how the query string is involved and used in the classes the user requested.
    """

# --- PROMPTS FOR GLOBAL MANAGEMENT ---

@mcp.prompt("analyze-table-globals-content")
def analyze_table_globals_content_prompt(table_name: str, table_schema: str = ""):
    """
    Creates a prompt that tells the AI to extract the globals related to a specified table and show their content.
    The persistent class is typically f"{table_schema}.{table_name}" when SqlTableName matches the SQL name.
    Args:
        table_name: The name of the table to analyze.
        table_schema: The name of the schema to analyze.
    """
    cls = f"{table_schema}.{table_name}"
    return f"""I need you to find and analyze the globals for a specified table named '{cls}'.
    Please perform the following steps:
    1. If table schema is not provided, ask the user to select the schema. Default is 'SQLUser'.
    2. Use the 'explore-class' prompt with query '{cls}' to drive reading class source, or use 'get_class_source' for '{cls}' and locate the <Storage> block: DataLocation, IdLocation, ExtentLocation, each Index <Location>, IndexLocation, StreamLocation.
    3. List every distinct global name (e.g. top node before first comma in ObjectScript ^global(sub,...)) and what each is used for (data vs index vs stream).
    4. For data rows, you may use 'check_global' / 'check_global_content' on sample subscripts, or 'fetch_data' to confirm row content if raw global nodes are encoded ($LIST) and hard to read in the tool.
    5. Summarize: global tree involved and how the four patient rows (if any) are reached from the data global.
    """


# --- PROMPTS FOR INTEROPERABILITY ---

@mcp.prompt("create-rest-bp-endpoint")
def create_rest_bp_endpoint_prompt(
    bp_class: str,
    bp_config_name: str = "",
    bs_config_name: str = "",
    web_app_path: str = "",
    production_name: str = "",
):
    """
    Guided workflow that drives the AI through the standard pattern of exposing
    an InterSystems IRIS Business Process as an HTTP endpoint:

        Web Application  --->  Business Service (EnsLib.REST.GenericService)  --->  Business Process

    Args:
        bp_class: Full class name of the Business Process to expose
            (e.g. 'MCPTest.BP.QueryService').
        bp_config_name: Suggested config name of the BP in the production.
            If empty, the AI should derive one from `bp_class`.
        bs_config_name: Suggested config name of the BS. If empty, the AI
            should propose one (e.g. '<bp_config_name>-REST-BS').
        web_app_path: Suggested REST web app path (must start with '/'). If
            empty, the AI should propose '/rest/<namespace-lowercased>/<bs_config_name-REST-BS>'.
        production_name: Production class name. If empty, the active production
            is used.
    """
    bp_default = bp_config_name or bp_class.split(".")[-1]
    bs_default = bs_config_name or f"{bp_default}-REST-BS"
    web_default = web_app_path or f"/rest/<namespace-lowercased>/{bs_default.lower()}"
    prod_clause = (
        f"the production '{production_name}'"
        if production_name
        else "the currently active production (use the `get_active_production` tool to discover its name)"
    )

    return f"""You are an InterSystems IRIS Interoperability assistant. The user wants to expose
the Business Process **{bp_class}** as an HTTP/REST endpoint. The standard pattern is:

    HTTP client  -->  CSP Web Application  -->  EnsLib.REST.GenericService (Business Service)  -->  {bp_class} (Business Process)

Work against {prod_clause}. Follow these steps in order, asking the user for confirmation only on
naming choices that are not yet decided. Otherwise proceed automatically and report each step.

Step 1 - Verify the Business Process class
   - Call `get_class_source` on '{bp_class}' to confirm the class exists, extends `Ens.BusinessProcess`,
     and exposes an `OnRequest` method that accepts/returns `EnsLib.HTTP.GenericMessage`.
     If those preconditions are not met, stop and explain what is missing.

Step 2 - Ensure a target production exists
   - Call `get_active_production`. If there is no active production:
       * If `production_name` is set, use that class as the target (it need not be running yet).
       * Otherwise call `create_empty_production` with a new class name in your namespace
         (e.g. `MCPTest.EmptyProduction` or `MCPTest.InteropEmpty1`), then `start_production`
         on that class, and confirm with `get_active_production`.
   - If the user already named `production_name`, treat that class as the target for later steps.

Step 3 - Choose names (only ask if not provided)
   - Business Process config name (default: '{bp_default}').
   - Business Service config name (default: '{bs_default}').
   - Web application path (default: '{web_default}', adjusted to the current namespace). 
    The path must start with '/'.

Step 4 - Add the Business Process
   - Call `add_production_item` with:
       class_name='{bp_class}', config_name=<bp_config_name>, pool_size=0, enabled=true,
       comment='Business Process exposed via REST'.
     A pool_size of 0 is correct for BPL/Business Processes (on-demand jobs).
     If the target production class from step 2 is not the one currently running, pass
     `production_name=<that class>` on this and the following add/list/update steps.

Step 5 - Add the Business Service (REST entry point)
   - Call `add_production_item` with:
       class_name='EnsLib.REST.GenericService',
       config_name=<bs_config_name>,
       pool_size=1, enabled=true,
       comment='REST entry point routing to <bp_config_name>',
       settings={{"TargetConfigNames": "<bp_config_name>"}}.
     The `TargetConfigNames` setting is what wires the BS to the BP.

Step 6 - Register the Web Application
   - Call `register_web_application` with:
       path=<web_app_path>,
       dispatch_class='EnsLib.REST.GenericService',
       description='REST endpoint for <bp_config_name>'.
     This creates an unauthenticated REST application in the current namespace.
     Warn the user that authentication should be tightened before production use.

Step 7 - Apply the changes
   - Call `update_production` so the new items become active without a full restart.
   - Call `list_production_items` and report the resulting configuration to the user.

Step 8 - Prepare demo data when the BP is MCPTest.BP.QueryService
   - Before any HTTP test or handoff, if **{bp_class}** is `MCPTest.BP.QueryService`, call
     `run_class_method` with class_name=`MCPTest.Employer`, method_name=`PopulateAndAssign`,
     args=[] so Employer/Employee tables are populated and linked. Skip this step for other BPs.

Step 9 - Modify the Business Service 
   - Modify the Business Service settings to:
       PoolSize=empty,
       Port=empty,
       settings={{"TargetConfigNames": "<bp_config_name>"}}.
     The `TargetConfigNames` setting is what wires the BS to the BP.

Step 10 - Tell the user how to call the endpoint
   - The HTTP URL pattern for `EnsLib.REST.GenericService` is:
         http://<host>:<webport><web_app_path>/<bs_config_name>
     Example (USER namespace, typical QueryService wiring):
         http://localhost:9092/rest/user/queryservice-rest-bs/QueryService-REST-BS
     (Docker maps host port 9092 to IRIS web inside the container; adjust host/port if needed.)
   - For `MCPTest.BP.QueryService`, the client must send an HTTP header `service` with value
     `employers` (all companies) or `employees` (employees for one company; also send header
     `employer-id` with the company ID). The singular `employee` is accepted as an alias for `employees`.
     Header values are compared case-insensitively.
     Show a concrete example using the configured names and remind the user that the BP's
     `OnRequest` will receive the request as an `EnsLib.HTTP.GenericMessage` (HTTP headers
     in `pRequest.HTTPHeaders`, body in `pRequest.Stream`).
     Provide the user with the HTTP URL pattern to call the endpoint. 
     Perform a test call to the endpoint using the HTTP URL pattern to confirm the endpoint is working.
     Provide the user with the HTTP response.
     Provide the user with the HTTP response body.
     Provide the user with the HTTP response headers.
     Provide the user with the HTTP response status code.
     Provide the user with the HTTP response status message.
     Provide the user with the HTTP response status message.

If any step returns a string starting with 'ERROR:', stop, surface the error verbatim, and ask
the user how to proceed (e.g. pick a different name, remove the conflicting item with
`remove_production_item`, etc.). Never silently retry destructive actions.
"""
