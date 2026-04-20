import json, logging, re, time, html, sys, asyncio, requests, os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pprint import pprint
from typing import List, Dict, Tuple, Union, Optional
## Netmiko 라이브러리
from netmiko import ConnectHandler
from utils.cisco_multicast import ProcessMulticastInfo
from utils.cisco_interface import ProcessCiscoInterfaceInfo
from utils.cisco_arp import ProcessCiscoArpInfo

## 장비관리 라이브러리
from genie.testbed import load

# ── 수집 메타데이터 유틸 ──────────────────────────────────

def get_collection_meta(response_json: dict) -> dict:
    """API 수집 결과에서 장비별 성공/실패 통계를 추출"""
    total = len(response_json)
    failed_list = []
    success_count = 0

    for device_name, device_data in response_json.items():
        if device_data.get('error') or not device_data.get('cmd_response_list'):
            failed_list.append(device_name)
        else:
            success_count += 1

    if success_count == total:
        status = "success"
    elif success_count > 0:
        status = "partial"
    else:
        status = "failed"

    return {
        "collected_at": datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S'),
        "status": status,
        "total_devices": total,
        "success_devices": success_count,
        "failed_devices": len(failed_list),
        "failed_list": failed_list[:10]
    }


def save_json_with_validation(file_path: str, new_data: dict, meta: dict):
    """검증 후 JSON 저장. 수집 실패 시 기존 정상 데이터를 보존한다."""
    new_records = new_data.get('data', []) if isinstance(new_data, dict) else []

    # 기존 파일 읽기
    existing_data = None
    existing_records = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            existing_records = existing_data.get('data', []) if isinstance(existing_data, dict) else []
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    if len(new_records) > 0:
        # 새 데이터가 있으면 저장
        new_data['_meta'] = meta
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, indent=4, ensure_ascii=False)
        logger.info(f"[SAVE] {os.path.basename(file_path)}: {len(new_records)}건 저장 (status={meta['status']})")
    elif existing_data and len(existing_records) > 0:
        # 새 데이터 없지만 기존에 데이터 있으면 → 기존 data 유지, _meta만 갱신
        meta['status'] = 'failed'
        meta['preserved_from'] = existing_data.get('_meta', {}).get('collected_at', 'unknown')
        existing_data['_meta'] = meta
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)
        logger.warning(f"[SAVE] {os.path.basename(file_path)}: 수집 실패 → 기존 {len(existing_records)}건 유지 (preserved_from={meta.get('preserved_from')})")
    else:
        # 새 데이터도 없고 기존도 없으면 빈 데이터 + meta 저장
        new_data['_meta'] = meta
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, indent=4, ensure_ascii=False)
        logger.warning(f"[SAVE] {os.path.basename(file_path)}: 데이터 없음 (status={meta['status']})")

# ─────────────────────────────────────────────────────────

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/batch.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 스레드풀 생성
executor = ThreadPoolExecutor(max_workers=60)

# FastAPI 웹훅 URL 설정
WEBHOOK_BASE_URL = "http://fastapi:8000/api/v1/webhook"

TODAY_STR = datetime.today().strftime('%Y-%m-%d')
FILE_PATH = "/app/data/"

# 공통 정보 수집 API URL
CISCO_COMMON_COLLECT_API_URL = [
    {
        "market_gubn":"pr",
        "url":"http://fastapi:8000/api/v1/network/collect/cisco/pr"
    },
    {
        "market_gubn":"ts",
        "url":"http://fastapi:8000/api/v1/network/collect/cisco/ts"
    }
]

