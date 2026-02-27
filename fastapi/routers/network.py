import json, logging, re, time, html, sys, asyncio, uvicorn, os, io
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple, Union, Optional

## 장비관리 라이브러리
from genie.testbed import load
## 장비정보 파싱 라이브러리
from utils.cisco_interface import Execute_GenieParser
from utils.arista_multicast import GetAristaMulticastInfo
from utils.arista_ptp import GetAristaPtpInfo
from utils.cisco_common import GetCiscoCommonInfo
from utils.librenms import GetLibrenmsLldp, GetLibrenmsVlanIps
from utils.database import get_connection
from psycopg2.extras import RealDictCursor

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

# [수정됨] PTP 통합 장비 로드 (파일 하나만 씁니다)
ARISTA_PTP_ALL_PATH = '/app/common/arista_ptp.json'
try:
    with open(ARISTA_PTP_ALL_PATH, 'rt', encoding='UTF8') as json_file:
        ARISTA_PTP_DEVICES = json.load(json_file)
    logger.info(f"PTP 통합 장비 목록 로드 완료: {len(ARISTA_PTP_DEVICES.get('devices', {}))}대")
except FileNotFoundError:
    logger.error(f"PTP 파일 없음: {ARISTA_PTP_ALL_PATH}")
    ARISTA_PTP_DEVICES = {"devices": {}}

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

    # 알람 상태 체크 - 수집 완료된 결과에 대해 상태 전환 확인 및 Slack 알람 발송
    try:
        from utils.alarm_state import check_transition
        from utils.slack_client import send_alert

        channel = "#network-alert-multicast"
        market_gubn = "pr_information"
        market_name = "정보사-가동"

        for result in results:
            if result is None:
                continue
            device_name = result.get("device_name", "")
            check_result_val = result.get("check_result", "")
            if not device_name or not check_result_val:
                continue

            transition = check_transition(market_gubn, device_name, check_result_val, result)
            action = transition["action"]

            if action == "send_alert":
                alert_time = transition.get("alert_time", "")
                member_name = result.get("member_name", "N/A")
                title = f":rotating_light: *({market_name}) {member_name} 시세수신 이상* :rotating_light:"
                fields = [
                    {"title": "대상회원사", "value": f"`{member_name}`", "short": True},
                    {"title": "장비이름", "value": f"*{device_name}*", "short": True},
                    {"title": "가입상품", "value": f"`{result.get('products', 'N/A')}`", "short": True},
                    {"title": "PIM_RP", "value": f"{result.get('pim_rp', 'N/A')}", "short": True},
                    {"title": "기준 mroute", "value": f"{result.get('product_cnt', 0)}", "short": True},
                    {"title": "현재 mroute", "value": f"{result.get('mroute_cnt', 0)}", "short": True},
                    {"title": "현재 oif_cnt", "value": f"{result.get('oif_cnt', 0)}", "short": True},
                    {"title": "RPF_NBR", "value": f"`{result.get('rpf_nbr', 'N/A')}`", "short": True},
                    {"title": "발생시간", "value": f"*{alert_time}*", "short": True},
                ]
                send_alert(channel=channel, title=title, message="", color="danger", fields=fields)
                logger.info(f"[ALARM SENT] Arista 장애 알람: {device_name}")

            elif action == "send_recovery":
                alert_time = transition.get("alert_time", "")
                recovery_time = transition.get("recovery_time", "")
                member_name = result.get("member_name", "N/A")
                title = f":white_check_mark: *({market_name}) {member_name} 시세수신 복구* :white_check_mark:"
                fields = [
                    {"title": "대상회원사", "value": f"`{member_name}`", "short": True},
                    {"title": "장비이름", "value": f"*{device_name}*", "short": True},
                    {"title": "발생시간", "value": f"*{alert_time}*", "short": True},
                    {"title": "복구시간", "value": f"*{recovery_time}*", "short": True},
                ]
                send_alert(channel=channel, title=title, message="", color="good", fields=fields)
                logger.info(f"[ALARM SENT] Arista 복구 알람: {device_name}")

    except Exception as e:
        logger.error(f"Arista 알람 상태 체크 중 오류: {e}")

    return results

@router.get("/collect/ptp/arista/{target}")
async def CollectAristaPtp(target: str):
    """
    Arista PTP 정보를 수집하는 엔드포인트
    [수정] PTP 전용 스레드 풀을 사용하여 다른 작업의 간섭을 받지 않도록 격리합니다.
    """
    # logger.info(f"Arista PTP 정보 수집 요청 (Target: {target} -> 무시하고 전체 수집)")

    # 통합된 목록 사용
    targets = ARISTA_PTP_DEVICES

    if "devices" not in targets or not targets["devices"]:
        logger.warning("등록된 PTP 장비가 없습니다.")
        return []

    # PTP 전용 스레드 풀 생성 (독립적인 도로 개통)
    # max_workers는 장비 수(4대)보다 넉넉하게 10으로 설정
    ptp_executor = ThreadPoolExecutor(max_workers=10)

    loop = asyncio.get_event_loop()
    
    # 작업 리스트 생성 (전용 executor 사용)
    tasks = [
        loop.run_in_executor(ptp_executor, GetAristaPtpInfo, device_info)
        for device_info in targets["devices"].items()
    ]

    try:
        # return_exceptions=True -> 에러 난 장비 때문에 전체가 죽지 않게 함
        results_with_errors = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        # [중요] 작업이 끝나면 스레드 풀을 반드시 닫아서 리소스(메모리/소켓)를 반환해야 함
        ptp_executor.shutdown(wait=False)

    # 에러가 아닌 정상 결과만 필터링
    final_results = []
    for res in results_with_errors:
        if isinstance(res, Exception):
            # 에러 로그는 너무 많이 뜨면 지저분하니 필요할 때만 주석 해제
            # logger.error(f"PTP 수집 중 개별 에러: {res}")
            pass
        elif res: 
            final_results.append(res)

    logger.info(f"Arista PTP 정보 수집 완료: {len(final_results)}개 성공 / 총 {len(targets['devices'])}대 시도")
    return final_results

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


@router.get("/collect/librenms/vlan_ips")
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


