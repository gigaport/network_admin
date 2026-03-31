import json, logging, re, time, html, sys, asyncio, os, textfsm, yaml
from pprint import pprint
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from pprint import pprint
from urllib.parse import quote
from typing import List, Dict, Tuple, Union, Optional
from contextlib import redirect_stdout, redirect_stderr
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
from genie.libs.parser.iosxe.show_interface import ShowInterfacesDescription
from genie.libs.parser.iosxe.show_mac_address import ShowMacAddressTableDynamic
from genie.libs.parser.iosxe.show_arp import ShowIpArp as ShowIpArpIosxe
## NXOS
from genie.libs.parser.nxos.show_interface import ShowInterfaceSwitchport
from genie.libs.parser.nxos.show_interface import ShowInterfaceStatus
from genie.libs.parser.nxos.show_mcast import ShowIpMrouteVrfAll
from genie.libs.parser.nxos.show_pim import ShowIpPimRp
from genie.libs.parser.nxos.show_interface import ShowInterfaceDescription
from genie.libs.parser.nxos.show_arp import ShowIpArp as ShowIpArpNxos
# .env 파일에서 환경 변수 로드
load_dotenv()

# 로거 설정
logger = logging.getLogger(__name__)

# TIME
KST = timezone(timedelta(hours=9))
TODAY_TIME = datetime.today().strftime('%Y-%m-%d %H:%M')

TODAY_STR = datetime.today().strftime('%Y-%m-%d')

CONFIG_PATH = "/app/common/ts_member_mpr.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    TS_DEVICES = yaml.safe_load(f)

CONFIG_PATH = "/app/common/pr_member_mpr.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    PR_DEVICES = yaml.safe_load(f)

FILE_PATH = "./data/"

# pyATS 로거 설정 (로그 출력 완전 비활성화)
def disable_pyats_logging():
    """pyATS 관련 모든 로그를 완전히 비활성화"""
    import logging
    
    # 모든 관련 로거들을 완전히 비활성화
    loggers_to_disable = [
        'pyats', 'genie', 'unicon', 'pyats.aetest', 'pyats.topology',
        'pyats.connections', 'pyats.datastructures', 'pyats.easypy',
        'genie.libs', 'genie.libs.parser', 'genie.libs.sdk',
        'unicon.core', 'unicon.plugins', 'unicon.connections'
    ]
    
    for logger_name in loggers_to_disable:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)
        logger.disabled = True
        logger.propagate = False
        
        # 핸들러 제거
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

# 로그 비활성화 실행
disable_pyats_logging()

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
    },
    {
        "key": "show_interface_description",
        "value": "show interface description"
    },
    {
        "key": "show_ip_arp_nxos",
        "value": "show ip arp"
    }
]

