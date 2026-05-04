import os
import sys
import logging
from contextlib import asynccontextmanager

from fastmcp import FastMCP
import iris as irisnative

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("iris-mcp-blueprint")

@asynccontextmanager
async def iris_lifespan(server: FastMCP):
    """
    Manages the IRIS connection lifecycle.
    By defining this once, we avoid the overhead of opening and closing
    connections for every single tool call.
    """
    db = None
    try:
        config = {
            "hostname": os.getenv("IRIS_HOSTNAME", "localhost"),
            "port": int(os.getenv("IRIS_PORT", "1972")),
            "namespace": os.getenv("IRIS_NAMESPACE", "USER"),
            "username": os.getenv("IRIS_USERNAME", "_SYSTEM"),
            "password": os.getenv("IRIS_PASSWORD", "SYS"),
            "web_port": int(os.getenv("IRIS_WEB_PORT", "52773")),
            # Atelier REST API version. v3+ is required for `action/search`.
            "atelier_api_version": os.getenv("IRIS_ATELIER_API_VERSION", "v3"),
        }

        logger.info(f"Connecting to IRIS at {config['hostname']}:{config['port']}...")

        db = irisnative.connect(
            hostname=config["hostname"],
            port=config["port"],
            namespace=config["namespace"],
            username=config["username"],
            password=config["password"],
        )
        iris = irisnative.createIRIS(db)

        logger.info("IRIS Connected Successfully.")
        yield {"iris": iris, "db": db, "config": config}

    except Exception as e:
        logger.error(f"LIFESPAN FAILURE: {e}")
        yield {"iris": None, "db": None, "error": str(e)}
    finally:
        if db:
            db.close()


mcp = FastMCP("IRIS MCP BLUEPRINT", lifespan=iris_lifespan)