@router.get("/contracts")
async def GetNetworkContracts():
    """네트워크 회선 계약 정보 조회"""
    logger.info("네트워크 계약 정보 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    id, 번호, key_code, 지역, 유형, 회원사명, 회선분류, 계약유형,
                    안내, 내부검토, 계약착수, 날인대기, 계약완료,
                    완료보고문서번호, 계약체결일, 추가체결일, 약정기간, 약정만료일,
                    계약금액, 추가신청금액, 계약금액합계, 비고
                FROM network_contracts
                ORDER BY id
            """

            cur.execute(query)
            results = cur.fetchall()

            for row in results:
                for key in ['계약체결일', '추가체결일', '약정만료일']:
                    if row.get(key):
                        row[key] = row[key].isoformat()

            cur.close()

        logger.info(f"네트워크 계약 정보 조회 완료: {len(results)}건")
        return {"data": results, "total": len(results)}

    except Exception as e:
        logger.error(f"네트워크 계약 정보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/contracts")
async def CreateNetworkContract(request: Request):
    """네트워크 회선 계약 정보 생성"""
    logger.info("네트워크 계약 정보 생성 요청")

    try:
        data = await request.json()

        with get_connection() as conn:
            cur = conn.cursor()

            insert_query = """
                INSERT INTO network_contracts (
                    번호, key_code, 지역, 유형, 회원사명, 회선분류, 계약유형,
                    안내, 내부검토, 계약착수, 날인대기, 계약완료,
                    완료보고문서번호, 계약체결일, 추가체결일, 약정기간, 약정만료일,
                    계약금액, 추가신청금액, 계약금액합계, 비고
                ) VALUES (
                    %(번호)s, %(key_code)s, %(지역)s, %(유형)s, %(회원사명)s, %(회선분류)s, %(계약유형)s,
                    %(안내)s, %(내부검토)s, %(계약착수)s, %(날인대기)s, %(계약완료)s,
                    %(완료보고문서번호)s, %(계약체결일)s, %(추가체결일)s, %(약정기간)s, %(약정만료일)s,
                    %(계약금액)s, %(추가신청금액)s, %(계약금액합계)s, %(비고)s
                )
                RETURNING id
            """

            params = {
                '번호': data.get('번호'),
                'key_code': data.get('key_code'),
                '지역': data.get('지역'),
                '유형': data.get('유형'),
                '회원사명': data.get('회원사명'),
                '회선분류': data.get('회선분류'),
                '계약유형': data.get('계약유형'),
                '안내': data.get('안내'),
                '내부검토': data.get('내부검토'),
                '계약착수': data.get('계약착수'),
                '날인대기': data.get('날인대기'),
                '계약완료': data.get('계약완료'),
                '완료보고문서번호': data.get('완료보고문서번호'),
                '계약체결일': data.get('계약체결일') or None,
                '추가체결일': data.get('추가체결일') or None,
                '약정기간': data.get('약정기간'),
                '약정만료일': data.get('약정만료일') or None,
                '계약금액': data.get('계약금액'),
                '추가신청금액': data.get('추가신청금액'),
                '계약금액합계': data.get('계약금액합계'),
                '비고': data.get('비고'),
            }

            cur.execute(insert_query, params)
            new_id = cur.fetchone()[0]
            cur.close()

        logger.info(f"네트워크 계약 정보 생성 완료: ID={new_id}")
        return {"success": True, "message": "Contract created successfully", "id": new_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"네트워크 계약 정보 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/contracts/{contract_id}")
async def GetNetworkContract(contract_id: int):
    """네트워크 회선 계약 정보 상세 조회"""
    logger.info(f"네트워크 계약 정보 상세 조회: ID={contract_id}")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    id, 번호, key_code, 지역, 유형, 회원사명, 회선분류, 계약유형,
                    안내, 내부검토, 계약착수, 날인대기, 계약완료,
                    완료보고문서번호, 계약체결일, 추가체결일, 약정기간, 약정만료일,
                    계약금액, 추가신청금액, 계약금액합계, 비고
                FROM network_contracts
                WHERE id = %s
            """

            cur.execute(query, (contract_id,))
            result = cur.fetchone()

            if not result:
                raise HTTPException(status_code=404, detail="Contract not found")

            for key in ['계약체결일', '추가체결일', '약정만료일']:
                if result.get(key):
                    result[key] = result[key].isoformat()

            cur.close()

        logger.info(f"네트워크 계약 정보 상세 조회 완료: ID={contract_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"네트워크 계약 정보 상세 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/contracts/{contract_id}")
async def UpdateNetworkContract(contract_id: int, request: Request):
    """네트워크 회선 계약 정보 수정"""
    logger.info(f"네트워크 계약 정보 수정: ID={contract_id}")

    try:
        data = await request.json()

        update_fields = []
        values = []

        field_mapping = {
            '번호': '번호',
            'key_code': 'key_code',
            '지역': '지역',
            '유형': '유형',
            '회원사명': '회원사명',
            '회선분류': '회선분류',
            '계약유형': '계약유형',
            '안내': '안내',
            '내부검토': '내부검토',
            '계약착수': '계약착수',
            '날인대기': '날인대기',
            '계약완료': '계약완료',
            '완료보고문서번호': '완료보고문서번호',
            '계약체결일': '계약체결일',
            '추가체결일': '추가체결일',
            '약정기간': '약정기간',
            '약정만료일': '약정만료일',
            '계약금액': '계약금액',
            '추가신청금액': '추가신청금액',
            '계약금액합계': '계약금액합계',
            '비고': '비고'
        }

        for field, db_field in field_mapping.items():
            if field in data:
                update_fields.append(f"{db_field} = %s")
                values.append(data[field])

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        values.append(contract_id)

        with get_connection() as conn:
            cur = conn.cursor()

            query = f"""
                UPDATE network_contracts
                SET {', '.join(update_fields)}
                WHERE id = %s
            """

            cur.execute(query, values)

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Contract not found")

            cur.close()

        logger.info(f"네트워크 계약 정보 수정 완료: ID={contract_id}")
        return {"success": True, "message": "Contract updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"네트워크 계약 정보 수정 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/contracts/{contract_id}")
async def DeleteNetworkContract(contract_id: int):
    """네트워크 회선 계약 정보 삭제"""
    logger.info(f"네트워크 계약 정보 삭제: ID={contract_id}")

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            query = "DELETE FROM network_contracts WHERE id = %s"
            cur.execute(query, (contract_id,))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Contract not found")

            cur.close()

        logger.info(f"네트워크 계약 정보 삭제 완료: ID={contract_id}")
        return {"success": True, "message": "Contract deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"네트워크 계약 정보 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ==================== 시세상품 관리 ====================

@router.get("/sise_products")
async def GetSiseProducts():
    """시세상품 데이터 조회 (채널 수 포함)"""
    logger.info("시세상품 정보 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    p.id,
                    p.product_name,
                    p.line_speed,
                    p.data_format,
                    p.operation_ip1,
                    p.operation_ip2,
                    p.test_ip,
                    p.dr_ip,
                    p.retransmit_port,
                    COUNT(c.id) as channel_count,
                    p.created_at,
                    p.updated_at
                FROM sise_products p
                LEFT JOIN sise_channels c ON p.id = c.product_id
                GROUP BY p.id, p.product_name, p.line_speed, p.data_format,
                         p.operation_ip1, p.operation_ip2, p.test_ip, p.dr_ip,
                         p.retransmit_port, p.created_at, p.updated_at
                ORDER BY p.product_name ASC
            """

            cur.execute(query)
            results = cur.fetchall()

            for row in results:
                for key in ['created_at', 'updated_at']:
                    if row.get(key):
                        row[key] = row[key].strftime('%Y-%m-%d %H:%M:%S')

            cur.close()

        logger.info(f"시세상품 정보 조회 완료: {len(results)}건")
        return {"success": True, "data": results}

    except Exception as e:
        logger.error(f"시세상품 정보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/sise_products/{product_id}")
async def GetSiseProduct(product_id: int):
    """시세상품 정보 상세 조회"""
    logger.info(f"시세상품 정보 상세 조회: ID={product_id}")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    p.id,
                    p.product_name,
                    p.line_speed,
                    p.data_format,
                    p.operation_ip1,
                    p.operation_ip2,
                    p.test_ip,
                    p.dr_ip,
                    p.retransmit_port,
                    COUNT(c.id) as channel_count,
                    p.created_at,
                    p.updated_at
                FROM sise_products p
                LEFT JOIN sise_channels c ON p.id = c.product_id
                WHERE p.id = %s
                GROUP BY p.id, p.product_name, p.line_speed, p.data_format,
                         p.operation_ip1, p.operation_ip2, p.test_ip, p.dr_ip,
                         p.retransmit_port, p.created_at, p.updated_at
            """

            cur.execute(query, (product_id,))
            result = cur.fetchone()

            if not result:
                raise HTTPException(status_code=404, detail="Product not found")

            for key in ['created_at', 'updated_at']:
                if result.get(key):
                    result[key] = result[key].strftime('%Y-%m-%d %H:%M:%S')

            cur.close()

        logger.info(f"시세상품 정보 상세 조회 완료: ID={product_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"시세상품 정보 상세 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/sise_products")
async def CreateSiseProduct(request: Request):
    """시세상품 추가"""
    logger.info("시세상품 추가 요청")

    try:
        data = await request.json()

        product_name = data.get('product_name', '').strip()
        line_speed = data.get('line_speed', '').strip()
        data_format = data.get('data_format', '').strip()
        operation_ip1 = data.get('operation_ip1', '').strip()
        operation_ip2 = data.get('operation_ip2', '').strip()
        test_ip = data.get('test_ip', '').strip()
        dr_ip = data.get('dr_ip', '').strip()
        retransmit_port = data.get('retransmit_port', '').strip()

        if not product_name or not line_speed or not data_format:
            raise HTTPException(status_code=400, detail="필수 필드를 모두 입력해주세요.")

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("SELECT id FROM sise_products WHERE product_name = %s", (product_name,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="이미 존재하는 상품명입니다.")

            insert_query = """
                INSERT INTO sise_products (
                    product_name, line_speed, data_format,
                    operation_ip1, operation_ip2, test_ip, dr_ip, retransmit_port
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            cur.execute(insert_query, (
                product_name, line_speed, data_format,
                operation_ip1, operation_ip2, test_ip, dr_ip, retransmit_port
            ))

            cur.close()

        logger.info(f"시세상품 추가 완료: {product_name}")
        return {"success": True, "message": "시세상품이 추가되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"시세상품 추가 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/sise_products/{product_id}")
async def UpdateSiseProduct(product_id: int, request: Request):
    """시세상품 수정"""
    logger.info(f"시세상품 수정 요청: ID={product_id}")

    try:
        data = await request.json()

        product_name = data.get('product_name', '').strip()
        line_speed = data.get('line_speed', '').strip()
        data_format = data.get('data_format', '').strip()
        operation_ip1 = data.get('operation_ip1', '').strip()
        operation_ip2 = data.get('operation_ip2', '').strip()
        test_ip = data.get('test_ip', '').strip()
        dr_ip = data.get('dr_ip', '').strip()
        retransmit_port = data.get('retransmit_port', '').strip()

        if not product_name or not line_speed or not data_format:
            raise HTTPException(status_code=400, detail="필수 필드를 모두 입력해주세요.")

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("SELECT id FROM sise_products WHERE product_name = %s AND id != %s",
                       (product_name, product_id))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="이미 존재하는 상품명입니다.")

            update_query = """
                UPDATE sise_products SET
                    product_name = %s,
                    line_speed = %s,
                    data_format = %s,
                    operation_ip1 = %s,
                    operation_ip2 = %s,
                    test_ip = %s,
                    dr_ip = %s,
                    retransmit_port = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """

            cur.execute(update_query, (
                product_name, line_speed, data_format,
                operation_ip1, operation_ip2, test_ip, dr_ip, retransmit_port,
                product_id
            ))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Product not found")

            cur.close()

        logger.info(f"시세상품 수정 완료: ID={product_id}")
        return {"success": True, "message": "시세상품이 수정되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"시세상품 수정 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/sise_products/{product_id}")
async def DeleteSiseProduct(product_id: int):
    """시세상품 삭제 (CASCADE로 채널도 함께 삭제됨)"""
    logger.info(f"시세상품 삭제 요청: ID={product_id}")

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            query = "DELETE FROM sise_products WHERE id = %s"
            cur.execute(query, (product_id,))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Product not found")

            cur.close()

        logger.info(f"시세상품 삭제 완료: ID={product_id}")
        return {"success": True, "message": "시세상품이 삭제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"시세상품 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ==================== 회원사 코드 관리 ====================

@router.get("/subscriber_codes")
async def GetSubscriberCodes():
    """회원사 코드 데이터 조회"""
    logger.info("회원사 코드 정보 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    id,
                    member_code,
                    member_number,
                    company_name,
                    subscription_type,
                    is_pb,
                    created_at,
                    updated_at
                FROM subscriber_codes
                ORDER BY member_number ASC
            """

            cur.execute(query)
            results = cur.fetchall()

            for row in results:
                for key in ['created_at', 'updated_at']:
                    if row.get(key):
                        row[key] = row[key].strftime('%Y-%m-%d %H:%M:%S')
                if 'is_pb' in row:
                    row['is_pb'] = bool(row['is_pb'])

            cur.close()

        logger.info(f"회원사 코드 정보 조회 완료: {len(results)}건")
        return {"success": True, "data": results}

    except Exception as e:
        logger.error(f"회원사 코드 정보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/subscriber_codes")
async def CreateSubscriberCode(request: Request):
    """회원사 코드 추가"""
    logger.info("회원사 코드 추가 요청")

    try:
        data = await request.json()

        member_code = data.get('member_code', '').strip()
        member_number = data.get('member_number')
        company_name = data.get('company_name', '').strip()
        subscription_type = data.get('subscription_type', '').strip()
        is_pb = data.get('is_pb', False)

        if not member_code or member_number is None or not company_name or not subscription_type:
            raise HTTPException(status_code=400, detail="필수 필드를 모두 입력해주세요.")

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("SELECT id FROM subscriber_codes WHERE member_code = %s", (member_code,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="이미 존재하는 회원사 코드입니다.")

            cur.execute("SELECT id FROM subscriber_codes WHERE member_number = %s", (member_number,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="이미 존재하는 회원사 넘버입니다.")

            insert_query = """
                INSERT INTO subscriber_codes (
                    member_code, member_number, company_name, subscription_type, is_pb
                ) VALUES (%s, %s, %s, %s, %s)
            """

            cur.execute(insert_query, (
                member_code, member_number, company_name, subscription_type, is_pb
            ))

            cur.close()

        logger.info(f"회원사 코드 추가 완료: {member_code}")
        return {"success": True, "message": "회원사 코드가 추가되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회원사 코드 추가 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/subscriber_codes/{code_id}")
async def UpdateSubscriberCode(code_id: int, request: Request):
    """회원사 코드 수정"""
    logger.info(f"회원사 코드 수정 요청: ID={code_id}")

    try:
        data = await request.json()

        member_code = data.get('member_code', '').strip()
        member_number = data.get('member_number')
        company_name = data.get('company_name', '').strip()
        subscription_type = data.get('subscription_type', '').strip()
        is_pb = data.get('is_pb', False)

        if not member_code or member_number is None or not company_name or not subscription_type:
            raise HTTPException(status_code=400, detail="필수 필드를 모두 입력해주세요.")

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("SELECT id FROM subscriber_codes WHERE member_code = %s AND id != %s",
                       (member_code, code_id))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="이미 존재하는 회원사 코드입니다.")

            cur.execute("SELECT id FROM subscriber_codes WHERE member_number = %s AND id != %s",
                       (member_number, code_id))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="이미 존재하는 회원사 넘버입니다.")

            update_query = """
                UPDATE subscriber_codes SET
                    member_code = %s,
                    member_number = %s,
                    company_name = %s,
                    subscription_type = %s,
                    is_pb = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """

            cur.execute(update_query, (
                member_code, member_number, company_name, subscription_type, is_pb,
                code_id
            ))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Subscriber code not found")

            cur.close()

        logger.info(f"회원사 코드 수정 완료: ID={code_id}")
        return {"success": True, "message": "회원사 코드가 수정되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회원사 코드 수정 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/subscriber_codes/{code_id}")
async def DeleteSubscriberCode(code_id: int):
    """회원사 코드 삭제 (CASCADE로 주소도 함께 삭제됨)"""
    logger.info(f"회원사 코드 삭제 요청: ID={code_id}")

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            query = "DELETE FROM subscriber_codes WHERE id = %s"
            cur.execute(query, (code_id,))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Subscriber code not found")

            cur.close()

        logger.info(f"회원사 코드 삭제 완료: ID={code_id}")
        return {"success": True, "message": "회원사 코드가 삭제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회원사 코드 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ==================== 회원사 주소 관리 ====================

@router.get("/subscriber_addresses")
async def GetSubscriberAddresses():
    """회원사 주소 데이터 조회 (subscriber_codes와 JOIN)"""
    logger.info("회원사 주소 정보 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    ca.id,
                    ca.member_code,
                    sc.member_number,
                    sc.company_name,
                    ca.datacenter_code,
                    ca.post_code,
                    ca.main_address,
                    ca.detailed_address,
                    ca.summary_address,
                    ca.created_at,
                    ca.updated_at
                FROM customer_addresses ca
                LEFT JOIN subscriber_codes sc ON ca.member_code = sc.member_code
                ORDER BY sc.member_number ASC NULLS LAST, ca.datacenter_code
            """

            cur.execute(query)
            results = cur.fetchall()

            for row in results:
                for key in ['created_at', 'updated_at']:
                    if row.get(key):
                        row[key] = row[key].strftime('%Y-%m-%d %H:%M:%S')
                if row.get('member_number') is None:
                    row['member_number'] = 0
                if row.get('company_name') is None:
                    row['company_name'] = '알 수 없음'

            cur.close()

        logger.info(f"회원사 주소 정보 조회 완료: {len(results)}건")
        return {"success": True, "data": results}

    except Exception as e:
        logger.error(f"회원사 주소 정보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/subscriber_addresses")
async def CreateSubscriberAddress(request: Request):
    """회원사 주소 정보 추가"""
    logger.info("회원사 주소 추가 요청")

    try:
        data = await request.json()

        member_code = data.get('member_code', '').strip()
        datacenter_code = data.get('datacenter_code', '').strip()
        post_code = data.get('post_code', '').strip()
        main_address = data.get('main_address', '').strip()
        detailed_address = data.get('detailed_address', '').strip()
        summary_address = data.get('summary_address', '').strip()

        if not all([member_code, datacenter_code, summary_address]):
            raise HTTPException(status_code=400, detail="필수 필드를 입력해주세요.")

        with get_connection() as conn:
            cur = conn.cursor()

            check_query = "SELECT member_code FROM subscriber_codes WHERE member_code = %s"
            cur.execute(check_query, (member_code,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail=f"회원사 코드 '{member_code}'가 존재하지 않습니다.")

            dup_query = "SELECT id FROM customer_addresses WHERE member_code = %s AND datacenter_code = %s"
            cur.execute(dup_query, (member_code, datacenter_code))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail=f"이미 등록된 주소입니다. (회원사: {member_code}, 데이터센터: {datacenter_code})")

            query = """
                INSERT INTO customer_addresses (member_code, datacenter_code, post_code, main_address, detailed_address, summary_address)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cur.execute(query, (member_code, datacenter_code, post_code, main_address, detailed_address, summary_address))

            cur.close()

        logger.info(f"회원사 주소 추가 완료: {member_code} - {datacenter_code}")
        return {"success": True, "message": "주소 정보가 추가되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회원사 주소 추가 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/subscriber_addresses/{address_id}")
async def UpdateSubscriberAddress(address_id: int, request: Request):
    """회원사 주소 정보 수정"""
    logger.info(f"회원사 주소 수정 요청: ID={address_id}")

    try:
        data = await request.json()

        member_code = data.get('member_code', '').strip()
        datacenter_code = data.get('datacenter_code', '').strip()
        post_code = data.get('post_code', '').strip()
        main_address = data.get('main_address', '').strip()
        detailed_address = data.get('detailed_address', '').strip()
        summary_address = data.get('summary_address', '').strip()

        if not all([member_code, datacenter_code, summary_address]):
            raise HTTPException(status_code=400, detail="필수 필드를 입력해주세요.")

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("SELECT member_code FROM subscriber_codes WHERE member_code = %s", (member_code,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail=f'회원사 코드 "{member_code}"가 존재하지 않습니다.')

            update_query = """
                UPDATE customer_addresses
                SET member_code = %s,
                    datacenter_code = %s,
                    post_code = %s,
                    main_address = %s,
                    detailed_address = %s,
                    summary_address = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """

            cur.execute(update_query, (member_code, datacenter_code, post_code, main_address, detailed_address, summary_address, address_id))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Address not found")

            cur.close()

        logger.info(f"회원사 주소 수정 완료: ID={address_id}")
        return {"success": True, "message": "주소 정보가 수정되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회원사 주소 수정 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/subscriber_addresses/{address_id}")
async def DeleteSubscriberAddress(address_id: int):
    """회원사 주소 삭제"""
    logger.info(f"회원사 주소 삭제 요청: ID={address_id}")

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            query = "DELETE FROM customer_addresses WHERE id = %s"
            cur.execute(query, (address_id,))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Address not found")

            cur.close()

        logger.info(f"회원사 주소 삭제 완료: ID={address_id}")
        return {"success": True, "message": "주소 정보가 삭제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회원사 주소 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ==================== 시세 채널 관리 ====================

@router.get("/sise_channels")
async def GetSiseChannels():
    """시세 채널 데이터 조회 (sise_products와 JOIN)"""
    logger.info("시세 채널 정보 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    sc.id,
                    sc.product_id,
                    sp.product_name,
                    sp.operation_ip1,
                    sp.operation_ip2,
                    sp.test_ip,
                    sp.dr_ip,
                    sc.service_type,
                    sc.market_type,
                    sc.multicast_group_ip,
                    sc.operation_port,
                    sc.test_port,
                    TO_CHAR(sc.created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at,
                    TO_CHAR(sc.updated_at, 'YYYY-MM-DD HH24:MI:SS') as updated_at
                FROM sise_channels sc
                INNER JOIN sise_products sp ON sc.product_id = sp.id
                ORDER BY sc.id
            """

            cur.execute(query)
            rows = cur.fetchall()

            results = []
            for row in rows:
                results.append(dict(row))

            cur.close()

        logger.info(f"시세 채널 정보 조회 완료: {len(results)}건")
        return {"success": True, "data": results}

    except Exception as e:
        logger.error(f"시세 채널 정보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/sise_channels")
async def CreateSiseChannel(request: Request):
    """시세 채널 정보 추가"""
    logger.info("시세 채널 추가 요청")

    try:
        data = await request.json()

        product_id = data.get('product_id')
        service_type = data.get('service_type', '').strip()
        market_type = data.get('market_type', '').strip()
        multicast_group_ip = data.get('multicast_group_ip', '').strip()
        operation_port = data.get('operation_port', '').strip()
        test_port = data.get('test_port', '').strip()

        if not all([product_id, service_type, market_type]):
            raise HTTPException(status_code=400, detail="필수 필드를 입력해주세요.")

        with get_connection() as conn:
            cur = conn.cursor()

            check_query = "SELECT id FROM sise_products WHERE id = %s"
            cur.execute(check_query, (product_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail=f"상품 ID '{product_id}'가 존재하지 않습니다.")

            dup_query = "SELECT id FROM sise_channels WHERE product_id = %s AND service_type = %s AND market_type = %s"
            cur.execute(dup_query, (product_id, service_type, market_type))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail=f"이미 등록된 채널입니다. (상품ID: {product_id}, 서비스: {service_type}, 시장: {market_type})")

            query = """
                INSERT INTO sise_channels (product_id, service_type, market_type, multicast_group_ip, operation_port, test_port)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cur.execute(query, (product_id, service_type, market_type, multicast_group_ip, operation_port, test_port))

            cur.close()

        logger.info(f"시세 채널 추가 완료: product_id={product_id}, service_type={service_type}, market_type={market_type}")
        return {"success": True, "message": "채널 정보가 추가되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"시세 채널 추가 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/sise_channels/{channel_id}")
async def UpdateSiseChannel(channel_id: int, request: Request):
    """시세 채널 정보 수정"""
    logger.info(f"시세 채널 수정 요청: ID={channel_id}")

    try:
        data = await request.json()

        product_id = data.get('product_id')
        service_type = data.get('service_type', '').strip()
        market_type = data.get('market_type', '').strip()
        multicast_group_ip = data.get('multicast_group_ip', '').strip()
        operation_port = data.get('operation_port', '').strip()
        test_port = data.get('test_port', '').strip()

        if not all([product_id, service_type, market_type]):
            raise HTTPException(status_code=400, detail="필수 필드를 입력해주세요.")

        with get_connection() as conn:
            cur = conn.cursor()

            check_query = "SELECT id FROM sise_products WHERE id = %s"
            cur.execute(check_query, (product_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail=f"상품 ID '{product_id}'가 존재하지 않습니다.")

            dup_query = "SELECT id FROM sise_channels WHERE product_id = %s AND service_type = %s AND market_type = %s AND id != %s"
            cur.execute(dup_query, (product_id, service_type, market_type, channel_id))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail=f"이미 등록된 채널입니다. (상품ID: {product_id}, 서비스: {service_type}, 시장: {market_type})")

            update_query = """
                UPDATE sise_channels SET
                    product_id = %s,
                    service_type = %s,
                    market_type = %s,
                    multicast_group_ip = %s,
                    operation_port = %s,
                    test_port = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """

            cur.execute(update_query, (
                product_id, service_type, market_type, multicast_group_ip, operation_port, test_port,
                channel_id
            ))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Channel not found")

            cur.close()

        logger.info(f"시세 채널 수정 완료: ID={channel_id}")
        return {"success": True, "message": "채널 정보가 수정되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"시세 채널 수정 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/sise_channels/{channel_id}")
async def DeleteSiseChannel(channel_id: int):
    """시세 채널 삭제"""
    logger.info(f"시세 채널 삭제 요청: ID={channel_id}")

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            query = "DELETE FROM sise_channels WHERE id = %s"
            cur.execute(query, (channel_id,))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Channel not found")

            cur.close()

        logger.info(f"시세 채널 삭제 완료: ID={channel_id}")
        return {"success": True, "message": "채널 정보가 삭제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"시세 채널 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ==================== 회선내역 (Circuit) 관리 ====================

@router.get("/circuits")
async def GetCircuits():
    """회선내역 전체 조회 (회원사코드/주소 JOIN)"""
    logger.info("회선내역 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    c.id, c.member_code,
                    sc.member_number, sc.company_name,
                    c.datacenter_code,
                    ca.summary_address,
                    c.side_a, c.provider, c.circuit_id, c.nni_id,
                    c.type, c.state, c.env, c.usage, c.product, c.bandwidth,
                    c.additional_circuit, c.phase,
                    mfs.price AS fee_price,
                    c.cot_device, c.rt_device,
                    c.lldp_cot_device, c.lldp_port, c.lldp_rt_device, c.lldp_rt_port,
                    c.join_type, c.contract_date, c.expiry_date, c.contract_period,
                    c.report_number, c.comments,
                    c.created_at, c.updated_at
                FROM circuit c
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN customer_addresses ca
                    ON c.member_code = ca.member_code
                    AND c.datacenter_code = ca.datacenter_code
                LEFT JOIN member_fee_schedule mfs
                    ON c.usage = mfs.usage
                    AND c.phase = mfs.phase
                    AND c.additional_circuit = mfs.additional_circuit
                    AND (c.bandwidth = mfs.bandwidth OR (c.bandwidth IS NULL AND mfs.bandwidth IS NULL))
                ORDER BY sc.member_number ASC,
                    CASE c.datacenter_code
                        WHEN 'DC1' THEN 1
                        WHEN 'DC2' THEN 2
                        WHEN 'DC3' THEN 3
                        WHEN 'DR' THEN 4
                        ELSE 5
                    END ASC,
                    c.id ASC
            """

            cur.execute(query)
            results = cur.fetchall()

            for row in results:
                for key in ['created_at', 'updated_at']:
                    if row.get(key):
                        row[key] = row[key].strftime('%Y-%m-%d %H:%M:%S')
                for key in ['contract_date', 'expiry_date']:
                    if row.get(key):
                        row[key] = row[key].strftime('%Y-%m-%d')

            cur.close()

        logger.info(f"회선내역 조회 완료: {len(results)}건")
        return {"success": True, "data": results}

    except Exception as e:
        logger.error(f"회선내역 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/circuits")
async def CreateCircuit(request: Request):
    """회선내역 추가"""
    logger.info("회선내역 추가 요청")

    try:
        data = await request.json()

        required_fields = ['member_code', 'datacenter_code', 'side_a', 'provider',
                           'circuit_id', 'nni_id', 'type', 'state', 'env', 'usage', 'bandwidth',
                           'cot_device', 'rt_device']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            raise HTTPException(status_code=400, detail=f"필수 필드 누락: {', '.join(missing)}")

        with get_connection() as conn:
            cur = conn.cursor()

            insert_query = """
                INSERT INTO circuit (
                    member_code, datacenter_code, side_a, provider, circuit_id, nni_id,
                    type, state, env, usage, product, bandwidth, additional_circuit,
                    cot_device, rt_device, lldp_cot_device, lldp_port, lldp_rt_device, lldp_rt_port,
                    join_type, contract_date, expiry_date, contract_period,
                    report_number, comments
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s
                )
            """

            cur.execute(insert_query, (
                data.get('member_code'), data.get('datacenter_code'),
                data.get('side_a'), data.get('provider'),
                data.get('circuit_id'), data.get('nni_id'),
                data.get('type'), data.get('state'),
                data.get('env'), data.get('usage'),
                data.get('product') or None, data.get('bandwidth'),
                data.get('additional_circuit', False),
                data.get('cot_device'), data.get('rt_device'),
                data.get('lldp_cot_device') or None, data.get('lldp_port') or None,
                data.get('lldp_rt_device') or None, data.get('lldp_rt_port') or None,
                data.get('join_type', 0),
                data.get('contract_date') or None, data.get('expiry_date') or None,
                data.get('contract_period') or None,
                data.get('report_number') or None, data.get('comments') or None,
            ))

            cur.close()

        logger.info(f"회선내역 추가 완료: {data.get('circuit_id')}")
        return {"success": True, "message": "회선내역이 추가되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회선내역 추가 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/circuits/{circuit_id}")
async def UpdateCircuit(circuit_id: int, request: Request):
    """회선내역 수정 (제공된 필드만 업데이트)"""
    logger.info(f"회선내역 수정 요청: ID={circuit_id}")

    try:
        data = await request.json()

        # id 필드는 WHERE 조건에 사용하므로 SET에서 제외
        data.pop('id', None)

        # 업데이트 가능한 컬럼 목록
        allowed_columns = {
            'member_code', 'datacenter_code', 'side_a', 'provider',
            'circuit_id', 'nni_id', 'type', 'state', 'env', 'usage',
            'product', 'bandwidth', 'additional_circuit',
            'cot_device', 'rt_device',
            'lldp_cot_device', 'lldp_port', 'lldp_rt_device', 'lldp_rt_port',
            'join_type', 'contract_date', 'expiry_date', 'contract_period',
            'report_number', 'comments', 'phase', 'side_a'
        }

        # 요청 데이터에 포함된 필드만 SET 절 구성
        set_parts = []
        values = []
        for key, value in data.items():
            if key in allowed_columns:
                set_parts.append(f"{key} = %s")
                values.append(value if value != '' else None)

        if not set_parts:
            raise HTTPException(status_code=400, detail="수정할 데이터가 없습니다.")

        set_parts.append("updated_at = CURRENT_TIMESTAMP")
        values.append(circuit_id)

        with get_connection() as conn:
            cur = conn.cursor()

            update_query = f"UPDATE circuit SET {', '.join(set_parts)} WHERE id = %s"
            cur.execute(update_query, values)

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Circuit not found")

            cur.close()

        logger.info(f"회선내역 수정 완료: ID={circuit_id}")
        return {"success": True, "message": "회선내역이 수정되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회선내역 수정 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/circuits/{circuit_id}")
async def DeleteCircuit(circuit_id: int):
    """회선내역 삭제"""
    logger.info(f"회선내역 삭제 요청: ID={circuit_id}")

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("DELETE FROM circuit WHERE id = %s", (circuit_id,))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Circuit not found")

            cur.close()

        logger.info(f"회선내역 삭제 완료: ID={circuit_id}")
        return {"success": True, "message": "회선내역이 삭제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회선내역 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/fee_schedule")
async def GetFeeSchedule():
    """과금기준 목록 조회"""
    logger.info("과금기준 목록 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT id, usage, description, price, phase, bandwidth, additional_circuit
                FROM member_fee_schedule
                ORDER BY id
            """)
            results = cur.fetchall()
            cur.close()

        logger.info(f"과금기준 목록 조회 완료: {len(results)}건")
        return {"success": True, "data": results}

    except Exception as e:
        logger.error(f"과금기준 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/fee_schedule")
async def CreateFeeSchedule(request: Request):
    """과금기준 추가"""
    logger.info("과금기준 추가 요청")

    try:
        data = await request.json()

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO member_fee_schedule (usage, description, price, phase, bandwidth, additional_circuit)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                data.get('usage'), data.get('description'),
                data.get('price', 0), data.get('phase', 0),
                data.get('bandwidth') or None, data.get('additional_circuit', False)
            ))

            cur.close()

        logger.info(f"과금기준 추가 완료: {data.get('usage')} - {data.get('description')}")
        return {"success": True, "message": "과금기준이 추가되었습니다."}

    except Exception as e:
        logger.error(f"과금기준 추가 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/fee_schedule/{fee_id}")
async def UpdateFeeSchedule(fee_id: int, request: Request):
    """과금기준 수정"""
    logger.info(f"과금기준 수정 요청: ID={fee_id}")

    try:
        data = await request.json()

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                UPDATE member_fee_schedule SET
                    usage = %s, description = %s,
                    price = %s, phase = %s,
                    bandwidth = %s, additional_circuit = %s
                WHERE id = %s
            """, (
                data.get('usage'), data.get('description'),
                data.get('price', 0), data.get('phase', 0),
                data.get('bandwidth') or None, data.get('additional_circuit', False),
                fee_id
            ))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Fee schedule not found")

            cur.close()

        logger.info(f"과금기준 수정 완료: ID={fee_id}")
        return {"success": True, "message": "과금기준이 수정되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"과금기준 수정 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/fee_schedule/{fee_id}")
async def DeleteFeeSchedule(fee_id: int):
    """과금기준 삭제"""
    logger.info(f"과금기준 삭제 요청: ID={fee_id}")

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("DELETE FROM member_fee_schedule WHERE id = %s", (fee_id,))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Fee schedule not found")

            cur.close()

        logger.info(f"과금기준 삭제 완료: ID={fee_id}")
        return {"success": True, "message": "과금기준이 삭제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"과금기준 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ==================== 대시보드 집계 API ====================

@router.get("/dashboard")
async def get_dashboard():
    """대시보드에 필요한 모든 집계 데이터를 한 번에 반환"""
    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # 1. 요약 통계
            cur.execute("SELECT COUNT(*) as cnt FROM circuit")
            total_circuits = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) as cnt FROM subscriber_codes")
            total_members = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) as cnt FROM sise_products")
            total_products = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) as cnt FROM member_fee_schedule")
            total_fee_items = cur.fetchone()['cnt']

            cur.execute("""
                SELECT COUNT(*) as cnt FROM circuit
                WHERE expiry_date IS NOT NULL
                  AND expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '90 days'
            """)
            expiring_soon = cur.fetchone()['cnt']

            # 2. 통신사별 회선
            cur.execute("""
                SELECT provider, COUNT(*) as cnt
                FROM circuit
                WHERE provider IS NOT NULL AND provider != ''
                GROUP BY provider ORDER BY cnt DESC
            """)
            circuits_by_provider = {row['provider']: row['cnt'] for row in cur.fetchall()}

            # 3. 환경별 회선
            cur.execute("""
                SELECT env, COUNT(*) as cnt
                FROM circuit
                WHERE env IS NOT NULL AND env != ''
                GROUP BY env ORDER BY cnt DESC
            """)
            circuits_by_env = {row['env']: row['cnt'] for row in cur.fetchall()}

            # 4. DC코드별 x 용도별 회선
            cur.execute("""
                SELECT datacenter_code, usage, COUNT(*) as cnt
                FROM circuit
                WHERE datacenter_code IS NOT NULL AND datacenter_code != ''
                GROUP BY datacenter_code, usage
                ORDER BY datacenter_code
            """)
            circuits_by_dc = {}
            for row in cur.fetchall():
                dc = row['datacenter_code']
                usage = row['usage'] or 'ETC'
                if dc not in circuits_by_dc:
                    circuits_by_dc[dc] = {}
                circuits_by_dc[dc][usage] = row['cnt']

            # 5. Top 10 회원사 (회선 수 기준)
            cur.execute("""
                SELECT c.member_code, sc.company_name, COUNT(*) as circuit_count
                FROM circuit c
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                GROUP BY c.member_code, sc.company_name
                ORDER BY circuit_count DESC
                LIMIT 10
            """)
            top_members = [dict(row) for row in cur.fetchall()]

            # 6. 용도별 회선
            cur.execute("""
                SELECT usage, COUNT(*) as cnt
                FROM circuit
                WHERE usage IS NOT NULL AND usage != ''
                GROUP BY usage ORDER BY cnt DESC
            """)
            circuits_by_usage = {row['usage']: row['cnt'] for row in cur.fetchall()}

            # 7. 만료 임박 회선 (90일 이내)
            cur.execute("""
                SELECT c.id, c.member_code, sc.company_name, c.circuit_id,
                       c.provider, c.env, c.usage, c.expiry_date,
                       (c.expiry_date - CURRENT_DATE) as days_left
                FROM circuit c
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                WHERE c.expiry_date IS NOT NULL
                  AND c.expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '90 days'
                ORDER BY c.expiry_date ASC
                LIMIT 20
            """)
            expiring_circuits = [dict(row) for row in cur.fetchall()]

            # 8. 매출 총액 (ORD/MPR)
            cur.execute("""
                SELECT
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'ORD'), 0) AS ord_total,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'MPR'), 0) AS mpr_total,
                    COALESCE(SUM(mfs.price), 0) AS grand_total
                FROM circuit c
                LEFT JOIN member_fee_schedule mfs
                    ON c.usage = mfs.usage AND c.phase = mfs.phase
                    AND c.additional_circuit = mfs.additional_circuit
                    AND (c.bandwidth = mfs.bandwidth OR (c.bandwidth IS NULL AND mfs.bandwidth IS NULL))
                WHERE c.usage IN ('ORD', 'MPR')
            """)
            revenue_total = dict(cur.fetchone())

            # 9. 매출 Top 10 회원사
            cur.execute("""
                SELECT sc.company_name, sc.member_code,
                       COALESCE(SUM(mfs.price), 0) AS total_revenue,
                       COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'ORD'), 0) AS ord_revenue,
                       COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'MPR'), 0) AS mpr_revenue
                FROM circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mfs
                    ON c.usage = mfs.usage AND c.phase = mfs.phase
                    AND c.additional_circuit = mfs.additional_circuit
                    AND (c.bandwidth = mfs.bandwidth OR (c.bandwidth IS NULL AND mfs.bandwidth IS NULL))
                WHERE c.usage IN ('ORD', 'MPR')
                GROUP BY sc.company_name, sc.member_code
                HAVING SUM(mfs.price) > 0
                ORDER BY total_revenue DESC
                LIMIT 10
            """)
            top_revenue_members = [dict(row) for row in cur.fetchall()]

            # 10. 용도별 매출 (ORD/MPR)
            cur.execute("""
                SELECT c.usage,
                       COALESCE(SUM(mfs.price), 0) AS revenue
                FROM circuit c
                LEFT JOIN member_fee_schedule mfs
                    ON c.usage = mfs.usage AND c.phase = mfs.phase
                    AND c.additional_circuit = mfs.additional_circuit
                    AND (c.bandwidth = mfs.bandwidth OR (c.bandwidth IS NULL AND mfs.bandwidth IS NULL))
                WHERE c.usage IN ('ORD', 'MPR')
                GROUP BY c.usage
                ORDER BY c.usage
            """)
            revenue_by_usage = {row['usage']: int(row['revenue']) for row in cur.fetchall()}

            cur.close()

        return {
            "success": True,
            "data": {
                "summary": {
                    "total_circuits": total_circuits,
                    "total_members": total_members,
                    "total_products": total_products,
                    "total_fee_items": total_fee_items,
                    "expiring_soon": expiring_soon
                },
                "circuits_by_provider": circuits_by_provider,
                "circuits_by_env": circuits_by_env,
                "circuits_by_usage": circuits_by_usage,
                "circuits_by_dc": circuits_by_dc,
                "top_members": top_members,
                "expiring_circuits": expiring_circuits,
                "revenue": {
                    "grand_total": int(revenue_total['grand_total']),
                    "ord_total": int(revenue_total['ord_total']),
                    "mpr_total": int(revenue_total['mpr_total']),
                    "by_usage": revenue_by_usage,
                    "top_members": top_revenue_members
                }
            }
        }

    except Exception as e:
        logger.error(f"대시보드 데이터 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ==================== 매출내역 (Revenue Summary) ====================

@router.get("/revenue_summary")
async def GetRevenueSummary():
    """회원사별 매출내역 조회 (ORD/MPR 회선 요금 집계)"""
    logger.info("매출내역 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # 회원사별 요약 집계
            summary_query = """
                SELECT
                    sc.member_code, sc.member_number, sc.company_name, sc.subscription_type,
                    sc.is_pb, c.phase,
                    COUNT(*) FILTER (WHERE c.usage = 'ORD') AS ord_count,
                    COUNT(*) FILTER (WHERE c.usage = 'MPR') AS mpr_count,
                    COUNT(*) AS total_count,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'ORD'), 0) AS ord_total,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'MPR'), 0) AS mpr_total,
                    COALESCE(SUM(mfs.price), 0) AS grand_total
                FROM circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mfs
                    ON c.usage = mfs.usage AND c.phase = mfs.phase
                    AND c.additional_circuit = mfs.additional_circuit
                    AND (c.bandwidth = mfs.bandwidth OR (c.bandwidth IS NULL AND mfs.bandwidth IS NULL))
                WHERE c.usage IN ('ORD', 'MPR')
                GROUP BY sc.member_code, sc.member_number, sc.company_name, sc.subscription_type, sc.is_pb, c.phase
                ORDER BY sc.is_pb ASC NULLS FIRST, sc.member_number ASC, c.phase ASC
            """
            cur.execute(summary_query)
            summary = cur.fetchall()

            # 회선별 상세 내역
            detail_query = """
                SELECT
                    c.id, c.member_code, sc.member_number, sc.company_name,
                    c.datacenter_code, c.usage, c.product, c.bandwidth,
                    c.additional_circuit, c.phase, c.provider, c.circuit_id,
                    mfs.price AS fee_price, mfs.description AS fee_description
                FROM circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mfs
                    ON c.usage = mfs.usage AND c.phase = mfs.phase
                    AND c.additional_circuit = mfs.additional_circuit
                    AND (c.bandwidth = mfs.bandwidth OR (c.bandwidth IS NULL AND mfs.bandwidth IS NULL))
                WHERE c.usage IN ('ORD', 'MPR')
                ORDER BY sc.member_number, c.datacenter_code, c.usage
            """
            cur.execute(detail_query)
            details = cur.fetchall()

            cur.close()

        logger.info(f"매출내역 조회 완료: 회원사 {len(summary)}건, 상세 {len(details)}건")
        return {"success": True, "summary": summary, "details": details}

    except Exception as e:
        logger.error(f"매출내역 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/revenue_monthly")
async def GetRevenueMonthly(year_month: str = Query(..., description="조회 월 (YYYY-MM 형식)")):
    """월별 매출내역 조회 (12개월 추이 + 해당 월 요약/상세)"""
    logger.info(f"월별 매출내역 조회: {year_month}")

    try:
        # year_month 파싱
        target = datetime.strptime(year_month, "%Y-%m").date()
        month_start = target.replace(day=1)
        next_month = month_start + relativedelta(months=1)
        month_end = next_month - relativedelta(days=1)

        # 12개월 추이 범위 (해당 월 포함 과거 12개월)
        trend_start = month_start - relativedelta(months=11)

        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # 1) 12개월 추이 쿼리
            trend_query = """
                WITH months AS (
                    SELECT generate_series(
                        %s::date,
                        %s::date,
                        '1 month'::interval
                    )::date AS m_start
                ),
                month_ranges AS (
                    SELECT
                        m_start,
                        (m_start + interval '1 month' - interval '1 day')::date AS m_end
                    FROM months
                )
                SELECT
                    to_char(mr.m_start, 'YYYY-MM') AS month,
                    COUNT(*) FILTER (WHERE c.usage = 'ORD') AS ord_count,
                    COUNT(*) FILTER (WHERE c.usage = 'MPR') AS mpr_count,
                    COUNT(*) AS circuit_count,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'ORD'), 0) AS ord_total,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'MPR'), 0) AS mpr_total,
                    COALESCE(SUM(mfs.price), 0) AS grand_total
                FROM month_ranges mr
                LEFT JOIN circuit c ON c.usage IN ('ORD', 'MPR')
                    AND (c.contract_date IS NULL OR c.contract_date <= mr.m_end)
                    AND (c.expiry_date IS NULL OR c.expiry_date >= mr.m_start)
                LEFT JOIN member_fee_schedule mfs
                    ON c.usage = mfs.usage AND c.phase = mfs.phase
                    AND c.additional_circuit = mfs.additional_circuit
                    AND (c.bandwidth = mfs.bandwidth OR (c.bandwidth IS NULL AND mfs.bandwidth IS NULL))
                GROUP BY mr.m_start
                ORDER BY mr.m_start
            """
            cur.execute(trend_query, (trend_start, month_start))
            trend = cur.fetchall()

            # 2) 해당 월 회원사별 요약
            summary_query = """
                SELECT
                    sc.member_code, sc.member_number, sc.company_name, sc.subscription_type,
                    sc.is_pb, c.phase,
                    COUNT(*) FILTER (WHERE c.usage = 'ORD') AS ord_count,
                    COUNT(*) FILTER (WHERE c.usage = 'MPR') AS mpr_count,
                    COUNT(*) AS total_count,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'ORD'), 0) AS ord_total,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'MPR'), 0) AS mpr_total,
                    COALESCE(SUM(mfs.price), 0) AS grand_total
                FROM circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mfs
                    ON c.usage = mfs.usage AND c.phase = mfs.phase
                    AND c.additional_circuit = mfs.additional_circuit
                    AND (c.bandwidth = mfs.bandwidth OR (c.bandwidth IS NULL AND mfs.bandwidth IS NULL))
                WHERE c.usage IN ('ORD', 'MPR')
                    AND (c.contract_date IS NULL OR c.contract_date <= %s)
                    AND (c.expiry_date IS NULL OR c.expiry_date >= %s)
                GROUP BY sc.member_code, sc.member_number, sc.company_name, sc.subscription_type, sc.is_pb, c.phase
                ORDER BY sc.is_pb ASC NULLS FIRST, sc.member_number ASC, c.phase ASC
            """
            cur.execute(summary_query, (month_end, month_start))
            summary = cur.fetchall()

            # 3) 해당 월 회선별 상세
            detail_query = """
                SELECT
                    c.id, c.member_code, sc.member_number, sc.company_name,
                    c.datacenter_code, c.usage, c.product, c.bandwidth,
                    c.additional_circuit, c.phase, c.provider, c.circuit_id,
                    c.contract_date, c.expiry_date,
                    mfs.price AS fee_price, mfs.description AS fee_description
                FROM circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mfs
                    ON c.usage = mfs.usage AND c.phase = mfs.phase
                    AND c.additional_circuit = mfs.additional_circuit
                    AND (c.bandwidth = mfs.bandwidth OR (c.bandwidth IS NULL AND mfs.bandwidth IS NULL))
                WHERE c.usage IN ('ORD', 'MPR')
                    AND (c.contract_date IS NULL OR c.contract_date <= %s)
                    AND (c.expiry_date IS NULL OR c.expiry_date >= %s)
                ORDER BY sc.member_number, c.datacenter_code, c.usage
            """
            cur.execute(detail_query, (month_end, month_start))
            details = cur.fetchall()

            cur.close()

        logger.info(f"월별 매출내역 조회 완료: 추이 {len(trend)}건, 요약 {len(summary)}건, 상세 {len(details)}건")
        return {
            "success": True,
            "year_month": year_month,
            "trend": trend,
            "summary": summary,
            "details": details
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="year_month 형식이 잘못되었습니다. YYYY-MM 형식으로 입력해주세요.")
    except Exception as e:
        logger.error(f"월별 매출내역 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/revenue_report_pdf")
async def GetRevenueReportPdf(year_month: str = Query(..., description="보고서 월 (YYYY-MM 형식)")):
    """월별 매출 보고서 PDF 다운로드"""
    logger.info(f"매출 보고서 PDF 생성: {year_month}")

    try:
        from fpdf import FPDF

        target = datetime.strptime(year_month, "%Y-%m").date()
        month_start = target.replace(day=1)
        next_month = month_start + relativedelta(months=1)
        month_end = next_month - relativedelta(days=1)

        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # 회원사별 요약
            summary_query = """
                SELECT
                    sc.member_code, sc.member_number, sc.company_name,
                    sc.subscription_type, sc.is_pb, c.phase,
                    COUNT(*) FILTER (WHERE c.usage = 'ORD') AS ord_count,
                    COUNT(*) FILTER (WHERE c.usage = 'MPR') AS mpr_count,
                    COUNT(*) AS total_count,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'ORD'), 0) AS ord_total,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'MPR'), 0) AS mpr_total,
                    COALESCE(SUM(mfs.price), 0) AS grand_total
                FROM circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mfs
                    ON c.usage = mfs.usage AND c.phase = mfs.phase
                    AND c.additional_circuit = mfs.additional_circuit
                    AND (c.bandwidth = mfs.bandwidth OR (c.bandwidth IS NULL AND mfs.bandwidth IS NULL))
                WHERE c.usage IN ('ORD', 'MPR')
                    AND (c.contract_date IS NULL OR c.contract_date <= %s)
                    AND (c.expiry_date IS NULL OR c.expiry_date >= %s)
                GROUP BY sc.member_code, sc.member_number, sc.company_name,
                         sc.subscription_type, sc.is_pb, c.phase
                ORDER BY sc.is_pb ASC NULLS FIRST, sc.member_number ASC, c.phase ASC
            """
            cur.execute(summary_query, (month_end, month_start))
            summary = cur.fetchall()
            cur.close()

        # PDF 생성
        font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "DroidSansFallback.ttf")

        # 커스텀 PDF 클래스 (헤더/푸터)
        class RevenuePDF(FPDF):
            report_title = ""
            report_period = ""

            def header(self):
                if self.page_no() == 1:
                    return  # 표지에는 헤더 없음
                self.set_font("Korean", "", 7)
                self.set_text_color(140, 140, 140)
                self.cell(0, 6, f"NEXTRADE MKNM  |  {self.report_title}", align='L')
                self.cell(0, 6, f"{self.report_period}", align='R', ln=True)
                # 헤더 구분선
                self.set_draw_color(200, 200, 200)
                self.line(10, 12, 287, 12)
                self.ln(4)

            def footer(self):
                self.set_y(-12)
                self.set_font("Korean", "", 7)
                self.set_text_color(160, 160, 160)
                self.set_draw_color(200, 200, 200)
                self.line(10, self.get_y() - 2, 287, self.get_y() - 2)
                self.cell(0, 8, "NEXTRADE MKNM 네트워크 관리시스템 자동생성 보고서", align='L')
                self.cell(0, 8, f"{self.page_no()} / {{nb}}", align='R')

        pdf = RevenuePDF(orientation='L', unit='mm', format='A4')
        pdf.add_font("Korean", "", font_path, uni=True)
        pdf.add_font("Korean", "B", font_path, uni=True)
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=18)

        target_year = target.strftime('%Y')
        target_month_num = target.strftime('%m')
        pdf.report_title = f"{target_year}년 {int(target_month_num)}월 매출 보고서"
        pdf.report_period = f"{month_start} ~ {month_end}"

        # 요약 집계
        total_ord = sum(r['ord_total'] for r in summary)
        total_mpr = sum(r['mpr_total'] for r in summary)
        total_grand = sum(r['grand_total'] for r in summary)
        total_ord_cnt = sum(r['ord_count'] for r in summary)
        total_mpr_cnt = sum(r['mpr_count'] for r in summary)
        total_circuits = sum(r['total_count'] for r in summary)
        member_set = set(r['member_code'] for r in summary)
        ord_ratio = (total_ord / total_grand * 100) if total_grand > 0 else 0
        mpr_ratio = (total_mpr / total_grand * 100) if total_grand > 0 else 0

        # ============================
        # 1페이지: 표지
        # ============================
        pdf.add_page()

        # 상단 컬러 바
        pdf.set_fill_color(30, 58, 138)  # 진한 남색
        pdf.rect(0, 0, 297, 50, 'F')
        # 악센트 바
        pdf.set_fill_color(59, 130, 246)  # 밝은 파랑
        pdf.rect(0, 50, 297, 4, 'F')

        # 표지 타이틀
        pdf.set_xy(0, 12)
        pdf.set_font("Korean", "B", 28)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 14, "월별 매출 보고서", align='C', ln=True)
        pdf.set_font("Korean", "", 13)
        pdf.set_text_color(190, 210, 255)
        pdf.cell(0, 10, "NEXTRADE MKNM 네트워크 통합운영시스템", align='C', ln=True)

        # 보고 기간 박스
        pdf.set_text_color(50, 50, 50)
        pdf.ln(20)
        pdf.set_font("Korean", "B", 20)
        pdf.cell(0, 14, f"{target_year}년 {int(target_month_num)}월", align='C', ln=True)
        pdf.set_font("Korean", "", 11)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 8, f"({month_start} ~ {month_end})", align='C', ln=True)

        # KPI 카드 영역
        pdf.ln(12)
        card_y = pdf.get_y()
        card_w = 85
        card_h = 32
        card_gap = 7
        card_start_x = (297 - (card_w * 3 + card_gap * 2)) / 2

        # 카드 그리기 함수
        def draw_kpi_card(x, y, w, h, label, value, sub_text, r, g, b):
            # 카드 배경
            pdf.set_fill_color(r, g, b)
            pdf.rect(x, y, w, h, 'F')
            # 왼쪽 악센트 바
            pdf.set_fill_color(max(r - 40, 0), max(g - 40, 0), max(b - 40, 0))
            pdf.rect(x, y, 3, h, 'F')
            # 라벨
            pdf.set_xy(x + 8, y + 4)
            pdf.set_font("Korean", "", 8)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(w - 12, 5, label)
            # 값
            pdf.set_xy(x + 8, y + 11)
            pdf.set_font("Korean", "B", 16)
            pdf.cell(w - 12, 10, value)
            # 보조 텍스트
            pdf.set_xy(x + 8, y + 23)
            pdf.set_font("Korean", "", 7)
            pdf.set_text_color(220, 220, 220)
            pdf.cell(w - 12, 5, sub_text)

        draw_kpi_card(card_start_x, card_y, card_w, card_h,
                      "총 매출", f"{total_grand:,.0f}원",
                      f"회원사 {len(member_set)}개사 | 회선 {total_circuits:,}건",
                      5, 150, 105)  # 초록
        draw_kpi_card(card_start_x + card_w + card_gap, card_y, card_w, card_h,
                      "ORD 매출", f"{total_ord:,.0f}원",
                      f"회선 {total_ord_cnt:,}건 | 비율 {ord_ratio:.1f}%",
                      37, 99, 235)  # 파랑
        draw_kpi_card(card_start_x + (card_w + card_gap) * 2, card_y, card_w, card_h,
                      "MPR 매출", f"{total_mpr:,.0f}원",
                      f"회선 {total_mpr_cnt:,}건 | 비율 {mpr_ratio:.1f}%",
                      217, 119, 6)  # 주황

        # 표지 하단 정보
        pdf.set_y(170)
        pdf.set_font("Korean", "", 9)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 6, f"보고서 생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", align='C', ln=True)
        pdf.cell(0, 6, "NEXTRADE MKNM 네트워크 관리시스템", align='C', ln=True)

        # 하단 장식 바
        pdf.set_fill_color(30, 58, 138)
        pdf.rect(0, 196, 297, 14, 'F')
        pdf.set_fill_color(59, 130, 246)
        pdf.rect(0, 192, 297, 4, 'F')

        # ============================
        # 2페이지: 요약 + 상위 매출 회원사
        # ============================
        pdf.add_page()

        # 섹션 제목 함수
        def section_title(text):
            pdf.set_font("Korean", "B", 12)
            pdf.set_text_color(30, 58, 138)
            pdf.cell(0, 8, text, ln=True)
            # 밑줄
            y = pdf.get_y()
            pdf.set_draw_color(59, 130, 246)
            pdf.set_line_width(0.6)
            pdf.line(10, y, 100, y)
            pdf.set_line_width(0.2)
            pdf.ln(4)

        section_title("매출 요약")

        # 요약 테이블 (2x3 그리드)
        info_items = [
            ("전체 회원사", f"{len(member_set)}개사"),
            ("전체 회선수", f"{total_circuits:,}회선"),
            ("총 매출", f"{total_grand:,.0f}원"),
            ("ORD 회선수", f"{total_ord_cnt:,}건"),
            ("MPR 회선수", f"{total_mpr_cnt:,}건"),
            ("ORD/MPR 비율", f"{ord_ratio:.1f}% / {mpr_ratio:.1f}%"),
        ]

        info_y = pdf.get_y()
        info_w = 88
        info_h = 14
        for i, (label, val) in enumerate(info_items):
            col = i % 3
            row = i // 3
            x = 10 + col * (info_w + 4)
            y = info_y + row * (info_h + 3)
            # 배경
            pdf.set_fill_color(248, 250, 252)
            pdf.rect(x, y, info_w, info_h, 'F')
            # 라벨
            pdf.set_xy(x + 4, y + 2)
            pdf.set_font("Korean", "", 7)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(40, 4, label)
            # 값
            pdf.set_xy(x + 4, y + 7)
            pdf.set_font("Korean", "B", 10)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(80, 5, val)

        pdf.set_y(info_y + 2 * (info_h + 3) + 8)

        # 매출 상위 10 회원사
        section_title("매출 상위 10 회원사")

        # 회원사별 합산 (phase 통합)
        member_agg = {}
        for r in summary:
            mc = r['member_code']
            if mc not in member_agg:
                member_agg[mc] = {
                    'member_number': r['member_number'],
                    'company_name': r['company_name'],
                    'ord_count': 0, 'mpr_count': 0,
                    'ord_total': 0, 'mpr_total': 0, 'grand_total': 0, 'total_count': 0
                }
            member_agg[mc]['ord_count'] += r['ord_count']
            member_agg[mc]['mpr_count'] += r['mpr_count']
            member_agg[mc]['ord_total'] += r['ord_total']
            member_agg[mc]['mpr_total'] += r['mpr_total']
            member_agg[mc]['grand_total'] += r['grand_total']
            member_agg[mc]['total_count'] += r['total_count']

        top10 = sorted(member_agg.values(), key=lambda x: x['grand_total'], reverse=True)[:10]
        max_revenue = top10[0]['grand_total'] if top10 else 1

        top_col_w = [12, 22, 70, 28, 28, 42, 75]
        top_headers = ['순위', '회원번호', '회사명', 'ORD 회선', 'MPR 회선', '총 매출(원)', '비율']

        pdf.set_font("Korean", "B", 8)
        pdf.set_fill_color(30, 58, 138)
        pdf.set_text_color(255, 255, 255)
        for i, h in enumerate(top_headers):
            pdf.cell(top_col_w[i], 7, h, border=0, fill=True, align='C')
        pdf.ln()

        for idx, m in enumerate(top10, 1):
            row_y = pdf.get_y()
            is_even = idx % 2 == 0
            if is_even:
                pdf.set_fill_color(245, 247, 250)
                pdf.rect(10, row_y, sum(top_col_w), 8, 'F')

            pdf.set_font("Korean", "B" if idx <= 3 else "", 8)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(top_col_w[0], 8, str(idx), align='C')
            pdf.set_font("Korean", "", 8)
            pdf.cell(top_col_w[1], 8, str(m['member_number'] or ''), align='C')
            pdf.cell(top_col_w[2], 8, str(m['company_name'] or '')[:28])
            pdf.cell(top_col_w[3], 8, f"{m['ord_count']:,}건", align='R')
            pdf.cell(top_col_w[4], 8, f"{m['mpr_count']:,}건", align='R')
            pdf.set_font("Korean", "B", 8)
            pdf.cell(top_col_w[5], 8, f"{m['grand_total']:,.0f}", align='R')

            # 비율 막대
            bar_x = pdf.get_x() + 2
            bar_w = top_col_w[6] - 20
            ratio = m['grand_total'] / max_revenue if max_revenue > 0 else 0
            pdf.set_fill_color(219, 234, 254)
            pdf.rect(bar_x, row_y + 2, bar_w, 4, 'F')
            pdf.set_fill_color(59, 130, 246)
            pdf.rect(bar_x, row_y + 2, bar_w * ratio, 4, 'F')
            pct_of_total = (m['grand_total'] / total_grand * 100) if total_grand > 0 else 0
            pdf.set_font("Korean", "", 7)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(top_col_w[6], 8, f"  {pct_of_total:.1f}%", align='R')
            pdf.ln()

        # ============================
        # 3페이지~: 회원사별 상세 테이블
        # ============================
        pdf.add_page()
        section_title("회원사별 매출 상세 내역")

        col_widths = [12, 22, 72, 22, 22, 22, 22, 40, 40]
        headers = ['No', '회원번호', '회사명', 'Phase', 'ORD', 'MPR', '합계', 'ORD 매출(원)', 'MPR 매출(원)']

        def draw_table_header():
            pdf.set_font("Korean", "B", 8)
            pdf.set_fill_color(30, 58, 138)
            pdf.set_text_color(255, 255, 255)
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 7, h, border=0, fill=True, align='C')
            pdf.ln()
            # 헤더 하단 라인
            y = pdf.get_y()
            pdf.set_draw_color(59, 130, 246)
            pdf.set_line_width(0.4)
            pdf.line(10, y, 10 + sum(col_widths), y)
            pdf.set_line_width(0.2)

        draw_table_header()

        for idx, row in enumerate(summary, 1):
            if pdf.get_y() > 178:
                pdf.add_page()
                section_title("회원사별 매출 상세 내역 (계속)")
                draw_table_header()

            row_y = pdf.get_y()
            is_even = idx % 2 == 0

            if is_even:
                pdf.set_fill_color(248, 250, 252)
                pdf.rect(10, row_y, sum(col_widths), 6.5, 'F')

            # 하단 구분선
            pdf.set_draw_color(230, 230, 230)
            pdf.line(10, row_y + 6.5, 10 + sum(col_widths), row_y + 6.5)

            pdf.set_text_color(80, 80, 80)
            pdf.set_font("Korean", "", 7.5)

            pdf.cell(col_widths[0], 6.5, str(idx), align='C')
            pdf.cell(col_widths[1], 6.5, str(row['member_number'] or ''), align='C')

            pdf.set_text_color(30, 41, 59)
            pdf.set_font("Korean", "", 7.5)
            pdf.cell(col_widths[2], 6.5, str(row['company_name'] or '')[:30])

            pdf.set_text_color(80, 80, 80)
            pdf.cell(col_widths[3], 6.5, str(row['phase'] or ''), align='C')
            pdf.cell(col_widths[4], 6.5, str(row['ord_count']), align='R')
            pdf.cell(col_widths[5], 6.5, str(row['mpr_count']), align='R')

            pdf.set_font("Korean", "B", 7.5)
            pdf.cell(col_widths[6], 6.5, str(row['total_count']), align='R')

            # 금액 컬러
            pdf.set_font("Korean", "", 7.5)
            pdf.set_text_color(37, 99, 235)
            pdf.cell(col_widths[7], 6.5, f"{row['ord_total']:,.0f}", align='R')
            pdf.set_text_color(217, 119, 6)
            pdf.cell(col_widths[8], 6.5, f"{row['mpr_total']:,.0f}", align='R')
            pdf.ln()

        # 합계 행
        total_y = pdf.get_y()
        pdf.set_draw_color(30, 58, 138)
        pdf.set_line_width(0.6)
        pdf.line(10, total_y, 10 + sum(col_widths), total_y)
        pdf.set_line_width(0.2)

        pdf.set_font("Korean", "B", 8)
        pdf.set_fill_color(240, 245, 255)
        pdf.set_text_color(30, 58, 138)

        pdf.cell(col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3], 8, "합계", fill=True, align='C')
        pdf.cell(col_widths[4], 8, str(total_ord_cnt), fill=True, align='R')
        pdf.cell(col_widths[5], 8, str(total_mpr_cnt), fill=True, align='R')
        pdf.cell(col_widths[6], 8, str(total_circuits), fill=True, align='R')
        pdf.set_text_color(37, 99, 235)
        pdf.cell(col_widths[7], 8, f"{total_ord:,.0f}", fill=True, align='R')
        pdf.set_text_color(217, 119, 6)
        pdf.cell(col_widths[8], 8, f"{total_mpr:,.0f}", fill=True, align='R')
        pdf.ln()

        # 합계 금액 강조
        pdf.set_text_color(30, 58, 138)
        pdf.set_font("Korean", "B", 9)
        pdf.ln(3)
        pdf.cell(sum(col_widths), 7, f"총 매출 합계:  {total_grand:,.0f}원", align='R')
        pdf.ln()

        # PDF 출력
        pdf_output = pdf.output()
        pdf_buffer = io.BytesIO(pdf_output)
        pdf_buffer.seek(0)

        filename = f"revenue_report_{year_month}.pdf"
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except ValueError:
        raise HTTPException(status_code=400, detail="year_month 형식이 잘못되었습니다. YYYY-MM 형식으로 입력해주세요.")
    except Exception as e:
        logger.error(f"매출 보고서 PDF 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")


# ==================== 통신사 원가정보 (Network Cost) ====================

@router.get("/network_cost")
async def GetNetworkCost():
    """통신사 원가정보 전체 조회"""
    logger.info("통신사 원가정보 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT id, code, provider, circuit_type, cost_standart, cost_price, description,
                       TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at,
                       TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI:SS') as updated_at
                FROM network_cost
                ORDER BY provider, cost_standart
            """)
            results = cur.fetchall()
            cur.close()

        logger.info(f"통신사 원가정보 조회 완료: {len(results)}건")
        return {"success": True, "data": results}

    except Exception as e:
        logger.error(f"통신사 원가정보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/network_cost")