IOSXE_CMDS = [
    {
        "key": "show_ip_mroute",
        "value": "show ip mroute"
    },
    {
        "key": "show_interfaces_status",
        "value": "show interfaces status"
    },
    {
        "key": "show_interfaces_description",
        "value": "show interfaces description"
    },
    {
        "key": "show_ip_arp_iosxe",
        "value": "show ip arp"
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
    logger.info(f"[00.network device {device_name} executing command...]")
    
    # 장비 정보 로드
    device_info = SelectToDeviceYAML(device_name)
    if not device_info:
        return None

    # 장비에 연결
    device_info = ConnectToDevice(device_info)
    logger.info(f"[01.network device {device_info.name} connected...]")
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
        logger.error(f"[ERROR] Unsupported command: {cmd}")
        return None
    else:
        logger.info(f"[01-1.PARSER] ==> {parser.__class__.__name__} selected for command: {cmd}")

    # 명령어 실행
    cmd_response = Execute_Command(device_info, cli_command)

    # 명령어 결과를 토대로 genie parser를 사용하여 파싱
    parsed_output, org_output = ParsePyatsToJson(parser, cmd_response)

    # print(f"[02-1.PARSED_OUTPUT] ==> {json.dumps(parsed_output, indent=4, ensure_ascii=False)}\n")
    
    # 연결 해제
    if device_info.connected:
        device_info.disconnect()
        # logger.info("network device disconnected...")

    return parsed_output


# geneie parser를 사용하여 정보를 수집할 네트워크 장비를 지정
def SelectToDeviceYAML(device_name):
    logger.info(f"[00.network device {device_name} selecting...]")
    data = load('/app/common/pr_member_mpr.yaml')
    try:
        device_info = data.devices[device_name]
        logger.info(f"[INFO] Device {device_info} found in PR devices.")
    except KeyError:
        try:
            device_info = data.devices[device_name]
        except KeyError:
            logger.error(f"[ERROR] Device {device_name} not found in TS or PR devices.")
            return None

    if not device_info:
        logger.error(f"[ERROR] Device {device_name} not found.")
        return None

    return device_info


# geneie parser를 사용하기 위해 장비에 연결하는 함수
def ConnectToDevice(device_info, connection_timeout=30):
    # logger.info(f"[01.network device {device_info.name} connecting...]")

    """
    pyATS는 connect메서드 실행 시 자동으로 terminal timeout 설정을 무한(0)으로 설정한다.
    이를 방지하기위해 init_exec_commands, init_config_commands 기본 명령을 제거.
    connection_timeout: SSH 연결 타임아웃 (초). 기본 30초.
    """
    device_info.connect(
        init_exec_commands=['terminal length 0', 'terminal width 511'],
        init_config_commands=[],
        log_stdout=False,
        prompt_recovery=False,
        learn_hostname=False,
        logfile=None,
        connection_timeout=connection_timeout
    )

    return device_info

# 명령어를 실행하는 함수
def Execute_Command(device_info, cli_command):
    # logger.info(f"[02.network device {device_info.name} executing command...]")
    
    # Python 레벨에서 stdout/stderr 차단 (더 안전함)
    with open(os.devnull, 'w') as devnull:
        with redirect_stdout(devnull), redirect_stderr(devnull):
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
    elif cmd == 'show_interface_description':
        return ShowInterfaceDescription(device=None)
    elif cmd == 'show_interfaces_description':
        return ShowInterfacesDescription(device=None)
    elif cmd == 'show_mac_address_dynamic':
        return ShowMacAddressTableDynamic(device=None)
    elif cmd == 'show_ip_arp_iosxe':
        return ShowIpArpIosxe(device=None)
    elif cmd == 'show_ip_arp_nxos':
        return ShowIpArpNxos(device=None)
    else:
        return None

def GetCiscoCommonInfo(device_info, device_name):
    # logger.info(f"[DEBUG] {device_name} COLLECTING COMMON INFO...]")

    # 장비에 연결 (타임아웃 30초)
    try:
        device_info = ConnectToDevice(device_info, connection_timeout=30)
    except Exception as e:
        logger.error(f"[CONNECT_TIMEOUT] {device_name} 연결 실패 (30초 타임아웃): {e}")
        return {
            "device_name": device_name,
            "device_os": device_info.os,
            "device_ip": str(device_info.connections.default.ip),
            "device_join_products": device_info.custom.get('join_products', []),
            "cmd_response_list": [],
            "error": f"Connection timeout: {str(e)}"
        }

    if not device_info:
        return None

    # 명령어 실행 및 결과 수집
    cmd_response_list = []
    parsed_output = None
    org_output = None

    if device_info.os == 'nxos':
        cmds = NXOS_CMDS
    elif device_info.os == 'iosxe':
        cmds = IOSXE_CMDS
    else:
        logger.error(f"[ERROR] Unsupported OS: {device_info.os}")
        return {"error": f"Unsupported OS: {device_info.os}"}

    for cmd in cmds:
        try:
            cmd_response = Execute_Command(device_info, cmd['value'])
        except Exception as e:
            logger.error(f"[CMD_ERROR] {device_name} 명령어 실행 실패: {cmd['value']} - {e}")
            continue

        # cmd_response 정상 체크
        if cmd_response is None:
            logger.error(f"[ERROR] Failed to execute command: {device_name}, {cmd['value']}")
            continue

        # nxos이고, show_mac_address_dynamic 명령어 실행 시 genieparser 지원이 되지 않으므로 (없음) 별도 처리 필요
        # 명령어 실행 결과를 파싱하여 파싱된 데이터와 명령어로 실행한 아웃풋 값을 리턴
        if device_info.os == 'nxos' and cmd['key'] == 'show_mac_address_dynamic':
            logger.debug(f"[DEBUG] {device_name} PARSING MAC_ADDRESS_DYNAMIC...")
            # parsed_output, org_output = ParseMacAddressDynamic(cmd_response)
        else:
            logger.debug(f"[DEBUG] {device_name} PARSING {cmd['key']}...")
            logger.debug(f"[DEBUG] CMD_RESPONSE: {cmd_response}")
            parser = GetParserByCommand(cmd['key'])
            if parser is None:
                logger.error(f"[ERROR] Unsupported command: {cmd['key']}")
                continue
            # 파싱된 데이터와 명령어로 실행한 아웃풋 값을 리턴
            parsed_output, org_output = ParsePyatsToJson(parser, cmd_response)

            if parsed_output is None:
                logger.error(f"[ERROR] Failed to parse command output for {cmd['key']}")
                continue

        cmd_response_list.append({
            "cmd": cmd['key'],
            "parsed_output": parsed_output,
            "org_output": org_output
        })

    # logger.info(f"[DEBUG] {device_name} COMMAND RESPONSE COLLECTED...")


    # 연결 해제
    try:
        if device_info.connected:
            device_info.disconnect()
    except Exception as e:
        logger.warning(f"[DISCONNECT_WARN] {device_name} 연결 해제 실패: {e}")

    data = {
        "device_name": device_name,
        "device_os": device_info.os,
        "device_ip": device_info.connections.default.ip,
        "device_join_products": device_info.custom.get('join_products', []),
        "cmd_response_list": cmd_response_list
    }

    return data

def ParseMacAddressDynamic(cmd_response):
    """
    show mac address-table dynamic 명령어 실행 결과를 파싱하여 파싱된 데이터와 명령어로 실행한 아웃풋 값을 리턴
    
    Legend:
        * - primary entry, G - Gateway MAC, (R) - Routed MAC, O - Overlay MAC
        age - seconds since last seen,+ - auto-learned
        (T) - True, (F) - False
        VLAN     MAC Address      Type      age     Secure NTFY   Ports
        -----------+-----------------+--------+---------+------+----+-----------
                10    0011.2233.4455    DYNAMIC   0          F    F    Eth1/1
                20    00aa.bbcc.ddee    DYNAMIC   10         F    F    Po1
                30    00ff.eedd.ccbb    DYNAMIC   5          F    F    Eth1/2
    """

    # cmd_response raw 값을 그대로 출력
    logger.debug(f"[DEBUG] CMD_RESPONSE_DYNAMIC: {cmd_response}")
    output = cmd_response.replace('\n', '\\n').replace('\r', '\\r')
    output = html.escape(output)

    pattern = re.compile(
        r'^\s*(\d+)\s+([\da-fA-F\.]+)\s+(\S+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)',
        re.MULTILINE
    )

    parsed_result = []
    for match in pattern.finditer(output):
        vlan, mac, type_, age, secure, ntfy, ports = match.groups()
        parsed_result.append({
            "VLAN": vlan,
            "MAC": mac,
            "TYPE": type_, 
            "AGE": age,
            "SECURE": secure,
            "NTFY": ntfy,
            "PORTS": ports
        })

    logger.debug(f"[DEBUG] PARSED MAC_ADDRESS_DYNAMIC: {parsed_result}")


    return parsed_result, output

if __name__ == "__main__":
    main()