import json, logging, re, time, html, sys, asyncio, uvicorn
from repynery import Repynery
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pprint import pprint
from urllib.parse import quote
from typing import List, Dict, Tuple, Union, Optional
## Netmiko 라이브러리
from netmiko import ConnectHandler
## 장비관리 라이브러리
from genie.testbed import load
## 장비정보 파싱 라이브러리리
## IOSXE
from genie.libs.parser.iosxe.show_interface import ShowInterfacesSwitchport
from genie.libs.parser.iosxe.show_interface import ShowInterfacesStatus
from genie.libs.parser.iosxe.show_mcast import ShowIpMroute
from genie.libs.parser.iosxe.show_pim import ShowPimNeighbor
## NXOS
from genie.libs.parser.nxos.show_interface import ShowInterfaceSwitchport
from genie.libs.parser.nxos.show_interface import ShowInterfaceStatus
from genie.libs.parser.nxos.show_mcast import ShowIpMrouteVrfAll
from genie.libs.parser.nxos.show_pim import ShowIpPimRp


app = FastAPI(root_path="/api")

# SLACK
slack_token = "***REMOVED***8455397334246-8462358192034-3F7aPVe7I0Jg686HyXzBtDU0"
client = WebClient(token=slack_token)

# TIME
KST = timezone(timedelta(hours=9))
TODAY_TIME = datetime.today().strftime('%Y-%m-%d %H:%M')

# 스레드풀 생성
executor = ThreadPoolExecutor(max_workers=60)

TODAY_STR = datetime.today().strftime('%Y-%m-%d')
TS_DEVICES = load('../ts_member_mpr.yaml')
PR_DEVICES = load('../pr_member_mpr.yaml')
FILE_PATH = "./data/"

# pyATS 로거 설정 (로그 출력 비활성화)
logging.getLogger('pyats').setLevel(logging.CRITICAL)
logging.getLogger('genie').setLevel(logging.CRITICAL)
logging.getLogger('unicon').setLevel(logging.CRITICAL)

NXOS_CMDS = [
    {
        "key": "show_ip_mroute_source-tree",
        "value": "show ip mroute source-tree"
    },
    {
        "key": "show_ip_pim_rp",
        "value": "show ip pim rp"
    },
    {
        "key": "show_interface_status",
        "value": "show interface status"
    }
]

IOSXE_CMDS = [
    {
        "key": "show_ip_mroute",
        "value": "show ip mroute"
    },
    {
        "key": "show_interface_status",
        "value": "show interface status"
    }
]

KNOWN_MULTICAST_IP = [
    "224.0.0.1/32", 
    "224.0.0.2/32", 
    "224.0.0.5/32", 
    "224.0.0.6/32", 
    "224.0.0.9/32", 
    "224.0.0.13/32", 
    "224.0.0.18/32", 
    "224.0.0.22/32", 
    "224.0.1.1/32", 
    "224.0.1.2/32", 
    "224.0.1.39/32", 
    "224.0.1.40/32", 
    "224.0.0.32/32", 
    "224.0.0.41/32",
    "239.255.255.250/32"
]

SYSLOG_NORMAL_KEYWORD = [
    "Authentication",
    "PAM",
    "PWD",
    "COMMAND",
    "pam",
    "auth",
    "User",
    "nwcfg",
    "Login",
    "Unexpected message type has arrived. Terminating the connection from"
]

SYSLOG_ENDPOINT_MNEMONIC = [
    "IF_UP",
    "IF_DOWN",
    "IF_DUPLEX"
]

# === [ 사용자 설정 영역 ] ===
feedname = "COR_ASN"
tag_values = ["ALL_SECUTIES","KB","KR_HQ","KR_KT","MR", "KW", "SH","NH","SS","KRX","STOCK-NET"]  # 여러 태그 지정 (리스트로 작성)
bind_value = 121

# 서버 접속 및 로그인
print("Log in")
r1 = Repynery(False, "172.24.32.47", 8080, "lampad", "Sprtmxm1@3")
if not r1.login():
    print("Failed to login. Check connection information")
    exit(-1)
