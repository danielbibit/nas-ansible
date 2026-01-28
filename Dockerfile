FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt update

RUN apt install -y \
    sshpass

COPY . /app

WORKDIR /app

RUN uv sync --locked

RUN uv run ansible-galaxy install -r ansible-requirements.yml

# Disable ssh host verification for ansible
RUN export ANSIBLE_HOST_KEY_CHECKING=False
