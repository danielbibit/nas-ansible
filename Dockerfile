FROM python:3.12

RUN apt update

RUN apt install -y \
    ansible-lint \
    sshpass

RUN apt remove --purge -y \
    ansible \
    ansible-lint \
    ansible-core

RUN apt autoremove -y

RUN pip install poetry

RUN poetry config virtualenvs.create false

COPY . ./

RUN poetry install --no-root

RUN ansible-galaxy collection install prometheus.prometheus

RUN export ANSIBLE_HOST_KEY_CHECKING=False
