import json, logging, re, time, html, sys, asyncio, uvicorn
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pprint import pprint
from typing import List, Dict, Tuple, Union, Optional
## Netmiko 라이브러리
from netmiko import ConnectHandler
## 장비관리 라이브러리
from genie.testbed import load
## 장비정보 파싱 라이브러리리
## IOSXE
from genie.libs.parser.iosxe.show_interface import ShowInterfaces
from genie.libs.parser.iosxe.show_mcast import ShowIpMroute
from genie.libs.parser.iosxe.show_pim import ShowPimNeighbor
## NXOS
from genie.libs.parser.nxos.show_mcast import ShowIpMrouteVrfAll
from genie.libs.parser.nxos.show_pim import ShowIpPimRp


app = FastAPI(root_path="/api")

# SLACK
slack_token = "***REMOVED***8455397334246-8462358192034-3F7aPVe7I0Jg686HyXzBtDU0"
client = WebClient(token=slack_token)

# 스레드풀 생성
executor = ThreadPoolExecutor(max_workers=60)

TODAY_STR = datetime.today().strftime('%Y-%m-%d')
TS_DEVICES = load('../ts_member_mpr.yaml')
PR_DEVICES = load('../pr_member_mpr.yaml')
FILE_PATH = "./data/"

NXOS_CMDS = [
    {
        "key": "show_ip_mroute_source-tree",
        "value": "show ip mroute source-tree"
    },
    {
        "key": "show_ip_pim_rp",
        "value": "show ip pim rp"
    }     
]

IOSXE_CMDS = [
    {
        "key": "show_ip_mroute",
        "value": "show ip mroute"
    }
]


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

    send_message_to_slack("#network-alert-syslog", data)

    return {"status": "ok"}

@app.post("/send_message_to_slack")
def send_message_to_slack(channel:str, message_info: Dict):
    if channel == "#network-alert-syslog":
        dt = datetime.fromisoformat(message_info['ISODATE'])
        formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        formatted_date = message_info['ISODATE']


    try:
        response = client.chat_postMessage(
            channel=channel,  # 예: "#general" 또는 "C12345678"
            text= f":warning: {message_info['LEVEL'].upper()}>>{message_info['PROGRAM']} :warning:",
            attachments=[
                {
                    "color": "warning",
                    "title": f"{message_info['PROGRAM']} // LEVEL:{message_info['LEVEL']}",
                    "text": (
                        f"*-장비이름: {message_info['PROGRAM']}*\n"
                        f"-장비IP: `{message_info['HOST']}`\n"
                        f"-발생일시: `{formatted_date}`\n"
                        f"-LEVEL: `{message_info['LEVEL'].upper()}`\n"
                        f"-MESSAGE: ```{message_info['MESSAGE']}```\n"
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
    print(f"[06.PROCESSED_DATA] ==> {json.dumps(processed_data, indent=4, ensure_ascii=False)}")

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

                print(f"[valid count] : {valid_source_address_count}\n")
                if not valid_multicast_data:
                    print('비어있음')
                else:
                    print(f"[vaild_multicast_data] => {valid_multicast_data}")
                    valid_source_address_count = valid_source_address_count
                    valid_oif_count = valid_multicast_data['valid_oif_count']
                    min_uptime = valid_multicast_data['min_uptime']
                    rpf_nbrs = valid_multicast_data['rpf_nbrs']
                    
                    if device_info.os == 'iosxe':
                        rp_addresses = valid_multicast_data['rp_addresses']
            else:
                print("[!!!데이터 없음!!!]")

        elif data['cmd'] == 'show_ip_pim_rp':
            print("[show ip pim rp logic]")
            rp_addresses.append(list(data['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']['rp']['static_rp'].keys())[0])

    result = {
        "device_name": device_name,
        "device_os": device_info.os,
        "mgmt_ip": str(device_info.connections.default.ip),
        "valid_source_address_count": valid_source_address_count,
        "valid_oif_count": valid_oif_count,
        "min_uptime": min_uptime,
        "rp_addresses": rp_addresses,
        "rpf_nbrs": rpf_nbrs,
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
        init_exec_commands=[],
        init_config_commands=[],
        log_stdout=True,
        prompt_recovery=False,
        learn_hostname=False
    ) 

    result = []

    try:
        if device_info.os == "nxos":
            for cmd in NXOS_CMDS:
                cmd_response:str = device_info.execute(cmd['value'])
                print(f"\n\n[02.CMD_RESPONSE] ==> \n {cmd_response}\n")

                ## 할당한 명령어 순차적 실행
                if cmd['key'] == 'show_ip_mroute_source-tree':
                    parser = ShowIpMrouteVrfAll(device=None)
                elif cmd['key'] == 'show_ip_pim_rp':
                    parser = ShowIpPimRp(device=None)
                
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

                parsed_output, org_output = parse_pyats_to_json(parser, cmd_response)

                temp = {
                    "cmd": cmd['key'],
                    "parsed_output": parsed_output,
                    "org_output": org_output
                }
                result.append(temp)

        print(f"[04.RESULT] ==> \n {result}\n")
        
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
    print(f"[02-1.PARSED_OUTPUT] ==> {json.dumps(parsed_output, indent=4, ensure_ascii=False)}\n")
        
    ## json 포맷으로 파싱된 데이터와 명령어로 실행한 아웃풋 값을 리턴
    ## html에 CLI값을 출력하기위해 \r, \n 포맷을 변경
    org_output = cmd_response.replace('\n', '\\n').replace('\r', '\\r')
    org_output = html.escape(org_output)

    return parsed_output, org_output


def count_valid_source_address(data):
    count = 0
    for ip, info in data.items():
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