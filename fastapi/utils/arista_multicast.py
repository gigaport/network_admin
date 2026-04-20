import pytz, json, os, logging
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pathlib import Path
from utils.arista_common import CallAristaAPI
from utils.slack_message_proxy import SendMulticastNotificationToSlack
from utils.database import get_connection
from psycopg2.extras import RealDictCursor

# .env 파일에서 환경 변수 로드
load_dotenv()

# Logger 설정
logger = logging.getLogger(__name__)

NETWORK_ID = os.getenv('NETWORK_ID')
NETWORK_PASSWD = os.getenv('NETWORK_PASSWD')

NOW_DATETIME    = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def main ():
    GetAristaMulticastInfo()

# pr_information_mkd.json 파일에 등록된 스위치 정보를 가져와서
# Arista API를 통해 정보를 가져오는 함수

_SISE_MAPPING_CACHE = {"ts": 0, "data": {}}


def _load_sise_mapping(ttl_seconds: int = 60):
    """sise_products(operation_ip1/ip2) × sise_channels(multicast_group_ip) 매핑 조회 (간단 캐시)."""
    import time as _time
    now = _time.time()
    if _SISE_MAPPING_CACHE["data"] and (now - _SISE_MAPPING_CACHE["ts"] < ttl_seconds):
        return _SISE_MAPPING_CACHE["data"]
    mapping = {}
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.product_name, p.operation_ip1, p.operation_ip2,
                           array_remove(array_agg(DISTINCT c.multicast_group_ip), NULL) AS group_ips
                    FROM sise_products p
                    LEFT JOIN sise_channels c ON c.product_id = p.id
                    GROUP BY p.id, p.product_name, p.operation_ip1, p.operation_ip2
                """)
                for r in cur.fetchall():
                    sources = [ip for ip in [r.get("operation_ip1"), r.get("operation_ip2")] if ip]
                    groups = [g for g in (r.get("group_ips") or []) if g]
                    mapping[r["product_name"]] = {"source_ips": sources, "group_ips": groups}
        _SISE_MAPPING_CACHE.update(ts=now, data=mapping)
    except Exception as e:
        logger.warning(f"sise_mapping 조회 실패: {e}")
    return mapping


def _compute_arista_received_products(valid_pairs: set):
    """전체 sise_mapping 순회, (source × group) 조합이 모두 valid_pairs에 있으면 수신중으로 판정."""
    mapping = _load_sise_mapping()
    received = []
    for product, info in mapping.items():
        sources = info.get("source_ips") or []
        groups = info.get("group_ips") or []
        if not sources or not groups:
            continue
        expected = {(s, g) for s in sources for g in groups}
        if expected.issubset(valid_pairs):
            received.append(product)
    return sorted(received)


def GetAristaMulticastInfo(device_info):
    """    Arista 멀티캐스트 정보를 수집하는 함수
    device_info: Arista 장비 정보 (IP, 사용자명, 비밀번호 등)
    """
    device_name = device_info[0]
    device_ip = device_info[1]['ip']
    device_auth = None
    if 'auth' in device_info[1]:
        device_auth = (device_info[1]['auth']['id'], device_info[1]['auth']['pw'])

    logger.info(f"[{device_name}] 멀티캐스트 정보 수집 시작 (IP: {device_ip})")

    import time
    start_time = time.time()

    data = CallAristaAPI(device_ip, [
        'show ip mroute',
        'show ip pim rp',
        'show interfaces status'
    ], auth=device_auth)

    # mroute raw text 출력 (명령어결과 모달용) - 실패해도 수집은 계속
    mroute_text = ""
    try:
        text_data = CallAristaAPI(device_ip, ['show ip mroute'], auth=device_auth, format='text')
        if text_data and isinstance(text_data, list) and text_data:
            mroute_text = text_data[0].get('output', '') if isinstance(text_data[0], dict) else ''
    except Exception as e:
        logger.warning(f"[{device_name}] mroute text 수집 실패: {e}")

    elapsed_time = time.time() - start_time

    # logger.debug(f" arista_response_json >> {json.dumps(data, indent=4, ensure_ascii=False)}")

    # show ip mroute 명령어의 결과 처리
    # 0.0.0.0인 경우를 제외한 groupSources 갯수를 구하고,
    # 해당 groupSources에 oifList키의 배열에 Vlan1100의 갯수도 구하는 로직
    valid_group_sources_count = 0
    oif_count = 0
    creation_time = None
    rpf_neighbor = None
    connected_server_cnt = 0

    if data is None:
        logger.error(f"[{device_name}] NO DATA RECEIVED FROM ARISTA API (IP: {device_ip}, 소요시간: {elapsed_time:.2f}초)")
        return None

    logger.info(f"[{device_name}] 멀티캐스트 정보 수집 완료 (소요시간: {elapsed_time:.2f}초)")
    
    logger.debug(f" ARISTA_DATA >> {data}")

    valid_sg_pairs = set()
    for idx, value in enumerate(data):
        # show ip mroute 명령어의 결과 처리
        if idx == 0:
            groups = value.get('groups', {})
            # 가져온 groups 정보를 순회하면서
            for group, group_info in groups.items():
                logger.debug(f" ARISTA_GROUP >> {group}")
                group_sources = group_info.get('groupSources', {})
                logger.debug(f" ARISTA_GROUP_SOURCES >> {group_sources}")
                # groupSources가 0.0.0.0인 경우를 제외한 groupSources 갯수를 구하고,
                # 해당 groupSources에 oifList키의 배열에 Vlan1100이 있는지 확인
                for src_key, src_value in group_sources.items():
                    logger.debug(f" ARISTA_GROUP_SOURCE >> {src_key}")
                    if src_key != "0.0.0.0":
                        logger.debug(f" ARISTA_VALID_GROUP_SOURCE >> {src_key}")
                        valid_group_sources_count += 1
                        valid_sg_pairs.add((src_key, group))
                        if any(x == 'Vlan1100' or x.startswith('Ethernet') for x in src_value.get('oifList', [])):
                            logger.debug(f" ARISTA_VLAN1100_IN_OIFLIST >> {src_key}")
                            oif_count += 1
                        # 첫번째 groupSources의 creationTime을 별도 저장
                        # creation_time을 kst datetime으로 변환하여 출력
                        creation_time = src_value.get('creationTime', None)
                        if creation_time:
                            # creationTime을 KST로 변환
                            utc_time = datetime.fromtimestamp(creation_time)
                            kst_timezone = pytz.timezone('Asia/Seoul')
                            creation_time = utc_time.replace(tzinfo=pytz.utc).astimezone(kst_timezone)
                            creation_time = creation_time.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            creation_time = "N/A"
                        logger.debug(f" ARISTA_CREATION_TIME >> {creation_time}")

                        # 첫번째 rfpNeighbor의 정보를 가져옴
                        # rfpNeighbor는 groupSources의 첫번째 key에 해당하는 값에서 가져옴
                        # rfpNeighbor가 존재하는 경우에만 가져옴 value.get('rpf', {}).get('rpfNeighbor', {})
                        if rpf_neighbor is not None:
                            logger.debug(f" ARISTA_RPF_NEIGHBOR >> {rpf_neighbor}")
                        else:
                            rpf_neighbor = src_value.get('rpf', {}).get('rpfNeighbor', {})
                            if rpf_neighbor:
                                logger.debug(f" ARISTA_RPF_NEIGHBOR >> {rpf_neighbor}")
                            else:
                                logger.debug(" ARISTA_RPF_NEIGHBOR IS EMPTY")
            # 디버깅용 출력
            logger.debug(f" ARISTA_VALID_GROUP_SOURCES_COUNT >> {valid_group_sources_count}")
            logger.debug(f" ARISTA_OIF_COUNT >> {oif_count}")
            logger.debug(f" ARISTA_CREATION_TIME >> {creation_time}")

        # show ip pim rp 명령어의 결과 처리
        elif idx == 1:
            rendezvous_point = value.get('sparseMode', {}).get('crpSet', {}).get('224.0.0.0/4', {}).get('crp', {})
            logger.debug(f" ARISTA_RENDEZVOUS_POINT >> {rendezvous_point}")
            # rendezvous_point의 키 네임을 가져와서 그대로 저장
            rp_address = list(rendezvous_point.keys())[0] if rendezvous_point else "N/A"
            logger.debug(f" ARISTA_RP_ADDRESS >> {rp_address}")

        # show interface status 명령어의 결과 처리
        elif idx == 2:
            # 현재 장비의 인터페이스 상태를 가져옴 (Ethernet1부터 12번포트까지)
            interface_status = value.get('interfaceStatuses', {})
            logger.debug(f" ARISTA_INTERFACE_STATUS >> {interface_status}")
            for intf, status in interface_status.items():
                logger.debug(f" ARISTA_INTERFACE_STATUS >> {intf}: {status}")
                link_status = status.get('lineProtocolStatus', 'N/A')
                # link_status가 'up'인 경우에 카운트를 올림
                if link_status == 'up':
                    logger.debug(f" ARISTA_INTERFACE_UP >> {intf} is UP")
                    connected_server_cnt += 1
                else:
                    logger.debug(f" ARISTA_INTERFACE_DOWN >> {intf} is DOWN")

            # 인터페이스 상태에서 Vlan1100의 상태를 확인
            vlan1100_status = interface_status.get('Vlan1100', {})
            if vlan1100_status:
                logger.debug(f" ARISTA_VLAN1100_STATUS >> {vlan1100_status}")
            else:
                logger.debug(" ARISTA_VLAN1100_STATUS IS EMPTY")

    response_json = {
        'valid_group_sources_count': valid_group_sources_count,
        'oif_count': oif_count,
        'creation_time': creation_time,
        'rp_address': rp_address,
        'rpf_neighbor': rpf_neighbor,
        'connected_server_cnt': connected_server_cnt,
        'valid_sg_pairs': valid_sg_pairs,
        'mroute_text': mroute_text
    }

    result = AddMemberInfoToAristaMulticastInfo(device_info, response_json)

    # mroute 원본 출력은 per-device 파일로 저장 (mroute_output 엔드포인트용)
    if mroute_text and result:
        try:
            data_dir = Path('/app/data/arista_mroute')
            data_dir.mkdir(parents=True, exist_ok=True)
            safe_name = result.get('device_name', device_name).replace('/', '_')
            with open(data_dir / f"{safe_name}.txt", 'w', encoding='utf-8') as f:
                f.write(mroute_text)
        except Exception as e:
            logger.warning(f"[{device_name}] mroute text 저장 실패: {e}")

    return result

def AddMemberInfoToAristaMulticastInfo(device_info, multicast_info):
    # information_info.json 파일에 등록된 멤버 정보를 가져와서
    # 멀티캐스트 정보에 추가하는 함수
    logger.debug(f" AddMemberInfoToAristaMulticastInfo >> {device_info}")

    # information_info.json 파일 경로
    information_info_path = Path('/app/common/information_info.json')
    if not information_info_path.exists():
        logger.error(f" INFORMATION_INFO_PATH DOES NOT EXIST: {information_info_path}")
        return None
    with open(information_info_path, 'r', encoding='UTF-8') as file:
        information_info = json.load(file)
    logger.debug(f" INFORMATION_INFO >> {information_info}")

    # pr_mpr_multicast_info.json 파일 경로
    pr_mpr_multicast_info_path = Path('/app/common/pr_mpr_multicast_info.json')
    if not pr_mpr_multicast_info_path.exists():
        logger.error(f" PR_MPR_MULTICAST_INFO_PATH DOES NOT EXIST: {pr_mpr_multicast_info_path}")
        return None
    with open(pr_mpr_multicast_info_path, 'r', encoding='UTF-8') as file:
        pr_mpr_multicast_info = json.load(file)
    logger.debug(f" PR_MPR_MULTICAST_INFO >> {pr_mpr_multicast_info}")

    # device_info에서 hostname을 가져와서 information_info에 swith_hostanme과 동일한 정보를 찾아서 멤버 정보를 가져옴
    device_hostname = device_info[0]
    logger.debug(f" DEVICE_HOSTNAME >> {device_hostname}")

    member_info = None
    member_no = None
    for member in information_info.items():
        if 'switch_hostname' in member[1] and device_hostname in member[1]['switch_hostname']:
            member_info = member[1]
            member_no = member[0]
            break
    if not member_info:
        logger.error(f" NO MEMBER INFO FOUND: {device_hostname}")
        return None
    logger.debug(f" MEMBER_NO, MEMBER_INFO >> {member_no}, {member_info}")

    alarm_icon = None
    alarm = member_info.get('alarm', False)
    if alarm:
        alarm_icon = "fa-bell"
    else:
        alarm_icon = "fa-bell-slash"

    # 장비별 신청 상품은 pr_information_mkd.json 의 custom.join_products 를 신청_시세상품(products)으로 사용
    # (information_info.json 의 member_products 는 회원사 레벨 정보로만 참고)
    product_cnt = 0
    device_info[1]['custom'] = device_info[1].get('custom', {})
    member_name = member_info.get('member_name', "N/A")
    logger.debug(f'!!!!!!!!! {member_name}')
    join_products = device_info[1]['custom'].get('join_products', [])
    products = join_products or member_info.get('member_products', [])
    rp_address = multicast_info.get('rp_address', "N/A")
    mroute_cnt = multicast_info.get('valid_group_sources_count', 0)
    oif_cnt = multicast_info.get('oif_count', 0)
    rpf_nbr = multicast_info.get('rpf_neighbor', "N/A")

    logger.debug(f" JOIN_PRODUCTS >> {join_products}")

    for product in join_products:
        for key, pr_mpr_info in pr_mpr_multicast_info.items():
            # logger.debug(f" pr_mpr_info >> {pr_mpr_info}")
            # pr_mpr_info의 key값과 product가 일치하는지 확인
            if key == product:
                logger.debug(f" PR_MPR_INFO >> {pr_mpr_info}")
                product_cnt += pr_mpr_info.get('multicast_group_count', 0)
                logger.debug(f" PRODUCT_CNT >> {product_cnt}")

    # 수신_시세상품 산출: sise_products(operation_ip1/ip2) × sise_channels(multicast_group_ip) AND 매칭
    received_products = _compute_arista_received_products(multicast_info.get('valid_sg_pairs') or set())
    applied_products = products or []
    missing_products = [p for p in applied_products if p not in received_products]

    ## 멀티캐스트 시세 정상 확인
    ## 우선순위: 연결서버 없음(=mroute 없는게 정상) > 누락상품 > 카운트초과 > 카운트 일치(정상확인)
    mroute_c = multicast_info.get('valid_group_sources_count', 0)
    oif_c = multicast_info.get('oif_count', 0)
    if multicast_info.get('connected_server_cnt', 0) == 0:
        check_result = '회원사연결서버없음'
        type = "primary"
        icon = "fas fa-check"
    elif missing_products:
        check_result = '확인필요'
        type = "danger"
        icon = "fas fa-x-square"
    elif mroute_c > product_cnt:
        check_result = '정상그룹개수초과'
        type = "warning"
        icon = "fas fa-exclamation-triangle"
    elif product_cnt == mroute_c == oif_c:
        check_result = '정상확인'
        type = "success"
        icon = "fas fa-check"
    else:
        check_result = '확인필요'
        type = "danger"
        icon = "fas fa-x-square"

    temp = {
        "updated_time": NOW_DATETIME,
        "member_no": member_no,
        "member_code": member_info.get('member_code', "N/A"),
        "member_name": member_info.get('member_name', "N/A"),
        "device_name": device_hostname,
        "device_os": device_info[1]['os'],
        "products": products,
        "received_products": received_products,
        "pim_rp": multicast_info.get('rp_address', "N/A"),
        "product_cnt": product_cnt,
        "mroute_cnt": mroute_cnt,
        "oif_cnt": multicast_info.get('oif_count', 0),
        "min_update": multicast_info.get('creation_time', "N/A"),
        "bfd_nbr": "업데이트예정",  # BFD neighbor count is not available in the current data
        "rpf_nbr": multicast_info.get('rpf_neighbor', "N/A"),
        "org_output": multicast_info.get('org_output', "N/A"),
        "connected_server_cnt": multicast_info.get('connected_server_cnt', 0),
        "alarm":member_info.get('alarm', False),
        "alarm_icon": alarm_icon,
        "member_note": member_info.get('member_note', "N/A"),
        "check_result": check_result,
        "check_result_badge": { "type": type, "icon": icon }
    }

    logger.debug(f" TEMP >> {temp}")
    return temp

if __name__ == "__main__":
    main()