from fastmcp import Context
import logging

from iris_mcp_blueprint.mcp_app import mcp

logger = logging.getLogger(__name__)    

# --- CLASS METHODS TOOLS ---

@mcp.tool()
def run_class_method(ctx: Context, class_name: str, method_name: str, args: list = []) -> str:
    """
    Run an ObjectScript ClassMethod.
    Args:
        ctx: The context of the tool call.
        class_name: The name of the class to run the method on.
        method_name: The name of the method to run.
        args: The arguments to pass to the method.
    """
    iris = ctx.request_context.lifespan_context["iris"]
    try:
        return f"Result: {iris.classMethodValue(class_name, method_name, *args)}"
    except Exception as e:
        return f"Error: {e}"