else:
    print(f'Logged in. Token: {r1.token}, Tag: {r1.tag}')



@app.get("/")
async def hello():
    return("message :hello from FastAPI + Gunicorn")


# ## netmiko connection info
# connection_info = {
#     "device_type": "cisco_xe",
#     "host": "50.5.1.51",
#     "username": "125003",
#     "password": "Swr278577@",
#     "port": 22
# }

@app.get("/member_mkd/status")
async def member_mkd():
    return {"status":"ok"}

@app.post("/logs")
async def receive_syslog(request: Request):
    data = await request.json()
    print(f"Received log: {data}")
    channel = "#network-alert-syslog"
    
    if any(keyword in data["message"] for keyword in SYSLOG_NORMAL_KEYWORD) :
        channel = "#network-alert-normal"
    
    if any(keyword in data["mnemonic"] for keyword in SYSLOG_ENDPOINT_MNEMONIC) :
        channel = "#network-alert-endpoint"

    send_message_to_slack(channel, data)

    return {"status": "ok"}

@app.post("/webhook/slack")
async def send_webhook_slack(request: Request):
    received_data = await request.json()
    market = received_data["market"]
    time_range = ""
    emoji = ""
    if market == "프리":
        market = "프리장"
        time_range = "07:58~08:01"
        emoji = ":sun:"
    elif market == "정규":
        market = "정규장"
        time_range = "08:58~09:01"
        emoji = ":gogo_dancer:"
    elif market == "에프터":
        market = "에프터장"
        time_range = "15:38~15:41"
        emoji = ":sunset:"

    # data = received_data["data"]
    # print(f"Received data: {data}")
    # channel = "network-test"
    channel = "network-monitor"

    try:
        response = client.chat_postMessage(
            channel=channel,  # 예: "#general" 또는 "C12345678"
            # text= f"*[{market}] 회원사 장시간 MAX 트래픽*",
            blocks=[
                {
                    "type": "section",
                    "text":{
                        "type": "mrkdwn",
                        "text": f"*{emoji} [{market}-{time_range}] MAX 트래픽*"
                    }
                }
            ],
            attachments=[
                {
                    "color": "#439FE0",
                    # "title": f"회원사 장시간 MAX 트래픽",
                    "text": (
                        f"`전체증권사` : {received_data['ALL_SECUTIES']['max_bps_unit']} ({received_data['ALL_SECUTIES']['diff_emoji']}{received_data['ALL_SECUTIES']['diff_unit']})\n"
                        f"`KB [100M]` : {received_data['KB']['max_bps_unit']} ({received_data['KB']['diff_emoji']}{received_data['KB']['diff_unit']})\n"
                        f"`KR_HQ [100M]` : {received_data['KR_HQ']['max_bps_unit']} ({received_data['KR_HQ']['diff_emoji']}{received_data['KR_HQ']['diff_unit']})\n"
                        f"`KR_KT [100M]` : {received_data['KR_KT']['max_bps_unit']} ({received_data['KR_KT']['diff_emoji']}{received_data['KR_KT']['diff_unit']})\n"
                        f"`MR [200M]` : {received_data['MR']['max_bps_unit']} ({received_data['MR']['diff_emoji']}{received_data['MR']['diff_unit']})\n"
                        f"`KW [50M]` : {received_data['KW']['max_bps_unit']} ({received_data['KW']['diff_emoji']}{received_data['KW']['diff_unit']})\n"
                        f"`SH [50M]` : {received_data['SH']['max_bps_unit']} ({received_data['SH']['diff_emoji']}{received_data['SH']['diff_unit']})\n"
                        f"`NH [50M]` : {received_data['NH']['max_bps_unit']} ({received_data['NH']['diff_emoji']}{received_data['NH']['diff_unit']})\n"
                        f"`SS [50M]` : {received_data['SS']['max_bps_unit']} ({received_data['SS']['diff_emoji']}{received_data['SS']['diff_unit']})\n"
                        f"`KRX [2G]` : {received_data['KRX']['max_bps_unit']} ({received_data['KRX']['diff_emoji']}{received_data['KRX']['diff_unit']})\n"
                        f"`STOCK-NET [45M]` : {received_data['STOCK-NET']['max_bps_unit']} ({received_data['STOCK-NET']['diff_emoji']}{received_data['STOCK-NET']['diff_unit']})\n"
                    ),
                    "mrkdwn_in": ["text", "title"]
                }
            ]
        )
        print("메시지 전송 성공:", response["ts"])

    except SlackApiError as e:
        print("메시지 전송 실패:", e.response["error"])


