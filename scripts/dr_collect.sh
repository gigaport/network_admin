#!/bin/bash
curl -s -X POST http://netview_fastapi:8000/api/v1/network/dr-training/collect >> /app/logs/dr_collect.log 2>&1
echo "" >> /app/logs/dr_collect.log
