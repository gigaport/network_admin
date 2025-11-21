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
from utils.librenms import GetLibrenmsLldp, GetLibrenmsVlanIps

router = APIRouter(prefix="/network", tags=["Network"])

# 로깅 설정
logger = logging.getLogger(__name__)

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
    logger.info(f"명령 실행 요청: device={device_name}, command={command}")
    result = await Execute_GenieParser(device_name, command)
    if not result:
        logger.error(f"명령 실행 실패: device={device_name}, command={command}")
        raise HTTPException(status_code=404, detail="Device not found or command failed")
    logger.info(f"명령 실행 성공: device={device_name}")
    return result


@router.get("/collect/cisco/{target}")
async def CollectCisco(target: str):
    logger.info(f"Cisco 정보 수집 시작: target={target}")
    
    if target == "pr":
        targets = CISCO_PR_DEVICES
        logger.info("PR 환경 장비 정보 로드")
    elif target == "ts":
        targets = CISCO_TS_DEVICES
        logger.info("TS 환경 장비 정보 로드")
    else:
        logger.error(f"알 수 없는 대상: {target}")
        return JSONResponse(content={"error": "알 수 없는 대상"}, status_code=404)
    
    device_count = len(targets.devices)
    logger.info(f"총 {device_count}개 장비에서 정보 수집 시작")
    
    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, GetCiscoCommonInfo, device_info, device_name)
        for device_name, device_info in targets.devices.items()
    ]

    results = await asyncio.gather(*tasks)
    # dictionary 형태로 변환
    results_dict = {item["device_name"]: item for item in results}

    logger.info(f"Cisco 정보 수집 완료: {len(results_dict)}개 장비")
    return results_dict


@router.get("/collect/multicast/arista/{target}")
async def CollectAristaMulticast(target: str):
    # 멀티캐스트 정보를 수집하는 앤드포인트
    # target이 pr일 경우 PR_DEVICES 정보를 가져오고, ts일 경우 TS_DEVICES 정보를 가져옴
    logger.info(f"Arista 멀티캐스트 정보 수집 시작: target={target}")

    if target == "pr":
        targets = ARISTA_PR_DEVICES
        logger.info("PR 환경 Arista 장비 정보 로드")
    # elif target == "ts":
    #     targets = ARISTA_TS_DEVICES
    else:
        logger.error(f"알 수 없는 대상: {target}")
        return JSONResponse(content={"error": "알 수 없는 대상"}, status_code=404)

    device_count = len(targets['devices'])
    logger.info(f"총 {device_count}개 Arista 장비에서 멀티캐스트 정보 수집 시작")

    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, GetAristaMulticastInfo, device_info)
        for device_info in targets['devices'].items()
    ]

    results = await asyncio.gather(*tasks)

    logger.info(f"Arista 멀티캐스트 정보 수집 완료: {len(results)}개 장비")
    logger.debug(f"수집 결과: {results}")

    return results


@router.get("/collect/librenms/lldp")
async def CollectLibrenmsLldp():
    logger.info("Librenms LLDP 정보 수집 시작")
    results = GetLibrenmsLldp()
    if not results:
        logger.error("Librenms LLDP 정보 수집 실패")
        raise HTTPException(status_code=404, detail="Librenms LLDP 정보 수집 실패")

    logger.info(f"Librenms LLDP 정보 수집 완료: {len(results)}개")
    logger.debug(f"수집 결과: {results}")

    return results


@router.get("/collect/librenms/vlan-ips")
async def CollectLibrenmsVlanIps():
    """VLAN 인터페이스의 IP 할당 정보 수집"""
    logger.info("LibreNMS VLAN IP 정보 수집 시작")
    results = GetLibrenmsVlanIps()
    if not results:
        logger.error("LibreNMS VLAN IP 정보 수집 실패")
        raise HTTPException(status_code=404, detail="LibreNMS VLAN IP 정보 수집 실패")

    logger.info(f"LibreNMS VLAN IP 정보 수집 완료: {len(results.get('data', []))}개 VLAN")
    logger.debug(f"수집 결과: {results}")

    return results