@app.post("/send_message_to_slack")
def send_message_to_slack(channel:str, message_info: Dict):
    # if channel == "#network-alert-syslog":
    #     print(f"IOSDATE : {message_info['kst_time_formatted']}")
    #     # dt = datetime.fromisoformat(message_info['timestamp'])
    #     dt_kst = dt.astimezone(KST)
    #     formatted_date = dt_kst.strftime("%Y-%m-%d %H:%M:%S")
    # else:
    #     formatted_date = message_info['kst_time_formatted']


    try:
        response = client.chat_postMessage(
            channel=channel,  # 예: "#general" 또는 "C12345678"
            text= f":warning: {message_info['severity'].upper()}>>{message_info['device']} :warning:",
            attachments=[
                {
                    "color": "warning",
                    # "title": f"{message_info['device']} // LEVEL:{message_info['severity']}",
                    "text": (
                        f"*-장비이름: {message_info['device']}*\n"
                        f"-장비IP: `{message_info['host_ip']}`\n"
                        f"-발생일시: `{message_info['timestamp_trans']}`\n"
                        f"-level: `{message_info['severity'].upper()}`\n"
                        f"-facility: {message_info['facility']}\n"
                        f"-mnemonic: {message_info['mnemonic']}\n"
                        f"-type: {message_info['type'].upper()}\n"
                        f"-message: ```{message_info['message']}```\n"
                    ),
                    "mrkdwn_in": ["text", "title"]
                }
            ]
            # blocks=[
            #     {
            #         "type": "section",
            #         "text": {
            #             "type": "mrkdwn",
            #             "text": f":alert:*{message_info['member_name']} 멀티캐스트수신 이상*:alert:"
            #         }
            #     },
            #     {
            #         "type": "context",
            #         "elements": [
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"장비이름: {message_info['device_name']}"
            #             },
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"가입상품: {message_info['products']}"
            #             },
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"PIM_RP: {message_info['pim_rp']}"
            #             },
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"기준 mroute: {message_info['product_cnt']}"
            #             },
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"헌재 mroute: {message_info['mroute_cnt']}"
            #             },
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"현재 oif_cnt: {message_info['oif_cnt']}"
            #             },
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"RPF_NBR: {message_info['rpf_nbr']}"
            #             },
            #         ]
            #     },
            #     {
            #         "type":"divider"
            #     }
            # ]
        )
        print("메시지 전송 성공:", response["ts"])

    except SlackApiError as e:
        print("메시지 전송 실패:", e.response["error"])


@app.get("/collect/{target}")
async def collect_data(target: str):
    if target == "pr":
        targets = load('../pr_member_mpr.yaml')
    elif target == "ts":
        targets = load('../ts_member_mpr.yaml')
    else:
        return JSONResponse(content={"error": "알 수 없는 대상"}, status_code=404)

    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, execute_collection, device_info, device_name)
        for device_name, device_info in targets.devices.items()
    ]

    results = await asyncio.gather(*tasks)
    return results

def execute_collection(device_info, device_name):

    ## 명령어01, 명렁어02 결과를 LIST 타입으로 수신신
    cmd_response_list:List = connect_device_and_execute_cmd(device_info)

    ## 멀티캐스트 관련 데이터 정제 시작 ##
    print(f"device_info : {device_info}")
    processed_data = process_multicast_info(cmd_response_list, device_info, device_name)
    # print(f"[06.PROCESSED_DATA] ==> {json.dumps(processed_data, indent=4, ensure_ascii=False)}")

    data = {"data": processed_data}

    return data