# batch.py main 함수
def main():
    # CISCO 공통 정보 수집
    for data in CISCO_COMMON_COLLECT_API_URL:
        logger.info(f"[{data['market_gubn']}] START_BATCH_PROCESS!!!!!")

        # API를 사용하여 CISCO 공통정보 수집
        response = requests.get(data["url"])

        if response.status_code == 200:
            try:
                logger.info("✅ API 요청 성공")
                response_json = response.json()

                # 수집 결과 통계 (성공/실패 장비 수)
                meta = get_collection_meta(response_json)
                logger.info(f"[{data['market_gubn']}] 수집 통계: {meta['success_devices']}/{meta['total_devices']} 성공 (status={meta['status']})")

                SaveToCommonInfoJson(response_json, data["market_gubn"])

                # CISCO 멀티캐스트 정보 처리
                cisco_multicast_info = ProcessMulticastInfo(response_json, data["market_gubn"])
                save_json_with_validation(
                    f"{FILE_PATH}{data['market_gubn']}_members_mroute.json",
                    cisco_multicast_info, dict(meta)
                )

                cisco_interface_info = ProcessCiscoInterfaceInfo(response_json, data["market_gubn"])
                save_json_with_validation(
                    f"{FILE_PATH}{data['market_gubn']}_cisco_interface_info.json",
                    cisco_interface_info, dict(meta)
                )

                cisco_arp_info = ProcessCiscoArpInfo(response_json, data["market_gubn"])
                save_json_with_validation(
                    f"{FILE_PATH}{data['market_gubn']}_cisco_arp_info.json",
                    cisco_arp_info, dict(meta)
                )

                # ## 확인필요 결과가 있을경우 슬랙으로 메세지 전송
                check_multicast_info(data["market_gubn"], cisco_multicast_info)

                # DB에 멀티캐스트 상태 저장
                mcast_data_list = cisco_multicast_info.get('data', []) if isinstance(cisco_multicast_info, dict) else cisco_multicast_info
                save_multicast_to_db(data["market_gubn"], mcast_data_list)

            except ValueError as e:
                logger.error("⚠️ JSON 디코딩 실패: %s", e)
                logger.error("응답 내용: %s", response.text)
        else:
            logger.error("❌ API 요청 실패 - 상태코드: %s", response.status_code)
            logger.error("응답 내용: %s", response.text)


