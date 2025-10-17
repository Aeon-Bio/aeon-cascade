FROM cgr.dev/chainguard-private/python:3.11-dev
USER root
RUN \
    set -eux; \
    apk update; \
    apk add --no-cache \
    py3-pip \
    build-base \
    python3-dev \
    ffmpeg \
    git \
    bash

RUN pip3 install -U pip && pip3 install -U wheel && pip3 install -U setuptools

# Install healthos_bot dependencies
COPY healthos_bot/requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt && rm -r /tmp/requirements.txt

# Copy and install indra_agent (direct Python import integration)
# Copy indra_agent source to permanent location (needed for editable install)
COPY indra_agent /opt/indra_agent
COPY pyproject.toml /opt/pyproject.toml

# Install indra_agent in editable mode (keeps source at /opt/indra_agent)
RUN cd /opt && pip3 install -e .

# Copy healthos_bot code
COPY healthos_bot /code
WORKDIR /code

CMD ["bash"]

