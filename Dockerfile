# ------------------------------------------------------------------------------
# Use the latest InterSystems IRIS Community Edition image as base
# ------------------------------------------------------------------------------
FROM intersystems/iris-community:latest-cd

# set variables for working directory
ENV WORKDIR=/opt/irisapp

# ------------------------------------------------------------------------------
# Work as root temporarily to create directories and adjust permissions
# ------------------------------------------------------------------------------
USER root

# Create the working directory inside the image for your application code
WORKDIR ${WORKDIR}

# Ensure the irisowner user (default IRIS user) owns the workdir
RUN chown ${ISC_PACKAGE_MGRUSER}:${ISC_PACKAGE_IRISGROUP} ${WORKDIR}

# ------------------------------------------------------------------------------
# Copy in application source and scripts
# ------------------------------------------------------------------------------

# Your application classes 
COPY src src

# Script that will be executed by entrypoint at runtime to import source code 
COPY iris.script .

# Startup script wrapper (will run at *container start*)
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Create logs directory and set permissions
RUN mkdir -p ${WORKDIR}/logs && \
    chown -R ${ISC_PACKAGE_MGRUSER}:${ISC_PACKAGE_IRISGROUP} ${WORKDIR}

# ------------------------------------------------------------------------------
# Switch back to the IRIS user (never run IRIS as root!)
# ------------------------------------------------------------------------------
USER ${ISC_PACKAGE_MGRUSER}

# ------------------------------------------------------------------------------
# Entrypoint: this runs your entrypoint.sh, which will start IRIS,
# import your code into the current USER namespace, and then hand over
# control to the default IRIS entrypoint.
# Logs can be found in ${WORKDIR}/logs and in Docker Desktop either.
# ------------------------------------------------------------------------------
WORKDIR ${WORKDIR}
ENTRYPOINT ["./docker-entrypoint.sh"]

# ------------------------------------------------------------------------------
# Ports
# 1972  -> IRIS SuperServer (ODBC, JDBC, etc.)
# 52773 -> Management Portal / Web Apps
# ------------------------------------------------------------------------------
EXPOSE 1972 52773