async def CreateNetworkCost(request: Request):
    """통신사 원가정보 추가"""
    logger.info("통신사 원가정보 추가 요청")

    try:
        data = await request.json()

        provider = data.get('provider', '').strip()
        circuit_type = data.get('circuit_type', '').strip()
        cost_standart = data.get('cost_standart', '').strip()
        cost_price = data.get('cost_price', 0)
        description = data.get('description', '').strip()

        if not provider or not cost_standart:
            raise HTTPException(status_code=400, detail="통신사, 비용기준은 필수 입력항목입니다.")

        # code 자동생성: {통신사약어}-{회선종류약어}-{순번3자리}
        provider_map = {'KT': 'KT', 'LGU': 'LGU', 'SKB': 'SKB', '세종': 'SJ'}
        ct_map = {'회원사': 'M', '정보이용사': 'I'}
        p_code = provider_map.get(provider, provider[:3].upper())
        ct_code = ct_map.get(circuit_type, 'X')

        with get_connection() as conn:
            cur = conn.cursor()

            # 동일 통신사+회선종류의 최대 순번 조회
            cur.execute("""
                SELECT code FROM network_cost
                WHERE code LIKE %s
                ORDER BY code DESC LIMIT 1
            """, (f"{p_code}-{ct_code}-%",))
            row = cur.fetchone()
            if row and row[0]:
                last_seq = int(row[0].split('-')[-1])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            new_code = f"{p_code}-{ct_code}-{new_seq:03d}"

            cur.execute("""
                INSERT INTO network_cost (code, provider, circuit_type, cost_standart, cost_price, description)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (new_code, provider, circuit_type, cost_standart, cost_price, description))

            cur.close()

        logger.info(f"통신사 원가정보 추가 완료: {new_code} - {provider} - {cost_standart}")
        return {"success": True, "message": "원가정보가 추가되었습니다.", "code": new_code}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"통신사 원가정보 추가 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/network_cost/{cost_id}")
async def UpdateNetworkCost(cost_id: int, request: Request):
    """통신사 원가정보 수정"""
    logger.info(f"통신사 원가정보 수정 요청: ID={cost_id}")

    try:
        data = await request.json()

        provider = data.get('provider', '').strip()
        circuit_type = data.get('circuit_type', '').strip()
        cost_standart = data.get('cost_standart', '').strip()
        cost_price = data.get('cost_price', 0)
        description = data.get('description', '').strip()

        if not provider or not cost_standart:
            raise HTTPException(status_code=400, detail="통신사, 비용기준은 필수 입력항목입니다.")

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                UPDATE network_cost SET
                    provider = %s, circuit_type = %s, cost_standart = %s,
                    cost_price = %s, description = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (provider, circuit_type, cost_standart, cost_price, description, cost_id))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Network cost not found")

            cur.close()

        logger.info(f"통신사 원가정보 수정 완료: ID={cost_id}")
        return {"success": True, "message": "원가정보가 수정되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"통신사 원가정보 수정 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/network_cost/{cost_id}")
async def DeleteNetworkCost(cost_id: int):
    """통신사 원가정보 삭제"""
    logger.info(f"통신사 원가정보 삭제 요청: ID={cost_id}")

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("DELETE FROM network_cost WHERE id = %s", (cost_id,))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Network cost not found")

            cur.close()

        logger.info(f"통신사 원가정보 삭제 완료: ID={cost_id}")
        return {"success": True, "message": "원가정보가 삭제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"통신사 원가정보 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ============================================================
# 회원사 매입내역 (Purchase Contract) CRUD
# ============================================================

@router.get("/network_cost/codes")
async def GetNetworkCostCodes():
    """원가코드 목록 조회 (select 옵션용)"""
    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT code, provider, circuit_type, cost_standart, cost_price
                FROM network_cost
                ORDER BY code
            """)
            results = cur.fetchall()
            cur.close()
        return {"success": True, "data": results}
    except Exception as e:
        logger.error(f"원가코드 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/purchase_contract")
