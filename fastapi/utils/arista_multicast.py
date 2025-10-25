import pytz, json, os, logging
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pathlib import Path
from utils.arista_common import CallAristaAPI
from utils.slack_message_proxy import SendMulticastNotificationToSlack

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

def GetAristaMulticastInfo(device_info):
    """    Arista 멀티캐스트 정보를 수집하는 함수
    device_info: Arista 장비 정보 (IP, 사용자명, 비밀번호 등)
    """
    logger.debug(f"GetAristaMulticastInfo >> {device_info}")

    data = CallAristaAPI(device_info[1]['ip'], [
        'show ip mroute',
        'show ip pim rp',
        'show interfaces status'
    ])

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
        logger.error(" NO DATA RECEIVED FROM ARISTA API")
        return None
    
    logger.debug(f" ARISTA_DATA >> {data}")

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
        'connected_server_cnt': connected_server_cnt
    }

    result = AddMemberInfoToAristaMulticastInfo(device_info, response_json)

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

    # device_info에서 custom안에 join_products 정보를 가져와서
    # pr_mpr_multicast_info에서 join_products와 동일한 정보를 찾아서 multicast_group_count 개수를 가져옴
    product_cnt = 0
    device_info[1]['custom'] = device_info[1].get('custom', {})
    member_name = member_info.get('member_name', "N/A")
    logger.debug(f'!!!!!!!!! {member_name}')
    products = member_info.get('member_products', [])
    join_products = device_info[1]['custom'].get('join_products', [])
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

    ## 멀티캐스트 시세 정상 확인
    ## 시세상품 멀티캐스트 그룹 카운트 == 장비 mroute 카운트 == vlan 1100 OIF 카운트 비교
    if product_cnt == multicast_info.get('valid_group_sources_count', 0) == multicast_info.get('oif_count', 0):
        check_result = '정상확인'
        type = "success"
        icon = "fas fa-check"
    elif multicast_info.get('connected_server_cnt', 0) == 0:
        check_result = '회원사연결서버없음'
        type = "primary"
        icon = "fas fa-check"
    else:
        check_result = '확인필요'
        type = "danger"
        icon = "fas fa-x-square"
        # 멀티캐스트 확인필요 메세지를 슬랙으로 전송
        message_title= f":alert: *(가동)시세수신 이상* :alert:",
        attachments=[
            {
                "color": "danger",
                "title": f"대상회원사 : `{member_name}`",
                "text": (
                    f"*- 장비이름: {device_hostname}*\n"
                    f"- 가입상품: `{products}`\n"
                    f"- PIM_RP: {rp_address}\n"
                    f"- 기준 mroute: {product_cnt}\n"
                    f"- 현재 mroute: {mroute_cnt}\n"
                    f"- 현재 oif_cnt: {oif_cnt}\n"
                    f"- RPF_NBR: `{rpf_nbr}`\n"
                ),
                "mrkdwn_in": ["text", "title"]
            }
        ]

        logger.debug(f'[DEBUG] ATTACHMENTS: {attachments}')

        # SendMulticastNotificationToSlack(message_title, attachments)

    temp = {
        "updated_time": NOW_DATETIME,
        "member_no": member_no,
        "member_code": member_info.get('member_code', "N/A"),
        "member_name": member_info.get('member_name', "N/A"),
        "device_name": device_hostname,
        "device_os": device_info[1]['os'],
        "products": member_info.get('member_products', []),
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