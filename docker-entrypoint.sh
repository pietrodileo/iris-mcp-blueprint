#!/bin/sh
set -e

# --- Configuration -------------------------------------------------------------
IRIS_INSTANCE="IRIS"
APP_DIR="/opt/irisapp"
LOG_DIR="${APP_DIR}/logs"
LOG_FILE="${LOG_DIR}/docker-entrypoint.log"
SCRIPT_FILE="${APP_DIR}/iris.script"
# ------------------------------------------------------------------------------

echo "docker-entrypoint.sh started"

# Start IRIS in the background
iris start "${IRIS_INSTANCE}" quietly
echo "IRIS instance '${IRIS_INSTANCE}' started"

# Run your import script every container start
echo "Running iris.script session, logging to ${LOG_FILE}..."
iris session "${IRIS_INSTANCE}" < "${SCRIPT_FILE}" >> "${LOG_FILE}" 2>&1
echo "iris.script session completed"

# Tail the log so it's visible in Docker Desktop console
echo "=== ${LOG_FILE} content ==="
cat "${LOG_FILE}"
echo "=== end of ${LOG_FILE} ==="

# Stop background if needed (optional, for clean start)
iris stop "${IRIS_INSTANCE}" quietly
echo "IRIS instance '${IRIS_INSTANCE}' stopped, handing off to iris-main"

# exec replaces this process — nothing after this line will ever run
exec /iris-main "$@"
# Note: The above script assumes that the IRIS instance is named "IRIS"
# and that the import script is located at /opt/irisapp/iris.script.
