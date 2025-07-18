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
logging.getLogger('pyats').propagate = False
logging.getLogger('genie').propagate = False
logging.getLogger('unicon').propagate = False

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

    # print(f"[02-1.PARSED_OUTPUT] ==> {json.dumps(parsed_output, indent=4, ensure_ascii=False)}\n")
    
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
    cmd_response = device_info.execute(cli_command, log=False)
    return cmd_response


def ParsePyatsToJson(parser, cmd_response):
    # print(f"[02-1.PARSED_OUTPUT] ==> {json.dumps(cmd_response, indent=4, ensure_ascii=False)}\n")
    
    parsed_output = parser.parse(output=cmd_response)
    # print(f"[02-1.PARSED_OUTPUT] ==> {json.dumps(parsed_output, indent=4, ensure_ascii=False)}\n")
        
    ## json 포맷으로 파싱된 데이터와 명령어로 실행한 아웃풋 값을 리턴
    ## html에 CLI값을 출력하기위해 \r, \n 포맷을 변경
    org_output = cmd_response.replace('\n', '\\n').replace('\r', '\\r')
    org_output = html.escape(org_output)

    return parsed_output, org_output


def GetParserByCommand(cmd):
    if cmd == 'show_ip_mroute_source-tree':
        return ShowIpMrouteVrfAll(device=None)
    elif cmd == 'show_ip_pim_rp':
        return ShowIpPimRp(device=None)
    elif cmd == 'show_interface_status':
        return ShowInterfaceStatus(device=None)
    elif cmd == 'show_ip_mroute':
        return ShowIpMroute(device=None)
    elif cmd == 'show_interfaces_status':
        return ShowInterfacesStatus(device=None)
    else:
        return None


if __name__ == "__main__":
    main()