def send_slack_message(message_info: Dict):
    """웹훅을 통해 Slack 메시지 전송"""
    logger.info("Slack 메시지 전송 요청: %s", message_info)
    
    try:
        # 웹훅 URL 구성
        webhook_url = f"{WEBHOOK_BASE_URL}/batch/multicast"
        
        # HTTP 요청으로 웹훅 호출
        response = requests.post(
            webhook_url,
            json=message_info,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('result'):
                logger.info("웹훅을 통한 메시지 전송 성공: %s", result.get('message', 'Success'))
            else:
                logger.error("웹훅 응답 오류: %s", result.get('detail', 'Unknown error'))
        else:
            logger.error("웹훅 호출 실패 - 상태코드: %s, 응답: %s", response.status_code, response.text)
            
    except requests.exceptions.RequestException as e:
        logger.error("웹훅 요청 실패: %s", e)
    except Exception as e:
        logger.error("메시지 전송 중 예상치 못한 오류: %s", e)
    
    # 전송 후 잠시 대기 (과도한 요청 방지)
    time.sleep(1)

# 멀티캐스트 정보 확인
# market_gubn: pr, ts
def check_multicast_info(market_gubn, members_mroute):
    path = f"/app/common/members_info.json"
    members_info:Dict = OpenJsonFile(path)

    path = f"/app/common/{market_gubn}_mpr_multicast_info.json"
    mpr_multicast_info:Dict = OpenJsonFile(path)

    logger.info(f"[DEBUG] rws_check_multicast_info")

    ## 데이터 유무 검증
    if members_mroute and members_info and mpr_multicast_info:
    ## 01. member_info <- 시세 멀티캐스트그룹 수신 개수 삽입
    ## 02. member_mroute <- member_info 정보 삽입
        merge_members_mroute = merge_multicast_group_count(members_mroute['data'], mpr_multicast_info)

        response_data:List = create_member_sise_info(merge_members_mroute, members_info, market_gubn)

        # 전체 장비 결과를 webhook으로 전송하여 상태 기반 알람 처리
        send_multicast_alarm_check(market_gubn, response_data)

# openJsonFile = lambda path: openJsonFile

def send_multicast_alarm_check(market_gubn: str, devices: List):
    """전체 장비 결과를 webhook으로 전송하여 상태 기반 알람 처리"""
    logger.info(f"[{market_gubn}] 멀티캐스트 알람 상태 체크 요청: {len(devices)}개 장비")
    try:
        webhook_url = f"{WEBHOOK_BASE_URL}/batch/multicast/check"
        response = requests.post(
            webhook_url,
            json={"market_gubn": market_gubn, "devices": devices},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        if response.status_code == 200:
            result = response.json()
            logger.info(f"[{market_gubn}] 알람 체크 결과: alerts={result.get('alerts_sent', 0)}, "
                        f"recoveries={result.get('recoveries_sent', 0)}, skipped={result.get('skipped', 0)}")
        else:
            logger.error(f"[{market_gubn}] 알람 체크 실패 - 상태코드: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"[{market_gubn}] 알람 체크 요청 실패: {e}")


def merge_multicast_group_count(members_mroute:list, mpr_multicast_info:Dict):
    for idx, device in enumerate(members_mroute):
        # products 키값 유무 확인하는 코드
        if "products" not in device:
            logger.warning("Device %s does not have 'products' key.", device['device_name'])
            break
        products = device["products"]
        total = 0

        for product in products:
            if product in mpr_multicast_info:
                total += mpr_multicast_info[product].get("multicast_group_count", 0)

        members_mroute[idx]["multicast_group_count"] = total

    return members_mroute


def create_member_sise_info(members_mroute:list, members_info:Dict, market_gubn:str):
    logger.info(f"[DEBUG] rws_create_member_sise_info")

    mapping_market = "ts_members" if market_gubn in ("ts", "ts_members") else "pr_members"
    sise_mapping = _fetch_sise_mapping(mapping_market)
    result = []
    member_no = 0
    member_code = ""
    member_name = ""
    device_name = ""
    device_os = ""
    products = ""
    pim_rp = ""
    product_cnt = 0
    mroute_cnt = 0
    oif_cnt = 0
    connected_server_cnt = 0
    min_update = ""
    bfd_nbr = ""
    rpf_nbr = ""
    org_output = ""
    check_result = ""
    type = ""
    icon = ""


    for idx, device in enumerate(members_mroute):
        if device['device_os'] == 'iosxe':
            device_os_key = ''
        elif device['device_os'] == 'nxos':
            device_os_key = 'default'
        
        device_name = device['device_name']
        device_os = device['device_os']
        pim_rp = device['rp_addresses']
        products = device['products']
        product_cnt = device['multicast_group_count']
        connected_server_cnt = device['connected_server_count']
        org_output = device['mroute'][0]['org_output'] ## ip mroute 정보만 표기하기 위함 show ip pim neighbor는 X

        # print(f"[multicast_group] : {device['mroute']['vrf'][device_os_key]['address_family']['ipv4']['multicast_group']}")
        # multicast_group = device['mroute']['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']['multicast_group']
    
        mroute_cnt = device['valid_source_address_count'] if 'valid_source_address_count' in device else 0
        oif_cnt = device['valid_oif_count'] if 'valid_oif_count' in device else 0
        min_update = device['min_uptime'] if 'min_uptime' in device else '확인필요'
        rpf_nbr = device['rpf_nbrs'] if 'rpf_nbrs' in device else '확인필요'

        second_octet = device['mgmt_ip'].split(".")[1] # IP두번째 자리 코드값 추출
        if second_octet in members_info:
            member_no = second_octet
            member_code = members_info[second_octet]['member_code']
            member_name = members_info[second_octet]['member_name']

        # 실제 수신중인 시세상품 및 누락 시세상품 산출 (check_result 판정 전 선행)
        valid_pairs = _extract_valid_sg_pairs(device)
        received_products = _compute_received_products(products, valid_pairs, sise_mapping)
        missing_products = [p for p in (products or []) if p not in received_products]

        ## 멀티캐스트 시세 정상 확인
        ## 우선순위: 누락상품 있음(확인필요) > 연결서버 없음 > 카운트초과 > 카운트 일치(정상확인) > 기타(확인필요)
        if missing_products:
            check_result = '확인필요'
            type = "danger"
            icon = "fas fa-x-square"
        elif connected_server_cnt == 0:
            check_result = '회원사연결서버없음'
            type = "primary"
            icon = "fas fa-check"
        elif mroute_cnt > product_cnt:
            check_result = '정상그룹개수초과'
            type = "warning"
            icon = "fas fa-exclamation-triangle"
        elif product_cnt == mroute_cnt == oif_cnt:
            check_result = '정상확인'
            type = "success"
            icon = "fas fa-check"
        else:
            check_result = '확인필요'
            type = "danger"
            icon = "fas fa-x-square"

        temp = {
            "id" : idx+1,
            "member_no": member_no,
            "member_code": member_code,
            "member_name": member_name,
            "device_name": device_name,
            "device_os": device_os,
            "products": products,
            "received_products": received_products,
            "missing_products": missing_products,
            "pim_rp": pim_rp,
            "product_cnt": product_cnt,
            "mroute_cnt": mroute_cnt,
            "oif_cnt": oif_cnt,
            "min_update": min_update,
            "bfd_nbr": bfd_nbr,
            "rpf_nbr": rpf_nbr,
            "org_output": org_output,
            "check_result": check_result,
            "check_result_badge": { "type": type, "icon": icon }
        }

        result.append(temp)

    logger.info("[DEBUG] CHECK_MUTLICAST_SUCCESS!!")
    return result

def SaveToMulticastJson(data, market_gubn):
    """Legacy: save_json_with_validation으로 대체됨"""
    logger.info("SaveToMulticastJson...")
    file_name = f"{FILE_PATH}{market_gubn}_members_mroute.json"
    with open(file_name, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)

def SaveToCommonInfoJson(data, market_gubn):
    logger.info("SaveToCommonInfoJson...")
    file_name = f"{FILE_PATH}{market_gubn}_cisco_common_info.json"
    logger.info("[DEBUG] 파일명: %s", file_name)
    logger.info("[DEBUG] 데이터 타입: %s", type(data))
    logger.info("[DEBUG] 데이터 길이: %s", len(data) if isinstance(data, (list, dict)) else 'N/A')
    
    try:
        with open(file_name, 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, indent=4, ensure_ascii=False)
        logger.info("[SUCCESS] 파일 저장 완료: %s", file_name)
        
        # 파일 크기 확인
        import os
        file_size = os.path.getsize(file_name)
        logger.info("[DEBUG] 저장된 파일 크기: %s bytes", file_size)
        
    except Exception as e:
        logger.error("[ERROR] 파일 저장 실패: %s", e)
        logger.error("[ERROR] 파일명: %s", file_name)
        logger.error("[ERROR] 데이터 타입: %s", type(data))
        raise e

def SaveToInterfaceJson(data, market_gubn):
    """Legacy: save_json_with_validation으로 대체됨"""
    logger.info("SaveToInterfaceJson...")
    file_name = f"{FILE_PATH}{market_gubn}_cisco_interface_info.json"
    with open(file_name, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)

def SaveToArpJson(data, market_gubn):
    """Legacy: save_json_with_validation으로 대체됨"""
    logger.info("SaveToArpJson...")
    file_name = f"{FILE_PATH}{market_gubn}_cisco_arp_info.json"
    with open(file_name, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)

def OpenJsonFile(path):
    data = {}
    try:
        with open(path, 'rt', encoding='UTF8') as json_file:
            data = json.load(json_file)
    except FileNotFoundError:
        logger.error("파일이 존재하지 않습니다: %s", path)
    except json.JSONDecodeError:
        logger.error("JSON 형식이 잘못되었습니다.: %s", path)

    return data

FASTAPI_API_URL = "http://fastapi:8000/api/v1/network"

def _extract_valid_sg_pairs(device):
    """장비의 raw mroute 파싱 결과에서 Incoming interface가 Null이 아닌 유효 (source, group) 페어 집합 추출."""
    pairs = set()
    device_os = device.get("device_os", "")
    os_key = "default" if device_os == "nxos" else ""
    for cmd in device.get("mroute", []) or []:
        if cmd.get("cmd") not in ("show_ip_mroute_source-tree", "show_ip_mroute"):
            continue
        try:
            mg = cmd["parsed_output"]["vrf"][os_key]["address_family"]["ipv4"]["multicast_group"]
        except (KeyError, TypeError):
            continue
        for group_ip, ginfo in (mg or {}).items():
            # "239.29.30.81/32" → "239.29.30.81"
            g = group_ip.split("/")[0]
            for src, addr_info in (ginfo.get("source_address") or {}).items():
                if "*" in src:
                    continue
                if device_os == "nxos":
                    iil = addr_info.get("incoming_interface_list") or {}
                    if not iil or all(k == "Null" for k in iil.keys()):
                        continue
                s = src.split("/")[0]
                pairs.add((s, g))
    return pairs


def _compute_received_products(device_products, valid_pairs, sise_mapping):
    """장비가 실제 수신중인 시세상품 목록 산출.
    신청 여부와 무관하게 sise_mapping 전체 product를 대상으로,
    (source_ips × group_ips) 조합이 모두 valid_pairs에 포함되면 수신중으로 판정."""
    received = []
    for product, info in (sise_mapping or {}).items():
        sources = info.get("source_ips") or []
        groups = info.get("group_ips") or []
        if not sources or not groups:
            continue
        expected = {(s, g) for s in sources for g in groups}
        if expected.issubset(valid_pairs):
            received.append(product)
    return sorted(received)


def _fetch_sise_mapping(market_type: str = "pr_members"):
    """FastAPI 에서 product → {source_ips, group_ips} 매핑 조회. 실패 시 빈 dict.
    market_type=ts_members 이면 test_ip 기반, 아니면 operation_ip1/ip2 기반."""
    try:
        resp = requests.get(
            f"{FASTAPI_API_URL}/multicast/sise_mapping",
            params={"market_type": market_type},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("data") or {}
    except Exception as e:
        logger.warning(f"sise_mapping 조회 실패: {e}")
    return {}


def save_multicast_to_db(market_gubn, cisco_multicast_info, members_mroute_data=None):
    """멀티캐스트 상태를 DB에 저장 (JSON 저장과 병행)"""
    try:
        # members_info, mpr_multicast_info 로드하여 최종 결과 생성
        # market_gubn이 "pr" 또는 "ts"로 올 수 있으므로 정규화
        if market_gubn in ("pr", "pr_members"):
            market_gubn = "pr_members"
            members_path = "/app/common/members_info.json"
            mpr_path = "/app/common/pr_mpr_multicast_info.json"
        elif market_gubn in ("ts", "ts_members"):
            market_gubn = "ts_members"
            members_path = "/app/common/members_info.json"
            mpr_path = "/app/common/ts_mpr_multicast_info.json"
        else:
            return

        with open(members_path, 'rt', encoding='UTF8') as f:
            members_info = json.load(f)
        with open(mpr_path, 'rt', encoding='UTF8') as f:
            mpr_multicast_info = json.load(f)

        sise_mapping = _fetch_sise_mapping(market_gubn)

        # multicast_group_count 병합
        for device in cisco_multicast_info:
            total = 0
            for product in device.get("products", []):
                if product in mpr_multicast_info:
                    total += mpr_multicast_info[product].get("multicast_group_count", 0)
            device["multicast_group_count"] = total

        # 최종 결과 생성 (create_member_sise_info 로직)
        result_data = []
        for device in cisco_multicast_info:
            if not device.get("device_name"):
                continue
            product_cnt = device.get("multicast_group_count", 0)
            mroute_cnt = device.get("valid_source_address_count", 0)
            oif_cnt = device.get("valid_oif_count", 0)
            connected_server_cnt = device.get("connected_server_count", 0)

            # 회원사 정보 매핑
            member_code = ""
            member_name = ""
            member_no = ""
            alarm = True
            mgmt_ip = device.get("mgmt_ip", "")
            if mgmt_ip:
                second_octet = mgmt_ip.split(".")[1]
                if second_octet in members_info:
                    member_code = members_info[second_octet].get("member_code", "")
                    member_name = members_info[second_octet].get("member_name", "")
                    member_no = second_octet
                    alarm = members_info[second_octet].get("alarm", True)

            # 실제 수신중인 시세상품 산출 (check_result 판정 전 선행)
            applied_products = device.get("products", []) or []
            valid_pairs = _extract_valid_sg_pairs(device)
            received_products = _compute_received_products(applied_products, valid_pairs, sise_mapping)
            missing_products = [p for p in applied_products if p not in received_products]

            # check_result 판정
            # 우선순위: 누락상품 있음(확인필요) > 연결서버 없음 > 카운트초과 > 카운트 일치(정상확인) > 기타(확인필요)
            if missing_products:
                check_result = "확인필요"
            elif connected_server_cnt == 0:
                check_result = "회원사연결서버없음"
            elif mroute_cnt > product_cnt:
                check_result = "정상그룹개수초과"
            elif product_cnt == mroute_cnt == oif_cnt:
                check_result = "정상확인"
            else:
                check_result = "확인필요"

            result_data.append({
                "member_code": member_code,
                "member_name": member_name,
                "member_no": member_no,
                "device_name": device.get("device_name", ""),
                "device_os": device.get("device_os", ""),
                "products": device.get("products", []),
                "received_products": received_products,
                "pim_rp": device.get("rp_addresses", []),
                "product_cnt": product_cnt,
                "mroute_cnt": mroute_cnt,
                "oif_cnt": oif_cnt,
                "connected_server_cnt": connected_server_cnt,
                "min_update": device.get("min_uptime", ""),
                "check_result": check_result,
                "alarm": alarm
            })

        # FastAPI collect API 호출
        resp = requests.post(
            f"{FASTAPI_API_URL}/multicast/collect",
            json={"market_type": market_gubn, "data": result_data},
            timeout=15
        )
        logger.info(f"멀티캐스트 DB 저장: market={market_gubn}, response={resp.json()}")

    except Exception as e:
        logger.error(f"멀티캐스트 DB 저장 실패: {e}")


if __name__ == "__main__":
    main()
    # uvicorn.run(app, host="0.0.0.0", port=5000)
