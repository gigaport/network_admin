#!/bin/bash

export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$("$PYENV_ROOT/bin/pyenv" init --path)"
eval "$("$PYENV_ROOT/bin/pyenv" init -)"
eval "$("$PYENV_ROOT/bin/pyenv" virtualenv-init -)"

echo "start:batch.sh"

pyenv activate venv

cd /home/sysmon/network_admin
python3 batch.py >> /home/sysmon/network_admin/batch.log 2>&1

echo "end:batch.sh"