def process_multicast_info(cmd_response_list, device_info, device_name):
    print("[05.processing...]")

    ## cisco pyats return key값이 os마다 다름 별도 처리 필요
    if device_info.os == 'iosxe':
        device_os_key = ''
    elif device_info.os == 'nxos':
        device_os_key = 'default'

    valid_source_address_count = 0
    valid_oif_count = 0
    connected_server_count = 0
    min_uptime = '확인필요'
    rpf_nbrs = '확인필요'
    rp_addresses = []

    result = {}
    for data in cmd_response_list:
        if data['cmd'] == 'show_ip_mroute_source-tree' or data['cmd'] == 'show_ip_mroute':
            print("[06.PROCESSING SHOW IP MROUTE]\n\n")

            ## show ip mroute에 대한 테이블이 있을경우만 진행
            if data['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']:
                multicast_group = data['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']['multicast_group']

                ## 유요한 (S,G) 및 VLAN 1100 개수를 계산하여 기존 데이터에 삽입
                valid_source_address_count = count_valid_source_address(multicast_group)

                #####################==>> RP Address os별 삽입 기준 정리 해야됨!!!!!
                valid_multicast_data = count_valid_oif_and_get_min_uptime(multicast_group, device_info.os)

                # print(f"[valid count] : {valid_source_address_count}\n")
                if not valid_multicast_data:
                    print('비어있음')
                else:
                    # print(f"[vaild_multicast_data] => {valid_multicast_data}")
                    valid_source_address_count = valid_source_address_count
                    valid_oif_count = valid_multicast_data['valid_oif_count']
                    min_uptime = valid_multicast_data['min_uptime']
                    rpf_nbrs = valid_multicast_data['rpf_nbrs']
                    
                    if device_info.os == 'iosxe':
                        rp_addresses = valid_multicast_data['rp_addresses']
            else:
                print("[!!!데이터 없음!!!]")

        elif data['cmd'] == 'show_ip_pim_rp':
            print("[show ip pim rp logic]\n")
            rp_addresses.append(list(data['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']['rp']['static_rp'].keys())[0])

        elif data['cmd'] == 'show_interface_status':
            print("[show interface status]\n")
            print(f"{data['parsed_output']}")

            for interface, details in data['parsed_output']['interfaces'].items():
                # access_vlan 값과 인터페이스 상태 확인
                access_vlan = details.get('vlan')
                oper_status = details.get('status')

                if access_vlan == '1100' and oper_status == 'connected':
                    connected_server_count += 1
                    print(f"Matched interfaces: {interface} Deivice: {device_name}\n\n")
            print(f"[VLAN1100 UP interfaces total COUNT] : {device_name}{device_info.os} ==> {connected_server_count}")

    print(f"device_info_join_products >> {device_info.custom.get('join_products', [])}")

    result = {
        "device_name": device_name,
        "updated_time":TODAY_TIME,
        "device_os": device_info.os,
        "products": device_info.custom.get('join_products', []),
        "mgmt_ip": str(device_info.connections.default.ip),
        "valid_source_address_count": valid_source_address_count,
        "valid_oif_count": valid_oif_count,
        "min_uptime": min_uptime,
        "rp_addresses": rp_addresses,
        "rpf_nbrs": rpf_nbrs,
        "connected_server_count": connected_server_count,
        "mroute": cmd_response_list
    }

    return result


