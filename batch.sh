#!/bin/bash

python3 batch.py pr >> batch_pr.log 2>&1
python3 batch.py ts >> batch_ts.log 2>&1