async def GetPurchaseContract():
    """회원사 매입내역 전체 조회 (network_cost JOIN)"""
    logger.info("회원사 매입내역 조회 시작")
    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT pc.id, pc.member_code, pc.datacenter_code, pc.provider,
                       TO_CHAR(pc.billing_start_date, 'YYYY-MM-DD') as billing_start_date,
                       TO_CHAR(pc.contract_end_date, 'YYYY-MM-DD') as contract_end_date,
                       pc.service_id, pc.nni_id, pc.cost_code,
                       nc.cost_price, nc.cost_standart,
                       sc.company_name
                FROM purchase_contract pc
                LEFT JOIN network_cost nc ON pc.cost_code = nc.code
                LEFT JOIN subscriber_codes sc ON pc.member_code = sc.member_code
                ORDER BY pc.member_code, pc.datacenter_code, pc.provider
            """)
            results = cur.fetchall()
            cur.close()
        logger.info(f"회원사 매입내역 조회 완료: {len(results)}건")
        return {"success": True, "data": results}
    except Exception as e:
        logger.error(f"회원사 매입내역 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/purchase_contract")
async def CreatePurchaseContract(request: Request):
    """회원사 매입내역 추가"""
    logger.info("회원사 매입내역 추가 요청")
    try:
        data = await request.json()
        member_code = data.get('member_code', '').strip()
        datacenter_code = data.get('datacenter_code', '').strip()
        provider = data.get('provider', '').strip()
        billing_start_date = data.get('billing_start_date') or None
        contract_end_date = data.get('contract_end_date') or None
        service_id = data.get('service_id', '').strip() or None
        nni_id = data.get('nni_id', '').strip() or None
        cost_code = data.get('cost_code', '').strip() or None

        if not member_code:
            raise HTTPException(status_code=400, detail="회원사코드는 필수입니다.")

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO purchase_contract
                    (member_code, datacenter_code, provider, billing_start_date, contract_end_date, service_id, nni_id, cost_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (member_code, datacenter_code, provider, billing_start_date, contract_end_date, service_id, nni_id, cost_code))
            cur.close()

        logger.info(f"회원사 매입내역 추가 완료: {member_code}")
        return {"success": True, "message": "매입내역이 추가되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회원사 매입내역 추가 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/purchase_contract/{item_id}")
async def UpdatePurchaseContract(item_id: int, request: Request):
    """회원사 매입내역 수정"""
    logger.info(f"회원사 매입내역 수정 요청: ID={item_id}")
    try:
        data = await request.json()
        member_code = data.get('member_code', '').strip()
        datacenter_code = data.get('datacenter_code', '').strip()
        provider = data.get('provider', '').strip()
        billing_start_date = data.get('billing_start_date') or None
        contract_end_date = data.get('contract_end_date') or None
        service_id = data.get('service_id', '').strip() or None
        nni_id = data.get('nni_id', '').strip() or None
        cost_code = data.get('cost_code', '').strip() or None

        if not member_code:
            raise HTTPException(status_code=400, detail="회원사코드는 필수입니다.")

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE purchase_contract SET
                    member_code = %s, datacenter_code = %s, provider = %s,
                    billing_start_date = %s, contract_end_date = %s,
                    service_id = %s, nni_id = %s, cost_code = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (member_code, datacenter_code, provider, billing_start_date, contract_end_date, service_id, nni_id, cost_code, item_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Purchase contract not found")
            cur.close()

        logger.info(f"회원사 매입내역 수정 완료: ID={item_id}")
        return {"success": True, "message": "매입내역이 수정되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회원사 매입내역 수정 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/purchase_contract/{item_id}")
async def DeletePurchaseContract(item_id: int):
    """회원사 매입내역 삭제"""
    logger.info(f"회원사 매입내역 삭제 요청: ID={item_id}")
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM purchase_contract WHERE id = %s", (item_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Purchase contract not found")
            cur.close()

        logger.info(f"회원사 매입내역 삭제 완료: ID={item_id}")
        return {"success": True, "message": "매입내역이 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회원사 매입내역 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# NetBox Proxy Endpoints
# ============================================================
import requests as http_requests

NETBOX_URL = os.environ.get('NETBOX_URL', 'http://172.25.32.221')
NETBOX_TOKEN = os.environ.get('NETBOX_TOKEN', '')
NETBOX_HEADERS = {"Authorization": f"Token {NETBOX_TOKEN}", "Accept": "application/json"}


@router.get("/netbox/devices")
async def GetNetboxDevices(request: Request):
    """NetBox 디바이스 목록 조회 (프록시)"""
    logger.info("NetBox 디바이스 목록 조회")
    try:
        params = list(request.query_params.multi_items())
        param_keys = [k for k, v in params]
        if 'limit' not in param_keys:
            params.append(('limit', 1000))
        if 'offset' not in param_keys:
            params.append(('offset', 0))

        resp = http_requests.get(
            f"{NETBOX_URL}/api/dcim/devices/",
            headers=NETBOX_HEADERS, params=params, timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"NetBox 디바이스 조회 완료: {data.get('count', 0)}건")
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"NetBox 디바이스 조회 실패: {e}")
        raise HTTPException(status_code=502, detail=f"NetBox API error: {str(e)}")


@router.get("/netbox/devices/{device_id}")
async def GetNetboxDeviceDetail(device_id: int):
    """NetBox 디바이스 상세 조회 (프록시)"""
    logger.info(f"NetBox 디바이스 상세 조회: ID={device_id}")
    try:
        resp = http_requests.get(
            f"{NETBOX_URL}/api/dcim/devices/{device_id}/",
            headers=NETBOX_HEADERS, timeout=15
        )
        resp.raise_for_status()
        return {"success": True, "data": resp.json()}
    except Exception as e:
        logger.error(f"NetBox 디바이스 상세 조회 실패: {e}")
        raise HTTPException(status_code=502, detail=f"NetBox API error: {str(e)}")


@router.get("/netbox/filters")
async def GetNetboxFilters():
    """NetBox 필터 옵션 조회 (역할, 제조사, 사이트)"""
    logger.info("NetBox 필터 옵션 조회")
    try:
        roles_resp = http_requests.get(
            f"{NETBOX_URL}/api/dcim/device-roles/?limit=100",
            headers=NETBOX_HEADERS, timeout=10
        )
        mfr_resp = http_requests.get(
            f"{NETBOX_URL}/api/dcim/manufacturers/?limit=200",
            headers=NETBOX_HEADERS, timeout=10
        )
        sites_resp = http_requests.get(
            f"{NETBOX_URL}/api/dcim/sites/?limit=200",
            headers=NETBOX_HEADERS, timeout=10
        )

        roles = [{"id": r["id"], "name": r["name"], "slug": r["slug"]}
                 for r in roles_resp.json().get("results", [])]
        manufacturers = [{"id": m["id"], "name": m["name"], "slug": m["slug"]}
                         for m in mfr_resp.json().get("results", [])]
        sites = [{"id": s["id"], "name": s["name"], "slug": s["slug"], "description": s.get("description", "")}
                 for s in sites_resp.json().get("results", [])]

        return {"success": True, "data": {
            "roles": sorted(roles, key=lambda x: x["name"]),
            "manufacturers": sorted(manufacturers, key=lambda x: x["name"]),
            "sites": sorted(sites, key=lambda x: x["name"])
        }}
    except Exception as e:
        logger.error(f"NetBox 필터 옵션 조회 실패: {e}")
        raise HTTPException(status_code=502, detail=f"NetBox API error: {str(e)}")


@router.get("/netbox/device-types")
async def GetNetboxDeviceTypes(request: Request):
    """NetBox 디바이스 타입 목록 조회 (제조사 필터 지원)"""
    try:
        params = list(request.query_params.multi_items())
        if not any(k == 'limit' for k, v in params):
            params.append(('limit', 500))
        resp = http_requests.get(
            f"{NETBOX_URL}/api/dcim/device-types/",
            headers=NETBOX_HEADERS, params=params, timeout=10
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        data = [{"id": r["id"], "model": r["model"], "manufacturer_id": r["manufacturer"]["id"],
                 "manufacturer_name": r["manufacturer"]["name"]} for r in results]
        return {"success": True, "data": sorted(data, key=lambda x: x["model"])}
    except Exception as e:
        logger.error(f"NetBox 디바이스 타입 조회 실패: {e}")
        raise HTTPException(status_code=502, detail=f"NetBox API error: {str(e)}")


@router.get("/netbox/locations")
async def GetNetboxLocations(request: Request):
    """NetBox 위치 목록 조회 (사이트 필터 지원)"""
    try:
        params = list(request.query_params.multi_items())
        if not any(k == 'limit' for k, v in params):
            params.append(('limit', 500))
        resp = http_requests.get(
            f"{NETBOX_URL}/api/dcim/locations/",
            headers=NETBOX_HEADERS, params=params, timeout=10
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        data = [{"id": r["id"], "name": r["name"],
                 "site_id": r.get("site", {}).get("id"), "site_name": r.get("site", {}).get("name", "")}
                for r in results]
        return {"success": True, "data": sorted(data, key=lambda x: x["name"])}
    except Exception as e:
        logger.error(f"NetBox 위치 조회 실패: {e}")
        raise HTTPException(status_code=502, detail=f"NetBox API error: {str(e)}")


@router.get("/netbox/racks")
async def GetNetboxRacks(request: Request):
    """NetBox 랙 목록 조회 (사이트/위치 필터 지원)"""
    try:
        params = list(request.query_params.multi_items())
        if not any(k == 'limit' for k, v in params):
            params.append(('limit', 500))
        resp = http_requests.get(
            f"{NETBOX_URL}/api/dcim/racks/",
            headers=NETBOX_HEADERS, params=params, timeout=10
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        data = [{"id": r["id"], "name": r["name"],
                 "site_id": r.get("site", {}).get("id"),
                 "location_id": r.get("location", {}).get("id") if r.get("location") else None}
                for r in results]
        return {"success": True, "data": sorted(data, key=lambda x: x["name"])}
    except Exception as e:
        logger.error(f"NetBox 랙 조회 실패: {e}")
        raise HTTPException(status_code=502, detail=f"NetBox API error: {str(e)}")


@router.post("/netbox/devices")
async def CreateNetboxDevice(request: Request):
    """NetBox 디바이스 생성"""
    logger.info("NetBox 디바이스 생성 요청")
    try:
        data = await request.json()
        resp = http_requests.post(
            f"{NETBOX_URL}/api/dcim/devices/",
            headers={**NETBOX_HEADERS, "Content-Type": "application/json"},
            json=data, timeout=15
        )
        if resp.status_code == 201:
            logger.info(f"NetBox 디바이스 생성 완료: {data.get('name', '')}")
            return {"success": True, "data": resp.json()}
        else:
            detail = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text
            logger.error(f"NetBox 디바이스 생성 실패: {resp.status_code} {detail}")
            raise HTTPException(status_code=resp.status_code, detail=detail)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"NetBox 디바이스 생성 실패: {e}")
        raise HTTPException(status_code=502, detail=f"NetBox API error: {str(e)}")


@router.patch("/netbox/devices/{device_id}")
async def UpdateNetboxDevice(device_id: int, request: Request):
    """NetBox 디바이스 수정"""
    logger.info(f"NetBox 디바이스 수정 요청: ID={device_id}")
    try:
        data = await request.json()
        resp = http_requests.patch(
            f"{NETBOX_URL}/api/dcim/devices/{device_id}/",
            headers={**NETBOX_HEADERS, "Content-Type": "application/json"},
            json=data, timeout=15
        )
        if resp.status_code == 200:
            logger.info(f"NetBox 디바이스 수정 완료: ID={device_id}")
            return {"success": True, "data": resp.json()}
        else:
            detail = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"NetBox 디바이스 수정 실패: {e}")
        raise HTTPException(status_code=502, detail=f"NetBox API error: {str(e)}")


@router.delete("/netbox/devices/{device_id}")
async def DeleteNetboxDevice(device_id: int):
    """NetBox 디바이스 삭제"""
    logger.info(f"NetBox 디바이스 삭제 요청: ID={device_id}")
    try:
        resp = http_requests.delete(
            f"{NETBOX_URL}/api/dcim/devices/{device_id}/",
            headers=NETBOX_HEADERS, timeout=15
        )
        if resp.status_code == 204:
            logger.info(f"NetBox 디바이스 삭제 완료: ID={device_id}")
            return {"success": True, "message": "디바이스가 삭제되었습니다."}
        else:
            detail = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"NetBox 디바이스 삭제 실패: {e}")
        raise HTTPException(status_code=502, detail=f"NetBox API error: {str(e)}")


# ==================== 통합검색 ====================

@router.get("/search")
async def unified_search(q: str = Query("", min_length=0)):
    """통합검색 - 6개 테이블에서 키워드 검색"""
    if len(q.strip()) < 2:
        return {"success": True, "query": q, "results": {}, "total_count": 0}

    logger.info(f"통합검색 요청: q={q}")
    pattern = f"%{q.strip()}%"

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            results = {}

            # 1. circuit (subscriber_codes JOIN으로 회사명 검색 가능)
            circuit_where = """
                c.circuit_id ILIKE %s OR c.cot_device ILIKE %s OR c.rt_device ILIKE %s
                OR c.member_code ILIKE %s OR c.provider ILIKE %s OR c.bandwidth ILIKE %s
                OR c.comments ILIKE %s OR sc.company_name ILIKE %s
            """
            circuit_params = (pattern, pattern, pattern, pattern, pattern, pattern, pattern, pattern)

            cur.execute(f"""
                SELECT c.id, c.circuit_id AS title,
                       COALESCE(sc.company_name, c.member_code) || ' / ' || COALESCE(c.provider, '') || ' / ' || COALESCE(c.bandwidth, '') AS subtitle,
                       c.member_code, c.provider, c.state
                FROM circuit c
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                WHERE {circuit_where}
                ORDER BY c.id LIMIT 5
            """, circuit_params)
            circuit_items = [dict(r) for r in cur.fetchall()]

            cur.execute(f"""
                SELECT count(*) FROM circuit c
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                WHERE {circuit_where}
            """, circuit_params)
            circuit_total = cur.fetchone()["count"]
            results["circuits"] = {"total": circuit_total, "items": circuit_items}

            # 2. subscriber_codes
            cur.execute("""
                SELECT id, company_name AS title,
                       COALESCE(member_code, '') || ' / ' || COALESCE(subscription_type, '') AS subtitle,
                       member_code
                FROM subscriber_codes
                WHERE company_name ILIKE %s OR member_code ILIKE %s
                ORDER BY member_number LIMIT 5
            """, (pattern, pattern))
            sub_items = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT count(*) FROM subscriber_codes
                WHERE company_name ILIKE %s OR member_code ILIKE %s
            """, (pattern, pattern))
            sub_total = cur.fetchone()["count"]
            results["subscribers"] = {"total": sub_total, "items": sub_items}

            # 3. network_contracts
            cur.execute("""
                SELECT id, COALESCE("회원사명", '') AS title,
                       COALESCE("회선분류", '') || ' / ' || COALESCE("계약유형", '') AS subtitle,
                       key_code, "지역"
                FROM network_contracts
                WHERE "회원사명" ILIKE %s OR key_code ILIKE %s
                      OR "회선분류" ILIKE %s OR "계약유형" ILIKE %s
                      OR "비고" ILIKE %s
                ORDER BY id LIMIT 5
            """, (pattern, pattern, pattern, pattern, pattern))
            contract_items = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT count(*) FROM network_contracts
                WHERE "회원사명" ILIKE %s OR key_code ILIKE %s
                      OR "회선분류" ILIKE %s OR "계약유형" ILIKE %s
                      OR "비고" ILIKE %s
            """, (pattern, pattern, pattern, pattern, pattern))
            contract_total = cur.fetchone()["count"]
            results["contracts"] = {"total": contract_total, "items": contract_items}

            # 4. customer_addresses
            cur.execute("""
                SELECT ca.id, COALESCE(ca.summary_address, ca.detailed_address, '') AS title,
                       COALESCE(sc.company_name, ca.member_code) || ' / ' || COALESCE(ca.datacenter_code, '') AS subtitle,
                       ca.member_code
                FROM customer_addresses ca
                LEFT JOIN subscriber_codes sc ON ca.member_code = sc.member_code
                WHERE ca.summary_address ILIKE %s OR ca.detailed_address ILIKE %s
                      OR ca.member_code ILIKE %s OR ca.main_address ILIKE %s
                      OR sc.company_name ILIKE %s
                ORDER BY ca.id LIMIT 5
            """, (pattern, pattern, pattern, pattern, pattern))
            addr_items = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT count(*) FROM customer_addresses ca
                LEFT JOIN subscriber_codes sc ON ca.member_code = sc.member_code
                WHERE ca.summary_address ILIKE %s OR ca.detailed_address ILIKE %s
                      OR ca.member_code ILIKE %s OR ca.main_address ILIKE %s
                      OR sc.company_name ILIKE %s
            """, (pattern, pattern, pattern, pattern, pattern))
            addr_total = cur.fetchone()["count"]
            results["addresses"] = {"total": addr_total, "items": addr_items}

            # 5. sise_products
            cur.execute("""
                SELECT id, product_name AS title,
                       COALESCE(line_speed, '') || ' / ' || COALESCE(data_format, '') AS subtitle
                FROM sise_products
                WHERE product_name ILIKE %s OR line_speed ILIKE %s
                      OR operation_ip1 ILIKE %s OR operation_ip2 ILIKE %s
                      OR test_ip ILIKE %s OR dr_ip ILIKE %s
                ORDER BY id LIMIT 5
            """, (pattern, pattern, pattern, pattern, pattern, pattern))
            product_items = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT count(*) FROM sise_products
                WHERE product_name ILIKE %s OR line_speed ILIKE %s
                      OR operation_ip1 ILIKE %s OR operation_ip2 ILIKE %s
                      OR test_ip ILIKE %s OR dr_ip ILIKE %s
            """, (pattern, pattern, pattern, pattern, pattern, pattern))
            product_total = cur.fetchone()["count"]
            results["products"] = {"total": product_total, "items": product_items}

            # 6. member_fee_schedule
            cur.execute("""
                SELECT id, COALESCE(description, '') AS title,
                       COALESCE(usage, '') || ' / ' || COALESCE(bandwidth, '') AS subtitle
                FROM member_fee_schedule
                WHERE description ILIKE %s OR usage ILIKE %s OR bandwidth ILIKE %s
                ORDER BY id LIMIT 5
            """, (pattern, pattern, pattern))
            fee_items = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT count(*) FROM member_fee_schedule
                WHERE description ILIKE %s OR usage ILIKE %s OR bandwidth ILIKE %s
            """, (pattern, pattern, pattern))
            fee_total = cur.fetchone()["count"]
            results["fees"] = {"total": fee_total, "items": fee_items}

            # 7. 회원사 회선내역 (회원사별 그룹핑 → /circuits 링크)
            cur.execute("""
                SELECT sc.company_name AS title,
                       sc.member_code || ' / 회선 ' || count(*)::text || '건' AS subtitle,
                       sc.member_code, count(*) AS circuit_count
                FROM circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                WHERE sc.company_name ILIKE %s OR sc.member_code ILIKE %s
                GROUP BY sc.company_name, sc.member_code
                ORDER BY count(*) DESC LIMIT 5
            """, (pattern, pattern))
            member_circuit_items = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT count(DISTINCT sc.member_code)
                FROM circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                WHERE sc.company_name ILIKE %s OR sc.member_code ILIKE %s
            """, (pattern, pattern))
            member_circuit_total = cur.fetchone()["count"]
            results["member_circuits"] = {"total": member_circuit_total, "items": member_circuit_items}

            # 8. 회원사 매출내역 (회원사별 매출 집계 → /revenue_summary 링크)
            cur.execute("""
                SELECT sc.company_name AS title,
                       sc.member_code || ' / ' ||
                       COALESCE(sum(mf.price)::text, '0') || '원 (' ||
                       count(*)::text || '회선)' AS subtitle,
                       sc.member_code, count(*) AS circuit_count,
                       COALESCE(sum(mf.price), 0) AS total_revenue
                FROM circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mf
                    ON c.usage = mf.usage AND c.bandwidth = mf.bandwidth
                    AND c.phase = mf.phase AND c.additional_circuit = mf.additional_circuit
                WHERE (sc.company_name ILIKE %s OR sc.member_code ILIKE %s)
                    AND c.usage IN ('ORD', 'MPR')
                GROUP BY sc.company_name, sc.member_code
                ORDER BY COALESCE(sum(mf.price), 0) DESC LIMIT 5
            """, (pattern, pattern))
            revenue_items = [dict(r) for r in cur.fetchall()]
            # price를 포맷팅
            for item in revenue_items:
                rev = item.get("total_revenue", 0)
                if rev and rev > 0:
                    item["subtitle"] = f"{item['member_code']} / 월 {rev:,.0f}원 ({item['circuit_count']}회선)"

            cur.execute("""
                SELECT count(DISTINCT sc.member_code)
                FROM circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mf
                    ON c.usage = mf.usage AND c.bandwidth = mf.bandwidth
                    AND c.phase = mf.phase AND c.additional_circuit = mf.additional_circuit
                WHERE (sc.company_name ILIKE %s OR sc.member_code ILIKE %s)
                    AND c.usage IN ('ORD', 'MPR')
            """, (pattern, pattern))
            revenue_total = cur.fetchone()["count"]
            results["revenue"] = {"total": revenue_total, "items": revenue_items}

            # 9. purchase_contract (회원사 매입내역)
            purchase_where = """
                pc.member_code ILIKE %s OR pc.datacenter_code ILIKE %s
                OR pc.provider ILIKE %s OR pc.service_id ILIKE %s
                OR pc.nni_id ILIKE %s OR pc.cost_code ILIKE %s
                OR sc.company_name ILIKE %s
            """
            purchase_params = (pattern, pattern, pattern, pattern, pattern, pattern, pattern)

            cur.execute(f"""
                SELECT pc.id, COALESCE(sc.company_name, pc.member_code) AS title,
                       COALESCE(pc.provider, '') || ' / ' || COALESCE(pc.service_id, '') || ' / ' || COALESCE(nc.cost_standart, '') AS subtitle,
                       pc.member_code
                FROM purchase_contract pc
                LEFT JOIN subscriber_codes sc ON pc.member_code = sc.member_code
                LEFT JOIN network_cost nc ON pc.cost_code = nc.code
                WHERE {purchase_where}
                ORDER BY pc.id LIMIT 5
            """, purchase_params)
            purchase_items = [dict(r) for r in cur.fetchall()]

            cur.execute(f"""
                SELECT count(*) FROM purchase_contract pc
                LEFT JOIN subscriber_codes sc ON pc.member_code = sc.member_code
                WHERE {purchase_where}
            """, purchase_params)
            purchase_total = cur.fetchone()["count"]
            results["purchases"] = {"total": purchase_total, "items": purchase_items}

            cur.close()

            total_count = sum(cat["total"] for cat in results.values())
            logger.info(f"통합검색 완료: q={q}, total={total_count}")

            return {
                "success": True,
                "query": q,
                "results": results,
                "total_count": total_count
            }

    except Exception as e:
        logger.error(f"통합검색 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")