def connect_device_and_execute_cmd(device_info):
    print(f"[01.network device {device_info.name} connecting...]")

    """
    pyATS는 connect메서드 실행 시 자동으로 terminal timeout 설정을 무한(0)으로 설정한다.
    이를 방지하기위해 init_exec_commands, init_config_commands 기본 명령을 제거."
    """
    device_info.connect(
        init_exec_commands=['terminal length 0', 'terminal width 511'],
        init_config_commands=[],
        log_stdout=False,
        prompt_recovery=False,
        learn_hostname=False,
        logfile=None
    ) 

    result = []

    try:
        if device_info.os == "nxos":
            for cmd in NXOS_CMDS:
                cmd_response:str = device_info.execute(cmd['value'])
                # print(f"\n\n[02.CMD_RESPONSE] ==> \n {cmd_response}\n")

                ## 할당한 명령어 순차적 실행
                if cmd['key'] == 'show_ip_mroute_source-tree':
                    parser = ShowIpMrouteVrfAll(device=None)
                elif cmd['key'] == 'show_ip_pim_rp':
                    parser = ShowIpPimRp(device=None)
                elif cmd['key'] == 'show_interface_status':
                    parser = ShowInterfaceStatus(device=None)
                
                parsed_output, org_output = parse_pyats_to_json(parser, cmd_response)
                
                temp = {
                    "cmd": cmd['key'],
                    "parsed_output": parsed_output,
                    "org_output": org_output
                }
                result.append(temp)

        elif device_info.os == "iosxe":
            for cmd in IOSXE_CMDS:
                cmd_response:str = device_info.execute(cmd['value'])

                ## 할당한 명령어 순차적 실행
                if cmd['key'] == 'show_ip_mroute':
                    parser = ShowIpMroute(device=None)
                elif cmd['key'] == 'show_interface_status':
                    parser = ShowInterfacesStatus(device=None)

                parsed_output, org_output = parse_pyats_to_json(parser, cmd_response)

                temp = {
                    "cmd": cmd['key'],
                    "parsed_output": parsed_output,
                    "org_output": org_output
                }
                result.append(temp)

        # print(f"[04.RESULT] ==> \n {result}\n")
        
        return result
        
    except Exception as e:
        print(f"error: {e}")

    finally:
        # 연결된 경우만 disconnect 실행
        if device_info.connected:
            device_info.disconnect()
            print("network device disconnected...")


def parse_pyats_to_json(parser, cmd_response):

    parsed_output = parser.parse(output=cmd_response)
    # print(f"[02-1.PARSED_OUTPUT] ==> {json.dumps(parsed_output, indent=4, ensure_ascii=False)}\n")
        
    ## json 포맷으로 파싱된 데이터와 명령어로 실행한 아웃풋 값을 리턴
    ## html에 CLI값을 출력하기위해 \r, \n 포맷을 변경
    org_output = cmd_response.replace('\n', '\\n').replace('\r', '\\r')
    org_output = html.escape(org_output)

    return parsed_output, org_output


def count_valid_source_address(data):
    count = 0
    for multicast_ip, info in data.items():
        print(f"multicast_group_ip : {multicast_ip}")
        if multicast_ip not in KNOWN_MULTICAST_IP :
            source = info.get('source_address',{})
            for key in source:
                if '*' not in key:
                    count += 1
    
    return count

