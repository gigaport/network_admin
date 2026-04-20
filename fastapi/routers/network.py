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
from utils.nxapi_client import query_interfaces as nxapi_query_interfaces, query_config_checks as nxapi_query_config_checks, query_pim_sparse_check as nxapi_query_pim_check
from utils.arista_eapi_client import query_config_checks as arista_query_config_checks
# system_monitor는 호스트 cron에서 JSON 파일로 저장
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
    # dictionary 형태로 변환 (None 결과 필터링)
    results_dict = {item["device_name"]: item for item in results if item is not None}

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

    # DB에 정보사 멀티캐스트 상태 저장
    try:
        valid_results = [r for r in results if r is not None]
        if valid_results:
            now = datetime.now()
            rows = []
            for item in valid_results:
                products = item.get("products", [])
                products_str = ",".join(products) if isinstance(products, list) else str(products or "")
                pim_rp = item.get("pim_rp", "")
                rows.append((
                    "pr_information",
                    item.get("member_code", ""),
                    item.get("member_name", ""),
                    str(item.get("member_no", "")),
                    item.get("device_name", ""),
                    item.get("device_os", ""),
                    products_str,
                    pim_rp if isinstance(pim_rp, str) else (pim_rp[0] if pim_rp else ""),
                    item.get("product_cnt", 0) or 0,
                    item.get("mroute_cnt", 0) or 0,
                    item.get("oif_cnt", 0) or 0,
                    item.get("connected_server_cnt", 0) or 0,
                    str(item.get("min_update", "") or ""),
                    item.get("check_result", ""),
                    item.get("alarm", False),
                    now
                ))
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM multicast_status WHERE market_type = 'pr_information' AND checked_at < NOW() - INTERVAL '2 days'")
                    from psycopg2.extras import execute_values
                    execute_values(cur, """
                        INSERT INTO multicast_status
                            (market_type, member_code, member_name, member_no, device_name, device_os,
                             products, pim_rp, product_cnt, mroute_cnt, oif_cnt, connected_server_cnt,
                             min_update, check_result, alarm, checked_at)
                        VALUES %s
                    """, rows)
                conn.commit()
            logger.info(f"정보사 멀티캐스트 DB 저장 완료: {len(rows)}건")
    except Exception as e:
        logger.error(f"정보사 멀티캐스트 DB 저장 실패: {e}")

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
                    c.datacenter_code, c.gubn,
                    ca.summary_address,
                    c.side_a, c.provider, c.circuit_id, c.nni_id,
                    c.type, c.state, c.env, c.usage, c.product, c.bandwidth,
                    c.additional_circuit, c.phase, c.fee_code,
                    mfs.price AS fee_price, mfs.description AS fee_description,
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
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
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

        required_fields = ['member_code', 'datacenter_code']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            raise HTTPException(status_code=400, detail=f"필수 필드 누락: {', '.join(missing)}")

        with get_connection() as conn:
            cur = conn.cursor()

            insert_query = """
                INSERT INTO circuit (
                    member_code, datacenter_code, gubn, side_a, provider, circuit_id, nni_id,
                    type, state, env, usage, product, bandwidth, additional_circuit,
                    cot_device, rt_device, lldp_cot_device, lldp_port, lldp_rt_device, lldp_rt_port,
                    join_type, contract_date, expiry_date, contract_period,
                    report_number, comments, phase, fee_code
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
            """

            cur.execute(insert_query, (
                data.get('member_code'), data.get('datacenter_code'),
                data.get('gubn') or None,
                data.get('side_a') or '', data.get('provider') or '',
                data.get('circuit_id') or '', data.get('nni_id') or None,
                data.get('type') or '', data.get('state') or '',
                data.get('env') or '', data.get('usage') or '',
                data.get('product') or None, data.get('bandwidth') or '',
                data.get('additional_circuit', False),
                data.get('cot_device') or '', data.get('rt_device') or '',
                data.get('lldp_cot_device') or None, data.get('lldp_port') or None,
                data.get('lldp_rt_device') or None, data.get('lldp_rt_port') or None,
                data.get('join_type', 0),
                data.get('contract_date') or None, data.get('expiry_date') or None,
                data.get('contract_period') or None,
                data.get('report_number') or None, data.get('comments') or None,
                data.get('phase') or 0, data.get('fee_code') or None,
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
            'member_code', 'datacenter_code', 'gubn', 'side_a', 'provider',
            'circuit_id', 'nni_id', 'type', 'state', 'env', 'usage',
            'product', 'bandwidth', 'additional_circuit',
            'cot_device', 'rt_device',
            'lldp_cot_device', 'lldp_port', 'lldp_rt_device', 'lldp_rt_port',
            'join_type', 'contract_date', 'expiry_date', 'contract_period',
            'report_number', 'comments', 'phase', 'fee_code'
        }

        # 요청 데이터에 포함된 필드만 SET 절 구성
        # 빈 문자열/None 허용 컬럼 (nullable 필드)
        nullable_columns = {'comments', 'report_number', 'gubn',
                            'lldp_cot_device', 'lldp_port', 'lldp_rt_device', 'lldp_rt_port'}
        set_parts = []
        values = []
        for key, value in data.items():
            if key not in allowed_columns:
                continue
            # nullable 컬럼은 빈 문자열도 허용 (NULL로 저장)
            if key in nullable_columns:
                set_parts.append(f"{key} = %s")
                values.append(value if value else None)
            elif value is not None and value != '':
                set_parts.append(f"{key} = %s")
                values.append(value)

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


# ==================== 정보이용사 회선내역 (Info Company Circuits) ====================

@router.get("/info_company_circuits")
async def GetInfoCompanyCircuits():
    """정보이용사 회선내역 전체 조회"""
    logger.info("정보이용사 회선내역 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    c.id, c.member_code,
                    sc.member_number, sc.company_name,
                    c.datacenter_code, c.gubn,
                    ca.summary_address,
                    c.side_a, c.provider, c.circuit_id,
                    c.type, c.env, c.usage, c.product, c.bandwidth,
                    c.additional_circuit, c.phase, c.fee_code,
                    mfs.price AS fee_price, mfs.description AS fee_description,
                    c.lldp_port,
                    c.join_type, c.contract_date, c.expiry_date, c.contract_period,
                    c.report_number, c.comments,
                    c.created_at, c.updated_at
                FROM info_company_circuit c
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN customer_addresses ca
                    ON c.member_code = ca.member_code
                    AND c.datacenter_code = ca.datacenter_code
                LEFT JOIN info_fee_schedule mfs ON c.fee_code = mfs.fee_code
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

        logger.info(f"정보이용사 회선내역 조회 완료: {len(results)}건")
        return {"success": True, "data": results}

    except Exception as e:
        logger.error(f"정보이용사 회선내역 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/info_company_circuits")
async def CreateInfoCompanyCircuit(request: Request):
    """정보이용사 회선내역 추가"""
    logger.info("정보이용사 회선내역 추가 요청")

    try:
        data = await request.json()

        required_fields = ['member_code', 'datacenter_code']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            raise HTTPException(status_code=400, detail=f"필수 필드 누락: {', '.join(missing)}")

        with get_connection() as conn:
            cur = conn.cursor()

            insert_query = """
                INSERT INTO info_company_circuit (
                    member_code, datacenter_code, gubn, side_a, provider, circuit_id,
                    type, env, usage, product, bandwidth, additional_circuit,
                    lldp_port, join_type, contract_date, expiry_date, contract_period,
                    report_number, comments, phase, fee_code
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
            """

            cur.execute(insert_query, (
                data.get('member_code'), data.get('datacenter_code'),
                data.get('gubn') or None, data.get('side_a') or None,
                data.get('provider') or '', data.get('circuit_id') or '',
                data.get('type') or '', data.get('env') or '',
                data.get('usage') or '', data.get('product') or None,
                data.get('bandwidth') or None,
                data.get('additional_circuit', False),
                data.get('lldp_port') or None,
                data.get('join_type', 0),
                data.get('contract_date') or None, data.get('expiry_date') or None,
                data.get('contract_period') or None,
                data.get('report_number') or None, data.get('comments') or None,
                data.get('phase') or 0, data.get('fee_code') or None,
            ))

            cur.close()

        logger.info(f"정보이용사 회선내역 추가 완료: {data.get('circuit_id')}")
        return {"success": True, "message": "정보이용사 회선내역이 추가되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"정보이용사 회선내역 추가 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/info_company_circuits/{circuit_id}")
async def UpdateInfoCompanyCircuit(circuit_id: int, request: Request):
    """정보이용사 회선내역 수정"""
    logger.info(f"정보이용사 회선내역 수정 요청: ID={circuit_id}")

    try:
        data = await request.json()
        data.pop('id', None)

        allowed_columns = {
            'member_code', 'datacenter_code', 'gubn', 'side_a', 'provider',
            'circuit_id', 'type', 'env', 'usage',
            'product', 'bandwidth', 'additional_circuit',
            'lldp_port', 'join_type', 'contract_date', 'expiry_date', 'contract_period',
            'report_number', 'comments', 'phase', 'fee_code'
        }

        nullable_columns = {'comments', 'report_number', 'lldp_port'}
        set_parts = []
        values = []
        for key, value in data.items():
            if key not in allowed_columns:
                continue
            if key in nullable_columns:
                set_parts.append(f"{key} = %s")
                values.append(value if value else None)
            elif value is not None and value != '':
                set_parts.append(f"{key} = %s")
                values.append(value)

        if not set_parts:
            raise HTTPException(status_code=400, detail="수정할 데이터가 없습니다.")

        set_parts.append("updated_at = CURRENT_TIMESTAMP")
        values.append(circuit_id)

        with get_connection() as conn:
            cur = conn.cursor()
            update_query = f"UPDATE info_company_circuit SET {', '.join(set_parts)} WHERE id = %s"
            cur.execute(update_query, values)
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="정보이용사 회선내역을 찾을 수 없습니다.")
            cur.close()

        logger.info(f"정보이용사 회선내역 수정 완료: ID={circuit_id}")
        return {"success": True, "message": "정보이용사 회선내역이 수정되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"정보이용사 회선내역 수정 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/info_company_circuits/{circuit_id}")
async def DeleteInfoCompanyCircuit(circuit_id: int):
    """정보이용사 회선내역 삭제"""
    logger.info(f"정보이용사 회선내역 삭제 요청: ID={circuit_id}")

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM info_company_circuit WHERE id = %s", (circuit_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="정보이용사 회선내역을 찾을 수 없습니다.")
            cur.close()

        logger.info(f"정보이용사 회선내역 삭제 완료: ID={circuit_id}")
        return {"success": True, "message": "정보이용사 회선내역이 삭제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"정보이용사 회선내역 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/fee_schedule")
async def GetFeeSchedule():
    """과금기준 목록 조회"""
    logger.info("과금기준 목록 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT id, fee_code, usage, description, price, phase, bandwidth, additional_circuit
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
                INSERT INTO member_fee_schedule (fee_code, usage, description, price, phase, bandwidth, additional_circuit)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                data.get('fee_code'), data.get('usage'), data.get('description'),
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
                    fee_code = %s, usage = %s, description = %s,
                    price = %s, phase = %s,
                    bandwidth = %s, additional_circuit = %s
                WHERE id = %s
            """, (
                data.get('fee_code'), data.get('usage'), data.get('description'),
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


# ==================== 정보이용사 요금기준 (Info Fee Schedule) ====================

@router.get("/info_fee_schedule")
async def GetInfoFeeSchedule():
    """정보이용사 과금기준 목록 조회"""
    logger.info("정보이용사 과금기준 목록 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT id, fee_code, usage, description, price, phase, bandwidth, additional_circuit
                FROM info_fee_schedule
                ORDER BY id
            """)
            results = cur.fetchall()
            cur.close()

        logger.info(f"정보이용사 과금기준 목록 조회 완료: {len(results)}건")
        return {"success": True, "data": results}

    except Exception as e:
        logger.error(f"정보이용사 과금기준 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/info_fee_schedule")
async def CreateInfoFeeSchedule(request: Request):
    """정보이용사 과금기준 추가"""
    logger.info("정보이용사 과금기준 추가 요청")

    try:
        data = await request.json()

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO info_fee_schedule (fee_code, usage, description, price, phase, bandwidth, additional_circuit)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                data.get('fee_code'), data.get('usage'), data.get('description'),
                data.get('price', 0), data.get('phase', 0),
                data.get('bandwidth') or None, data.get('additional_circuit', False)
            ))

            cur.close()

        logger.info(f"정보이용사 과금기준 추가 완료: {data.get('usage')} - {data.get('description')}")
        return {"success": True, "message": "정보이용사 과금기준이 추가되었습니다."}

    except Exception as e:
        logger.error(f"정보이용사 과금기준 추가 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/info_fee_schedule/{fee_id}")
async def UpdateInfoFeeSchedule(fee_id: int, request: Request):
    """정보이용사 과금기준 수정"""
    logger.info(f"정보이용사 과금기준 수정 요청: ID={fee_id}")

    try:
        data = await request.json()

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                UPDATE info_fee_schedule SET
                    fee_code = %s, usage = %s, description = %s,
                    price = %s, phase = %s,
                    bandwidth = %s, additional_circuit = %s
                WHERE id = %s
            """, (
                data.get('fee_code'), data.get('usage'), data.get('description'),
                data.get('price', 0), data.get('phase', 0),
                data.get('bandwidth') or None, data.get('additional_circuit', False),
                fee_id
            ))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Info fee schedule not found")

            cur.close()

        logger.info(f"정보이용사 과금기준 수정 완료: ID={fee_id}")
        return {"success": True, "message": "정보이용사 과금기준이 수정되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"정보이용사 과금기준 수정 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/info_fee_schedule/{fee_id}")
async def DeleteInfoFeeSchedule(fee_id: int):
    """정보이용사 과금기준 삭제"""
    logger.info(f"정보이용사 과금기준 삭제 요청: ID={fee_id}")

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("DELETE FROM info_fee_schedule WHERE id = %s", (fee_id,))

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Info fee schedule not found")

            cur.close()

        logger.info(f"정보이용사 과금기준 삭제 완료: ID={fee_id}")
        return {"success": True, "message": "정보이용사 과금기준이 삭제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"정보이용사 과금기준 삭제 실패: {e}")
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
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
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
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
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
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
                WHERE c.usage IN ('ORD', 'MPR')
                GROUP BY c.usage
                ORDER BY c.usage
            """)
            revenue_by_usage = {row['usage']: int(row['revenue']) for row in cur.fetchall()}

            # 10-1. 정보이용사 MKD 매출 총액
            cur.execute("""
                SELECT
                    COUNT(*) AS mkd_count,
                    COALESCE(SUM(ifs.price), 0) AS mkd_total
                FROM info_company_circuit c
                LEFT JOIN info_fee_schedule ifs ON c.fee_code = ifs.fee_code
                WHERE c.usage = 'MKD'
            """)
            info_revenue_row = dict(cur.fetchone())

            # 10-2. 정보이용사 매출 Top 10
            cur.execute("""
                SELECT sc.company_name, sc.member_code,
                       COALESCE(SUM(ifs.price), 0) AS total_revenue
                FROM info_company_circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN info_fee_schedule ifs ON c.fee_code = ifs.fee_code
                WHERE c.usage = 'MKD'
                GROUP BY sc.company_name, sc.member_code
                HAVING SUM(ifs.price) > 0
                ORDER BY total_revenue DESC
                LIMIT 10
            """)
            info_top_revenue_members = [dict(row) for row in cur.fetchall()]

            # 10-3. 정보이용사 매입 총액
            cur.execute("""
                SELECT COALESCE(SUM(nc.cost_price), 0) AS purchase_total
                FROM info_purchase_contract pc
                LEFT JOIN network_cost nc ON pc.cost_code = nc.code
            """)
            info_purchase_total = float(cur.fetchone()['purchase_total'] or 0)

            # 11. 이익 현황 (매출 - 매입)
            cur.execute("""
                SELECT COALESCE(SUM(nc.cost_price), 0) AS purchase_total
                FROM purchase_contract pc
                LEFT JOIN network_cost nc ON pc.cost_code = nc.code
            """)
            purchase_total_row = cur.fetchone()
            purchase_grand_total = float(purchase_total_row['purchase_total'] or 0)

            # 12. 회원사별 이익 (전체)
            cur.execute("""
                WITH rev AS (
                    SELECT sc.member_code, sc.company_name,
                           COALESCE(SUM(mfs.price), 0) AS revenue_total
                    FROM circuit c
                    JOIN subscriber_codes sc ON c.member_code = sc.member_code
                    LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
                    WHERE c.usage IN ('ORD', 'MPR')
                    GROUP BY sc.member_code, sc.company_name
                ),
                pur AS (
                    SELECT pc.member_code,
                           COALESCE(SUM(nc.cost_price), 0) AS purchase_total
                    FROM purchase_contract pc
                    LEFT JOIN network_cost nc ON pc.cost_code = nc.code
                    GROUP BY pc.member_code
                )
                SELECT rev.member_code, rev.company_name,
                       rev.revenue_total,
                       COALESCE(pur.purchase_total, 0) AS purchase_total,
                       rev.revenue_total - COALESCE(pur.purchase_total, 0) AS profit
                FROM rev
                LEFT JOIN pur ON rev.member_code = pur.member_code
                ORDER BY profit DESC
            """)
            all_profit_members = [dict(row) for row in cur.fetchall()]

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
                },
                "info_revenue": {
                    "mkd_count": int(info_revenue_row['mkd_count']),
                    "mkd_total": int(info_revenue_row['mkd_total']),
                    "top_members": info_top_revenue_members,
                    "purchase_total": int(info_purchase_total)
                },
                "profit": {
                    "revenue_total": int(revenue_total['grand_total']),
                    "purchase_total": int(purchase_grand_total),
                    "profit_total": int(revenue_total['grand_total']) - int(purchase_grand_total),
                    "profit_rate": round(((int(revenue_total['grand_total']) - int(purchase_grand_total)) / int(revenue_total['grand_total'])) * 100, 1) if int(revenue_total['grand_total']) > 0 else 0.0,
                    "info_revenue_total": int(info_revenue_row['mkd_total']),
                    "info_purchase_total": int(info_purchase_total),
                    "members": all_profit_members
                }
            }
        }

    except Exception as e:
        logger.error(f"대시보드 데이터 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ==================== 매출내역 (Revenue Summary) ====================

@router.get("/revenue_summary")
async def GetRevenueSummary():
    """회원사별 매출내역 조회 (ORD/MPR 회선 요금 집계) - 날짜 필터 없음"""
    logger.info("매출내역 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # 회원사별 요약 집계
            summary_query = """
                SELECT
                    COALESCE(sc.member_code, c.member_code) as member_code,
                    sc.member_number, sc.company_name, sc.subscription_type,
                    sc.is_pb, c.phase,
                    COUNT(*) FILTER (WHERE c.usage = 'ORD') AS ord_count,
                    COUNT(*) FILTER (WHERE c.usage = 'MPR') AS mpr_count,
                    COUNT(*) AS total_count,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'ORD'), 0) AS ord_total,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'MPR'), 0) AS mpr_total,
                    COALESCE(SUM(mfs.price), 0) AS grand_total
                FROM circuit c
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
                WHERE c.usage IN ('ORD', 'MPR')
                GROUP BY COALESCE(sc.member_code, c.member_code), sc.member_number, sc.company_name, sc.subscription_type, sc.is_pb, c.phase
                ORDER BY sc.is_pb ASC NULLS FIRST, sc.member_number ASC NULLS LAST, c.phase ASC
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
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
                WHERE c.usage IN ('ORD', 'MPR')
                ORDER BY sc.member_number ASC NULLS LAST, c.datacenter_code, c.usage
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
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
                GROUP BY mr.m_start
                ORDER BY mr.m_start
            """
            cur.execute(trend_query, (trend_start, month_start))
            trend = cur.fetchall()

            # 2) 해당 월 회원사별 요약 (cumulative: only contract_date filter)
            summary_query = """
                SELECT
                    COALESCE(sc.member_code, c.member_code) as member_code,
                    sc.member_number, sc.company_name, sc.subscription_type,
                    sc.is_pb, c.phase,
                    COUNT(*) FILTER (WHERE c.usage = 'ORD') AS ord_count,
                    COUNT(*) FILTER (WHERE c.usage = 'MPR') AS mpr_count,
                    COUNT(*) AS total_count,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'ORD'), 0) AS ord_total,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'MPR'), 0) AS mpr_total,
                    COALESCE(SUM(mfs.price), 0) AS grand_total
                FROM circuit c
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
                WHERE c.usage IN ('ORD', 'MPR')
                    AND (c.contract_date IS NULL OR c.contract_date <= %s)
                GROUP BY COALESCE(sc.member_code, c.member_code), sc.member_number, sc.company_name, sc.subscription_type, sc.is_pb, c.phase
                ORDER BY sc.is_pb ASC NULLS FIRST, sc.member_number ASC NULLS LAST, c.phase ASC
            """
            cur.execute(summary_query, (month_end,))
            summary = cur.fetchall()

            # 3) 해당 월 회선별 상세 (cumulative: only contract_date filter)
            detail_query = """
                SELECT
                    c.id, c.member_code, sc.member_number, sc.company_name,
                    c.datacenter_code, c.usage, c.product, c.bandwidth,
                    c.additional_circuit, c.phase, c.provider, c.circuit_id,
                    c.contract_date, c.expiry_date,
                    mfs.price AS fee_price, mfs.description AS fee_description
                FROM circuit c
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
                WHERE c.usage IN ('ORD', 'MPR')
                    AND (c.contract_date IS NULL OR c.contract_date <= %s)
                ORDER BY sc.member_number ASC NULLS LAST, c.datacenter_code, c.usage
            """
            cur.execute(detail_query, (month_end,))
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


@router.get("/revenue_monthly_diff")
async def GetRevenueMonthlyDiff(year_month: str = Query(...)):
    """전월 대비 회선 변동 내역 조회 (추가/제거된 회선)"""
    try:
        target = datetime.strptime(year_month, "%Y-%m").date()
        cur_start = target.replace(day=1)
        cur_end = (cur_start + relativedelta(months=1)) - relativedelta(days=1)
        prev_start = cur_start - relativedelta(months=1)
        prev_end = cur_start - relativedelta(days=1)

        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # 해당 월 활성 회선
            circuit_query = """
                SELECT c.id, c.member_code, sc.company_name, c.usage, c.product,
                       c.bandwidth, c.provider, c.circuit_id, c.contract_date,
                       mfs.price, mfs.description AS fee_desc
                FROM circuit c
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
                WHERE c.usage IN ('ORD', 'MPR')
                  AND (c.contract_date IS NULL OR c.contract_date <= %s)
            """

            cur.execute(circuit_query, (cur_end,))
            cur_circuits = {r['id']: r for r in cur.fetchall()}

            cur.execute(circuit_query, (prev_end,))
            prev_circuits = {r['id']: r for r in cur.fetchall()}

            cur.close()

        added = []
        for cid, c in cur_circuits.items():
            if cid not in prev_circuits:
                added.append({
                    "type": "added",
                    "member_code": c["member_code"],
                    "company_name": c["company_name"],
                    "usage": c["usage"],
                    "product": c["product"] or "",
                    "bandwidth": c["bandwidth"] or "",
                    "provider": c["provider"] or "",
                    "circuit_id": c["circuit_id"] or "",
                    "contract_date": str(c["contract_date"]) if c["contract_date"] else "",
                    "price": c["price"] or 0,
                    "fee_desc": c["fee_desc"] or ""
                })

        removed = []
        for cid, c in prev_circuits.items():
            if cid not in cur_circuits:
                removed.append({
                    "type": "removed",
                    "member_code": c["member_code"],
                    "company_name": c["company_name"],
                    "usage": c["usage"],
                    "product": c["product"] or "",
                    "bandwidth": c["bandwidth"] or "",
                    "provider": c["provider"] or "",
                    "circuit_id": c["circuit_id"] or "",
                    "contract_date": str(c["contract_date"]) if c["contract_date"] else "",
                    "price": c["price"] or 0,
                    "fee_desc": c["fee_desc"] or ""
                })

        return {
            "success": True,
            "year_month": year_month,
            "added": sorted(added, key=lambda x: (x["usage"], x["company_name"])),
            "removed": sorted(removed, key=lambda x: (x["usage"], x["company_name"])),
            "added_count": len(added),
            "removed_count": len(removed)
        }

    except Exception as e:
        logger.error(f"월별 변동 내역 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 정보이용사 매출내역 (Info Revenue Summary) ====================

@router.get("/info_revenue_summary")
async def GetInfoRevenueSummary():
    """정보이용사별 매출내역 조회 (MKD 회선 요금 집계) - 날짜 필터 없음"""
    logger.info("정보이용사 매출내역 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            summary_query = """
                SELECT
                    sc.member_code, sc.member_number, sc.company_name, sc.subscription_type,
                    sc.is_pb, c.phase,
                    COUNT(*) AS mkd_count,
                    COALESCE(SUM(ifs.price), 0) AS mkd_total
                FROM info_company_circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN info_fee_schedule ifs ON c.fee_code = ifs.fee_code
                WHERE c.usage = 'MKD'
                GROUP BY sc.member_code, sc.member_number, sc.company_name, sc.subscription_type, sc.is_pb, c.phase
                ORDER BY sc.is_pb ASC NULLS FIRST, sc.member_number ASC, c.phase ASC
            """
            cur.execute(summary_query)
            summary = cur.fetchall()

            detail_query = """
                SELECT
                    c.id, c.member_code, sc.member_number, sc.company_name,
                    c.datacenter_code, c.usage, c.product, c.bandwidth,
                    c.additional_circuit, c.phase, c.provider, c.circuit_id,
                    ifs.price AS fee_price, ifs.description AS fee_description
                FROM info_company_circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN info_fee_schedule ifs ON c.fee_code = ifs.fee_code
                WHERE c.usage = 'MKD'
                ORDER BY sc.member_number, c.datacenter_code
            """
            cur.execute(detail_query)
            details = cur.fetchall()

            cur.close()

        logger.info(f"정보이용사 매출내역 조회 완료: {len(summary)}건, 상세 {len(details)}건")
        return {"success": True, "summary": summary, "details": details}

    except Exception as e:
        logger.error(f"정보이용사 매출내역 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/info_revenue_monthly")
async def GetInfoRevenueMonthly(year_month: str = Query(..., description="조회 월 (YYYY-MM 형식)")):
    """정보이용사 월별 매출내역 조회 (12개월 추이 + 해당 월 요약/상세)"""
    logger.info(f"정보이용사 월별 매출내역 조회: {year_month}")

    try:
        target = datetime.strptime(year_month, "%Y-%m").date()
        month_start = target.replace(day=1)
        next_month = month_start + relativedelta(months=1)
        month_end = next_month - relativedelta(days=1)
        trend_start = month_start - relativedelta(months=11)

        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            trend_query = """
                WITH months AS (
                    SELECT generate_series(%s::date, %s::date, '1 month'::interval)::date AS m_start
                ),
                month_ranges AS (
                    SELECT m_start, (m_start + interval '1 month' - interval '1 day')::date AS m_end
                    FROM months
                )
                SELECT
                    to_char(mr.m_start, 'YYYY-MM') AS month,
                    COUNT(*) AS mkd_count,
                    COALESCE(SUM(ifs.price), 0) AS mkd_total
                FROM month_ranges mr
                LEFT JOIN info_company_circuit c ON c.usage = 'MKD'
                    AND (c.contract_date IS NULL OR c.contract_date <= mr.m_end)
                LEFT JOIN info_fee_schedule ifs ON c.fee_code = ifs.fee_code
                GROUP BY mr.m_start
                ORDER BY mr.m_start
            """
            cur.execute(trend_query, (trend_start, month_start))
            trend = cur.fetchall()

            summary_query = """
                SELECT
                    sc.member_code, sc.member_number, sc.company_name, sc.subscription_type,
                    sc.is_pb, c.phase,
                    COUNT(*) AS mkd_count,
                    COALESCE(SUM(ifs.price), 0) AS mkd_total
                FROM info_company_circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN info_fee_schedule ifs ON c.fee_code = ifs.fee_code
                WHERE c.usage = 'MKD'
                    AND (c.contract_date IS NULL OR c.contract_date <= %s)
                    AND (c.expiry_date IS NULL OR c.expiry_date >= %s)
                GROUP BY sc.member_code, sc.member_number, sc.company_name, sc.subscription_type, sc.is_pb, c.phase
                ORDER BY sc.is_pb ASC NULLS FIRST, sc.member_number ASC, c.phase ASC
            """
            cur.execute(summary_query, (month_end, month_start))
            summary = cur.fetchall()

            detail_query = """
                SELECT
                    c.id, c.member_code, sc.member_number, sc.company_name,
                    c.datacenter_code, c.usage, c.product, c.bandwidth,
                    c.additional_circuit, c.phase, c.provider, c.circuit_id,
                    c.contract_date, c.expiry_date,
                    ifs.price AS fee_price, ifs.description AS fee_description
                FROM info_company_circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN info_fee_schedule ifs ON c.fee_code = ifs.fee_code
                WHERE c.usage = 'MKD'
                    AND (c.contract_date IS NULL OR c.contract_date <= %s)
                    AND (c.expiry_date IS NULL OR c.expiry_date >= %s)
                ORDER BY sc.member_number, c.datacenter_code
            """
            cur.execute(detail_query, (month_end, month_start))
            details = cur.fetchall()

            cur.close()

        logger.info(f"정보이용사 월별 매출내역 조회 완료: 추이 {len(trend)}건, 요약 {len(summary)}건, 상세 {len(details)}건")
        return {"success": True, "year_month": year_month, "trend": trend, "summary": summary, "details": details}

    except ValueError:
        raise HTTPException(status_code=400, detail="year_month 형식이 잘못되었습니다. YYYY-MM 형식으로 입력해주세요.")
    except Exception as e:
        logger.error(f"정보이용사 월별 매출내역 조회 실패: {e}")
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
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
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


@router.get("/info_revenue_report_pdf")
async def GetInfoRevenueReportPdf(year_month: str = Query(..., description="보고서 월 (YYYY-MM 형식)")):
    """정보이용사 월별 매출 보고서 PDF 다운로드"""
    logger.info(f"정보이용사 매출 보고서 PDF 생성: {year_month}")

    try:
        from fpdf import FPDF

        target = datetime.strptime(year_month, "%Y-%m").date()
        month_start = target.replace(day=1)
        next_month = month_start + relativedelta(months=1)
        month_end = next_month - relativedelta(days=1)

        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            summary_query = """
                SELECT
                    sc.member_code, sc.member_number, sc.company_name,
                    sc.subscription_type, sc.is_pb, c.phase,
                    COUNT(*) AS mkd_count,
                    COALESCE(SUM(ifs.price), 0) AS mkd_total
                FROM info_company_circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN info_fee_schedule ifs ON c.fee_code = ifs.fee_code
                WHERE c.usage = 'MKD'
                    AND (c.contract_date IS NULL OR c.contract_date <= %s)
                    AND (c.expiry_date IS NULL OR c.expiry_date >= %s)
                GROUP BY sc.member_code, sc.member_number, sc.company_name,
                         sc.subscription_type, sc.is_pb, c.phase
                ORDER BY sc.is_pb ASC NULLS FIRST, sc.member_number ASC, c.phase ASC
            """
            cur.execute(summary_query, (month_end, month_start))
            summary = cur.fetchall()
            cur.close()

        font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "DroidSansFallback.ttf")

        class InfoRevenuePDF(FPDF):
            report_title = ""
            report_period = ""

            def header(self):
                if self.page_no() == 1:
                    return
                self.set_font("Korean", "", 7)
                self.set_text_color(140, 140, 140)
                self.cell(0, 6, f"NEXTRADE MKNM  |  {self.report_title}", align='L')
                self.cell(0, 6, f"{self.report_period}", align='R', ln=True)
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

        pdf = InfoRevenuePDF(orientation='L', unit='mm', format='A4')
        pdf.add_font("Korean", "", font_path, uni=True)
        pdf.add_font("Korean", "B", font_path, uni=True)
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=18)

        target_year = target.strftime('%Y')
        target_month_num = target.strftime('%m')
        pdf.report_title = f"{target_year}년 {int(target_month_num)}월 정보이용사 매출 보고서"
        pdf.report_period = f"{month_start} ~ {month_end}"

        total_mkd = sum(r['mkd_total'] for r in summary)
        total_mkd_cnt = sum(r['mkd_count'] for r in summary)
        member_set = set(r['member_code'] for r in summary)

        # ============================
        # 1페이지: 표지
        # ============================
        pdf.add_page()
        pdf.set_fill_color(30, 58, 138)
        pdf.rect(0, 0, 297, 50, 'F')
        pdf.set_fill_color(59, 130, 246)
        pdf.rect(0, 50, 297, 4, 'F')

        pdf.set_xy(0, 12)
        pdf.set_font("Korean", "B", 28)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 14, "정보이용사 월별 매출 보고서", align='C', ln=True)
        pdf.set_font("Korean", "", 13)
        pdf.set_text_color(190, 210, 255)
        pdf.cell(0, 10, "NEXTRADE MKNM 네트워크 통합운영시스템", align='C', ln=True)

        pdf.set_text_color(50, 50, 50)
        pdf.ln(20)
        pdf.set_font("Korean", "B", 20)
        pdf.cell(0, 14, f"{target_year}년 {int(target_month_num)}월", align='C', ln=True)
        pdf.set_font("Korean", "", 11)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 8, f"({month_start} ~ {month_end})", align='C', ln=True)

        # KPI 카드
        pdf.ln(12)
        card_y = pdf.get_y()
        card_w = 85
        card_h = 32
        card_gap = 7
        card_start_x = (297 - (card_w * 3 + card_gap * 2)) / 2

        def draw_kpi_card(x, y, w, h, label, value, sub_text, r, g, b):
            pdf.set_fill_color(r, g, b)
            pdf.rect(x, y, w, h, 'F')
            pdf.set_fill_color(max(r - 40, 0), max(g - 40, 0), max(b - 40, 0))
            pdf.rect(x, y, 3, h, 'F')
            pdf.set_xy(x + 8, y + 4)
            pdf.set_font("Korean", "", 8)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(w - 12, 5, label)
            pdf.set_xy(x + 8, y + 11)
            pdf.set_font("Korean", "B", 16)
            pdf.cell(w - 12, 10, value)
            pdf.set_xy(x + 8, y + 23)
            pdf.set_font("Korean", "", 7)
            pdf.set_text_color(220, 220, 220)
            pdf.cell(w - 12, 5, sub_text)

        draw_kpi_card(card_start_x, card_y, card_w, card_h,
                      "전체 정보이용사", f"{len(member_set)}개사",
                      f"MKD 회선 {total_mkd_cnt:,}건",
                      99, 102, 241)
        draw_kpi_card(card_start_x + card_w + card_gap, card_y, card_w, card_h,
                      "MKD 회선수", f"{total_mkd_cnt:,}건",
                      f"정보이용사 {len(member_set)}개사",
                      14, 165, 233)
        draw_kpi_card(card_start_x + (card_w + card_gap) * 2, card_y, card_w, card_h,
                      "MKD 매출", f"{total_mkd:,.0f}원",
                      f"정보이용사 {len(member_set)}개사 합산",
                      5, 150, 105)

        pdf.set_y(170)
        pdf.set_font("Korean", "", 9)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 6, f"보고서 생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", align='C', ln=True)
        pdf.cell(0, 6, "NEXTRADE MKNM 네트워크 관리시스템", align='C', ln=True)

        pdf.set_fill_color(30, 58, 138)
        pdf.rect(0, 196, 297, 14, 'F')
        pdf.set_fill_color(59, 130, 246)
        pdf.rect(0, 192, 297, 4, 'F')

        # ============================
        # 2페이지: 요약 + 상위 매출
        # ============================
        pdf.add_page()

        def section_title(text):
            pdf.set_font("Korean", "B", 12)
            pdf.set_text_color(30, 58, 138)
            pdf.cell(0, 8, text, ln=True)
            y = pdf.get_y()
            pdf.set_draw_color(59, 130, 246)
            pdf.set_line_width(0.6)
            pdf.line(10, y, 100, y)
            pdf.set_line_width(0.2)
            pdf.ln(4)

        section_title("매출 요약")

        info_items = [
            ("전체 정보이용사", f"{len(member_set)}개사"),
            ("MKD 회선수", f"{total_mkd_cnt:,}건"),
            ("MKD 매출", f"{total_mkd:,.0f}원"),
        ]
        info_y = pdf.get_y()
        info_w = 88
        info_h = 14
        for i, (label, val) in enumerate(info_items):
            x = 10 + i * (info_w + 4)
            y = info_y
            pdf.set_fill_color(248, 250, 252)
            pdf.rect(x, y, info_w, info_h, 'F')
            pdf.set_xy(x + 4, y + 2)
            pdf.set_font("Korean", "", 7)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(40, 4, label)
            pdf.set_xy(x + 4, y + 7)
            pdf.set_font("Korean", "B", 10)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(80, 5, val)

        pdf.set_y(info_y + info_h + 8)

        # 매출 상위 10
        section_title("매출 상위 10 정보이용사")

        member_agg = {}
        for r in summary:
            mc = r['member_code']
            if mc not in member_agg:
                member_agg[mc] = {
                    'member_number': r['member_number'],
                    'company_name': r['company_name'],
                    'mkd_count': 0, 'mkd_total': 0
                }
            member_agg[mc]['mkd_count'] += r['mkd_count']
            member_agg[mc]['mkd_total'] += r['mkd_total']

        top10 = sorted(member_agg.values(), key=lambda x: x['mkd_total'], reverse=True)[:10]
        max_revenue = top10[0]['mkd_total'] if top10 else 1

        top_col_w = [12, 22, 80, 30, 50, 83]
        top_headers = ['순위', '정보이용사번호', '회사명', 'MKD 회선', '매출(원)', '비율']

        pdf.set_font("Korean", "B", 8)
        pdf.set_fill_color(30, 58, 138)
        pdf.set_text_color(255, 255, 255)
        for i, h in enumerate(top_headers):
            pdf.cell(top_col_w[i], 7, h, border=0, fill=True, align='C')
        pdf.ln()

        for idx, m in enumerate(top10, 1):
            row_y = pdf.get_y()
            if idx % 2 == 0:
                pdf.set_fill_color(245, 247, 250)
                pdf.rect(10, row_y, sum(top_col_w), 8, 'F')
            pdf.set_font("Korean", "B" if idx <= 3 else "", 8)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(top_col_w[0], 8, str(idx), align='C')
            pdf.set_font("Korean", "", 8)
            pdf.cell(top_col_w[1], 8, str(m['member_number'] or ''), align='C')
            pdf.cell(top_col_w[2], 8, str(m['company_name'] or '')[:32])
            pdf.cell(top_col_w[3], 8, f"{m['mkd_count']:,}건", align='R')
            pdf.set_font("Korean", "B", 8)
            pdf.cell(top_col_w[4], 8, f"{m['mkd_total']:,.0f}", align='R')
            bar_x = pdf.get_x() + 2
            bar_w = top_col_w[5] - 20
            ratio = m['mkd_total'] / max_revenue if max_revenue > 0 else 0
            pdf.set_fill_color(219, 234, 254)
            pdf.rect(bar_x, row_y + 2, bar_w, 4, 'F')
            pdf.set_fill_color(59, 130, 246)
            pdf.rect(bar_x, row_y + 2, bar_w * ratio, 4, 'F')
            pct_of_total = (m['mkd_total'] / total_mkd * 100) if total_mkd > 0 else 0
            pdf.set_font("Korean", "", 7)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(top_col_w[5], 8, f"  {pct_of_total:.1f}%", align='R')
            pdf.ln()

        # ============================
        # 3페이지~: 상세 테이블
        # ============================
        pdf.add_page()
        section_title("정보이용사별 매출 상세 내역")

        col_widths = [12, 28, 90, 22, 30, 50]
        headers = ['No', '정보이용사번호', '회사명', 'Phase', 'MKD 회선', 'MKD 매출(원)']

        def draw_table_header():
            pdf.set_font("Korean", "B", 8)
            pdf.set_fill_color(30, 58, 138)
            pdf.set_text_color(255, 255, 255)
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 7, h, border=0, fill=True, align='C')
            pdf.ln()
            y = pdf.get_y()
            pdf.set_draw_color(59, 130, 246)
            pdf.set_line_width(0.4)
            pdf.line(10, y, 10 + sum(col_widths), y)
            pdf.set_line_width(0.2)

        draw_table_header()

        for idx, row in enumerate(summary, 1):
            if pdf.get_y() > 178:
                pdf.add_page()
                section_title("정보이용사별 매출 상세 내역 (계속)")
                draw_table_header()

            row_y = pdf.get_y()
            if idx % 2 == 0:
                pdf.set_fill_color(248, 250, 252)
                pdf.rect(10, row_y, sum(col_widths), 6.5, 'F')
            pdf.set_draw_color(230, 230, 230)
            pdf.line(10, row_y + 6.5, 10 + sum(col_widths), row_y + 6.5)
            pdf.set_text_color(80, 80, 80)
            pdf.set_font("Korean", "", 7.5)
            pdf.cell(col_widths[0], 6.5, str(idx), align='C')
            pdf.cell(col_widths[1], 6.5, str(row['member_number'] or ''), align='C')
            pdf.set_text_color(30, 41, 59)
            pdf.cell(col_widths[2], 6.5, str(row['company_name'] or '')[:36])
            pdf.set_text_color(80, 80, 80)
            pdf.cell(col_widths[3], 6.5, str(row['phase'] or ''), align='C')
            pdf.set_font("Korean", "B", 7.5)
            pdf.cell(col_widths[4], 6.5, str(row['mkd_count']), align='R')
            pdf.set_text_color(5, 150, 105)
            pdf.cell(col_widths[5], 6.5, f"{row['mkd_total']:,.0f}", align='R')
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
        pdf.cell(col_widths[4], 8, str(total_mkd_cnt), fill=True, align='R')
        pdf.set_text_color(5, 150, 105)
        pdf.cell(col_widths[5], 8, f"{total_mkd:,.0f}", fill=True, align='R')
        pdf.ln()
        pdf.set_text_color(30, 58, 138)
        pdf.set_font("Korean", "B", 9)
        pdf.ln(3)
        pdf.cell(sum(col_widths), 7, f"MKD 매출 합계:  {total_mkd:,.0f}원", align='R')
        pdf.ln()

        pdf_output = pdf.output()
        pdf_buffer = io.BytesIO(pdf_output)
        pdf_buffer.seek(0)

        filename = f"info_revenue_report_{year_month}.pdf"
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except ValueError:
        raise HTTPException(status_code=400, detail="year_month 형식이 잘못되었습니다. YYYY-MM 형식으로 입력해주세요.")
    except Exception as e:
        logger.error(f"정보이용사 매출 보고서 PDF 생성 실패: {e}")
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

            # 동일 코드 중복 체크
            cur.execute("SELECT id FROM network_cost WHERE code = %s", (new_code,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail=f"이미 존재하는 원가코드입니다: {new_code}")

            # 동일 비용기준 중복 체크 (같은 통신사+회선종류)
            cur.execute("SELECT id FROM network_cost WHERE provider = %s AND circuit_type = %s AND cost_standart = %s", (provider, circuit_type, cost_standart))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail=f"동일한 통신사/회선종류/비용기준이 이미 존재합니다.")

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

            # 동일 비용기준 중복 체크 (자기 자신 제외)
            cur.execute("SELECT id FROM network_cost WHERE provider = %s AND circuit_type = %s AND cost_standart = %s AND id != %s", (provider, circuit_type, cost_standart, cost_id))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail=f"동일한 통신사/회선종류/비용기준이 이미 존재합니다.")

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
                SELECT pc.id, sc.member_number, pc.member_code, pc.datacenter_code, pc.provider,
                       TO_CHAR(pc.billing_start_date, 'YYYY-MM-DD') as billing_start_date,
                       TO_CHAR(pc.contract_end_date, 'YYYY-MM-DD') as contract_end_date,
                       pc.service_id, pc.nni_id, pc.cost_code,
                       nc.cost_price, nc.cost_standart,
                       sc.company_name
                FROM purchase_contract pc
                LEFT JOIN network_cost nc ON pc.cost_code = nc.code
                LEFT JOIN subscriber_codes sc ON pc.member_code = sc.member_code
                ORDER BY sc.member_number ASC, pc.datacenter_code, pc.provider
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
        member_code = (data.get('member_code') or '').strip()
        datacenter_code = (data.get('datacenter_code') or '').strip()
        provider = (data.get('provider') or '').strip()
        billing_start_date = data.get('billing_start_date') or None
        contract_end_date = data.get('contract_end_date') or None
        service_id = (data.get('service_id') or '').strip() or None
        nni_id = (data.get('nni_id') or '').strip() or None
        cost_code = (data.get('cost_code') or '').strip() or None

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
        member_code = (data.get('member_code') or '').strip()
        datacenter_code = (data.get('datacenter_code') or '').strip()
        provider = (data.get('provider') or '').strip()
        billing_start_date = data.get('billing_start_date') or None
        contract_end_date = data.get('contract_end_date') or None
        service_id = (data.get('service_id') or '').strip() or None
        nni_id = (data.get('nni_id') or '').strip() or None
        cost_code = (data.get('cost_code') or '').strip() or None

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
# 정보이용사 매입내역 (Info Purchase Contract) CRUD
# ============================================================

@router.get("/info_purchase_contract")
async def GetInfoPurchaseContract():
    """정보이용사 매입내역 전체 조회 (network_cost JOIN)"""
    logger.info("정보이용사 매입내역 조회 시작")
    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT pc.id, sc.member_number, pc.member_code, pc.datacenter_code, pc.provider,
                       TO_CHAR(pc.billing_start_date, 'YYYY-MM-DD') as billing_start_date,
                       TO_CHAR(pc.contract_end_date, 'YYYY-MM-DD') as contract_end_date,
                       pc.service_id, pc.nni_id, pc.cost_code,
                       nc.cost_price, nc.cost_standart,
                       sc.company_name
                FROM info_purchase_contract pc
                LEFT JOIN network_cost nc ON pc.cost_code = nc.code
                LEFT JOIN subscriber_codes sc ON pc.member_code = sc.member_code
                ORDER BY sc.member_number ASC, pc.datacenter_code, pc.provider
            """)
            results = cur.fetchall()
            cur.close()
        logger.info(f"정보이용사 매입내역 조회 완료: {len(results)}건")
        return {"success": True, "data": results}
    except Exception as e:
        logger.error(f"정보이용사 매입내역 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/info_purchase_contract")
async def CreateInfoPurchaseContract(request: Request):
    """정보이용사 매입내역 추가"""
    logger.info("정보이용사 매입내역 추가 요청")
    try:
        data = await request.json()
        member_code = (data.get('member_code') or '').strip()
        datacenter_code = (data.get('datacenter_code') or '').strip()
        provider = (data.get('provider') or '').strip()
        billing_start_date = data.get('billing_start_date') or None
        contract_end_date = data.get('contract_end_date') or None
        service_id = (data.get('service_id') or '').strip() or None
        nni_id = (data.get('nni_id') or '').strip() or None
        cost_code = (data.get('cost_code') or '').strip() or None

        if not member_code:
            raise HTTPException(status_code=400, detail="정보이용사코드는 필수입니다.")

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO info_purchase_contract
                    (member_code, datacenter_code, provider, billing_start_date, contract_end_date, service_id, nni_id, cost_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (member_code, datacenter_code, provider, billing_start_date, contract_end_date, service_id, nni_id, cost_code))
            cur.close()

        logger.info(f"정보이용사 매입내역 추가 완료: {member_code}")
        return {"success": True, "message": "매입내역이 추가되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"정보이용사 매입내역 추가 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/info_purchase_contract/{item_id}")
async def UpdateInfoPurchaseContract(item_id: int, request: Request):
    """정보이용사 매입내역 수정"""
    logger.info(f"정보이용사 매입내역 수정 요청: ID={item_id}")
    try:
        data = await request.json()
        member_code = (data.get('member_code') or '').strip()
        datacenter_code = (data.get('datacenter_code') or '').strip()
        provider = (data.get('provider') or '').strip()
        billing_start_date = data.get('billing_start_date') or None
        contract_end_date = data.get('contract_end_date') or None
        service_id = (data.get('service_id') or '').strip() or None
        nni_id = (data.get('nni_id') or '').strip() or None
        cost_code = (data.get('cost_code') or '').strip() or None

        if not member_code:
            raise HTTPException(status_code=400, detail="정보이용사코드는 필수입니다.")

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE info_purchase_contract SET
                    member_code = %s, datacenter_code = %s, provider = %s,
                    billing_start_date = %s, contract_end_date = %s,
                    service_id = %s, nni_id = %s, cost_code = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (member_code, datacenter_code, provider, billing_start_date, contract_end_date, service_id, nni_id, cost_code, item_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Info purchase contract not found")
            cur.close()

        logger.info(f"정보이용사 매입내역 수정 완료: ID={item_id}")
        return {"success": True, "message": "매입내역이 수정되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"정보이용사 매입내역 수정 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/info_purchase_contract/{item_id}")
async def DeleteInfoPurchaseContract(item_id: int):
    """정보이용사 매입내역 삭제"""
    logger.info(f"정보이용사 매입내역 삭제 요청: ID={item_id}")
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM info_purchase_contract WHERE id = %s", (item_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Info purchase contract not found")
            cur.close()

        logger.info(f"정보이용사 매입내역 삭제 완료: ID={item_id}")
        return {"success": True, "message": "매입내역이 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"정보이용사 매입내역 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 회원사 이익내역 (Profit Summary)
# ============================================================

@router.get("/profit_summary")
async def GetProfitSummary():
    """회원사별 이익내역 조회 (매출 - 매입)"""
    logger.info("회원사 이익내역 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # 1) 매출 집계 (member_code + phase 기준)
            revenue_query = """
                SELECT
                    COALESCE(sc.member_code, c.member_code) as member_code,
                    sc.member_number, sc.company_name, sc.subscription_type,
                    sc.is_pb, c.phase,
                    COUNT(*) FILTER (WHERE c.usage = 'ORD') AS ord_count,
                    COUNT(*) FILTER (WHERE c.usage = 'MPR') AS mpr_count,
                    COUNT(*) AS total_count,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'ORD'), 0) AS ord_total,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'MPR'), 0) AS mpr_total,
                    COALESCE(SUM(mfs.price), 0) AS revenue_total
                FROM circuit c
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
                WHERE c.usage IN ('ORD', 'MPR')
                GROUP BY COALESCE(sc.member_code, c.member_code), sc.member_number, sc.company_name, sc.subscription_type, sc.is_pb, c.phase
                ORDER BY sc.is_pb ASC NULLS FIRST, sc.member_number ASC NULLS LAST, c.phase ASC
            """
            cur.execute(revenue_query)
            revenue_rows = cur.fetchall()

            # 2) 매입 집계 (member_code 기준)
            purchase_query = """
                SELECT
                    pc.member_code,
                    COUNT(*) AS purchase_count,
                    COALESCE(SUM(nc.cost_price), 0) AS purchase_total
                FROM purchase_contract pc
                LEFT JOIN network_cost nc ON pc.cost_code = nc.code
                GROUP BY pc.member_code
            """
            cur.execute(purchase_query)
            purchase_rows = cur.fetchall()
            cur.close()

        # 3) 매입 데이터를 member_code 기준 dict로 변환
        purchase_map = {}
        for p in purchase_rows:
            purchase_map[p['member_code']] = {
                'purchase_count': int(p['purchase_count'] or 0),
                'purchase_total': float(p['purchase_total'] or 0)
            }

        # 4) 매출 + 매입 병합하여 이익 계산
        result = []
        for r in revenue_rows:
            member_code = r['member_code']
            purchase_info = purchase_map.get(member_code, {'purchase_count': 0, 'purchase_total': 0})
            revenue_total = float(r['revenue_total'] or 0)
            purchase_total = float(purchase_info['purchase_total'])
            profit = revenue_total - purchase_total
            profit_rate = round((profit / revenue_total) * 100, 1) if revenue_total > 0 else 0.0

            result.append({
                'member_code': r['member_code'],
                'member_number': r['member_number'],
                'company_name': r['company_name'],
                'subscription_type': r['subscription_type'],
                'is_pb': r['is_pb'],
                'phase': r['phase'],
                'ord_count': int(r['ord_count'] or 0),
                'mpr_count': int(r['mpr_count'] or 0),
                'total_count': int(r['total_count'] or 0),
                'ord_total': float(r['ord_total'] or 0),
                'mpr_total': float(r['mpr_total'] or 0),
                'revenue_total': revenue_total,
                'purchase_count': purchase_info['purchase_count'],
                'purchase_total': purchase_total,
                'profit': profit,
                'profit_rate': profit_rate
            })

        logger.info(f"회원사 이익내역 조회 완료: {len(result)}건")
        return {"success": True, "data": result}

    except Exception as e:
        logger.error(f"회원사 이익내역 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/profit_monthly")
async def GetProfitMonthly():
    """월별 이익 추이 조회 (최근 12개월)"""
    logger.info("월별 이익 추이 조회 시작")

    try:
        today = datetime.now().date()
        current_month_start = today.replace(day=1)
        trend_start = current_month_start - relativedelta(months=11)

        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # 12개월 매출 추이
            trend_query = """
                WITH months AS (
                    SELECT generate_series(
                        %s::date, %s::date, '1 month'::interval
                    )::date AS m_start
                ),
                month_ranges AS (
                    SELECT m_start,
                           (m_start + interval '1 month' - interval '1 day')::date AS m_end
                    FROM months
                )
                SELECT
                    to_char(mr.m_start, 'YYYY-MM') AS month,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'ORD'), 0) AS ord_total,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'MPR'), 0) AS mpr_total,
                    COALESCE(SUM(mfs.price), 0) AS revenue_total
                FROM month_ranges mr
                LEFT JOIN circuit c ON c.usage IN ('ORD', 'MPR')
                    AND (c.contract_date IS NULL OR c.contract_date <= mr.m_end)
                    AND (c.expiry_date IS NULL OR c.expiry_date >= mr.m_start)
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
                GROUP BY mr.m_start
                ORDER BY mr.m_start
            """
            cur.execute(trend_query, (trend_start, current_month_start))
            revenue_trend = cur.fetchall()

            # 총 매입 (날짜 필터 없음 - 고정값)
            purchase_query = """
                SELECT COALESCE(SUM(nc.cost_price), 0) AS purchase_total
                FROM purchase_contract pc
                LEFT JOIN network_cost nc ON pc.cost_code = nc.code
            """
            cur.execute(purchase_query)
            purchase_result = cur.fetchone()
            purchase_total = float(purchase_result['purchase_total'] or 0)
            cur.close()

        # 월별 이익 계산
        trend = []
        for r in revenue_trend:
            rev = float(r['revenue_total'] or 0)
            profit = rev - purchase_total
            trend.append({
                'month': r['month'],
                'revenue_total': rev,
                'purchase_total': purchase_total,
                'profit': profit,
                'ord_total': float(r['ord_total'] or 0),
                'mpr_total': float(r['mpr_total'] or 0)
            })

        logger.info(f"월별 이익 추이 조회 완료: {len(trend)}개월")
        return {"success": True, "data": trend}

    except Exception as e:
        logger.error(f"월별 이익 추이 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ==================== 정보이용사 이익내역 (Info Profit Summary) ====================

@router.get("/info_profit_summary")
async def GetInfoProfitSummary():
    """정보이용사별 이익내역 조회 (MKD 매출 - 매입)"""
    logger.info("정보이용사 이익내역 조회 시작")

    try:
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            revenue_query = """
                SELECT
                    COALESCE(sc.member_code, c.member_code) as member_code,
                    sc.member_number, sc.company_name, sc.subscription_type,
                    sc.is_pb, c.phase,
                    COUNT(*) AS mkd_count,
                    COALESCE(SUM(ifs.price), 0) AS revenue_total
                FROM info_company_circuit c
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN info_fee_schedule ifs ON c.fee_code = ifs.fee_code
                WHERE c.usage = 'MKD'
                GROUP BY COALESCE(sc.member_code, c.member_code), sc.member_number, sc.company_name, sc.subscription_type, sc.is_pb, c.phase
                ORDER BY sc.is_pb ASC NULLS FIRST, sc.member_number ASC NULLS LAST, c.phase ASC
            """
            cur.execute(revenue_query)
            revenue_rows = cur.fetchall()

            purchase_query = """
                SELECT
                    pc.member_code,
                    COUNT(*) AS purchase_count,
                    COALESCE(SUM(nc.cost_price), 0) AS purchase_total
                FROM info_purchase_contract pc
                LEFT JOIN network_cost nc ON pc.cost_code = nc.code
                GROUP BY pc.member_code
            """
            cur.execute(purchase_query)
            purchase_rows = cur.fetchall()
            cur.close()

        purchase_map = {}
        for p in purchase_rows:
            purchase_map[p['member_code']] = {
                'purchase_count': int(p['purchase_count'] or 0),
                'purchase_total': float(p['purchase_total'] or 0)
            }

        result = []
        for r in revenue_rows:
            member_code = r['member_code']
            purchase_info = purchase_map.get(member_code, {'purchase_count': 0, 'purchase_total': 0})
            revenue_total = float(r['revenue_total'] or 0)
            purchase_total = float(purchase_info['purchase_total'])
            profit = revenue_total - purchase_total
            profit_rate = round((profit / revenue_total) * 100, 1) if revenue_total > 0 else 0.0

            result.append({
                'member_code': r['member_code'],
                'member_number': r['member_number'],
                'company_name': r['company_name'],
                'subscription_type': r['subscription_type'],
                'is_pb': r['is_pb'],
                'phase': r['phase'],
                'mkd_count': int(r['mkd_count'] or 0),
                'revenue_total': revenue_total,
                'purchase_count': purchase_info['purchase_count'],
                'purchase_total': purchase_total,
                'profit': profit,
                'profit_rate': profit_rate
            })

        logger.info(f"정보이용사 이익내역 조회 완료: {len(result)}건")
        return {"success": True, "data": result}

    except Exception as e:
        logger.error(f"정보이용사 이익내역 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/info_profit_monthly")
async def GetInfoProfitMonthly():
    """정보이용사 월별 이익 추이 조회 (최근 12개월)"""
    logger.info("정보이용사 월별 이익 추이 조회 시작")

    try:
        today = datetime.now().date()
        current_month_start = today.replace(day=1)
        trend_start = current_month_start - relativedelta(months=11)

        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            trend_query = """
                WITH months AS (
                    SELECT generate_series(%s::date, %s::date, '1 month'::interval)::date AS m_start
                ),
                month_ranges AS (
                    SELECT m_start, (m_start + interval '1 month' - interval '1 day')::date AS m_end
                    FROM months
                )
                SELECT
                    to_char(mr.m_start, 'YYYY-MM') AS month,
                    COUNT(*) AS mkd_count,
                    COALESCE(SUM(ifs.price), 0) AS revenue_total
                FROM month_ranges mr
                LEFT JOIN info_company_circuit c ON c.usage = 'MKD'
                    AND (c.contract_date IS NULL OR c.contract_date <= mr.m_end)
                    AND (c.expiry_date IS NULL OR c.expiry_date >= mr.m_start)
                LEFT JOIN info_fee_schedule ifs ON c.fee_code = ifs.fee_code
                GROUP BY mr.m_start
                ORDER BY mr.m_start
            """
            cur.execute(trend_query, (trend_start, current_month_start))
            revenue_trend = cur.fetchall()

            purchase_query = """
                SELECT COALESCE(SUM(nc.cost_price), 0) AS purchase_total
                FROM info_purchase_contract pc
                LEFT JOIN network_cost nc ON pc.cost_code = nc.code
            """
            cur.execute(purchase_query)
            purchase_total = float(cur.fetchone()['purchase_total'] or 0)
            cur.close()

        trend = []
        for r in revenue_trend:
            rev = float(r['revenue_total'] or 0)
            trend.append({
                'month': r['month'],
                'revenue_total': rev,
                'purchase_total': purchase_total,
                'profit': rev - purchase_total
            })

        logger.info(f"정보이용사 월별 이익 추이 조회 완료: {len(trend)}개월")
        return {"success": True, "data": trend}

    except Exception as e:
        logger.error(f"정보이용사 월별 이익 추이 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/profit_report_pdf")
async def GetProfitReportPdf():
    """회원사 이익내역 보고서 PDF 다운로드"""
    logger.info("이익내역 보고서 PDF 생성 시작")

    try:
        from fpdf import FPDF
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
        import tempfile

        # 한글 폰트 설정
        font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "DroidSansFallback.ttf")
        font_prop = fm.FontProperties(fname=font_path)
        fm.fontManager.addfont(font_path)
        plt.rcParams['font.family'] = fm.FontProperties(fname=font_path).get_name()
        plt.rcParams['axes.unicode_minus'] = False

        # ── 데이터 조회 ──
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            revenue_query = """
                SELECT
                    COALESCE(sc.member_code, c.member_code) as member_code,
                    sc.member_number, sc.company_name, sc.subscription_type,
                    sc.is_pb, c.phase,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'ORD'), 0) AS ord_total,
                    COALESCE(SUM(mfs.price) FILTER (WHERE c.usage = 'MPR'), 0) AS mpr_total,
                    COALESCE(SUM(mfs.price), 0) AS revenue_total
                FROM circuit c
                LEFT JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
                WHERE c.usage IN ('ORD', 'MPR')
                GROUP BY COALESCE(sc.member_code, c.member_code), sc.member_number, sc.company_name, sc.subscription_type, sc.is_pb, c.phase
                ORDER BY sc.is_pb ASC NULLS FIRST, sc.member_number ASC NULLS LAST, c.phase ASC
            """
            cur.execute(revenue_query)
            revenue_rows = cur.fetchall()

            purchase_query = """
                SELECT pc.member_code, COALESCE(SUM(nc.cost_price), 0) AS purchase_total
                FROM purchase_contract pc
                LEFT JOIN network_cost nc ON pc.cost_code = nc.code
                GROUP BY pc.member_code
            """
            cur.execute(purchase_query)
            purchase_rows = cur.fetchall()
            cur.close()

        purchase_map = {p['member_code']: float(p['purchase_total'] or 0) for p in purchase_rows}

        detail_rows = []
        for r in revenue_rows:
            mc = r['member_code']
            rev = float(r['revenue_total'] or 0)
            pur = purchase_map.get(mc, 0)
            profit = rev - pur
            rate = round((profit / rev) * 100, 1) if rev > 0 else 0.0
            detail_rows.append({
                'member_code': mc, 'member_number': r['member_number'],
                'company_name': r['company_name'], 'subscription_type': r['subscription_type'],
                'is_pb': r['is_pb'], 'phase': r['phase'],
                'ord_total': float(r['ord_total'] or 0), 'mpr_total': float(r['mpr_total'] or 0),
                'revenue_total': rev, 'purchase_total': pur, 'profit': profit, 'profit_rate': rate
            })

        member_agg = {}
        for r in detail_rows:
            mc = r['member_code']
            if mc not in member_agg:
                member_agg[mc] = {
                    'member_number': r['member_number'], 'company_name': r['company_name'],
                    'subscription_type': r['subscription_type'], 'is_pb': r['is_pb'],
                    'ord_total': 0, 'mpr_total': 0, 'revenue_total': 0, 'purchase_total': 0, 'profit': 0
                }
            for k in ('ord_total', 'mpr_total', 'revenue_total', 'purchase_total', 'profit'):
                member_agg[mc][k] += r[k]

        total_revenue = sum(m['revenue_total'] for m in member_agg.values())
        total_purchase = sum(m['purchase_total'] for m in member_agg.values())
        total_profit = sum(m['profit'] for m in member_agg.values())
        total_ord = sum(m['ord_total'] for m in member_agg.values())
        total_mpr = sum(m['mpr_total'] for m in member_agg.values())
        member_count = len(member_agg)
        profit_rate_total = round((total_profit / total_revenue) * 100, 1) if total_revenue > 0 else 0.0

        # ── 월별 추이 데이터 ──
        today = datetime.now().date()
        current_month_start = today.replace(day=1)
        trend_start = current_month_start - relativedelta(months=11)
        with get_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                WITH months AS (
                    SELECT generate_series(%s::date, %s::date, '1 month'::interval)::date AS m_start
                ),
                month_ranges AS (
                    SELECT m_start, (m_start + interval '1 month' - interval '1 day')::date AS m_end FROM months
                )
                SELECT to_char(mr.m_start, 'YYYY-MM') AS month,
                    COALESCE(SUM(mfs.price), 0) AS revenue_total
                FROM month_ranges mr
                LEFT JOIN circuit c ON c.usage IN ('ORD', 'MPR')
                    AND (c.contract_date IS NULL OR c.contract_date <= mr.m_end)
                    AND (c.expiry_date IS NULL OR c.expiry_date >= mr.m_start)
                LEFT JOIN member_fee_schedule mfs ON c.fee_code = mfs.fee_code
                GROUP BY mr.m_start ORDER BY mr.m_start
            """, (trend_start, current_month_start))
            monthly_trend = cur.fetchall()
            cur.close()

        monthly_data = []
        for r in monthly_trend:
            rev = float(r['revenue_total'] or 0)
            monthly_data.append({'month': r['month'], 'revenue': rev, 'purchase': total_purchase, 'profit': rev - total_purchase})

        # 작년 12월 기준선 찾기
        base_line_data = None
        if monthly_data:
            last_year = str(int(monthly_data[-1]['month'][:4]) - 1)
            for md in monthly_data:
                if md['month'] == f"{last_year}-12":
                    base_line_data = md
                    break

        # ──────────────────────────────────────
        # 차트 생성 (화면 디자인 매칭)
        # ──────────────────────────────────────
        # 색상 팔레트 (화면 기준)
        C_DARK = '#1e293b'      # 매출
        C_INDIGO = '#6366f1'    # 매입
        C_RED = '#dc2626'       # 이익
        C_GREEN = '#059669'     # 이익률/긍정
        C_NAVY = '#1b2a4a'      # 타이틀
        C_STEEL = '#475569'
        C_SLATE = '#94a3b8'
        C_GRID = '#e8ecf1'

        chart_files = []

        # 공통 차트 스타일
        def apply_chart_style(ax, title_text):
            ax.set_facecolor('white')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color(C_GRID)
            ax.spines['bottom'].set_color(C_GRID)
            ax.tick_params(colors=C_STEEL, labelsize=7)
            for tick in ax.get_xticklabels():
                tick.set_fontproperties(font_prop)
            for tick in ax.get_yticklabels():
                tick.set_fontproperties(font_prop)
            if title_text:
                ax.set_title(title_text, fontproperties=font_prop, fontsize=10, fontweight='bold', color=C_NAVY, pad=10, loc='left')

        # 차트0: 월별 추이 (라인 차트 - 화면과 동일)
        fig0, ax0 = plt.subplots(figsize=(10, 3.2))
        fig0.patch.set_facecolor('white')
        m_labels = [d['month'][2:].replace('-', '.') for d in monthly_data]
        m_revenues = [d['revenue'] / 10000 for d in monthly_data]
        m_purchases = [d['purchase'] / 10000 for d in monthly_data]
        m_profits = [d['profit'] / 10000 for d in monthly_data]
        x_idx = list(range(len(m_labels)))

        # 매출: 어두운색 + fill
        ax0.plot(x_idx, m_revenues, color='rgba(30,41,59,0.7)'.replace('rgba(', '#').split(',')[0] if False else C_DARK,
                 linewidth=1.2, label='매출', alpha=0.7)
        ax0.fill_between(x_idx, m_revenues, alpha=0.05, color=C_DARK)
        # 매입: 인디고 + fill
        ax0.plot(x_idx, m_purchases, color=C_INDIGO,
                 linewidth=1.2, label='매입', alpha=0.7)
        ax0.fill_between(x_idx, m_purchases, alpha=0.05, color=C_INDIGO)
        # 이익: 초록 대시
        ax0.plot(x_idx, m_profits, color=C_GREEN,
                 linewidth=1.5, label='이익', linestyle='--', alpha=0.9)

        ax0.set_xticks(x_idx)
        ax0.set_xticklabels(m_labels, fontproperties=font_prop, fontsize=7)
        apply_chart_style(ax0, None)
        ax0.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))
        ax0.grid(axis='y', alpha=0.06, color=C_STEEL)
        ax0.set_ylabel('금액 (만원)', fontproperties=font_prop, fontsize=7.5, color=C_SLATE)
        leg = ax0.legend(prop=font_prop, fontsize=8, loc='upper right', ncol=3,
                         frameon=True, fancybox=False, edgecolor=C_GRID, framealpha=0.95)
        leg.get_frame().set_linewidth(0.5)
        fig0.subplots_adjust(top=0.88)
        tmp0 = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        fig0.savefig(tmp0.name, dpi=160, bbox_inches='tight', facecolor='white')
        plt.close(fig0)
        chart_files.append(tmp0.name)

        # 차트1: 매출/매입 비율 (도넛) - 큰 사이즈, 라벨 잘 보이게
        fig1, ax1 = plt.subplots(figsize=(5.5, 4.5))
        fig1.patch.set_facecolor('white')
        wedges, texts, autotexts = ax1.pie(
            [total_revenue, total_purchase], labels=['매출', '매입'],
            colors=[C_DARK, C_INDIGO],
            autopct='%1.1f%%', startangle=90, pctdistance=0.82,
            labeldistance=1.15,
            wedgeprops=dict(width=0.32, edgecolor='white', linewidth=3)
        )
        for t in texts: t.set_fontproperties(font_prop); t.set_fontsize(13); t.set_color(C_NAVY); t.set_fontweight('bold')
        for t in autotexts: t.set_fontproperties(font_prop); t.set_fontsize(11); t.set_fontweight('bold'); t.set_color(C_NAVY)
        rev_pct = round(total_revenue / (total_revenue + total_purchase) * 100, 1) if (total_revenue + total_purchase) > 0 else 0
        ax1.text(0, 0.04, f'{rev_pct}%', ha='center', va='center',
                 fontproperties=font_prop, fontsize=22, fontweight='bold', color=C_NAVY)
        ax1.text(0, -0.18, '매출 비율', ha='center', va='center',
                 fontproperties=font_prop, fontsize=10, color=C_SLATE)
        ax1.set_title('매출 / 매입 비율', fontproperties=font_prop, fontsize=13, fontweight='bold', color=C_NAVY, pad=12, loc='center')
        fig1.tight_layout()
        tmp1 = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        fig1.savefig(tmp1.name, dpi=160, bbox_inches='tight', facecolor='white')
        plt.close(fig1)
        chart_files.append(tmp1.name)

        # 차트2: 이익률 분포 (도넛) - 큰 사이즈, 라벨 잘 보이게
        dist = {'90% 이상': 0, '70~90%': 0, '50~70%': 0, '50% 미만': 0}
        for m in member_agg.values():
            rate = (m['profit'] / m['revenue_total'] * 100) if m['revenue_total'] > 0 else 0
            if rate >= 90: dist['90% 이상'] += 1
            elif rate >= 70: dist['70~90%'] += 1
            elif rate >= 50: dist['50~70%'] += 1
            else: dist['50% 미만'] += 1
        fig2, ax2 = plt.subplots(figsize=(5.5, 4.5))
        fig2.patch.set_facecolor('white')
        dist_colors = ['#10b981', '#6366f1', '#f59e0b', '#ef4444']
        dist_vals = list(dist.values())
        dist_total = sum(dist_vals)
        wedges2, texts2, autotexts2 = ax2.pie(
            dist_vals, labels=list(dist.keys()), colors=dist_colors,
            autopct=lambda pct: f'{int(round(pct/100.*dist_total))}개사\n({pct:.0f}%)',
            startangle=90, pctdistance=0.78,
            labeldistance=1.15,
            wedgeprops=dict(width=0.32, edgecolor='white', linewidth=3)
        )
        for t in texts2: t.set_fontproperties(font_prop); t.set_fontsize(12); t.set_color(C_NAVY); t.set_fontweight('bold')
        for t in autotexts2: t.set_fontproperties(font_prop); t.set_fontsize(9); t.set_fontweight('bold'); t.set_color('white')
        ax2.text(0, 0.04, f'{member_count}개사', ha='center', va='center',
                 fontproperties=font_prop, fontsize=18, fontweight='bold', color=C_NAVY)
        ax2.text(0, -0.18, '전체 회원사', ha='center', va='center',
                 fontproperties=font_prop, fontsize=10, color=C_SLATE)
        ax2.set_title('이익률 분포', fontproperties=font_prop, fontsize=13, fontweight='bold', color=C_NAVY, pad=12, loc='center')
        fig2.tight_layout()
        tmp2 = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        fig2.savefig(tmp2.name, dpi=160, bbox_inches='tight', facecolor='white')
        plt.close(fig2)
        chart_files.append(tmp2.name)

        # ──────────────────────────────────────
        # PDF 생성 (미니멀 기업 보고서)
        # ──────────────────────────────────────
        class ProfitPDF(FPDF):
            def header(self):
                if self.page_no() == 1:
                    return
                # 상단 인디고 accent line
                self.set_fill_color(99, 102, 241)
                self.rect(0, 0, 297, 1.5, 'F')
                # 좌측: 보고서명
                self.set_xy(15, 5)
                self.set_font("Korean", "", 7)
                self.set_text_color(100, 116, 139)
                _now = datetime.now()
                self.cell(0, 5, f"회원사 이익내역 보고서  |  {_now.strftime('%Y.%m.%d')}", align='L')
                # 우측: 페이지 번호
                self.set_xy(15, 5)
                self.set_font("Korean", "B", 7)
                self.set_text_color(99, 102, 241)
                self.cell(0, 5, f"P.{self.page_no()}", align='R')
                self.set_y(14)

            def footer(self):
                self.set_y(-10)
                self.set_font("Korean", "", 5.5)
                self.set_text_color(168, 178, 195)
                self.cell(0, 6, "NEXTRADE MKNM  Network Management System", align='L')
                self.cell(0, 6, f"{self.page_no()} / {{nb}}", align='R')

        pdf = ProfitPDF(orientation='L', unit='mm', format='A4')
        pdf.add_font("Korean", "", font_path, uni=True)
        pdf.add_font("Korean", "B", font_path, uni=True)
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=15)

        # 증감 포맷 헬퍼
        def fmt_compact(v):
            if v == 0: return '0'
            s = '+' if v >= 0 else ''
            if abs(v) >= 100000000: return f"{s}{v / 100000000:.1f}억"
            if abs(v) >= 10000: return f"{s}{v / 10000:.0f}만"
            return f"{s}{v:,.0f}"

        # ── 1페이지: 표지 (모던 미니멀) ──
        pdf.add_page()
        now = datetime.now()
        title_date = f"{now.strftime('%y')}년 {now.month}월"

        # 상단 그라데이션 바 (얇은 accent line)
        pdf.set_fill_color(99, 102, 241)
        pdf.rect(0, 0, 297, 3, 'F')

        # 좌측 상단 브랜드
        pdf.set_xy(24, 14)
        pdf.set_font("Korean", "", 8)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(0, 5, "NEXTRADE MKNM")

        # 메인 타이틀 영역 (넓은 여백)
        pdf.set_xy(24, 48)
        pdf.set_font("Korean", "B", 34)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 16, "회원사 이익내역")
        pdf.set_xy(24, 66)
        pdf.set_font("Korean", "", 34)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(0, 16, "보고서")

        # 날짜 태그
        pdf.set_xy(24, 90)
        pdf.set_fill_color(241, 245, 249)
        pdf.set_font("Korean", "B", 11)
        pdf.set_text_color(99, 102, 241)
        pdf.cell(55, 8, f"  {title_date}", fill=True)

        # 구분선
        pdf.set_draw_color(226, 232, 240)
        pdf.set_line_width(0.2)
        pdf.line(24, 108, 273, 108)

        # KPI 카드 영역 (4개 수치 + 증감)
        kpi_y = 115
        kpi_diff_texts = ['', '', '', '']
        if base_line_data:
            b_rev = base_line_data['revenue']
            b_pur = base_line_data['purchase']
            b_pf = base_line_data['profit']
            r_diff = total_revenue - b_rev
            p_diff = total_purchase - b_pur
            pf_diff = total_profit - b_pf
            r_pct = f"{(r_diff / b_rev * 100):.1f}" if b_rev > 0 else '0.0'
            p_pct = f"{(p_diff / b_pur * 100):.1f}" if b_pur > 0 else '0.0'
            pf_pct = f"{(pf_diff / abs(b_pf) * 100):.1f}" if b_pf != 0 else '0.0'
            kpi_diff_texts[1] = f"{fmt_compact(r_diff)} ({'+' if r_diff >= 0 else ''}{r_pct}%)"
            kpi_diff_texts[2] = f"{fmt_compact(p_diff)} ({'+' if p_diff >= 0 else ''}{p_pct}%)"
            kpi_diff_texts[3] = f"{fmt_compact(pf_diff)} ({'+' if pf_diff >= 0 else ''}{pf_pct}%)"

        kpi_data = [
            ("전체 회원사", f"{member_count}개사", "회선계약 기준"),
            ("총 매출", f"{total_revenue:,.0f}원", f"ORD {total_ord:,.0f} + MPR {total_mpr:,.0f}"),
            ("총 매입", f"{total_purchase:,.0f}원", "매입계약 기준"),
            ("총 이익", f"{total_profit:,.0f}원", f"이익률 {profit_rate_total}%"),
        ]
        kpi_w = 62
        kpi_start = 24
        dot_colors = [(99, 102, 241), (16, 185, 129), (239, 68, 68), (245, 158, 11)]

        for i, (label, value, sub) in enumerate(kpi_data):
            x = kpi_start + i * kpi_w

            # 카드 배경 (라운드 효과 - 직사각형)
            pdf.set_fill_color(249, 250, 251)
            pdf.rect(x, kpi_y, kpi_w - 4, 38, 'F')

            # 컬러 탑 라인
            dc = dot_colors[i]
            pdf.set_fill_color(dc[0], dc[1], dc[2])
            pdf.rect(x, kpi_y, kpi_w - 4, 1.5, 'F')

            # 라벨
            pdf.set_xy(x + 6, kpi_y + 5)
            pdf.set_font("Korean", "", 7.5)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(kpi_w - 10, 4, label)

            # 값
            pdf.set_xy(x + 6, kpi_y + 12)
            pdf.set_font("Korean", "B", 15)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(kpi_w - 10, 9, value)

            # 보조
            pdf.set_xy(x + 6, kpi_y + 23)
            pdf.set_font("Korean", "", 6)
            pdf.set_text_color(148, 163, 184)
            pdf.cell(kpi_w - 10, 3.5, sub)

            # 증감 표시
            if kpi_diff_texts[i]:
                pdf.set_xy(x + 6, kpi_y + 28)
                pdf.set_font("Korean", "B", 6)
                diff_val = [0, total_revenue - (base_line_data['revenue'] if base_line_data else 0),
                            total_purchase - (base_line_data['purchase'] if base_line_data else 0),
                            total_profit - (base_line_data['profit'] if base_line_data else 0)][i]
                if diff_val >= 0:
                    pdf.set_text_color(220, 38, 38)
                    pdf.cell(kpi_w - 10, 3.5, f"▲ {kpi_diff_texts[i]}")
                else:
                    pdf.set_text_color(37, 99, 235)
                    pdf.cell(kpi_w - 10, 3.5, f"▼ {kpi_diff_texts[i]}")

        # 증감 설명
        pdf.set_xy(24, kpi_y + 42)
        pdf.set_font("Korean", "", 5.5)
        pdf.set_text_color(168, 178, 195)
        pdf.cell(0, 3, "* 전년 12월 대비 증감")

        # 하단 생성 정보
        pdf.set_xy(24, 178)
        pdf.set_font("Korean", "", 7.5)
        pdf.set_text_color(168, 178, 195)
        pdf.cell(0, 5, f"Generated  {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  Network Management System")

        # ── 2페이지: 월별 추이 차트 + 추이 테이블 ──
        pdf.add_page()

        def section_heading(text, num):
            y = pdf.get_y()
            # 인디고 넘버 태그
            pdf.set_fill_color(99, 102, 241)
            pdf.set_xy(15, y)
            pdf.set_font("Korean", "B", 9)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(14, 7, num, fill=True, align='C')
            # 제목 텍스트
            pdf.set_xy(32, y)
            pdf.set_font("Korean", "B", 13)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(0, 7, text)
            pdf.ln(10)
            # 얇은 구분선
            pdf.set_draw_color(226, 232, 240)
            pdf.set_line_width(0.2)
            pdf.line(15, pdf.get_y(), 282, pdf.get_y())
            pdf.ln(5)

        section_heading("월별 이익 추이", "01")

        # 차트: 풀 가로 배치
        chart0_y = pdf.get_y()
        pdf.image(chart_files[0], x=15, y=chart0_y, w=267)
        pdf.set_y(chart0_y + 58)
        pdf.ln(3)

        # 테이블: 차트 아래 풀 가로 배치
        tbl_x = 15
        pdf.set_xy(tbl_x, pdf.get_y())
        pdf.set_font("Korean", "B", 9)
        pdf.set_text_color(27, 42, 74)
        pdf.cell(100, 7, "최근 월별 이익 추이", ln=False)
        pdf.set_font("Korean", "", 6)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(0, 7, "  전월 대비 증감")
        pdf.ln()

        # 테이블 헤더 (가로로 넓게)
        trend_col_w = [22, 50, 50, 50, 50, 45]
        trend_headers = ['월', '매출', '매입', '이익', '이익 증감', '증감률']
        pdf.set_xy(tbl_x, pdf.get_y() + 1)
        pdf.set_font("Korean", "B", 7)
        for ci, (h, w) in enumerate(zip(trend_headers, trend_col_w)):
            clr = (5, 150, 105) if ci == 3 else (27, 42, 74)
            pdf.set_text_color(clr[0], clr[1], clr[2])
            pdf.cell(w, 5.5, h, align='C')
        pdf.ln()
        pdf.set_draw_color(27, 42, 74)
        pdf.set_line_width(0.3)
        pdf.line(tbl_x, pdf.get_y(), tbl_x + sum(trend_col_w), pdf.get_y())
        pdf.set_line_width(0.2)
        pdf.ln(0.5)

        # 테이블 데이터 (최신 순)
        rev_data = list(reversed(monthly_data))
        for ri, d in enumerate(rev_data):
            if pdf.get_y() > 178:
                break
            ry = pdf.get_y()
            rv = d['revenue']
            pu = d['purchase']
            pf = d['profit']
            has_prev = ri < len(rev_data) - 1
            prev_pf = rev_data[ri + 1]['profit'] if has_prev else 0
            pf_diff = pf - prev_pf if has_prev else 0
            pf_pct_str = ''
            if has_prev and prev_pf != 0:
                pf_pct = (pf_diff / abs(prev_pf)) * 100
                arrow = '▲' if pf_diff >= 0 else '▼'
                pf_pct_str = f"{arrow} {'+' if pf_diff >= 0 else ''}{pf_pct:.1f}%"

            # 짝수행 배경
            if ri % 2 == 0:
                pdf.set_fill_color(248, 250, 252)
                pdf.rect(tbl_x, ry, sum(trend_col_w), 6.5, 'F')

            pdf.set_xy(tbl_x, ry)
            pdf.set_font("Korean", "B", 7)
            pdf.set_text_color(71, 85, 105)
            pdf.cell(trend_col_w[0], 6.5, d['month'][2:].replace('-', '.'), align='C')

            # 매출
            pdf.set_font("Korean", "", 7)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(trend_col_w[1], 6.5, f"{rv:,.0f}원", align='R')

            # 매입
            pdf.set_text_color(99, 102, 241)
            pdf.cell(trend_col_w[2], 6.5, f"{pu:,.0f}원", align='R')

            # 이익
            pdf.set_font("Korean", "B", 7)
            pdf.set_text_color(5, 150, 105)
            pdf.cell(trend_col_w[3], 6.5, f"{pf:,.0f}원", align='R')

            # 이익 증감값
            pdf.set_font("Korean", "", 6.5)
            if has_prev and pf_diff != 0:
                pdf.set_text_color(220, 38, 38) if pf_diff >= 0 else pdf.set_text_color(37, 99, 235)
                pdf.cell(trend_col_w[4], 6.5, fmt_compact(pf_diff), align='R')
            else:
                pdf.set_text_color(148, 163, 184)
                pdf.cell(trend_col_w[4], 6.5, '-', align='C')

            # 증감률
            pdf.set_font("Korean", "B", 7)
            if pf_pct_str:
                pdf.set_text_color(220, 38, 38) if pf_diff >= 0 else pdf.set_text_color(37, 99, 235)
            else:
                pdf.set_text_color(148, 163, 184)
            pdf.cell(trend_col_w[5], 6.5, pf_pct_str or '-', align='C')
            pdf.ln()

            pdf.set_draw_color(240, 242, 245)
            pdf.line(tbl_x, pdf.get_y(), tbl_x + sum(trend_col_w), pdf.get_y())

        # ── 3페이지: 요약 + 이익 TOP 10 리스트 + 도넛 차트 ──
        pdf.add_page()
        section_heading("요약 분석", "02")

        # 추가 지표 산출
        member_list_sorted = sorted(member_agg.values(), key=lambda x: x['profit'], reverse=True)
        avg_revenue = total_revenue / member_count if member_count > 0 else 0
        avg_profit = total_profit / member_count if member_count > 0 else 0
        max_profit_m = member_list_sorted[0] if member_list_sorted else None
        min_profit_m = member_list_sorted[-1] if member_list_sorted else None
        pb_count = sum(1 for m in member_agg.values() if m.get('is_pb'))
        non_pb_count = member_count - pb_count
        pb_revenue = sum(m['revenue_total'] for m in member_agg.values() if m.get('is_pb'))
        non_pb_revenue = total_revenue - pb_revenue
        ord_ratio = round((total_ord / total_revenue) * 100, 1) if total_revenue > 0 else 0
        mpr_ratio = round((total_mpr / total_revenue) * 100, 1) if total_revenue > 0 else 0
        profit_over_90 = sum(1 for m in member_agg.values() if m['revenue_total'] > 0 and (m['profit'] / m['revenue_total'] * 100) >= 90)
        profit_under_50 = sum(1 for m in member_agg.values() if m['revenue_total'] > 0 and (m['profit'] / m['revenue_total'] * 100) < 50)

        # 표 그리기 함수
        def draw_summary_table(title, rows, start_y, table_x=15, col_label_w=55, col_value_w=75):
            pdf.set_xy(table_x, start_y)
            pdf.set_font("Korean", "B", 9)
            pdf.set_text_color(27, 42, 74)
            pdf.cell(0, 7, title, ln=True)
            pdf.ln(1)
            row_h = 7.5
            for i, (label, value) in enumerate(rows):
                ry = pdf.get_y()
                if i % 2 == 0:
                    pdf.set_fill_color(248, 250, 252)
                    pdf.rect(table_x, ry, col_label_w + col_value_w, row_h, 'F')
                pdf.set_xy(table_x + 4, ry)
                pdf.set_font("Korean", "", 7.5)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(col_label_w - 4, row_h, label)
                pdf.set_xy(table_x + col_label_w, ry)
                pdf.set_font("Korean", "B", 8)
                pdf.set_text_color(27, 42, 74)
                pdf.cell(col_value_w - 4, row_h, value, align='R')
                pdf.set_draw_color(236, 239, 243)
                pdf.line(table_x, ry + row_h, table_x + col_label_w + col_value_w, ry + row_h)
                pdf.set_y(ry + row_h)
            return pdf.get_y()

        # 좌측: 매출/매입/이익 요약
        tbl1_rows = [
            ("전체 회원사", f"{member_count}개사"),
            ("총 매출", f"{total_revenue:,.0f}원"),
            ("  ORD 매출", f"{total_ord:,.0f}원  ({ord_ratio}%)"),
            ("  MPR 매출", f"{total_mpr:,.0f}원  ({mpr_ratio}%)"),
            ("총 매입", f"{total_purchase:,.0f}원"),
            ("총 이익", f"{total_profit:,.0f}원"),
            ("이익률", f"{profit_rate_total}%"),
            ("회원사당 평균 매출", f"{avg_revenue:,.0f}원"),
            ("회원사당 평균 이익", f"{avg_profit:,.0f}원"),
        ]
        tbl1_start = pdf.get_y()
        draw_summary_table("매출 / 매입 / 이익 현황", tbl1_rows, tbl1_start)

        # 우측: 분석 지표
        tbl2_rows = [
            ("이익 최고 회원사", f"{max_profit_m['company_name']}  ({max_profit_m['profit']:,.0f}원)" if max_profit_m else "-"),
            ("이익 최저 회원사", f"{min_profit_m['company_name']}  ({min_profit_m['profit']:,.0f}원)" if min_profit_m else "-"),
            ("PB 회원사", f"{pb_count}개사  (매출 {pb_revenue:,.0f}원)"),
            ("비PB 회원사", f"{non_pb_count}개사  (매출 {non_pb_revenue:,.0f}원)"),
            ("이익률 90% 이상", f"{profit_over_90}개사"),
            ("이익률 50% 미만", f"{profit_under_50}개사"),
        ]
        draw_summary_table("분석 지표", tbl2_rows, tbl1_start, table_x=150, col_label_w=50, col_value_w=82)

        # 하단: 이익률 분포 바
        dist_bar_y = max(tbl1_start + len(tbl1_rows) * 7.5 + 20, pdf.get_y() + 12)
        pdf.set_xy(15, dist_bar_y)
        pdf.set_font("Korean", "B", 9)
        pdf.set_text_color(27, 42, 74)
        pdf.cell(0, 7, "이익률 분포 현황", ln=True)
        pdf.ln(2)

        dist_cats = [
            ("90% 이상", profit_over_90, (16, 185, 129)),
            ("70~90%", sum(1 for m in member_agg.values() if m['revenue_total'] > 0 and 70 <= (m['profit'] / m['revenue_total'] * 100) < 90), (99, 102, 241)),
            ("50~70%", sum(1 for m in member_agg.values() if m['revenue_total'] > 0 and 50 <= (m['profit'] / m['revenue_total'] * 100) < 70), (245, 158, 11)),
            ("50% 미만", profit_under_50, (239, 68, 68)),
        ]
        bar_x = 15
        bar_total_w = 267
        bar_h = 10
        bar_y = pdf.get_y()
        pdf.set_fill_color(240, 242, 245)
        pdf.rect(bar_x, bar_y, bar_total_w, bar_h, 'F')

        offset = 0
        for cat_label, cat_count, (cr, cg, cb) in dist_cats:
            if member_count == 0: continue
            seg_w = (cat_count / member_count) * bar_total_w
            if seg_w > 0:
                pdf.set_fill_color(cr, cg, cb)
                pdf.rect(bar_x + offset, bar_y, seg_w, bar_h, 'F')
                if seg_w > 25:
                    pdf.set_xy(bar_x + offset, bar_y + 1)
                    pdf.set_font("Korean", "B", 6.5)
                    pdf.set_text_color(255, 255, 255)
                    pdf.cell(seg_w, 4, f"{cat_label}", align='C')
                    pdf.set_xy(bar_x + offset, bar_y + 5)
                    pdf.set_font("Korean", "", 6)
                    pdf.cell(seg_w, 4, f"{cat_count}개사 ({cat_count/member_count*100:.0f}%)", align='C')
            offset += seg_w

        pdf.set_y(bar_y + bar_h + 4)
        legend_x = 15
        for cat_label, cat_count, (cr, cg, cb) in dist_cats:
            pdf.set_fill_color(cr, cg, cb)
            pdf.rect(legend_x, pdf.get_y() + 1.5, 3, 3, 'F')
            pdf.set_xy(legend_x + 5, pdf.get_y())
            pdf.set_font("Korean", "", 6.5)
            pdf.set_text_color(74, 85, 104)
            pdf.cell(0, 5, f"{cat_label}: {cat_count}개사")
            legend_x += 55

        # ── 4페이지: 이익 TOP 10 리스트 + 도넛 차트 ──
        pdf.add_page()
        section_heading("이익 분석", "03")

        # 이익 TOP 10 리스트 (화면과 동일한 프로그레스바 스타일)
        top10 = sorted(member_agg.values(), key=lambda x: x['profit'], reverse=True)[:10]
        max_profit_val = top10[0]['profit'] if top10 else 1

        pdf.set_font("Korean", "B", 9)
        pdf.set_text_color(27, 42, 74)
        pdf.cell(0, 7, "이익 TOP 10", ln=True)
        pdf.ln(2)

        list_x = 15
        for idx, m in enumerate(top10):
            ry = pdf.get_y()
            bar_pct = m['profit'] / max_profit_val * 100 if max_profit_val > 0 else 0
            profit_str = f"{m['profit']:,.0f}원"

            # 순위
            pdf.set_xy(list_x, ry)
            pdf.set_font("Korean", "B", 7)
            pdf.set_text_color(148, 163, 184)
            pdf.cell(10, 7, str(idx + 1), align='R')

            # 회사명
            pdf.set_xy(list_x + 13, ry)
            pdf.set_font("Korean", "B", 7.5)
            pdf.set_text_color(27, 42, 74)
            pdf.cell(52, 7, str(m['company_name'] or '')[:20])

            # 프로그레스 바
            prog_x = list_x + 68
            prog_w = 120
            prog_h = 4
            prog_y = ry + 1.8
            pdf.set_fill_color(245, 245, 245)
            pdf.rect(prog_x, prog_y, prog_w, prog_h, 'F')
            pdf.set_fill_color(239, 68, 68)  # 빨강 (이익 색상)
            pdf.rect(prog_x, prog_y, prog_w * bar_pct / 100, prog_h, 'F')

            # 금액
            pdf.set_xy(prog_x + prog_w + 3, ry)
            pdf.set_font("Korean", "B", 7.5)
            pdf.set_text_color(220, 38, 38)
            pdf.cell(45, 7, profit_str, align='R')

            pdf.set_y(ry + 8)

        # 도넛 차트들: TOP10 아래에 큰 사이즈로 배치
        chart_row_y = pdf.get_y() + 6
        pdf.image(chart_files[1], x=15, y=chart_row_y, w=130)
        pdf.image(chart_files[2], x=152, y=chart_row_y, w=130)

        # ── 5페이지: TOP 10 상세 테이블 ──
        pdf.add_page()
        section_heading("이익 상위 10 회원사 상세", "04")

        top_col_w = [10, 18, 55, 38, 38, 38, 22, 45]
        top_headers = ['순위', '회원번호', '회사명', '총매출(원)', '총매입(원)', '이익(원)', '이익률', '점유율']

        pdf.set_font("Korean", "B", 7)
        pdf.set_text_color(136, 150, 171)
        for i, h in enumerate(top_headers):
            pdf.cell(top_col_w[i], 6, h, align='C')
        pdf.ln()
        hdr_y = pdf.get_y()
        pdf.set_draw_color(27, 42, 74)
        pdf.set_line_width(0.4)
        pdf.line(15, hdr_y, 15 + sum(top_col_w), hdr_y)
        pdf.set_line_width(0.2)
        pdf.ln(1)

        for idx, m in enumerate(top10, 1):
            row_y = pdf.get_y()
            rate = round((m['profit'] / m['revenue_total'] * 100), 1) if m['revenue_total'] > 0 else 0.0

            pdf.set_font("Korean", "B" if idx <= 3 else "", 7.5)
            pdf.set_text_color(27, 42, 74)
            pdf.cell(top_col_w[0], 7, str(idx), align='C')
            pdf.set_font("Korean", "", 7)
            pdf.set_text_color(136, 150, 171)
            pdf.cell(top_col_w[1], 7, str(m['member_number'] or ''), align='C')
            pdf.set_text_color(27, 42, 74)
            pdf.cell(top_col_w[2], 7, str(m['company_name'] or '')[:24])
            # 매출 (어두운색)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(top_col_w[3], 7, f"{m['revenue_total']:,.0f}", align='R')
            # 매입 (인디고)
            pdf.set_text_color(99, 102, 241)
            pdf.cell(top_col_w[4], 7, f"{m['purchase_total']:,.0f}", align='R')
            # 이익 (빨강 볼드)
            pdf.set_font("Korean", "B", 7.5)
            pdf.set_text_color(220, 38, 38)
            pdf.cell(top_col_w[5], 7, f"{m['profit']:,.0f}", align='R')
            # 이익률
            pdf.set_font("Korean", "", 7)
            rate_color = (5, 150, 105) if rate >= 70 else ((217, 119, 6) if rate >= 50 else (220, 38, 38))
            pdf.set_text_color(rate_color[0], rate_color[1], rate_color[2])
            pdf.cell(top_col_w[6], 7, f"{rate}%", align='C')
            # 점유율 바
            bx = pdf.get_x() + 1
            bar_full_w = top_col_w[7] - 16
            ratio = m['profit'] / max_profit_val if max_profit_val > 0 else 0
            pdf.set_fill_color(245, 245, 245)
            pdf.rect(bx, row_y + 2.2, bar_full_w, 2.5, 'F')
            pdf.set_fill_color(239, 68, 68)
            pdf.rect(bx, row_y + 2.2, bar_full_w * ratio, 2.5, 'F')
            pct = (m['profit'] / total_profit * 100) if total_profit > 0 else 0
            pdf.set_font("Korean", "", 6.5)
            pdf.set_text_color(136, 150, 171)
            pdf.cell(top_col_w[7], 7, f"{pct:.1f}%", align='R')
            pdf.ln()
            pdf.set_draw_color(240, 242, 245)
            pdf.line(15, pdf.get_y(), 15 + sum(top_col_w), pdf.get_y())

        # ── 6페이지~: 상세 테이블 ──
        pdf.add_page()
        section_heading("회원사별 상세 내역", "05")

        col_widths = [9, 16, 55, 14, 32, 32, 34, 34, 34, 22]
        headers = ['No', '회원번호', '회사명', 'Phase', 'ORD매출(원)', 'MPR매출(원)', '총매출(원)', '총매입(원)', '이익(원)', '이익률']

        def draw_detail_header():
            pdf.set_font("Korean", "B", 7)
            pdf.set_text_color(136, 150, 171)
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 6, h, align='C')
            pdf.ln()
            y = pdf.get_y()
            pdf.set_draw_color(27, 42, 74)
            pdf.set_line_width(0.4)
            pdf.line(15, y, 15 + sum(col_widths), y)
            pdf.set_line_width(0.2)
            pdf.ln(0.5)

        draw_detail_header()

        for idx, row in enumerate(detail_rows, 1):
            if pdf.get_y() > 178:
                pdf.add_page()
                section_heading("회원사별 상세 내역 (계속)", "05")
                draw_detail_header()

            row_y = pdf.get_y()
            if idx % 2 == 0:
                pdf.set_fill_color(250, 251, 252)
                pdf.rect(15, row_y, sum(col_widths), 6.2, 'F')

            pdf.set_font("Korean", "", 6.5)
            pdf.set_text_color(136, 150, 171)
            pdf.cell(col_widths[0], 6.2, str(idx), align='C')
            pdf.cell(col_widths[1], 6.2, str(row['member_number'] or ''), align='C')
            pdf.set_text_color(27, 42, 74)
            pdf.cell(col_widths[2], 6.2, str(row['company_name'] or '')[:24])
            pdf.set_text_color(136, 150, 171)
            pdf.cell(col_widths[3], 6.2, str(row['phase'] or ''), align='C')

            # ORD/MPR 매출
            pdf.set_text_color(31, 41, 55)
            pdf.cell(col_widths[4], 6.2, f"{row['ord_total']:,.0f}", align='R')
            pdf.cell(col_widths[5], 6.2, f"{row['mpr_total']:,.0f}", align='R')
            # 총매출 (어두운색 볼드)
            pdf.set_font("Korean", "B", 6.5)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(col_widths[6], 6.2, f"{row['revenue_total']:,.0f}", align='R')
            # 총매입 (인디고)
            pdf.set_font("Korean", "", 6.5)
            pdf.set_text_color(99, 102, 241)
            pdf.cell(col_widths[7], 6.2, f"{row['purchase_total']:,.0f}", align='R')
            # 이익 (빨강)
            profit_val = row['profit']
            pdf.set_font("Korean", "B", 6.5)
            if profit_val >= 0:
                pdf.set_text_color(220, 38, 38)
            else:
                pdf.set_text_color(148, 163, 184)
            pdf.cell(col_widths[8], 6.2, f"{profit_val:,.0f}", align='R')
            # 이익률
            pdf.set_font("Korean", "", 6.5)
            pr = row['profit_rate']
            if pr >= 70:
                pdf.set_text_color(5, 150, 105)
            elif pr >= 50:
                pdf.set_text_color(217, 119, 6)
            else:
                pdf.set_text_color(220, 38, 38)
            pdf.cell(col_widths[9], 6.2, f"{pr}%", align='C')
            pdf.ln()
            pdf.set_draw_color(244, 245, 247)
            pdf.line(15, pdf.get_y(), 15 + sum(col_widths), pdf.get_y())

        # 합계 행
        total_y = pdf.get_y()
        pdf.set_draw_color(27, 42, 74)
        pdf.set_line_width(0.5)
        pdf.line(15, total_y, 15 + sum(col_widths), total_y)
        pdf.set_line_width(0.2)
        pdf.ln(0.5)

        pdf.set_font("Korean", "B", 7)
        pdf.set_fill_color(30, 41, 59)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3], 7, "TOTAL", fill=True, align='C')
        # ORD/MPR (밝은 회색)
        pdf.set_text_color(203, 213, 225)
        pdf.cell(col_widths[4], 7, f"{total_ord:,.0f}", fill=True, align='R')
        pdf.cell(col_widths[5], 7, f"{total_mpr:,.0f}", fill=True, align='R')
        # 총매출 (흰색)
        pdf.set_text_color(241, 245, 249)
        pdf.cell(col_widths[6], 7, f"{total_revenue:,.0f}", fill=True, align='R')
        # 총매입 (연보라)
        pdf.set_text_color(165, 180, 252)
        pdf.cell(col_widths[7], 7, f"{total_purchase:,.0f}", fill=True, align='R')
        # 이익 (연빨강)
        pdf.set_text_color(252, 165, 165)
        pdf.cell(col_widths[8], 7, f"{total_profit:,.0f}", fill=True, align='R')
        pdf.cell(col_widths[9], 7, f"{profit_rate_total}%", fill=True, align='C')
        pdf.ln()

        # PDF 출력
        pdf_output = pdf.output()
        pdf_buffer = io.BytesIO(pdf_output)
        pdf_buffer.seek(0)

        for f in chart_files:
            try:
                os.remove(f)
            except OSError:
                pass

        filename = f"profit_report_{datetime.now().strftime('%Y%m%d')}.pdf"
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"이익내역 보고서 PDF 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")


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
                LEFT JOIN member_fee_schedule mf ON c.fee_code = mf.fee_code
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
                LEFT JOIN member_fee_schedule mf ON c.fee_code = mf.fee_code
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

            # 10. info_company_circuit (정보이용사 회선내역)
            cur.execute("""
                SELECT sc.company_name AS title,
                       sc.member_code || ' / 회선 ' || count(*)::text || '건' AS subtitle,
                       sc.member_code, count(*) AS circuit_count
                FROM info_company_circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                WHERE sc.company_name ILIKE %s OR sc.member_code ILIKE %s
                GROUP BY sc.company_name, sc.member_code
                ORDER BY count(*) DESC LIMIT 5
            """, (pattern, pattern))
            info_circuit_items = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT count(DISTINCT sc.member_code)
                FROM info_company_circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                WHERE sc.company_name ILIKE %s OR sc.member_code ILIKE %s
            """, (pattern, pattern))
            info_circuit_total = cur.fetchone()["count"]
            results["info_circuits"] = {"total": info_circuit_total, "items": info_circuit_items}

            # 11. 정보이용사 매출내역
            cur.execute("""
                SELECT sc.company_name AS title,
                       sc.member_code || ' / ' ||
                       COALESCE(sum(ifs.price)::text, '0') || '원 (' ||
                       count(*)::text || '회선)' AS subtitle,
                       sc.member_code, count(*) AS circuit_count,
                       COALESCE(sum(ifs.price), 0) AS total_revenue
                FROM info_company_circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                LEFT JOIN info_fee_schedule ifs ON c.fee_code = ifs.fee_code
                WHERE (sc.company_name ILIKE %s OR sc.member_code ILIKE %s)
                    AND c.usage = 'MKD'
                GROUP BY sc.company_name, sc.member_code
                ORDER BY COALESCE(sum(ifs.price), 0) DESC LIMIT 5
            """, (pattern, pattern))
            info_revenue_items = [dict(r) for r in cur.fetchall()]
            for item in info_revenue_items:
                rev = item.get("total_revenue", 0)
                if rev and rev > 0:
                    item["subtitle"] = f"{item['member_code']} / 월 {rev:,.0f}원 ({item['circuit_count']}회선)"

            cur.execute("""
                SELECT count(DISTINCT sc.member_code)
                FROM info_company_circuit c
                JOIN subscriber_codes sc ON c.member_code = sc.member_code
                WHERE (sc.company_name ILIKE %s OR sc.member_code ILIKE %s)
                    AND c.usage = 'MKD'
            """, (pattern, pattern))
            info_revenue_total = cur.fetchone()["count"]
            results["info_revenue"] = {"total": info_revenue_total, "items": info_revenue_items}

            # 12. info_purchase_contract (정보이용사 매입내역)
            info_purchase_where = """
                pc.member_code ILIKE %s OR pc.datacenter_code ILIKE %s
                OR pc.provider ILIKE %s OR pc.service_id ILIKE %s
                OR pc.nni_id ILIKE %s OR pc.cost_code ILIKE %s
                OR sc.company_name ILIKE %s
            """
            info_purchase_params = (pattern, pattern, pattern, pattern, pattern, pattern, pattern)

            cur.execute(f"""
                SELECT pc.id, COALESCE(sc.company_name, pc.member_code) AS title,
                       COALESCE(pc.provider, '') || ' / ' || COALESCE(pc.nni_id, '') || ' / ' || COALESCE(nc.cost_standart, '') AS subtitle,
                       pc.member_code
                FROM info_purchase_contract pc
                LEFT JOIN subscriber_codes sc ON pc.member_code = sc.member_code
                LEFT JOIN network_cost nc ON pc.cost_code = nc.code
                WHERE {info_purchase_where}
                ORDER BY pc.id LIMIT 5
            """, info_purchase_params)
            info_purchase_items = [dict(r) for r in cur.fetchall()]

            cur.execute(f"""
                SELECT count(*) FROM info_purchase_contract pc
                LEFT JOIN subscriber_codes sc ON pc.member_code = sc.member_code
                WHERE {info_purchase_where}
            """, info_purchase_params)
            info_purchase_total = cur.fetchone()["count"]
            results["info_purchases"] = {"total": info_purchase_total, "items": info_purchase_items}

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


# ── 재해복구훈련 ──

DR_TRAINING_TARGETS = [
    {
        "procedure": "51.01",
        "device_name": "RBD_ASN_L3_01",
        "ip": "172.30.172.13",
        "label": "DR 주문망 인터페이스 활성화 (RBD_COM_FW_01 방화벽 작업)",
        "interfaces": ["Ethernet1/48"],
        "config_checks": []
    },
    {
        "procedure": "51.01",
        "device_name": "RBD_SVC_L3_01",
        "ip": "172.30.172.12",
        "label": "DR 주문망 인터페이스 활성화 (RBD_COM_FW_01 방화벽 작업)",
        "interfaces": ["Ethernet1/41"],
        "config_checks": []
    },
    {
        "procedure": "51.02",
        "device_name": "PYD_DFP_BB_01",
        "ip": "172.28.172.34",
        "label": "주센터 RP인터페이스 셧다운 처리",
        "interfaces": ["loopback100"],
        "config_checks": []
    },
    {
        "procedure": "51.02",
        "device_name": "PYD_DFP_BB_02",
        "ip": "172.28.172.35",
        "label": "주센터 RP인터페이스 셧다운 처리",
        "interfaces": ["loopback100"],
        "config_checks": []
    },
    {
        "procedure": "51.02",
        "device_name": "PYD_MPR_L3_01",
        "ip": "172.28.172.40",
        "label": "RP라우팅 및 BGP Redip Route-Map RP 제거",
        "interfaces": [],
        "config_checks": [
            {
                "type": "route",
                "command": "show ip route 192.23.180.1/32",
                "description": "ip route 192.23.180.1/32 172.16.66.1",
                "expected": "172.16.66.1"
            },
            {
                "type": "prefix_list",
                "command": "show ip prefix-list Static_to_BGP",
                "description": "ip prefix-list Static_to_BGP seq 70 permit 192.23.180.1/32",
                "expected": "192.23.180.1/32"
            }
        ]
    },
    {
        "procedure": "51.02",
        "device_name": "PHQ_MPR_L3_01",
        "ip": "192.168.254.43",
        "label": "RP라우팅 및 BGP Redip Route-Map RP 제거",
        "interfaces": [],
        "config_checks": [
            {
                "type": "route",
                "command": "show ip route 192.23.180.1/32",
                "description": "ip route 192.23.180.1/32 172.16.67.1",
                "expected": "172.16.67.1"
            },
            {
                "type": "prefix_list",
                "command": "show ip prefix-list Static_to_BGP",
                "description": "ip prefix-list Static_to_BGP seq 70 permit 192.23.180.1/32",
                "expected": "192.23.180.1/32"
            }
        ]
    },
    {
        "procedure": "51.02",
        "device_name": "PYD_MKD_L3_01",
        "ip": "99.99.1.5",
        "vendor": "arista",
        "label": "RP라우팅 및 BGP Redip Route-Map RP 제거",
        "interfaces": [],
        "config_checks": [
            {
                "type": "route",
                "command": "show ip route 192.23.180.1/32",
                "description": "ip route 192.23.180.1/32 172.16.68.1",
                "expected": "172.16.68.1"
            },
            {
                "type": "prefix_list",
                "command": "show ip prefix-list Static_Redip",
                "description": "ip prefix-list Static_Redip seq 130 permit 192.23.180.1/32",
                "expected": "192.23.180.1/32"
            }
        ]
    },
    {
        "procedure": "51.02",
        "device_name": "PHQ_MKD_L3_01",
        "ip": "99.99.1.6",
        "vendor": "arista",
        "label": "RP라우팅 및 BGP Redip Route-Map RP 제거",
        "interfaces": [],
        "config_checks": [
            {
                "type": "route",
                "command": "show ip route 192.23.180.1/32",
                "description": "ip route 192.23.180.1/32 172.16.69.1",
                "expected": "172.16.69.1"
            },
            {
                "type": "prefix_list",
                "command": "show ip prefix-list Static_Redip",
                "description": "ip prefix-list Static_Redip seq 130 permit 192.23.180.1/32",
                "expected": "192.23.180.1/32"
            }
        ]
    },
    {
        "procedure": "51.02",
        "device_name": "RBD_SVC_L3_01",
        "ip": "172.30.172.12",
        "label": "DR 시세망 인터페이스 활성화",
        "interfaces": ["Ethernet1/42"],
        "config_checks": []
    },
    {
        "procedure": "51.02",
        "device_name": "RBD_MPR_L3_01",
        "ip": "172.30.172.14",
        "label": "DR 시세망 인터페이스 활성화 및 ip pim sparse-mode 활성화",
        "interfaces": ["Ethernet1/48"],
        "config_checks": [],
        "pim_checks": [
            {"description": "Ethernet1/41", "interfaces": ["Ethernet1/41"]},
            {"description": "Ethernet1/45", "interfaces": ["Ethernet1/45"]},
            {"description": "Ethernet1/45.3801~3825",
             "interfaces": [f"Ethernet1/45.{i}" for i in range(3801, 3826)]},
            {"description": "Ethernet1/46", "interfaces": ["Ethernet1/46"]},
            {"description": "Ethernet1/46.3601~3632",
             "interfaces": [f"Ethernet1/46.{i}" for i in range(3601, 3633)]},
            {"description": "Ethernet1/47", "interfaces": ["Ethernet1/47"]},
            {"description": "Ethernet1/47.3701~3732",
             "interfaces": [f"Ethernet1/47.{i}" for i in range(3701, 3733)]}
        ]
    },
    {
        "procedure": "51.04",
        "device_name": "PYD_ASN_L3_01",
        "ip": "172.28.172.29",
        "label": "KRX 전용회선 인터페이스 셧다운 처리",
        "interfaces": ["Ethernet1/42"],
        "config_checks": []
    },
    {
        "procedure": "51.05",
        "device_name": "PYD_ASN_L3_01",
        "ip": "172.28.172.29",
        "label": "코스콤 전용회선 인터페이스 셧다운 처리",
        "interfaces": ["Ethernet1/41"],
        "config_checks": []
    },
    {
        "procedure": "51.05",
        "device_name": "PHQ_ASN_L3_01",
        "ip": "192.168.254.40",
        "label": "코스콤 전용회선 인터페이스 셧다운 처리",
        "interfaces": ["Ethernet1/47"],
        "config_checks": []
    }
]


def _judge_main_dr(target, item_type, oper_state=None, found=None):
    """가동상태/DR상태 판정 로직"""
    proc = target["procedure"]
    name = target["device_name"]
    is_down = oper_state != "up" if oper_state else None

    if item_type == "interface":
        # 51.01, 51.02 RBD_MPR/RBD_SVC: 평상 시 down=OK
        if proc == "51.01" or (proc == "51.02" and name in ("RBD_MPR_L3_01", "RBD_SVC_L3_01")):
            return (is_down, not is_down)
        # 51.02 BB, 51.04, 51.05: 평상 시 up=OK
        else:
            return (not is_down, is_down)
    else:
        # config/pim: RBD_MPR 미설정=평상시OK, 나머지 설정됨=평상시OK
        if name == "RBD_MPR_L3_01":
            return (not found, found)
        else:
            return (found, not found)


@router.post("/dr-training/collect")
async def collect_dr_training_status():
    """재해복구훈련 상태 수집 (1분 주기 배치 호출용) - 스위치 API 호출 후 DB 저장"""
    try:
        intf_futures = {}
        config_futures = {}
        pim_futures = {}
        now = datetime.now()

        for idx, target in enumerate(DR_TRAINING_TARGETS):
            key = f"{idx}_{target['device_name']}"
            if target.get("interfaces"):
                intf_futures[key] = (target, executor.submit(nxapi_query_interfaces, target["ip"], target["interfaces"]))
            if target.get("config_checks"):
                check_fn = arista_query_config_checks if target.get("vendor") == "arista" else nxapi_query_config_checks
                config_futures[key] = (target, executor.submit(check_fn, target["ip"], target["config_checks"]))
            if target.get("pim_checks"):
                pim_futures[key] = (target, executor.submit(nxapi_query_pim_check, target["ip"], target["pim_checks"]))

        rows = []
        for idx, target in enumerate(DR_TRAINING_TARGETS):
            key = f"{idx}_{target['device_name']}"
            reachable = True
            error_msg = None
            item_no = 0

            # 인터페이스 결과
            if key in intf_futures:
                try:
                    result = intf_futures[key][1].result(timeout=30)
                except Exception as e:
                    result = {"success": False, "interfaces": [], "error": str(e)}
                if not result["success"]:
                    reachable = False
                    error_msg = result.get("error")
                for intf in result.get("interfaces", []):
                    item_no += 1
                    main_ok, dr_ok = _judge_main_dr(target, "interface", oper_state=intf.get("oper_state"))
                    rows.append((
                        target["procedure"], target["device_name"], target["ip"],
                        target.get("label", ""), reachable, error_msg,
                        item_no, "interface", intf.get("name", ""),
                        intf.get("admin_state"), intf.get("oper_state"),
                        intf.get("speed"), intf.get("mtu"),
                        intf.get("description"), intf.get("last_link_flapped"),
                        None, None, main_ok, dr_ok, now
                    ))

            # 설정 확인 결과
            if key in config_futures:
                try:
                    result = config_futures[key][1].result(timeout=30)
                except Exception as e:
                    result = {"success": False, "checks": [], "error": str(e)}
                if not result["success"]:
                    reachable = False
                    error_msg = result.get("error")
                for chk in result.get("checks", []):
                    item_no += 1
                    main_ok, dr_ok = _judge_main_dr(target, "config", found=chk.get("found"))
                    rows.append((
                        target["procedure"], target["device_name"], target["ip"],
                        target.get("label", ""), reachable, error_msg,
                        item_no, chk.get("type", "config"), chk.get("description", ""),
                        None, None, None, None, None, None,
                        chk.get("found"), chk.get("detail"), main_ok, dr_ok, now
                    ))

            # PIM 결과
            if key in pim_futures:
                try:
                    result = pim_futures[key][1].result(timeout=30)
                except Exception as e:
                    result = {"success": False, "checks": [], "error": str(e)}
                if not result["success"]:
                    reachable = False
                    error_msg = result.get("error")
                for chk in result.get("checks", []):
                    item_no += 1
                    main_ok, dr_ok = _judge_main_dr(target, "config", found=chk.get("found"))
                    rows.append((
                        target["procedure"], target["device_name"], target["ip"],
                        target.get("label", ""), reachable, error_msg,
                        item_no, chk.get("type", "pim_sparse"), chk.get("description", ""),
                        None, None, None, None, None, None,
                        chk.get("found"), chk.get("detail"), main_ok, dr_ok, now
                    ))

            # 인터페이스/설정 모두 없는 장비가 접속 불가인 경우
            if item_no == 0 and not reachable:
                rows.append((
                    target["procedure"], target["device_name"], target["ip"],
                    target.get("label", ""), False, error_msg,
                    1, "error", "접속불가",
                    None, None, None, None, None, None,
                    None, error_msg, False, False, now
                ))

        # 이전 값 조회 → 변경 감지 → Slack 알림
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT procedure_code, device_name, item_no, item_name, main_ok, dr_ok
                    FROM dr_training_result
                    WHERE checked_at = (SELECT MAX(checked_at) FROM dr_training_result)
                """)
                prev_map = {}
                for r in cur.fetchall():
                    key = f"{r['procedure_code']}_{r['device_name']}_{r['item_no']}"
                    prev_map[key] = (r['main_ok'], r['dr_ok'], r['item_name'])

        # 변경된 항목 Slack 전송
        if prev_map and rows:
            import threading
            from utils.slack_client import send_alert
            changed = []
            unreachable_alerted = set()

            # 이전에 접속 가능했던 장비 목록
            prev_reachable = set()
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT DISTINCT procedure_code, device_name, ip
                        FROM dr_training_result
                        WHERE checked_at = (SELECT MAX(checked_at) FROM dr_training_result)
                          AND reachable = true
                    """)
                    for r in cur.fetchall():
                        prev_reachable.add(f"{r['procedure_code']}_{r['device_name']}")

            for row in rows:
                # row: (procedure, device_name, ip, label, reachable, error, item_no, item_type, item_name, ...)
                proc, dev, ip, label = row[0], row[1], row[2], row[3]
                reachable, error_msg = row[4], row[5]
                item_no, item_type, item_name = row[6], row[7], row[8]
                new_main, new_dr = row[17], row[18]
                dev_key = f"{proc}_{dev}"

                # 접속 불가: 이전에 접속 가능했으면 통신불가 알림 (장비당 1회)
                if not reachable or item_type == "error":
                    if dev_key in prev_reachable and dev_key not in unreachable_alerted:
                        unreachable_alerted.add(dev_key)
                        changed.append({
                            "proc": proc, "dev": dev, "ip": ip, "label": label,
                            "item_no": 0, "item_name": "통신불가", "item_type": "unreachable",
                            "old_main": None, "new_main": None,
                            "old_dr": None, "new_dr": None,
                            "error": error_msg
                        })
                    continue

                key = f"{proc}_{dev}_{item_no}"
                if key in prev_map:
                    old_main, old_dr, _ = prev_map[key]
                    if old_main != new_main or old_dr != new_dr:
                        changed.append({
                            "proc": proc, "dev": dev, "ip": ip, "label": label,
                            "item_no": item_no, "item_name": item_name, "item_type": item_type,
                            "old_main": old_main, "new_main": new_main,
                            "old_dr": old_dr, "new_dr": new_dr
                        })

            if changed:
                # 전체 전환율 계산
                total_items = len(rows)
                total_main_ok = sum(1 for r in rows if r[17])
                total_dr_ok = sum(1 for r in rows if r[18])
                main_pct = round(total_main_ok / max(total_items, 1) * 100)
                dr_pct = round(total_dr_ok / max(total_items, 1) * 100)
                rate_summary = f"가동전환율 {main_pct}% ({total_main_ok}/{total_items}) | DR전환율 {dr_pct}% ({total_dr_ok}/{total_items})"

                def _send_dr_alerts(items, summary):
                    for c in items:
                        # 통신불가 알림
                        if c.get("item_type") == "unreachable":
                            fields = [
                                {"title": "절차", "value": c["proc"], "short": True},
                                {"title": "장비", "value": f"*{c['dev']}* ({c['ip']})", "short": True},
                                {"title": "상태", "value": ":x: 통신불가", "short": True},
                            ]
                            if c.get("error"):
                                fields.append({"title": "오류", "value": f"`{c['error']}`", "short": False})
                            if c.get("label"):
                                fields.append({"title": "설명", "value": c["label"], "short": False})
                            send_alert(
                                channel="#network-alert-dr훈련",
                                title=f":warning: DR훈련 장비 통신불가 >> {c['dev']}",
                                message="",
                                color="#dc2626",
                                fields=fields
                            )
                            continue

                        main_chg = f"{'OK' if c['old_main'] else 'Not OK'} → {'OK' if c['new_main'] else 'Not OK'}" if c['old_main'] != c['new_main'] else ""
                        dr_chg = f"{'OK' if c['old_dr'] else 'Not OK'} → {'OK' if c['new_dr'] else 'Not OK'}" if c['old_dr'] != c['new_dr'] else ""
                        fields = [
                            {"title": "절차", "value": c["proc"], "short": True},
                            {"title": "장비", "value": f"*{c['dev']}* ({c['ip']})", "short": True},
                            {"title": "항목", "value": f"[{c['item_no']}] {c['item_name']}", "short": False},
                        ]
                        if main_chg:
                            fields.append({"title": "가동상태 변경", "value": main_chg, "short": True})
                        if dr_chg:
                            fields.append({"title": "DR상태 변경", "value": dr_chg, "short": True})
                        if c.get("label"):
                            fields.append({"title": "설명", "value": c["label"], "short": False})
                        fields.append({"title": "전체 전환율", "value": f"`{summary}`", "short": False})

                        send_alert(
                            channel="#network-alert-dr훈련",
                            title=f":rotating_light: DR훈련 상태 변경 >> {c['dev']}",
                            message="",
                            color="#ff9900",
                            fields=fields
                        )
                    logger.info(f"DR 훈련 상태 변경 알림 {len(items)}건 전송")

                threading.Thread(target=_send_dr_alerts, args=(changed, rate_summary), daemon=True).start()

        # DB 저장 (신규 INSERT + 1일 이전 데이터 정리)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM dr_training_result WHERE checked_at < NOW() - INTERVAL '1 day'")
                if rows:
                    from psycopg2.extras import execute_values
                    execute_values(cur, """
                        INSERT INTO dr_training_result
                            (procedure_code, device_name, ip, label, reachable, error_message,
                             item_no, item_type, item_name,
                             admin_state, oper_state, speed, mtu, intf_description, last_link_flapped,
                             config_found, config_detail, main_ok, dr_ok, checked_at)
                        VALUES %s
                    """, rows)
            conn.commit()

        logger.info(f"DR 훈련 상태 수집 완료: {len(rows)}건 저장")
        return {"success": True, "count": len(rows), "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")}

    except Exception as e:
        logger.error(f"DR 훈련 상태 수집 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dr-training/status")
async def get_dr_training_status():
    """재해복구훈련 상태 조회 (DB에서 읽기)"""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT procedure_code, device_name, ip, label, reachable, error_message,
                           item_no, item_type, item_name,
                           admin_state, oper_state, speed, mtu, intf_description, last_link_flapped,
                           config_found, config_detail, main_ok, dr_ok, checked_at
                    FROM dr_training_result
                    WHERE checked_at = (SELECT MAX(checked_at) FROM dr_training_result)
                    ORDER BY id
                """)
                rows = cur.fetchall()

        if not rows:
            return {"success": True, "timestamp": "-", "devices": [], "summary": {
                "total_interfaces": 0, "up_count": 0, "down_count": 0,
                "total_config_checks": 0, "config_ok": 0, "config_fail": 0, "all_ok": True
            }}

        timestamp = rows[0]["checked_at"].strftime("%Y-%m-%d %H:%M:%S") if rows else "-"

        # 장비별로 그룹핑
        devices = []
        current_key = None
        device_data = None
        up_count = down_count = check_ok = check_fail = 0

        for row in rows:
            key = f"{row['procedure_code']}_{row['device_name']}_{row['ip']}"
            if key != current_key:
                if device_data:
                    devices.append(device_data)
                device_data = {
                    "procedure": row["procedure_code"],
                    "device_name": row["device_name"],
                    "ip": row["ip"],
                    "label": row["label"] or "",
                    "reachable": row["reachable"],
                    "interfaces": [],
                    "config_checks": [],
                    "error": row["error_message"]
                }
                current_key = key

            if row["item_type"] == "interface":
                device_data["interfaces"].append({
                    "name": row["item_name"],
                    "admin_state": row["admin_state"] or "-",
                    "oper_state": row["oper_state"] or "unknown",
                    "speed": row["speed"] or "-",
                    "mtu": row["mtu"] or "-",
                    "description": row["intf_description"] or "",
                    "last_link_flapped": row["last_link_flapped"] or "-"
                })
                if row["oper_state"] == "up":
                    up_count += 1
                else:
                    down_count += 1
            elif row["item_type"] != "error":
                device_data["config_checks"].append({
                    "type": row["item_type"],
                    "description": row["item_name"],
                    "found": row["config_found"],
                    "detail": row["config_detail"] or ""
                })
                if row["config_found"]:
                    check_ok += 1
                else:
                    check_fail += 1

        if device_data:
            devices.append(device_data)

        total_intf = up_count + down_count
        total_checks = check_ok + check_fail

        return {
            "success": True,
            "timestamp": timestamp,
            "devices": devices,
            "summary": {
                "total_interfaces": total_intf,
                "up_count": up_count,
                "down_count": down_count,
                "total_config_checks": total_checks,
                "config_ok": check_ok,
                "config_fail": check_fail,
                "all_ok": down_count == 0 and check_fail == 0
            }
        }

    except Exception as e:
        logger.error(f"DR 훈련 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 시스템 모니터링 ──

@router.get("/system/metrics")
async def get_system_metrics():
    """호스트 시스템 및 컨테이너 메트릭 조회 (호스트 cron이 생성한 JSON 파일 읽기)"""
    try:
        metrics_path = "/app/data/system_metrics.json"
        if not os.path.exists(metrics_path):
            return {"success": False, "error": "메트릭 파일 없음"}
        with open(metrics_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"시스템 메트릭 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 멀티캐스트 상태 DB 저장/조회 ──

@router.post("/multicast/collect")
async def collect_multicast_status(request: Request):
    """멀티캐스트 상태 수집 결과를 DB에 저장"""
    try:
        data = await request.json()
        market_type = data.get("market_type", "")
        items = data.get("data", [])
        now = datetime.now()

        if not items:
            return {"success": True, "count": 0}

        rows = []
        for item in items:
            if not item or not item.get("device_name"):
                continue
            products = item.get("products", [])
            products_str = ",".join(products) if isinstance(products, list) else str(products or "")
            rp_list = item.get("pim_rp") or item.get("rp_addresses", [])
            pim_rp = rp_list[0] if isinstance(rp_list, list) and rp_list else (str(rp_list) if rp_list else "")

            received = item.get("received_products", [])
            received_str = ",".join(received) if isinstance(received, list) else str(received or "")

            rows.append((
                market_type,
                item.get("member_code", ""),
                item.get("member_name", ""),
                str(item.get("member_no", "")),
                item.get("device_name", ""),
                item.get("device_os", ""),
                products_str,
                pim_rp,
                item.get("product_cnt", 0) or 0,
                item.get("mroute_cnt", 0) or 0,
                item.get("oif_cnt", 0) or 0,
                item.get("connected_server_cnt", 0) or 0,
                str(item.get("min_update", "") or ""),
                item.get("check_result", ""),
                item.get("alarm", False),
                received_str,
                now
            ))

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM multicast_status WHERE checked_at < NOW() - INTERVAL '2 days'")
                if rows:
                    from psycopg2.extras import execute_values
                    execute_values(cur, """
                        INSERT INTO multicast_status
                            (market_type, member_code, member_name, member_no, device_name, device_os,
                             products, pim_rp, product_cnt, mroute_cnt, oif_cnt, connected_server_cnt,
                             min_update, check_result, alarm, received_products, checked_at)
                        VALUES %s
                    """, rows)
            conn.commit()

        logger.info(f"멀티캐스트 상태 수집 완료: market={market_type}, {len(rows)}건")
        return {"success": True, "count": len(rows), "market_type": market_type}

    except Exception as e:
        logger.error(f"멀티캐스트 상태 수집 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multicast/status")
async def get_multicast_status(market_type: str = Query(...)):
    """멀티캐스트 상태 조회 (DB에서 최신 데이터)"""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT market_type, member_code, member_name, member_no, device_name, device_os,
                           products, pim_rp, product_cnt, mroute_cnt, oif_cnt, connected_server_cnt,
                           min_update, check_result, alarm, received_products, checked_at
                    FROM multicast_status
                    WHERE market_type = %s
                      AND checked_at = (SELECT MAX(checked_at) FROM multicast_status WHERE market_type = %s)
                    ORDER BY member_no::int ASC
                """, (market_type, market_type))
                rows = cur.fetchall()

        if not rows:
            return {"data": [], "_meta": {"collected_at": "-", "status": "no_data"}}

        timestamp = rows[0]["checked_at"].strftime("%Y-%m-%d %H:%M:%S")
        data = []
        for r in rows:
            products = r["products"].split(",") if r["products"] else []
            received_products = r["received_products"].split(",") if r.get("received_products") else []
            check_result = r["check_result"] or ""
            badge_type = "success" if check_result == "정상확인" else ("primary" if check_result == "회원사연결서버없음" else ("warning" if check_result == "정상그룹개수초과" else "danger"))
            badge_icon = "fas fa-check" if badge_type == "success" else ("fas fa-info-circle" if badge_type == "primary" else "fas fa-exclamation-triangle")

            data.append({
                "updated_time": timestamp,
                "member_no": r["member_no"],
                "member_code": r["member_code"],
                "member_name": r["member_name"],
                "device_name": r["device_name"],
                "device_os": r["device_os"],
                "products": products,
                "received_products": received_products,
                "pim_rp": r["pim_rp"],
                "product_cnt": r["product_cnt"],
                "mroute_cnt": r["mroute_cnt"],
                "oif_cnt": r["oif_cnt"],
                "min_update": r["min_update"],
                "checked_at": r["checked_at"].strftime("%Y-%m-%d %H:%M") if r["checked_at"] else "-",
                "connected_server_cnt": r["connected_server_cnt"],
                "alarm": r["alarm"],
                "alarm_icon": "fa-bell" if r["alarm"] else "fa-bell-slash",
                "check_result": check_result,
                "check_result_badge": {"type": badge_type, "icon": badge_icon}
            })

        return {
            "data": data,
            "_meta": {"collected_at": timestamp, "status": "success", "total_devices": len(data)}
        }

    except Exception as e:
        logger.error(f"멀티캐스트 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multicast/sise_mapping")
async def get_sise_mapping():
    """수신_시세상품 판정용 product → {source_ips, group_ips} 매핑 반환.
    sise_products.operation_ip1/ip2 를 소스 IP, sise_channels.multicast_group_ip 를 그룹 IP로 사용."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.product_name, p.operation_ip1, p.operation_ip2,
                           array_remove(array_agg(DISTINCT c.multicast_group_ip), NULL) AS group_ips
                    FROM sise_products p
                    LEFT JOIN sise_channels c ON c.product_id = p.id
                    GROUP BY p.id, p.product_name, p.operation_ip1, p.operation_ip2
                    ORDER BY p.product_name
                """)
                rows = cur.fetchall()

        mapping = {}
        for r in rows:
            sources = [ip for ip in [r.get("operation_ip1"), r.get("operation_ip2")] if ip]
            groups = [g for g in (r.get("group_ips") or []) if g]
            mapping[r["product_name"]] = {
                "source_ips": sources,
                "group_ips": groups
            }
        return {"success": True, "data": mapping}

    except Exception as e:
        logger.error(f"시세상품 매핑 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
