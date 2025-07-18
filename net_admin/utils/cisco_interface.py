import json, logging, re, time, html, sys, asyncio, uvicorn, os
from dotenv import load_dotenv
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

## Cisco Common
from utils.cisco_common import Execute_GenieParser

# .env 파일에서 환경 변수 로드
load_dotenv()

# TIME
KST = timezone(timedelta(hours=9))
TODAY_TIME = datetime.today().strftime('%Y-%m-%d %H:%M')

TODAY_STR = datetime.today().strftime('%Y-%m-%d')
TS_DEVICES = load('../common/ts_member_mpr.yaml')
PR_DEVICES = load('../common/pr_member_mpr.yaml')
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

def main():
    # geneie parser를 사용하여 명령어 실행
    # 첫번째 인자는 장비 이름, 두번째 인자는 명령어
    device_name = sys.argv[1]
    cmd = sys.argv[2]

    parsed_output = Execute_GenieParser(device_name, cmd)


# geneie parser를 사용하여 정보를 수집하기 위한 첫번째 단계
def Execute_GenieParser(device_name, cmd):
    print(f"[00.network device {device_name} executing command...]")
    
    # 장비 정보 로드
    device_info = SelectToDeviceYAML(device_name)
    if not device_info:
        return None

    # 장비에 연결
    device_info = ConnectToDevice(device_info)
    print(f"[01.network device {device_info.name} connected...]")
    if not device_info:
        return None

    # 명령어를 확인하여 매핑되는 genie parser를 선택
    if cmd == 'show_ip_mroute_source-tree':
        cli_command = 'show ip mroute source-tree'
        parser = ShowIpMrouteVrfAll(device=None)
    elif cmd == 'show_ip_pim_rp':
        cli_command = 'show ip pim rp'
        parser = ShowIpPimRp(device=None)
    elif cmd == 'show_interface_status':   
        cli_command = 'show interface status'  
        parser = ShowInterfaceStatus(device=None)

    # parser가 None인 경우, 지원하지 않는 명령어이므로 종료
    if parser is None:
        print(f"[ERROR] Unsupported command: {cmd}")
        return None
    else:
        print(f"[01-1.PARSER] ==> {parser.__class__.__name__} selected for command: {cmd}")

    # 명령어 실행
    cmd_response = Execute_Command(device_info, cli_command)

    # 명령어 결과를 토대로 genie parser를 사용하여 파싱
    parsed_output, org_output = ParsePyatsToJson(parser, cmd_response)

    print(f"[02-1.PARSED_OUTPUT] ==> {json.dumps(parsed_output, indent=4, ensure_ascii=False)}\n")
    
    # 연결 해제
    if device_info.connected:
        device_info.disconnect()
        print("network device disconnected...")

    return parsed_output


# geneie parser를 사용하여 정보를 수집할 네트워크 장비를 지정
def SelectToDeviceYAML(device_name):
    print(f"[00.network device {device_name} selecting...]")
    data = load('../common/pr_member_mpr.yaml')
    try:
        device_info = data.devices[device_name]
        print(f"[INFO] Device {device_info} found in PR devices.")
    except KeyError:
        try:
            device_info = data.devices[device_name]
        except KeyError:
            print(f"[ERROR] Device {device_name} not found in TS or PR devices.")
            return None

    if not device_info:
        print(f"[ERROR] Device {device_name} not found.")
        return None

    return device_info


# geneie parser를 사용하기 위해 장비에 연결하는 함수
def ConnectToDevice(device_info):
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

    return device_info

# 명령어를 실행하는 함수
def Execute_Command(device_info, cli_command):
    print(f"[02.network device {device_info.name} executing command...]")
    cmd_response = device_info.execute(cli_command)
    return cmd_response


def ParsePyatsToJson(parser, cmd_response):
    print(f"[02-1.PARSED_OUTPUT] ==> {json.dumps(cmd_response, indent=4, ensure_ascii=False)}\n")
    
    parsed_output = parser.parse(output=cmd_response)
    # print(f"[02-1.PARSED_OUTPUT] ==> {json.dumps(parsed_output, indent=4, ensure_ascii=False)}\n")
        
    ## json 포맷으로 파싱된 데이터와 명령어로 실행한 아웃풋 값을 리턴
    ## html에 CLI값을 출력하기위해 \r, \n 포맷을 변경
    org_output = cmd_response.replace('\n', '\\n').replace('\r', '\\r')
    org_output = html.escape(org_output)

    return parsed_output, org_output


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
                cmd_response = Execute_Command(device_info, cmd['value'])
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

async def collect_data(target: str):
    print(f"[collect_data] target: {target}")
    if target == "pr":
        targets = load('../common/pr_member_mpr.yaml')
    elif target == "ts":
        targets = load('../common/ts_member_mpr.yaml')
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


if __name__ == "__main__":
    main()