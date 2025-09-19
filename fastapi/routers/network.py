import json, logging, re, time, html, sys, asyncio, uvicorn, os
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple, Union, Optional

## 장비관리 라이브러리
from genie.testbed import load
## 장비정보 파싱 라이브러리
from utils.cisco_interface import Execute_GenieParser
from utils.arista_multicast import GetAristaMulticastInfo
from utils.cisco_common import GetCiscoCommonInfo

router = APIRouter(prefix="/network", tags=["Network"])

# 스레드풀 생성
executor = ThreadPoolExecutor(max_workers=60)

CISCO_TS_DEVICES = load('/app/common/ts_member_mpr.yaml')
CISCO_PR_DEVICES = load('/app/common/pr_member_mpr.yaml')

ARISTA_PR_DEVICE_PATH = '/app/common/pr_information_mkd.json'
## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
with open(ARISTA_PR_DEVICE_PATH, 'rt', encoding='UTF8') as json_file:
    ARISTA_PR_DEVICES = json.load(json_file)



@router.get("/execute")
async def execute_command(device_name: str, command: str):
    result = await Execute_GenieParser(device_name, command)
    if not result:
        raise HTTPException(status_code=404, detail="Device not found or command failed")
    return result


@router.get("/collect/cisco/{target}")
async def CollectCisco(target: str):
    if target == "pr":
        targets = CISCO_PR_DEVICES
    elif target == "ts":
        targets = CISCO_TS_DEVICES
    else:
        return JSONResponse(content={"error": "알 수 없는 대상"}, status_code=404)
    
    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, GetCiscoCommonInfo, device_info, device_name)
        for device_name, device_info in targets.devices.items()
    ]

    results = await asyncio.gather(*tasks)
    # dictionary 형태로 변환
    results_dict = {item["device_name"]: item for item in results}

    return results_dict


@router.get("/collect/multicast/arista/{target}")
async def CollectAristaMulticast(target: str):
    # 멀티캐스트 정보를 수집하는 앤드포인트
    # target이 pr일 경우 PR_DEVICES 정보를 가져오고, ts일 경우 TS_DEVICES 정보를 가져옴

    if target == "pr":
        targets = ARISTA_PR_DEVICES
    # elif target == "ts":
    #     targets = ARISTA_TS_DEVICES
    else:
        return JSONResponse(content={"error": "알 수 없는 대상"}, status_code=404)

    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, GetAristaMulticastInfo, device_info)
        for device_info in targets['devices'].items()
    ]

    results = await asyncio.gather(*tasks)

    return results



