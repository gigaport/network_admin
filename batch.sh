#!/bin/bash
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"

echo "start:batch.sh"

pyenv active venv
python3 /home/sysmon/network_admin/batch.py >> batch.log 2>&1

echo "end:batch.sh"