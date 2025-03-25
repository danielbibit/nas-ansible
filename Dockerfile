FROM python:3.12

RUN apt update

RUN apt install -y \
    ansible-lint \
    sshpass

RUN pip install poetry

RUN poetry config virtualenvs.create false

COPY . ./

RUN poetry install --no-root

RUN export ANSIBLE_HOST_KEY_CHECKING=False
