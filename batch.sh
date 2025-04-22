#!/bin/bash
pyenv active venv
python3 /home/sysmon/network_admin/batch.py >> batch.log 2>&1
