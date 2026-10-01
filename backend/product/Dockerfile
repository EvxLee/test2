FROM python:3.11-slim

# Get to a known good state
RUN apt-get update && apt-get upgrade --yes

# Install dependencies via apt
COPY "requirements.apt.txt" "/tmp/requirements.apt.txt"
RUN apt-get update && \
    sed 's/\r$//' /tmp/requirements.apt.txt | xargs apt-get install --yes && \
    rm -rf /var/lib/apt/lists/*

COPY "requirements.pip.txt" "/tmp/requirements.pip"
RUN pip3 install --disable-pip-version-check -r "/tmp/requirements.pip"

# Create non-privileged user
RUN useradd --create-home --groups users user

# Layout of the application
WORKDIR /app
COPY . /app

# Optional debug check — can remove later
RUN ls -R /app

# Copy entrypoint script
COPY "docker.entrypoint.sh" "/app/entrypoint.sh"


# Make it executable (important!)
RUN chmod +x /app/entrypoint.sh

# Run as unprivileged user
USER user
ENTRYPOINT [ "/app/entrypoint.sh" ]