def count_valid_oif_and_get_min_uptime(data, device_os:str):
    print(f'device_os {device_os}')
    valid_oif_count = 0
    uptimes = []
    rp_addresses = []
    rpf_nbrs = []
    vaild_check = False

    for ip, ip_info in data.items():
        ## 멀티캐스트그룹 239.29.30.x 대역 필터링
        if ip.startswith("239.29.30."):
            vaild_check = True
            source_addresses = ip_info.get("source_address", {})

            for addr, addr_info in source_addresses.items():
                if addr == "*": ## (*, G)인 경우만 rp KEY가 존재하고, rpf_neighbor도 이 기준으로로 수집
                    # 특정 멀티캐스트그룹IP : rp_address 값 모두 가져오기
                    if device_os == 'iosxe':
                        if addr_info['rp'] not in rp_addresses:
                            rp_addresses.append(addr_info['rp'])
                    
                    # 특정 멀티캐스트그룹IP : rpf_neighbor 값 모두 가져오기
                    if device_os == 'iosxe':
                        if addr_info['rpf_nbr'] not in rpf_nbrs:
                            rpf_nbrs.append(addr_info['rpf_nbr'])
                    continue

                if device_os == 'nxos':
                    ## nxos ex
                    # "239.29.30.62/32": {
                    #     "source_address": {
                    #         "177.21.180.101/32": {
                    #             "uptime": "2w4d",
                    #             "flags": "ip mrib pim",
                    #             "incoming_interface_list": {
                    #                 "Ethernet1/23": {
                    #                     "rpf_nbr": "99.3.3.9"
                    #                 }
                    #             },
                    #             "oil_count": 1,
                    #             "outgoing_interface_list": {
                    #                 "Vlan1100": {
                    #                     "oil_uptime": "2w4d",
                    #                     "oil_flags": "mrib"
                    #                 }
                    #             }
                    #         }
                    #     }
                    # }
                    first_key = next(iter(addr_info['incoming_interface_list']))
                    first_value = addr_info['incoming_interface_list'][first_key]
                    print(f"rpf {first_key}, {first_value}")
                    if first_value['rpf_nbr'] not in rpf_nbrs:
                        rpf_nbrs.append(first_value['rpf_nbr'])
                
                outgoing_interface = addr_info.get("outgoing_interface_list", {})
                ## OIF가 Vlan1100일 때 (정상수신)
                if "Vlan1100" in outgoing_interface:
                    ## 특정 멀티캐스트그룹IP : uptime 값 가져오기
                    if device_os == 'iosxe':
                        uptimes.append(outgoing_interface['Vlan1100']['uptime'])
                    elif device_os == 'nxos':
                        uptimes.append(outgoing_interface['Vlan1100']['oil_uptime'])
                    print(f"addr_info: {addr_info}")

                    # print(f"total_uptime_days: {total_uptime_days}")
                    valid_oif_count += 1 


    if vaild_check:
        min_uptime = min(uptimes, key=parse_uptime)

        print("vlan1100 개수", valid_oif_count)
        print(f"min_uptimes : {min_uptime}")
        print(f"rp_addresses: {rp_addresses}")
        print(f"rpf_nbrs: {rpf_nbrs}")
        return_data = {
            "valid_oif_count": valid_oif_count,
            "min_uptime": min_uptime,
            "rp_addresses": rp_addresses,
            "rpf_nbrs": rpf_nbrs
        }
    else:
        return_data = {}

    return return_data 

def parse_uptime(uptime:str):
    ## 정규식으로 9w3d 같은 포맷에서 숫자를 추출
    match = re.match(r"(?:(\d+)w)?(?:(\d+)d)?", uptime)

    if not match:
        return 0
    
    weeks = int(match.group(1)) if match.group(1) else 0
    days = int(match.group(2)) if match.group(2) else 0
    total_days = weeks * 7 + days

    return total_days


@app.get("/lampad")
async def execute_collect():
    kst = timezone(timedelta(hours=9))
    kst_now = datetime.now(kst)
    epoch_kst_now = int(kst_now.timestamp())
    kst_from = kst_now - timedelta(seconds=120)
    epoch_kst_from = int(kst_from.timestamp())

    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, collect_data, tag, epoch_kst_from, epoch_kst_now)
        for tag in tag_values
    ]

    results = await asyncio.gather(*tasks)
    return results

def collect_data(tag, epoch_kst_from, epoch_kst_now):
    print(f"\n=== Processing Tag: {tag} ===")
#    print(f"kst_now : {E_NOW_DATETIME}, E_THIRTY_SECONDS_AGO : {E_THIRTY_SECONDS_AGO}")

    # 데이터 요청
    error = r1.request_data_generation(feedname, {
        'from': epoch_kst_from,
        'to': epoch_kst_now,
        'type': 'bps',
        'base': 'bytes',
        'tags': tag
    })
    if error != '':
        print(f"Error for tag {tag}: {error}")

    # 결과 조회
    get_parameters = {'bind': bind_value}
    status = r1.get_result({})
    while status != 200:
        if status < 300:
            status = r1.get_result(get_parameters)
        else:
            print(f"Failed to get result for tag {tag}. Status code: {status}")
            continue

    # 결과 저장
    try:
        decoded = r1.result.decode('utf-8')
        fixed_json = re.sub(r'(\w+):"', r'"\1":"', decoded)
        fixed_json = re.sub(r'(\w+):', r'"\1":', fixed_json)
        data = json.loads(fixed_json)
        data[0]['tag'] = tag
        print(f">> {tag} : {data[0]}")

        return data[0]
    
    except Exception as e:
        print(f"❌ Failed to process result for tag {tag}: {e}")