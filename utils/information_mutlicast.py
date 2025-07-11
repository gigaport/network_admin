import pytz, sys
import requests, json, codecs, threading, asyncio, pymsteams, paramiko, time, concurrent.futures, re, os
from dotenv import load_dotenv
from pysnmp.hlapi import *
from pysnmp import hlapi
from pysnmp.entity.rfc3413.oneliner import cmdgen
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from netmiko import ConnectHandler, NetmikoTimeoutException, NetMikoAuthenticationException
from deepdiff import DeepDiff
from pathlib import Path

# .env 파일에서 환경 변수 로드
load_dotenv()

NETWORK_ID = os.getenv('NETWORK_ID')
NETWORK_PASSWD = os.getenv('NETWORK_PW')

SLACK_PROXY_URL = 'http://slack-message-gateway.live.tossinvest.bz/api/v1/slack/message'

NOW_DATETIME    = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

SLACK_CHANNEL = "network-alert-asset-증권"
# SLACK_CHANNEL = "network-alert-test-증권"

DEVICE_10G_48 = [
    'N3K-C3548P-10GX',
    'N9K-C93180YC-EX',
    'N9K-C93180YC-FX',
    'DCS-7050SX3-48C8',
    'DCS-7050SX3-48YC8',
    'DCS-7280SR3-48YC8',
    'DCS-7280TR-48C'
]

IP_NET = [
    {
        'location':'d1',
        'net':'172.21.200.{0}'
    },
    {
        'location':'d2',
        'net':'10.76.200.{0}'
    },
    {
        'location':'dr',
        'net':'172.23.200.{0}'
    },
    {
        'location':'ht',
        'net':'10.79.13.{0}'
    },
    {
        'location': 'd2',
        'net': '10.76.201.{0}'
    },
    {
        'location': 'd1',
        'net': '172.21.202.{0}'
    },
    {
        'location': 'd3',
        'net': '172.21.201.{0}'
    },
    {
        'location':'d2',
        'net':'10.76.205.{0}'
    },
    {
        'location':'d1',
        'net':'172.21.205.{0}'
    }
]

L7_IP = [
    {
        'location':'d1',
        'hostname':'d1-p-in-6A01-lb01',
        'ip':'172.16.100.11'
    },
    {
        'location':'d1',
        'hostname':'d1-p-in-6A02-lb02',
        'ip':'172.16.100.12',
    },
    {
        'location':'d1',
        'hostname':'d1-p-md-6A10-lb01',
        'ip':'172.16.100.13',
    },
    {
        'location':'d1',
        'hostname':'d1-p-md-6A11-lb02',
        'ip':'172.16.100.14',
    },
    {
        'location':'d1',
        'hostname':'d1-p-kt-6A14-lb01',
        'ip':'172.16.50.6',
    },
    {
        'location':'d1',
        'hostname':'d1-p-dz-6A10-lb03',
        'ip':'172.16.50.8',
    },
    {
        'location': 'd1',
        'hostname':'d1-p-dz-6A11-lb04',
        'ip':'172.16.50.9',
    },
    {
        'location': 'd1',
        'hostname':'d1-p-dz-6A03-lb01',
        'ip':'172.16.50.11',
    },
    {
        'location': 'd1',
        'hostname':'d1-p-dz-6A04-lb02',
        'ip':'172.16.50.12',
    },
    {
        'location': 'd1',
        'ip':'172.19.27.11',
    },
    {
        'location': 'd1',
        'ip':'172.19.27.12',
    },
    {
        'location': 'd1',
        'ip':'172.21.216.11',
    },
    {
        'location': 'd1',
        'ip':'172.21.216.12',
    },
    {
        'location': 'd1',
        'ip':'172.17.100.10',
    },
    {
        'location': 'd1',
        'ip': '172.17.100.12',
    },
    {
        'location': 'd2',
        'ip':'10.75.50.8',
    },
    {
        'location': 'd2',
        'ip':'10.75.50.9',
    },
    {
        'location': 'd2',
        'ip':'10.75.50.11',
    },
    {
        'location': 'd2',
        'ip': '10.75.50.12',
    },
    {
        'location': 'd2',
        'ip': '10.75.100.11',
    },
    {
        'location': 'd2',
        'ip': '10.75.100.12',
    },
    {
        'location': 'd2',
        'ip': '10.76.10.11',
    },
    {
        'location': 'd2',
        'ip': '10.76.10.12',
    },
    {
        'location': 'd2',
        'ip': '10.76.160.11',
    }
]

ETC_DEVICE = [
    {
        'location' : 'd1',
        'ip' : '172.21.67.254'
    },
    {
        'location': 'd1',
        'ip': '172.21.67.250'
    },
    {
        'location': 'ht',
        'ip': '10.79.9.254'
    },
]


CISCO_IOS_STACK_SERIAL_NO_OIDS  = [
    '1.3.6.1.2.1.47.1.1.1.1.11.1000',
    '1.3.6.1.2.1.47.1.1.1.1.11.2000',
    '1.3.6.1.2.1.47.1.1.1.1.11.3000',
    '1.3.6.1.2.1.47.1.1.1.1.11.4000',
    '1.3.6.1.2.1.47.1.1.1.1.11.5000'
]

CISCO_IOS_STACK_MODEL_OIDS = [
    '1.3.6.1.2.1.47.1.1.1.1.13.1000',
    '1.3.6.1.2.1.47.1.1.1.1.13.2000',
    '1.3.6.1.2.1.47.1.1.1.1.13.3000',
    '1.3.6.1.2.1.47.1.1.1.1.13.4000',
    '1.3.6.1.2.1.47.1.1.1.1.13.5000'
]

RUCKUS_STACK_SERIAL_NO_OIDS  = [
    '1.3.6.1.2.1.47.1.1.1.1.11.2400',
    '1.3.6.1.2.1.47.1.1.1.1.11.4400'
]

RUCKUS_STACK_MODEL_OIDS = [
    '1.3.6.1.2.1.47.1.1.1.1.2.2400',
    '1.3.6.1.2.1.47.1.1.1.1.2.4400'
]

## Device Gubn OID ##
CISCO_NXOS_OID  = '1.3.6.1.4.1.9.9.360.1.1.2.1.1.4.110.120.111.115'
CISCO_IOS_OID   = '1.3.6.1.4.1.9.2.1.1.0'
ARISTA_OID      = '1.3.6.1.4.1.30065.3.12.1.1.1.5.100006001'
NETSCALER_OID   = '1.3.6.1.4.1.5951.4.1.1.1.0'
RUCKUS_OID      = '1.3.6.1.4.1.1991.1.1.2.2.1.1.2.1'
F5_OID          = '1.3.6.1.4.1.3375.2.1.2.14.1.2.1.14.29.47.67.111.109.109.111.110.47.100.50.45.112.45.103.1'
ALTEON_OID      = '1.3.6.1.4.1.1872.2.5.1.3.1.30'
NSE_OID         = '1.3.6.1.2.1.1.5'

CISCO_NXOS_HOSTNAME_OID = '1.3.6.1.2.1.1.5'
CISCO_IOS_HOSTNAME_OID  = '1.3.6.1.2.1.1.5'
ARISTA_HOSTNAME_OID     = '1.3.6.1.2.1.1.5'
NETSCALER_HOSTNAME_OID  = '1.3.6.1.2.1.1.5'
RUCKUS_HOSTNAME_OID     = '1.3.6.1.2.1.1.5'
F5_HOSTNAME_OID         = '1.3.6.1.2.1.1.5'
ALTEON_HOSTNAME_OID     = '1.3.6.1.2.1.1.5'
NSE_HOSTNAME_OID        = '1.3.6.1.2.1.1.5'

CISCO_NXOS_SERIAL_NO_OID = '1.3.6.1.2.1.47.1.1.1.1.11.10'
CISCO_IOS_SERIAL_NO_OID  = '1.3.6.1.2.1.47.1.1.1.1.11.1'
ARISTA_SERIAL_NO_OID     = '1.3.6.1.2.1.47.1.1.1.1.11.1'
NETSCALER_SERIAL_NO_OID  = '1.3.6.1.4.1.5951.4.1.1.14.0'
RUCKUS_SERIAL_NO_OID     = '1.3.6.1.2.1.47.1.1.1.1.11.2400'  # stack 구성의 경우 1번 스위치 시리얼 2400, 2번 스위치 시리얼 4400
F5_SERIAL_NO_OID         = '1.3.6.1.4.1.3375.2.1.3.3.3.0'
ALTEON_SERIAL_NO_OID     = '1.3.6.1.4.1.1872.2.5.1.3.1.18.0'

CISCO_NXOS_OSVERSION_OID = '1.3.6.1.2.1.1.1.0'
CISCO_IOS_OSVERSION_OID  = '1.3.6.1.2.1.1.1.0'
ARISTA_OSVERSION_OID     = '1.3.6.1.2.1.1.1.0'
NETSCALER_OSVERSION_OID  = '1.3.6.1.2.1.1.1.0'
RUCKUS_OSVERSION_OID     = '1.3.6.1.2.1.1.1.0'
F5_OSVERSION_OID         = '1.3.6.1.4.1.3375.2.1.4.2.0'
ALTEON_OSVERSION_OID     = '1.3.6.1.4.1.1872.2.5.1.1.1.82.2.1.2.1'

CISCO_NXOS_UPTIME_OID = '1.3.6.1.2.1.1.3.0'
CISCO_IOS_UPTIME_OID  = '1.3.6.1.2.1.1.3.0'
ARISTA_UPTIME_OID     = '1.3.6.1.2.1.1.3.0'
NETSCALER_UPTIME_OID  = '1.3.6.1.2.1.1.3.0'
RUCKUS_UPTIME_OID     = '1.3.6.1.2.1.1.3.0'
F5_UPTIME_OID         = '1.3.6.1.2.1.1.3.0'
ALTEON_UPTIME_OID     = '1.3.6.1.2.1.1.3.0'

CISCO_NXOS_MODEL_OID = '1.3.6.1.2.1.47.1.1.1.1.13.10'
CISCO_IOS_MODEL_OID  = '1.3.6.1.2.1.47.1.1.1.1.13.1'
ARISTA_MODEL_OID     = '1.3.6.1.2.1.47.1.1.1.1.13.1'
NETSCALER_MODEL_OID  = '1.3.6.1.4.1.5951.4.1.1.16.0'
RUCKUS_MODEL_OID     = '1.3.6.1.2.1.47.1.1.1.1.2.2400'
F5_MODEL_OID         = '1.3.6.1.4.1.3375.2.1.3.5.2.0'
ALTEON_MODEL_OID     = '1.3.6.1.4.1.1872.2.5.1.1.1.77.0'

CISCO_NXOS_INT_IP_OID = '1.3.6.1.2.1.4.20.1.1'

NETSCALER_SYS_IP_OID = '1.3.6.1.4.1.5951.4.1.1.26.1.1'
NETSCALER_VSERVERS_NAME_OID = '1.3.6.1.4.1.5951.4.1.3.1.1.1'
NETSCALER_VSERVERS_IP_OID = '1.3.6.1.4.1.5951.4.1.3.1.1.2'

NETSCALER_ADDTIONAL_INFO = [
    {'gubn':'sys_ip', 'oid':NETSCALER_SYS_IP_OID},
    {'gubn':'vserver_name', 'oid':NETSCALER_VSERVERS_NAME_OID},
    {'gubn':'vserver_ip', 'oid':NETSCALER_VSERVERS_IP_OID}
]

## 디바이스 종류 체크를 위한 최초 조회하는 SNMP OID
DEFAULT_OID = [
    CISCO_NXOS_OID,
    CISCO_IOS_OID,
    ARISTA_OID,
    NETSCALER_OID,
    RUCKUS_OID,
    F5_OID,
    ALTEON_OID,
    NSE_OID
]

CISCO_NXOS_OIDS = {
    'hostname' : CISCO_NXOS_HOSTNAME_OID,
    'serialno' : CISCO_NXOS_SERIAL_NO_OID,
    'osversion' : CISCO_NXOS_OSVERSION_OID,
    'uptime' : CISCO_NXOS_UPTIME_OID,
    'model' : CISCO_NXOS_MODEL_OID
}

CISCO_IOS_OIDS = {
    'hostname' : CISCO_IOS_HOSTNAME_OID,
    'serialno' : CISCO_IOS_SERIAL_NO_OID,
    'osversion' : CISCO_IOS_OSVERSION_OID,
    'uptime' : CISCO_IOS_UPTIME_OID,
    'model' : CISCO_IOS_MODEL_OID
}

ARISTA_OIDS = {
    'hostname' : ARISTA_HOSTNAME_OID,
    'serialno' : ARISTA_SERIAL_NO_OID,
    'osversion' : ARISTA_OSVERSION_OID,
    'uptime' : ARISTA_UPTIME_OID,
    'model' : ARISTA_MODEL_OID
}

NETSCALER_OIDS = {
    'hostname' : NETSCALER_HOSTNAME_OID,
    'serialno' : NETSCALER_SERIAL_NO_OID,
    'osversion' : NETSCALER_OSVERSION_OID,
    'uptime' : NETSCALER_UPTIME_OID,
    'model' : NETSCALER_MODEL_OID
}

RUCKUS_OIDS = {
    'hostname' : RUCKUS_HOSTNAME_OID,
    'serialno' : RUCKUS_SERIAL_NO_OID,
    'osversion' : RUCKUS_OSVERSION_OID,
    'uptime' : RUCKUS_UPTIME_OID,
    'model' : RUCKUS_MODEL_OID
}

F5_OIDS = {
    'hostname' : F5_HOSTNAME_OID,
    'serialno' : F5_SERIAL_NO_OID,
    'osversion' : F5_OSVERSION_OID,
    'uptime' : F5_UPTIME_OID,
    'model' : F5_MODEL_OID
}

ALTEON_OIDS = {
    'hostname' : ALTEON_HOSTNAME_OID,
    'serialno' : ALTEON_SERIAL_NO_OID,
    'osversion' : ALTEON_OSVERSION_OID,
    'uptime' : ALTEON_UPTIME_OID,
    'model' : ALTEON_MODEL_OID
}

def main ():
    # check_device_basic_info()
    # get_snmp_Info()
    # compare_devices()
    # get_netmiko_result()
    get_arista_information()
    # get_Interface_statistics()

def ciscoAPItest():
    # 스위치의 관리 IP 주소와 인증 정보
    switch_ip = '172.21.200.252'
    username = 'tosssec'
    password = '@Wsxcde34'

    # NXAPI URL
    url = f'http://{switch_ip}/ins'

    # NXAPI 요청 헤더
    headers = {
        'Content-Type': 'application/json'
    }

    # NXAPI 요청 페이로드
    payload = {
        "ins_api": {
            "version": "1.0",
            "type": "cli_show",
            "chunk": "0",
            "sid": "1",
            "input": "show int status",
            "output_format": "json"
        }
    }

    # NXAPI 요청 보내기
    response = requests.post(url, headers=headers, data=json.dumps(payload), auth=(username, password), verify=False)

    # 응답 확인
    if response.status_code == 200:
        # 응답이 성공적이면 JSON 형식으로 파싱하여 출력
        response_json = response.json()
        print(json.dumps(response_json, indent=4))
    else:
        # 오류 발생 시 상태 코드와 응답 내용 출력
        print(f'Error: {response.status_code}')
        print(response.text)

def get_arista_api_result(host_info, location, hostname, vendor, model):
    print(f'{host_info} {location} {hostname} {vendor} {model}')

    return 'test_ok'

def api_connection(host, location, hostname, vendor, model):
    print("api_connectio_start!!")

    max_attempt = 3
    attempt = 0

    while attempt < max_attempt:
        try:
            # print(f"{NOW_DATETIME} open_connection_start : attempt{attempt} | {host['host']} | {hostname}")
            print(f"{NOW_DATETIME} api_connection_start | {host['host']} | {hostname} | {vendor} | {model}")

            # Arista 스위치의 IP 주소와 로그인 정보
            username = 'tosssec'
            password = '@Wsxcde34'

            # eAPI 엔드포인트 URL
            url = f"http://{host['host']}/command-api"

            # 요청에 사용할 헤더 설정
            headers = {
                'Content-Type': 'application/json'
            }

            # 요청할 명령어와 매개변수
            payload = {
                'jsonrpc': '2.0',
                'method': 'runCmds',
                'params': {
                    'version': 1,
                    'cmds': [
                        'show ip interface brief',
                        'show interfaces status',
                        'show ip arp',
                        'show mac address-table',
                        'show ip route'
                    ],
                    'format': 'json'
                },
                'id': 1
            }

            # eAPI 요청 보내기
            response = requests.post(url, headers=headers, data=json.dumps(payload), auth=(username, password),
                                     verify=False)

            response_json = response.json()
            # print(json.dumps(response_json, indent=4))
            return response_json

        except Exception as e:
            print('error')
            ###################
            ###################
            ###################
        #     output = []
        #     connection = ConnectHandler(**host)
        #
        #     # print('Trying connection', host['host'], hostname)
        #     # print('Connection Established to host:', host['host'], hostname)
        #     connection.enable()
        #     cmd_list = [
        #         'show ip interface brief',
        #         'show int status',
        #         'show ip arp',
        #         'show mac address',
        #         'show ip route'
        #     ]
        #
        #     for idx, cmd in enumerate(cmd_list):
        #         # print(f"{NOW_DATETIME} open_connection_idx_cmd >> {hostname}, {idx}, {cmd}")
        #         output.append(connection.send_command(cmd, use_textfsm=True))
        #         # print('output >> ', output)
        #
        #     host['location'] = location
        #     host['hostname'] = hostname
        #     host['vendor'] = vendor
        #     host['model'] = model
        #
        #     # print(f"{NOW_DATETIME} open_connection_established : attempt{attempt} | {host['host']} | {hostname}")
        #     print(f"{NOW_DATETIME} open_connection_established | {host['host']} | {hostname} | {vendor} | {model}")
        #
        #     return host, output
        #
        # except (NetmikoTimeoutException, NetMikoAuthenticationException) as e:
        #     print(
        #         f"{NOW_DATETIME} Connection Failed to host : attempt{attempt} | {host['host']} | {hostname} | {vendor} | {model}")
        #
        #     attempt += 1
        #     time.sleep(5)

# pr_information_mkd.json 파일에 등록된 스위치 정보를 가져와서
# Arista API를 통해 정보를 가져오는 함수
def get_arista_information():
    print("get_arista_information_start!!")
    device_info_file = '../common/pr_information_mkd.json'

    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(device_info_file, 'rt', encoding='UTF8') as json_file:
        device_info_json_data = json.load(json_file)

    ip_info, arp_info, mac_info, interface_info, route_info, host_info, location, hostname, vendor, model = [], [], [], [], [], [], [], [], [], []

    # device_info_json_data['devices']에 등록된 스위치 IP 정보를 순회하면서
    # Arista API를 통해 정보를 가져옵니다.

    for i, value in enumerate(device_info_json_data['devices']):
        # eAPI 엔드포인트 URL
        url = f"http://{value['ip']}/command-api"

        # 요청에 사용할 헤더 설정
        headers = {
            'Content-Type': 'application/json'
        }

        # 요청할 명령어와 매개변수
        payload = {
            'jsonrpc': '2.0',
            'method': 'runCmds',
            'params': {
                'version': 1,
                'cmds': [
                    'show ip interface brief',
                    'show interfaces status',
                    'show ip arp',
                    'show mac address-table',
                    'show ip route'
                ],
                'format': 'json'
            },
            'id': 1
        }

        print(f"[DEBUG] device_ip : {value['ip']}")
        # eAPI 요청 보내기
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), auth=(NETWORK_ID, NETWORK_PASSWD),                                        verify=False)
            # 상태 코드 확인
            if response.status_code != 200:
                print(f"Error: Received status code {response.status_code}")
                continue
            # 응답이 비어 있는지 확인
            if not response.text.strip():
                print("Response body is empty")
                return None

            # JSON 확인 및 파싱
            if 'application/json' in response.headers.get('Content-Type', ''):
                try:
                    response_json = response.json()
                    # return response_json
                except json.JSONDecodeError:
                    print("Failed to decode JSON")
                    print(f"Response Content: {response.text}")
                    return None
            else:
                print("Response is not JSON")
                print(f"Response Content: {response.text}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None


        response_json = response.json()
        print(f"[DEBUG] response_json >> {response_json}")

        ## show ip interface brief ##
        if any("interfaces" in item for item in response_json['result']):
            print("interfaces_exist_start")
            for idx, interface_ip_info in enumerate(response_json['result'][0]['interfaces'].items()):
                if interface_ip_info[1]['name'] == 'Vlan1':
                    continue

                ip_info_last_idx += 1
                ip_info.append(
                    {
                        'id': ip_info_last_idx,
                        'location': value['location'],
                        'hostname': value['hostname'],
                        'ip': interface_ip_info[1]['interfaceAddress']['ipAddr']['address'],
                        'interface': interface_ip_info[1]['name']
                    }
                )

        ## show interfaces status ##
        if any("interfaceStatuses" in item for item in response_json['result']):
            print("interface_status_exist_start")
            for idx, interface_status_info in enumerate(response_json['result'][1]['interfaceStatuses'].items()):
                print(f'interface_status_exist_start: {interface_status_info[1]}')
                interface_info_last_idx += 1
                ## vlan check ##
                if interface_status_info[1]['vlanInformation']['interfaceForwardingModel'] == 'dataLink':
                    vlanID = interface_status_info[1]['vlanInformation']['vlanExplanation']
                elif interface_status_info[1]['vlanInformation']['interfaceForwardingModel'] == 'routed':
                    vlanID = 'routed'
                elif interface_status_info[1]['vlanInformation']['interfaceForwardingModel'] == 'bridged':
                    if interface_status_info[1]['vlanInformation']['interfaceMode'] == 'trunk':
                        vlanID = 'trunk'
                    elif interface_status_info[1]['vlanInformation']['interfaceMode'] == 'bridged' :
                        vlanID = interface_status_info[1]['vlanInformation']['vlanId']

                interface_info.append(
                    {
                        'port': interface_status_info[0],
                        'name': interface_status_info[1]['description'],
                        'status': interface_status_info[1]['linkStatus'],
                        'vlan': vlanID,
                        'duplex': interface_status_info[1]['duplex'],
                        'speed': interface_status_info[1]['bandwidth'],
                        'type': interface_status_info[1]['interfaceType'],
                        'id': interface_info_last_idx,
                        'location': value['location'],
                        'hostname': value['hostname'],
                        'vendor': value['vendor'],
                        'model': value['model'],
                        'idx': idx
                    }
                )

        ## show ip arp ##
        if any("ipV4Neighbors" in item for item in response_json['result']):
            print("ip_arp_exist")

        ## show mac address-table ##
        if any("unicastTable" in item for item in response_json['result']):
            print("mac_address_exist")

        ## show ip route ##
        if any("vrfs" in item for item in response_json['result']):
            # vrfs:{
                # default:{
                    # routes:{
                        # 목적지IP:{}
                    # }
                # }
            # }
            print("ip_route_exist")



def aristaAPItest():
    # Arista 스위치의 IP 주소와 로그인 정보
    switch_ip = '172.21.200.176'
    username = 'tosssec'
    password = '@Wsxcde34'

    # eAPI 엔드포인트 URL
    url = f'http://{switch_ip}/command-api'

    # 요청에 사용할 헤더 설정
    headers = {
        'Content-Type': 'application/json'
    }
    # 요청할 명령어와 매개변수
    payload = {
        'jsonrpc': '2.0',
        'method': 'runCmds',
        'params': {
            'version': 1,
            'cmds': [
                'show interfaces',
                'show interfaces status',
                'show ip arp',
                'show mac address-table',
                'show ip route'
            ],
            'format': 'json'
        },
        'id': 1
    }

    # eAPI 요청 보내기
    response = requests.post(url, headers=headers, data=json.dumps(payload), auth=(username, password), verify=False)

    # 응답 확인
    if response.status_code == 200:
        # 응답이 성공적이면 JSON 형식으로 파싱하여 출력
        response_json = response.json()
        print(json.dumps(response_json, indent=4))
    else:
        # 오류 발생 시 상태 코드와 응답 내용 출력
        print(f'Error: {response.status_code}')
        print(response.text)


def clockTest():
    kst_time = datetime.now()
    utc_time = kst_to_utc(kst_time)

    print('kst_time >> ', kst_time)
    print('utc_time >> ', utc_time)

def kst_to_utc(kst_time):
    kst = pytz.timezone('Asia/Seoul')
    utc = pytz.utc

    return kst.localize(kst_time).astimezone(utc)

# def itsmtest():
#     for idx, id in enumerate(ID):
#         payload = {
#             "_id": id,
#             "수정자": "라원수",
#             "업무명": HOSTNAMES[idx]
#         }
#         print(payload)
#         requests.post(f'https://itsm-live.tossinvest.bz/api/v2/devices', json=payload)
#         time.sleep(1)

def compare_devices():
    ## 어제자 날짜 구하기 ##
    yesterday_date = datetime.now() - timedelta(days=1)
    yesterday = yesterday_date.strftime('%Y-%m-%d')

    device_info_file_name = '/home/tossinvest/lamp/gather/device_info.json'
    with open(device_info_file_name, 'rt', encoding='UTF8') as json_file:
        device_info_json_data = json.load(json_file)

    device_info_file_name_yd = f'/home/tossinvest/lamp/gather/backup/device_info_{yesterday}.json'
    with open(device_info_file_name_yd, 'rt', encoding='UTF8') as json_file:
        device_info_json_data_yd = json.load(json_file)

    # print(type(device_info_json_data['device_info']))
    device_info = device_info_json_data['device_info']
    device_info_yd = device_info_json_data_yd['device_info']
    today_serial_no, yesterday_serial_no, removed_serailno, added_serialno, removed_devices, added_devices  = [], [], [], [], [], []

    ## lamp 기준 오늘/어제 자산 차이 확인 start >>
    ## 오늘/어제 시리얼번호 차이 확인
    ## 기준 : SNMP수집정보
    for index, value in enumerate(device_info):
        today_serial_no.append(value['serialno'])

    for index, value in enumerate(device_info_yd):
        yesterday_serial_no.append(value['serialno'])

    result = DeepDiff(yesterday_serial_no, today_serial_no, ignore_order=True, report_repetition=True)
    keys = result.keys()

    for idx, key in enumerate(keys):
        if key == 'iterable_item_removed':
            # print(f'{NOW_DATETIME} removed', result['iterable_item_removed'])
            removed_serailno = list(result['iterable_item_removed'].values())

        elif key == 'iterable_item_added':
            # print(f'{NOW_DATETIME} removed', result['iterable_item_added'])
            added_serialno = list(result['iterable_item_added'].values())

    print(f'{NOW_DATETIME} || today_lamp_added serialno : ', added_serialno)
    print(f'{NOW_DATETIME} || today_lamp_removed serialno : ',removed_serailno)

    ##--------------------------------------------------------------------------##
    if len(removed_serailno) > 0 : ## 제거된 항목이 있을 경우 어제 데이터를 조회 // 오늘 데이터에는 삭제된 세부정보가 없으므로
        for serialno in removed_serailno:
            removed_device = next(item for item in device_info_yd if item['serialno'] == serialno)
            print(f'{NOW_DATETIME} || lamp Removed devices!! >> ',  removed_device)
            removed_devices.append(removed_device)

    if len(added_serialno) > 0:  ## 추가된 항목이 있을 경우 오늘 데이터를 조회 // 어제 데이터에는 추가된 세부정보가 없으므로
        for serialno in added_serialno:
            added_device = next(item for item in device_info if item['serialno'] == serialno)
            print(f'{NOW_DATETIME} || lamp Added devices!! >> ',  added_device)
            added_devices.append(added_device)

    print(f'{NOW_DATETIME} || lamp Added Devices >> ', added_devices)
    print(f'{NOW_DATETIME} || lamp Removed Devices >> ', removed_devices)
    ## lamp 기준 오늘/어제 자산 차이 확인 end 1

    ## 동일한 serialno 확인 후 내부정보 변경사항 확인 start >>
    equal_serialno = set(today_serial_no) & set(yesterday_serial_no)
    # print('equal serial_no >> ', equal_serialno, len(equal_serialno))

    exclude_paths = [
        "root['uptime']",
        "root['id']"
    ]

    changed_values = []
    for serialno in equal_serialno:
        device_yd = next(item for item in device_info_yd if item['serialno'] == serialno)
        device_td = next(item for item in device_info if item['serialno'] == serialno)
        diff_result = DeepDiff(device_yd, device_td, ignore_order=True, report_repetition=True, exclude_paths=exclude_paths)

        equal_keys = diff_result.keys()
        if len(equal_keys) > 0 :
            # print('diff_result >> ', serialno, diff_result, len(equal_keys))
            data = {
                'serialno': serialno,
                'changed':diff_result['values_changed']
            }
            changed_values.append(data)

    print(f'{NOW_DATETIME} LAMP Changed values!! >> ', changed_values)
    ## 동일한 serialno 확인 후 내부정보 변경사항 확인 end

    ## ITSM 자료 비교 로직 start
    itsm_network_devices = get_itsm_network_devices()
    # print('itsm devices >> ', itsm_network_devices)

    itsm_serialno, itsm_added_serialno, itsm_removed_serailno = [], [], []
    for idx, device in enumerate(itsm_network_devices):
        ## 무선 // 샤시모듈 // Netis(구)모니터링 서버 // 자산 예외처리 ##
        if device['모델'] == 'Ruckus 650' or device['모델'] == 'RUCKUS SmartZone 104' or device['모델'] == 'N9K-X97160YC-EX' or device['시리얼'] == 'SR190225S029': continue
        itsm_serialno.append(device['시리얼'])

    print(f'{NOW_DATETIME} [itsm_serialno] >> ', itsm_serialno)

    result = DeepDiff(today_serial_no, itsm_serialno, ignore_order=True, report_repetition=True)
    keys = result.keys()

    for idx, key in enumerate(keys):
        if key == 'iterable_item_removed':
            print(f"{NOW_DATETIME} || removed {result['iterable_item_removed']}")
            itsm_removed_serailno = list(result['iterable_item_removed'].values())

        elif key == 'iterable_item_added':
            print(f"{NOW_DATETIME} || removed {result['iterable_item_added']}")
            itsm_added_serialno = list(result['iterable_item_added'].values())

    print(f'{NOW_DATETIME} itsm_added serialno >>  : ', itsm_added_serialno)
    print(f'{NOW_DATETIME} itsm_removed serialno >>  : ', itsm_removed_serailno)
    # print('today_serial_no >> ', today_serial_no)

    ## ITSM에만 자산이 있는 경우 ##
    itsm_added_devices = []
    if len(itsm_added_serialno) > 0:
        print(f'{NOW_DATETIME} || ITSM에만 자산이 있는 경우')
        for itsm_serial_no in itsm_added_serialno:
            itsm_device_info = next(item for item in itsm_network_devices if item['시리얼'] == itsm_serial_no)
            comment = 'unknown'
            if '비고' in itsm_device_info:
                comment = itsm_device_info['비고']
            temp = {
                '시리얼': itsm_device_info['시리얼'],
                '업무명': itsm_device_info['업무명'],
                '벤더': itsm_device_info['벤더'],
                '모델': itsm_device_info['모델'],
                '상태': itsm_device_info['상태'],
                '위치': itsm_device_info['위치'],
                '비고': comment
            }
            itsm_added_devices.append(temp)

    ## LAMP에만 자산이 있는 경우 ##
    itsm_removed_devices = []
    if len(itsm_added_serialno) > 0:
        print(f'{NOW_DATETIME} || LAMP에만 자산이 있는 경우')
        for lamp_serial_no in itsm_removed_serailno:
            temp = next(item for item in device_info if item['serialno'] == lamp_serial_no)
            itsm_removed_devices.append(temp)

    ## LAMP -- ITSM 동일한 serialno 확인 후 내부정보 변경사항 확인
    # lamp_itsm_equal_serialno = set(today_serial_no) & set(itsm_serialno)
    #
    # lamp_itsm_compared_values = []
    # for serialno in equal_serialno:
    #     lamp_device = next(item for item in device_info if item['serialno'] == serialno)
    #     fitler_lamp_device = {
    #         'hostname' : lamp_device['hostname'],
    #         'vendor' : lamp_device['vendor'],
    #         'model' : lamp_device['model']
    #     }
    #     itsm_device = next(item for item in itsm_network_devices if item['시리얼'] == serialno)
    #     filter_itsm_device = {
    #         'hostname' : itsm_device['업무명'],
    #         'vendor' : itsm_device['벤더'],
    #         'model' : itsm_device['모델']
    #     }
    #
    #     lamp_itsm_diff_result = DeepDiff(fitler_lamp_device, filter_itsm_device, ignore_order=True, report_repetition=True)
    #     print('[lamp_itsm_diff_result] >> ', lamp_itsm_diff_result)
    #
    #     equal_keys = lamp_itsm_diff_result.keys()
    #     if len(equal_keys) > 0 :
    #         print('diff_result >> ', serialno, diff_result, len(equal_keys), equal_keys)
    #         data = {
    #             'serialno': serialno,
    #             'changed':lamp_itsm_diff_result['values_changed']
    #         }
    #         lamp_itsm_compared_values.append(data)
    #
    # print('lamp_itsm compare values!! >> ', lamp_itsm_compared_values)



    ## 변경사항 여부 확인하여 슬랙전송 ##
    add_payload = []
    if len(removed_devices) > 0:
        payload_data = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"`LAMP 삭제 자산` : ```{json.dumps(removed_devices, indent=1)}```"
            }
        }
        send_slack_message(":minus-arrow: LAMP 삭제 자산 :minus-arrow:", payload_data)

    if len(added_devices) > 0:
        print(f'{NOW_DATETIME} || lamp_added_devices_payload gogo >>')
        payload_data = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"`LAMP 추가 자산` : ```{json.dumps(added_devices, indent=1)}```"
            }
        }
        send_slack_message(":plus: LAMP 추가 자산 :plus:", payload_data)

    if len(changed_values) > 0:
        print(f'{NOW_DATETIME} || lamp_changed_devices_payload gogo >>')
        payload_data = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                # "text": f"`자산 변경내역` : ```{changed_values}```"
                "text": f"`LAMP 자산 변경내역` : ```{json.dumps(changed_values, indent=1)}```"
            }
        }
        send_slack_message(":check_blue: LAMP 자산 변경내역 :check_blue:", payload_data)

    if len(itsm_added_devices) > 0:
        print(f'{NOW_DATETIME} || itsm_added_devices_payload gogo >>')
        payload_data = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                # "text": f"`자산 변경내역` : ```{changed_values}```"
                "text": f"`ITSM [등록 O] // LAMP [등록 X]` : ```{json.dumps(itsm_added_devices, ensure_ascii=False, indent=1)}```"
            }
        }
        send_slack_message(":check_red: ITSM [O] // LAMP [X] :check_red:", payload_data)
        # add_payload.append(temp)

    if len(itsm_removed_devices) > 0:
        print(f'{NOW_DATETIME} || itsm_removed_devices_payload gogo >>')
        payload_data = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                # "text": f"`자산 변경내역` : ```{changed_values}```"
                "text": f"`ITSM [등록 X] // LAMP [등록 O]` : ```{json.dumps(itsm_removed_devices, ensure_ascii=False, indent=1)}```"
            }
        }
        send_slack_message(":check_red: ITSM [X] // LAMP [O] :check_red:", payload_data)

    # if len(lamp_itsm_compared_values) > 0:
    #     temp = {
    #         "type": "section",
    #         "text": {
    #             "type": "mrkdwn",
    #             # "text": f"`자산 변경내역` : ```{changed_values}```"
    #             "text": f"`LAMP && ITSM 비교` : ```{json.dumps(lamp_itsm_compared_values, ensure_ascii=False, indent=1)}```"
    #         }
    #     }
    #     add_payload.append(temp)

    # if len(add_payload) > 0:
    #     # print(f'{NOW_DATETIME} add_payload : {json.dumps(add_payload, indent=4)}')
    #     payload = {
    #         "sender": "lamp",
    #         "webHookUrl": "https://hooks.slack.com/services/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",
    #         "payload": {
    #             "icon_emoji": ":robot:",
    #             "text": "네트워크 데일리점검",
    #             "username": "네트워크관리봇",
    #             # "channel": "network-alert-asset-증권",
    #             "channel": "network-alert-test-증권",
    #             "blocks": [
    #                 {
    #                     "type": "header",
    #                     "text": {
    #                         "type": "plain_text",
    #                         "text": ":check_red: 네트워크 자산변동사항 :check_red:"
    #                     }
    #                 }
    #             ]
    #         }
    #     }
    #
    #     payload['payload']['blocks'] = payload['payload']['blocks'] + add_payload
    #     # print('payload!!! >> ', payload['payload']['blocks'])
    #     # print('[diff] sended message to slack-channel!! >>>')
    #
    # else:
    #     payload = {
    #         "sender": "mg-net03",
    #         "webHookUrl": "https://hooks.slack.com/services/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",
    #         "payload": {
    #             "icon_emoji": ":robot:",
    #             "text": "네트워크 데일리점검",
    #             "username": "네트워크관리봇",
    #             "channel": "network-alert-asset-증권",
    #             # "channel": "network-alert-test-증권",
    #             "blocks": [
    #                 {
    #                     "type": "header",
    #                     "text": {
    #                         "type": "plain_text",
    #                         "text": ":check_red: 네트워크 자산변동사항 :check_red:"
    #                     }
    #                 },
    #                 {
    #                     "type": "section",
    #                     "text": {
    #                         "type": "mrkdwn",
    #                         # "text": f"`자산 변경내역` : ```{changed_values}```"
    #                         "text": f"`자산 변동사항 없음`"
    #                     }
    #                 }
    #             ]
    #         }
    #     }
    # print(f'{NOW_DATETIME} payload : {json.dumps(payload, ensure_ascii=False, indent=4)}')
    # requests.post(SLACK_PROXY_URL, json=payload, headers={'Content-Type': 'application/json; charset=utf-8'})

def send_slack_message(title, payload_data):
    payload = {
        "sender": "lamp",
        "webHookUrl": "https://hooks.slack.com/services/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",
        "payload": {
            "icon_emoji": ":robot:",
            "text": "네트워크 데일리점검",
            "username": "네트워크관리봇",
            "channel": SLACK_CHANNEL,
            # "channel": "network-alert-test-증권",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title
                    }
                },
                payload_data
            ]
        }
    }
    # payload['payload']['blocks'] = payload['payload']['blocks'] + payload_data

    print(f'{NOW_DATETIME} || payload : {json.dumps(payload, ensure_ascii=False, indent=4)}')
    requests.post(SLACK_PROXY_URL, json=payload, headers={'Content-Type': 'application/json; charset=utf-8'})

def get_itsm_network_devices():
    itsm_device_info_file_name = '/home/tossinvest/lamp/gather/itsm_device_info.json'
    device_info_file_name = '/home/tossinvest/lamp/gather/device_info.json'
    with open(itsm_device_info_file_name, 'rt', encoding='UTF8') as json_file:
        itsm_device_info_json_data = json.load(json_file)

    with open(device_info_file_name, 'rt', encoding='UTF8') as json_file:
        device_info_json_data = json.load(json_file)
        # print(device_info_json_data)

    itsm_url = 'https://itsm-live.tossinvest.bz/api/v2/devices'
    headers = {'Content-Type': 'application/json'}

    response = requests.get(itsm_url, headers=headers)

    if response.status_code == 200:
        result = [d for d in response.json() if d.get("분류") == "네트워크"]
        return result
    else:
        print(f"{NOW_DATETIME} || request failed with status code {response.status_code}")

def check_device_basic_info():
    os_path = os.getcwd()
    file_name = f'/home/tossinvest/lamp/gather/device_info.json'
    nse_file_name = f'/home/tossinvest/lamp/gather/nse_device_info.json'
    dic_device_info, dic_nse_device_info = {}, {}

    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(file_name, 'rt', encoding='UTF8') as json_file:
        json_data = json.load(json_file)
    with open(nse_file_name, 'rt', encoding='UTF8') as json_file:
        nse_json_data = json.load(json_file)

    arr_result, arr_nse_result = [], []
    id, nse_id = 1, 1
    for data in IP_NET:
        ## .1 ~ .255 IP 조회 ##
        for n in range(1, 255):
            temp = {}
            device_ip = data['net'].format(n)

            for oid in DEFAULT_OID:                         ## 타겟 IP마다 장비를 구분할 수 있는 SNMP OID로 조회함
                if device_ip == '172.21.200.1' or device_ip == '10.76.200.1' or device_ip == '10.76.205.1' or device_ip == '10.76.205.2' or device_ip == '10.76.205.3' or device_ip == '172.21.205.1' or device_ip == '172.21.205.2' or device_ip == '172.21.205.3' : continue     ## dc2 관리백본은 10.76.200.2 + 10.76.205.1~3까지는 중복되어 제외처리

                if oid == NSE_OID:                          ## NSE 장비일경우 hostname값 추출
                    check_result = query_snmp('nse', 'NSE', device_ip, oid)
                else :
                    check_result = query_snmp('init', 'INIT', device_ip, oid)

                print(f'{NOW_DATETIME} || [01. device_gubn_SNMP_result >> : {device_ip} ==> {check_result}')

                ## ERR : 응답이 없는 경우
                ## CON : 응답이 있으나, SNMP OID값 조회가 불가한 경우
                if check_result == 'ERR': break
                elif check_result != 'CON':
                    ## CITRIX는 관리IP 지정이 어려워 하드코딩했기때문에 관리IP에서 citrix가 나오면 스킵한다.
                    if 'CITRIX' == check_result['vendor']: continue

                    temp['ip'] = device_ip
                    temp['location'] = data['location']
                    temp['vendor'] = check_result['vendor']
                    temp['gubn'] = check_result['platform']

                    if oid == NSE_OID:                      ## NSE 장비정보 추가
                        temp['id'] = nse_id
                        temp['hostname'] = check_result['hostname']
                        nse_id += 1
                        arr_nse_result.append(temp)
                    else:                                   ## 네트워크 장비정보 추가
                        temp['id'] = id
                        id += 1
                        arr_result.append(temp)
                    break

    ## 관리대역으로 조회가 불가한 대상들 우선 직접 추가 ##
    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.16.100.11',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.16.100.12',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.16.100.13',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.16.100.14',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.16.50.6',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.16.50.8',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.16.50.9',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.16.50.11',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.16.50.12',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.19.27.11',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.19.27.12',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.21.216.11',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.21.216.12',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.17.100.10',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.17.100.12',
        'location': 'd1',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '10.75.50.8',
        'location': 'd2',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '10.75.50.9',
        'location': 'd2',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '10.75.50.11',
        'location': 'd2',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '10.75.50.12',
        'location': 'd2',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '10.75.100.11',
        'location': 'd2',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '10.75.100.12',
        'location': 'd2',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '10.76.10.11',
        'location': 'd2',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '10.76.10.12',
        'location': 'd2',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '10.76.160.11',
        'location': 'd2',
        'vendor': 'CITRIX',
        'gubn': 'NS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id' : id,
        'ip' : '172.21.67.254',
        'location' : 'd1',
        'vendor' : 'CISCO',
        'gubn' : 'IOS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.21.67.250',
        'location': 'd1',
        'vendor': 'RUCKUS',
        'gubn': 'ICX'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '10.79.9.254',
        'location': 'ht',
        'vendor': 'CISCO',
        'gubn': 'IOS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '10.76.30.252',
        'location': 'd2',
        'vendor': 'RUCKUS',
        'gubn': 'ICX'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '10.76.30.253',
        'location': 'd2',
        'vendor': 'CISCO',
        'gubn': 'IOS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '10.76.30.254',
        'location': 'd2',
        'vendor': 'CISCO',
        'gubn': 'IOS'
    }
    arr_result.append(etc_temp)

    id = id + 1
    etc_temp = {
        'id': id,
        'ip': '172.23.211.1',
        'location': 'dr',
        'vendor': 'CISCO',
        'gubn': 'IOS'
    }
    arr_result.append(etc_temp)

    print(f'{NOW_DATETIME} || [ne_arr_result] >>> {arr_result}')
    print(f'{NOW_DATETIME} || [nse_arr_result] >>> {arr_nse_result}')

    dic_device_info['device_info'] = arr_result
    print(f'{NOW_DATETIME} || Init device Gubn >>> {dic_device_info}')

    dic_nse_device_info['device_info'] = arr_nse_result
    print(f'{NOW_DATETIME} || Init device Gubn >>> {dic_nse_device_info}')

    with open(file_name, 'w') as json_file:
        data = json.dump(dic_device_info, json_file, indent=4)

    with open(nse_file_name, 'w') as json_file:
        data = json.dump(dic_nse_device_info, json_file, indent=4)

########################### SNMP TEST #############################

def query_snmp(key, vendor, strIP, oid):
    if key == 'hostname' or key == 'nse':
        g = getCmd(
            SnmpEngine(), CommunityData('Wwfbs365%'), UdpTransportTarget(
                (strIP, 161), timeout=1, retries=0), ContextData(), ObjectType(
                ObjectIdentity('SNMPv2-MIB', 'sysName', 0)
            )
        )
    else :
        g = getCmd(
            SnmpEngine(), CommunityData('Wwfbs365%'), UdpTransportTarget(
                (strIP, 161), timeout=1, retries=0), ContextData(), ObjectType(
                ObjectIdentity(oid)
            )
        )

    errorIndication, errorStatus, errorIndex, varBinds = next(g)
    # print(f'errorIndication : {errorIndication}')
    # print(f'errorStatus : {errorStatus}')
    # print(f'errorIndex : {errorIndex}')

    if errorIndication or errorStatus or errorIndex:
        return 'ERR'
    else:
        snmp_result = ''
        for varBind in varBinds:
            print(f'{NOW_DATETIME} || [varBind contents] >>> {varBind}')
            temp = ' ='.join([x.prettyPrint() for x in varBind])
            idx = temp.find('=')
            snmp_result = temp[idx + 1:]
            ## Cisco IOS 검증 ##

        ## 장비 구분용 쿼리일 경우 ##
        if key == 'init' or key == 'nse':
            if snmp_result == 'No Such Object currently exists at this OID':
                return 'CON'
            else :
                print(f'{NOW_DATETIME} || 02. 장비구분 결과 >> : {strIP} // {oid} >> {snmp_result}')
                ## 체크결과 json update ##
                if oid == CISCO_NXOS_OID: return {'vendor':'CISCO', 'platform':'NX-OS'}
                elif oid == CISCO_IOS_OID: return {'vendor':'CISCO', 'platform':'IOS'}
                elif oid == ARISTA_OID: return {'vendor':'ARISTA', 'platform':'EOS'}
                elif oid == NETSCALER_OID: return {'vendor':'CITRIX', 'platform':'NS'}
                elif oid == RUCKUS_OID: return {'vendor':'RUCKUS', 'platform':'ICX'}
                elif oid == F5_OID: return {'vendor':'F5', 'platform':'BIG-IP'}
                elif oid == ALTEON_OID: return {'vendor': 'ALTEON', 'platform': 'Radware'}
                elif oid == NSE_OID: return {'vendor': 'NSE', 'platform': 'NSE', 'hostname': snmp_result}
        ## SNMP 정보조회 시작 ##
        else :
            ## uptime snmp조회 결과처리 ##
            if key == 'uptime':
                seconds = int(snmp_result)/100
                snmp_result = str(timedelta(seconds=seconds)).split(' ')[0]
                ## uptime이 하루가 지나지않은 경우 ##
                if snmp_result.find(':') != -1:
                    snmp_result = 0
            ## hostname snmp조회 결과처리 ##
            elif key == 'hostname':
                ## hostname 불필요 추가문자 삭제 처리 ##
                snmp_result = snmp_result.replace('.Toss', '')
                snmp_result = snmp_result.replace('.com', '')
                snmp_result = snmp_result.replace('.toss', '')
                snmp_result = snmp_result.replace('invest', '')
                snmp_result = snmp_result.replace('.tosssecurities', '')
                snmp_result = snmp_result.replace('.tossinvest', '')
                snmp_result = snmp_result.replace('.tossinvest.com', '')
            elif oid == RUCKUS_MODEL_OID or oid == RUCKUS_STACK_MODEL_OIDS[1]: ## RUCKUS ICX7150-24P (POE 24-port Management Module) ==> ICX7150-24P
                snmp_result = snmp_result.split(' ')[0]
            elif key == 'serialno':
                snmp_result = snmp_result.replace(' ', '')
            elif key == 'osversion':
                print(f'{NOW_DATETIME} || [OSVERSION >>> {vendor}')
                if vendor == 'NX-OS': ## Version xxx,
                    firts_idx = snmp_result.find('Version')
                    last_idx = snmp_result.find('RELEASE')
                    snmp_result = snmp_result[firts_idx + 8:last_idx - 2]
                    print(f"{NOW_DATETIME} || NX-OS:{snmp_result}")
                elif vendor == 'IOS':
                    firts_idx = snmp_result.find('Version')
                    last_idx = snmp_result.find('RELEASE')
                    snmp_result = snmp_result[firts_idx + 8:last_idx - 2]
                    print(f"{NOW_DATETIME} || IOS:{snmp_result}")
                elif vendor == 'EOS': ## version xxx
                    firts_idx = snmp_result.find('version')
                    last_idx = snmp_result.find('running')
                    snmp_result = snmp_result[firts_idx + 8:last_idx - 1]
                    print(f"{NOW_DATETIME} || EOS:{snmp_result}")
                elif vendor == 'NS': ## NS13.0: Build 79.64.nc,
                    firts_idx = snmp_result.find('NetScaler')
                    last_idx = snmp_result.find('Date')
                    snmp_result = snmp_result[firts_idx + 10:last_idx - 2]
                    print(f"{NOW_DATETIME} || NS:{snmp_result}")
                elif vendor == 'ICX': ## Version 08.0.90kT211
                    firts_idx = snmp_result.find('Version')
                    last_idx = snmp_result.find('Compiled')
                    snmp_result = snmp_result[firts_idx + 8:last_idx - 1]
                    print(f"{NOW_DATETIME} || ICX:{snmp_result}")
                ## F5는 리턴값 그대로 사용
                print(f'{NOW_DATETIME} || snmp_result')
            return snmp_result

def reCheckSNMP(key, os, ip, oid):
    check_result = 'unknown'
    retry = 0
    while retry < 3:
        check_result = query_snmp(key, os, ip, oid)
        if check_result == 'ERR':
            retry += 1
        else:
            break

    return check_result

def get_snmp_Info():
    d1_cnt, d1_cisco_nx_cnt, d1_cisco_ios_cnt, d1_arista_cnt, d1_arista_mg_cnt, d1_citrix_cnt, d1_f5_cnt, d1_ruckus_cnt, d1_alteon_cnt = 0, 0, 0, 0, 0, 0, 0, 0, 0
    d2_cnt, d2_cisco_nx_cnt, d2_cisco_ios_cnt, d2_arista_cnt, d2_arista_mg_cnt, d2_citrix_cnt, d2_f5_cnt, d2_ruckus_cnt, d2_alteon_cnt = 0, 0, 0, 0, 0, 0, 0, 0, 0
    dr_cnt, dr_cisco_nx_cnt, dr_cisco_ios_cnt = 0, 0, 0
    ht_cnt, ht_cisco_ios_cnt, ht_ruckus_cnt = 0, 0, 0
    d1_unused_cnt, d1_unused_cisco_nx_cnt, d1_unused_cisco_ios_cnt, d1_unused_arista_cnt, d1_unused_arista_mg_cnt, d1_unused_citrix_cnt, d1_unused_f5_cnt, d1_unused_ruckus_cnt, d1_unused_alteon_cnt = 0, 0, 0, 0, 0, 0, 0, 0, 0
    d2_unused_cnt, d2_unused_cisco_nx_cnt, d2_unused_cisco_ios_cnt, d2_unused_arista_cnt, d2_unused_arista_mg_cnt, d2_unused_citrix_cnt, d2_unused_f5_cnt, d2_unused_ruckus_cnt, d2_unused_alteon_cnt = 0, 0, 0, 0, 0, 0, 0, 0, 0


    file_name = '/home/tossinvest/lamp/gather/device_info.json'
    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(file_name, 'rt', encoding='UTF8') as json_file:
        json_data = json.load(json_file)
        print(f'{NOW_DATETIME} || {json_data}')

    for index, value in enumerate(json_data['device_info']):
        print(f'{NOW_DATETIME} || 추가 SNMP정보 수집대상장비 idx/device >> {index} / {value}')
        ## oid 값 구분로직 추가 ##
        if value['gubn'] == 'NX-OS':
            for key in CISCO_NXOS_OIDS:
                check_result = query_snmp(key, 'NX-OS', value['ip'], CISCO_NXOS_OIDS[key])
                if check_result == 'ERR': ## SNMP 조회 ERR 발생 시 ##
                    check_result = reCheckSNMP(key, 'NX-OS', value['ip'], CISCO_NXOS_OIDS[key])

                json_data['device_info'][index].setdefault(key, check_result)
        elif value['gubn'] == 'IOS':
            for key in CISCO_IOS_OIDS:
                check_result = query_snmp(key, 'IOS', value['ip'], CISCO_IOS_OIDS[key])
                if check_result == 'ERR':  ## SNMP 조회 ERR 발생 시 ##
                    check_result = reCheckSNMP(key, 'IOS', value['ip'], CISCO_IOS_OIDS[key])

                json_data['device_info'][index].setdefault(key, check_result)
        elif value['gubn'] == 'EOS':
            for key in ARISTA_OIDS:
                check_result = query_snmp(key, 'EOS', value['ip'], ARISTA_OIDS[key])
                if check_result == 'ERR':  ## SNMP 조회 ERR 발생 시 ##
                    check_result = reCheckSNMP(key, 'EOS', value['ip'], ARISTA_OIDS[key])

                json_data['device_info'][index].setdefault(key, check_result)
        elif value['gubn'] == 'NS':
            for key in NETSCALER_OIDS:
                check_result = query_snmp(key, 'NS', value['ip'], NETSCALER_OIDS[key])
                if check_result == 'ERR':  ## SNMP 조회 ERR 발생 시 ##
                    check_result = reCheckSNMP(key, 'NS', value['ip'], NETSCALER_OIDS[key])

                json_data['device_info'][index].setdefault(key, check_result)
        elif value['gubn'] == 'ICX':
            for key in RUCKUS_OIDS:
                check_result = query_snmp(key, 'ICX', value['ip'], RUCKUS_OIDS[key])
                if check_result == 'ERR':  ## SNMP 조회 ERR 발생 시 ##
                    check_result = reCheckSNMP(key, 'ICX', value['ip'], RUCKUS_OIDS[key])

                json_data['device_info'][index].setdefault(key, check_result)
        elif value['gubn'] == 'BIG-IP':
            for key in F5_OIDS:
                check_result = query_snmp(key, 'BIG-IP', value['ip'], F5_OIDS[key])
                if check_result == 'ERR':  ## SNMP 조회 ERR 발생 시 ##
                    check_result = reCheckSNMP(key, 'BIG-IP', value['ip'], F5_OIDS[key])

                json_data['device_info'][index].setdefault(key, check_result)
        elif value['gubn'] == 'Radware':
            for key in F5_OIDS:
                check_result = query_snmp(key, 'Radware', value['ip'], ALTEON_OIDS[key])
                if check_result == 'ERR':  ## SNMP 조회 ERR 발생 시 ##
                    check_result = reCheckSNMP(key, 'Radware', value['ip'], ALTEON_OIDS[key])

                json_data['device_info'][index].setdefault(key, check_result)

    ## stack 장비정보 수집
    ## 사무실, 논현센터 CTI,전용선스위치,망분리스위치
    stack_devices = [item for item in json_data['device_info'] if item['hostname'][15:17] == '91' and not item['vendor'] == 'ARISTA']
    data_count = len(json_data['device_info'])
    print(f'{NOW_DATETIME} || Stack_devices >> {stack_devices}')

    for idx, device in enumerate(stack_devices):
        stack_count = getMultiSnmpResultQuery(device['ip'], device['gubn'])
        print(f"{NOW_DATETIME} || Stack count >> {device['ip']} {device['hostname']}-{stack_count}")

        for i in range(0, stack_count):
            if i == 0: continue
            if device['gubn'] == 'IOS':
                data_count += 1
                stack_serial_no = query_snmp('stack_serial_no', 'IOS', device['ip'], CISCO_IOS_STACK_SERIAL_NO_OIDS[i])
                stack_model = query_snmp('stack_model', 'IOS', device['ip'], CISCO_IOS_STACK_MODEL_OIDS[i])
                stack_hostname = replaceAtIndex(device['hostname'], 16, str(i + 1))

                stack_data = {
                    'ip': device['ip'],
                    'location': device['location'],
                    'vendor': device['vendor'],
                    'gubn': device['gubn'],
                    'id': data_count,
                    'hostname': stack_hostname,
                    'serialno': stack_serial_no,
                    'osversion': device['osversion'],
                    'uptime': device['uptime'],
                    'model': stack_model
                }

                json_data['device_info'].append(stack_data)
            elif device['gubn'] == 'ICX':
                data_count += 1
                stack_serial_no = query_snmp('stack_serial_no', 'ICX', device['ip'], RUCKUS_STACK_SERIAL_NO_OIDS[i])
                stack_model = query_snmp('stack_model', 'ICX', device['ip'], RUCKUS_STACK_MODEL_OIDS[i])
                stack_hostname = replaceAtIndex(device['hostname'], 16, str(i + 1))

                stack_data = {
                    'ip': device['ip'],
                    'location': device['location'],
                    'vendor': device['vendor'],
                    'gubn': device['gubn'],
                    'id': data_count,
                    'hostname': stack_hostname,
                    'serialno': stack_serial_no,
                    'osversion': device['osversion'],
                    'uptime': device['uptime'],
                    'model': stack_model
                }

                json_data['device_info'].append(stack_data)
            print(f'{NOW_DATETIME} || Stack Data >> {stack_data}')


    ## 장비수량 계산로직 => 개선필요
    for value in json_data['device_info']:
        ## dc2 유휴장비 구분 ##
        if '10.76.205.' in value['ip']:
            d2_unused_cnt = d2_unused_cnt + 1
            if value['vendor'] == 'CISCO':
                if value['gubn'] == 'NX-OS':
                    d2_unused_cisco_nx_cnt = d2_unused_cisco_nx_cnt + 1
                elif value['gubn'] == 'IOS':
                    d2_unused_cisco_ios_cnt = d2_unused_cisco_ios_cnt + 1
            elif value['vendor'] == 'ARISTA':
                if value['model'] == 'DCS-7010TX-48':
                    d2_unused_arista_mg_cnt = d2_unused_arista_mg_cnt + 1
                else:
                    d2_unused_arista_cnt = d2_unused_arista_cnt + 1
            elif value['vendor'] == 'CITRIX':
                d2_unused_citrix_cnt = d2_unused_citrix_cnt + 1
            elif value['vendor'] == 'F5':
                d2_unused_f5_cnt = d2_unused_f5_cnt + 1
            elif value['vendor'] == 'RUCKUS':
                d2_unused_ruckus_cnt = d2_unused_ruckus_cnt + 1
            elif value['vendor'] == 'ALTEON':
                d2_unused_alteon_cnt = d2_unused_alteon_cnt + 1
        ## dc1 유휴장비 구분 ##
        elif '172.21.205.' in value['ip']:
            d1_unused_cnt = d1_unused_cnt + 1
            if value['vendor'] == 'CISCO':
                if value['gubn'] == 'NX-OS':
                    d1_unused_cisco_nx_cnt = d1_unused_cisco_nx_cnt + 1
                elif value['gubn'] == 'IOS':
                    d1_unused_cisco_ios_cnt = d1_unused_cisco_ios_cnt + 1
            elif value['vendor'] == 'ARISTA':
                if value['model'] == 'DCS-7010TX-48':
                    d1_unused_arista_mg_cnt = d1_unused_arista_mg_cnt + 1
                else:
                    d1_unused_arista_cnt = d1_unused_arista_cnt + 1
            elif value['vendor'] == 'CITRIX':
                d1_unused_citrix_cnt = d1_unused_citrix_cnt + 1
            elif value['vendor'] == 'F5':
                d1_unused_f5_cnt = d1_unused_f5_cnt + 1
            elif value['vendor'] == 'RUCKUS':
                d1_unused_ruckus_cnt = d1_unused_ruckus_cnt + 1
            elif value['vendor'] == 'ALTEON':
                d1_unused_alteon_cnt = d1_unused_alteon_cnt + 1
        else:
            if value['location'] == 'd1':
                d1_cnt = d1_cnt + 1
                if value['vendor'] == 'CISCO':
                    if value['gubn'] == 'NX-OS':
                        d1_cisco_nx_cnt = d1_cisco_nx_cnt + 1
                    elif value['gubn'] == 'IOS':
                        d1_cisco_ios_cnt = d1_cisco_ios_cnt + 1
                elif value['vendor'] == 'ARISTA':
                    if value['model'] == 'DCS-7010TX-48':
                        d1_arista_mg_cnt = d1_arista_mg_cnt + 1
                    else:
                        d1_arista_cnt = d1_arista_cnt + 1
                elif value['vendor'] == 'CITRIX':
                    d1_citrix_cnt = d1_citrix_cnt + 1
                elif value['vendor'] == 'F5':
                    d1_f5_cnt = d1_f5_cnt + 1
                elif value['vendor'] == 'RUCKUS':
                    d1_ruckus_cnt = d1_ruckus_cnt + 1
                elif value['vendor'] == 'ALTEON':
                    d1_alteon_cnt = d1_alteon_cnt + 1
            elif value['location'] == 'd2':
                d2_cnt = d2_cnt + 1
                if value['vendor'] == 'CISCO':
                    if value['gubn'] == 'NX-OS':
                        d2_cisco_nx_cnt = d2_cisco_nx_cnt + 1
                    elif value['gubn'] == 'IOS':
                        d2_cisco_ios_cnt = d2_cisco_ios_cnt + 1
                elif value['vendor'] == 'ARISTA':
                    if value['model'] == 'DCS-7010TX-48':
                        d2_arista_mg_cnt = d2_arista_mg_cnt + 1
                    else:
                        d2_arista_cnt = d2_arista_cnt + 1
                elif value['vendor'] == 'CITRIX':
                    d2_citrix_cnt = d2_citrix_cnt + 1
                elif value['vendor'] == 'F5':
                    d2_f5_cnt = d2_f5_cnt + 1
                elif value['vendor'] == 'RUCKUS':
                    d2_ruckus_cnt = d2_ruckus_cnt + 1
                elif value['vendor'] == 'ALTEON':
                    d2_alteon_cnt = d2_alteon_cnt + 1
            elif value['location'] == 'dr':
                dr_cnt = dr_cnt + 1
                if value['vendor'] == 'CISCO':
                    if value['gubn'] == 'NX-OS':
                        dr_cisco_nx_cnt = dr_cisco_nx_cnt + 1
                    elif value['gubn'] == 'IOS':
                        dr_cisco_ios_cnt = dr_cisco_ios_cnt + 1
            elif value['location'] == 'ht':
                ht_cnt = ht_cnt + 1
                if value['vendor'] == 'CISCO':
                    ht_cisco_ios_cnt = ht_cisco_ios_cnt + 1
                elif value['vendor'] == 'RUCKUS':
                    ht_ruckus_cnt = ht_ruckus_cnt + 1

    json_data['total_cnt'] = len(json_data['device_info'])

    json_data['d1_cnt'] = d1_cnt
    json_data['d1_cisco_nx_cnt'] = d1_cisco_nx_cnt
    json_data['d1_cisco_ios_cnt'] = d1_cisco_ios_cnt
    json_data['d1_arista_cnt'] = d1_arista_cnt
    json_data['d1_arista_mg_cnt'] = d1_arista_mg_cnt
    json_data['d1_citrix_cnt'] = d1_citrix_cnt
    json_data['d1_f5_cnt'] = d1_f5_cnt
    json_data['d1_ruckus_cnt'] = d1_ruckus_cnt
    json_data['d1_alteon_cnt'] = d1_alteon_cnt

    json_data['d2_cnt'] = d2_cnt
    json_data['d2_cisco_nx_cnt'] = d2_cisco_nx_cnt
    json_data['d2_cisco_ios_cnt'] = d2_cisco_ios_cnt
    json_data['d2_arista_cnt'] = d2_arista_cnt
    json_data['d2_arista_mg_cnt'] = d2_arista_mg_cnt
    json_data['d2_citrix_cnt'] = d2_citrix_cnt
    json_data['d2_f5_cnt'] = d2_f5_cnt
    json_data['d2_ruckus_cnt'] = d2_ruckus_cnt
    json_data['d2_alteon_cnt'] = d2_alteon_cnt

    json_data['dr_cnt'] = dr_cnt
    json_data['dr_cisco_nx_cnt'] = dr_cisco_nx_cnt
    json_data['dr_cisco_ios_cnt'] = dr_cisco_ios_cnt

    json_data['ht_cnt'] = ht_cnt
    json_data['ht_cisco_ios_cnt'] = ht_cisco_ios_cnt
    json_data['ht_ruckus_cnt'] = ht_ruckus_cnt

    json_data['d2_unused_cnt'] = d2_unused_cnt
    json_data['d2_unused_cisco_nx_cnt'] = d2_unused_cisco_nx_cnt
    json_data['d2_unused_cisco_ios_cnt'] = d2_unused_cisco_ios_cnt
    json_data['d2_unused_arista_cnt'] = d2_unused_arista_cnt
    json_data['d2_unused_arista_mg_cnt'] = d2_unused_arista_mg_cnt
    json_data['d2_unused_citrix_cnt'] = d2_unused_citrix_cnt
    json_data['d2_unused_f5_cnt'] = d2_unused_f5_cnt
    json_data['d2_unused_ruckus_cnt'] = d2_unused_ruckus_cnt
    json_data['d2_unused_alteon_cnt'] = d2_unused_alteon_cnt

    json_data['d1_unused_cnt'] = d1_unused_cnt
    json_data['d1_unused_cisco_nx_cnt'] = d1_unused_cisco_nx_cnt
    json_data['d1_unused_cisco_ios_cnt'] = d1_unused_cisco_ios_cnt
    json_data['d1_unused_arista_cnt'] = d1_unused_arista_cnt
    json_data['d1_unused_arista_mg_cnt'] = d1_unused_arista_mg_cnt
    json_data['d1_unused_citrix_cnt'] = d1_unused_citrix_cnt
    json_data['d1_unused_f5_cnt'] = d1_unused_f5_cnt
    json_data['d1_unused_ruckus_cnt'] = d1_unused_ruckus_cnt
    json_data['d1_unused_alteon_cnt'] = d1_unused_alteon_cnt

    print(f'{NOW_DATETIME} || Final Result : {json_data}')
    with open(file_name, 'w') as json_file:
        data = json.dump(json_data, json_file, indent=4)

    ## ITSM 자산내역 불러오기 ##
    itsm_network_devices = get_itsm_network_devices()
    # print('itsm devices >> ', itsm_network_devices)

    itsm_serialno = []
    for idx, device in enumerate(itsm_network_devices):
        ## 무선 // 샤시모듈 자산 예외처리 ##
        if device['모델'] == 'Ruckus 650' or device['모델'] == 'RUCKUS SmartZone 104' or device[
            '모델'] == 'N9K-X97160YC-EX' or device['시리얼'] == 'SR190225S029': continue
        itsm_serialno.append(device['시리얼'])

    payload = {
        "sender": "mg-net03",
        "webHookUrl": "https://hooks.slack.com/services/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",
        "payload": {
            "icon_emoji": ":robot:",
            "text": "네트워크 데일리점검",
            "username": "네트워크관리봇",
            "channel": SLACK_CHANNEL,
            # "channel": "network-webhook-test",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": ":check_blue: 네트워크 자산현황 :check_blue:"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f":credit: `장비수량` *ITSM : {len(itsm_serialno)} // LAMP : {json_data['total_cnt']}*"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"`!!자산관리 버그 수정 및 업데이트 중!! 데이터가 맞지않을 수 있음`"
                        },
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":idc: `dc1 전체수량` : *{json_data['d1_cnt']}*"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Cisco* [NX-OS] : {json_data['d1_cisco_nx_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Cisco* [IOS] : {json_data['d1_cisco_ios_cnt']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Arista* : {json_data['d1_arista_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Arista* [7010-UTP] : {json_data['d1_arista_mg_cnt']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Citrix* [L7]: {json_data['d1_citrix_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *F5*  [GSLB]: {json_data['d1_f5_cnt']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Ruckus* : {json_data['d1_ruckus_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Alteon* [L4]: {json_data['d1_alteon_cnt']}"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":idc: `dc2 전체수량` : *{json_data['d2_cnt']}*"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Cisco* [NX-OS] : {json_data['d2_cisco_nx_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Cisco* [IOS] : {json_data['d2_cisco_ios_cnt']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Arista* : {json_data['d2_arista_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Arista* [7010-UTP] : {json_data['d2_arista_mg_cnt']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Citrix* [L7] : {json_data['d2_citrix_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *F5* [GSLB]: {json_data['d2_f5_cnt']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Ruckus* : {json_data['d2_ruckus_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Alteon* [L4] : {json_data['d2_alteon_cnt']}"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":idc: `dr 전체수량` : *{json_data['dr_cnt']}*"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Cisco* [NX-OS] : {json_data['dr_cisco_nx_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Cisco* [IOS] : {json_data['dr_cisco_ios_cnt']}"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":office: `한타 전체수량` : *{json_data['ht_cnt']}*"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Cisco* [IOS] : {json_data['ht_cisco_ios_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Ruckus* : {json_data['ht_ruckus_cnt']}"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":zzz: `dc1 유휴 전체수량` : *{json_data['d1_unused_cnt']}*"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Cisco* [NX-OS] : {json_data['d1_unused_cisco_nx_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Cisco* [IOS] : {json_data['d1_unused_cisco_ios_cnt']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Arista* : {json_data['d1_unused_arista_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Arista* [7010-UTP] : {json_data['d1_unused_arista_mg_cnt']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Citrix* [L7] : {json_data['d1_unused_citrix_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *F5* [GSLB] : {json_data['d1_unused_f5_cnt']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Ruckus* : {json_data['d1_unused_ruckus_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Alteon* [L4] : {json_data['d1_unused_alteon_cnt']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":zzz: `dc2 유휴 전체수량` : *{json_data['d2_unused_cnt']}*"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Cisco* [NX-OS] : {json_data['d2_unused_cisco_nx_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Cisco* [IOS] : {json_data['d2_unused_cisco_ios_cnt']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Arista* : {json_data['d2_unused_arista_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Arista* [7010-UTP] : {json_data['d2_unused_arista_mg_cnt']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Citrix* [L7] : {json_data['d2_unused_citrix_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *F5* [GSLB] : {json_data['d2_unused_f5_cnt']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"● *Ruckus* : {json_data['d2_unused_ruckus_cnt']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"● *Alteon* [L4] : {json_data['d2_unused_alteon_cnt']}"
                        }
                    ]
                }
            ]
        }
    }
    print('{NOW_DATETIME} || [MGMT] sended message to slack-channel!! >>>')
    requests.post(SLACK_PROXY_URL, json=payload)


def sendSlackChannel(gubn, channel, main_text, message_body, image_url):
    username, icon_emoji = "", ""
    if gubn == "zabbix":
        username = "Network Zabbix Alert"
        icon_emoji = ":zabbix:"
    elif gubn == "grafana":
        username = "Network Grafana Alert"
        icon_emoji = ":grafana:"
    elif gubn == "119":
        username = "Network Zabbix Alert"
        icon_emoji = ":robot:"

    headers = {
        'accept': '*/*',
        'Content-Type': 'application/json',
    }

    params = (
        ('url', 'https://hooks.slack.com/services/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'),
    )

    json_data = {
        "channel": channel,
        "icon_emoji": icon_emoji,
        "text": main_text,
        "username": username,
        "attachments": [message_body]
    }

    try:
        response = requests.post('http://slack-message-gateway.live.tossinvest.bz/api/v1/slack/proxy', headers=headers,
                                 params=params, json=json_data)
    except requests.exceptions.Timeout as errd:
        print(f"{NOW_DATETIME} || Timeout Error!! : ", errd)
    except requests.exceptions.ConnectionError as errc:
        print(f"{NOW_DATETIME} || Connecting Error!! : ", errc)
    except requests.exceptions.HTTPError as errb:
        print(f"{NOW_DATETIME} || Http Error!! : ", errb)
    except requests.exceptions.RequestException as erra:
        print(f"{NOW_DATETIME} || Http Error!! : ", erra)
def get(target, oids, credentials, port=161, engine=hlapi.SnmpEngine(), context=hlapi.ContextData()):
    handler = hlapi.getCmd(
        engine,
        credentials,
        hlapi.UdpTransportTarget((target, port)),
        context,
        *construct_object_types(oids)
    )
    return fetch(handler, 1)[0]

def construct_object_types(list_of_oids):
    object_types = []
    for oid in list_of_oids:
        object_types.append(hlapi.ObjectType(hlapi.ObjectIdentity(oid)))

    return object_types

def fetch(handler, count):
    result = []
    for i in range(count):
        try:
            error_indication, error_status, error_index, var_binds = next(handler)
            if not error_indication and not error_status:
                items = {}
                for var_bind in var_binds:
                    items[str(var_bind[0])] = cast(var_bind[1])
                result.append(items)
            else:
                raise RuntimeError('Got SNMP error: (0)'.format(error_index))
        except StopIteration:
            break
    return result

def cast(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        try:
            return float(value)
        except (ValueError, TypeError):
            try:
                return str(value)
            except (ValueError, TypeError):
                pass
    return value

def testCheckSNMP():
    # print('testchecksnmp')
    # g = getCmd(
    #     SnmpEngine(), CommunityData('Wwfbs365%'), UdpTransportTarget(
    #         ('10.76.205.11', 161), timeout=0.5, retries=0), ContextData(), ObjectType(
    #         ObjectIdentity(ALTEON_OSVERSION_OID)
    #     )
    # )
    #
    # errorIndication, errorStatus, errorIndex, varBinds = next(g)
    # # print(f'errorIndication : {errorIndication}')
    # # print(f'errorStatus : {errorStatus}')
    # # print(f'errorIndex : {errorIndex}')
    #
    # if errorIndication or errorStatus or errorIndex:
    #     return print('err')
    # else:
    #     for varBind in varBinds:
    #         print(f'[varBind contents] >>> {varBind}')
    #         temp = ' ='.join([x.prettyPrint() for x in varBind])
    #         idx = temp.find('=')
    #         snmp_result = temp[idx + 1:]
    #         print(f'Result : {snmp_result}')
    #         ## Cisco IOS 검증 ##
    #
    # host = 'ht-i-us-5F02-sw11'

    # SNMP parameters
    target_host = '172.21.200.110'  # Replace with your target SNMP device's IP address
    community = 'Wwfbs365%'  # Replace with your SNMP community string
    port = 161  # Default SNMP port

    # SNMP GETBULK operation
    iterator = nextCmd(
        SnmpEngine(),
        CommunityData(community),
        UdpTransportTarget((target_host, port)),
        ContextData(),
        ObjectType(ObjectIdentity('1.3.6.1.4.1.9.9.500.1.2.1.1.6')),
        lexicographicMode=False # Replace with the OID you want to start from
    )

    stack_count = 0
    print(iterator)
    for errorIndication, errorStatus, errorIndex, varBinds in iterator:
        if errorIndication:
            print(f"SNMP operation failed: {errorIndication}")
            break
        elif errorStatus:
            print(f"SNMP error: {errorStatus} at {errorIndex}")
            break
        else:
            stack_count += 1
            # print(varBinds)
            # for varBind in varBinds:
            #     print(f"OID: {varBind[0]}, Value: {varBind[1]}")

    print(f'{NOW_DATETIME} || stack_count : {stack_count}')


def replaceAtIndex(hostname, index, replacement):
    if index < 0 or index >= len(hostname):
        return hostname
    else:
        return hostname[:index] + replacement + hostname[index + len(replacement):]

def getMultiSnmpResultQuery(strIP, gubn):
    # SNMP parameters
    # target_host = '10.79.13.12'  # Replace with your target SNMP device's IP address
    print(f'{NOW_DATETIME} || [getMultiSnmpResultQuery] start >> IP : {strIP} gubn : {gubn}')
    community = 'Wwfbs365%'  # Replace with your SNMP community string
    port = 161  # Default SNMP port
    oid = ''
    # SNMP GETBULK operation
    if gubn == 'IOS':
        oid = '1.3.6.1.4.1.9.9.500.1.2.1.1.6'
    elif gubn == 'ICX':
        oid = '1.3.6.1.4.1.1991.1.1.1.2.2.1.1'
    iterator = nextCmd(
        SnmpEngine(),
        CommunityData(community),
        UdpTransportTarget((strIP, port)),
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
        lexicographicMode=False  # Replace with the OID you want to start from
    )
    print(f'{NOW_DATETIME} || getMultiSnmpResultQuery Done strIP, gubn >> {strIP}, {gubn}, {iterator}')
    stack_count = 0
    for errorIndication, errorStatus, errorIndex, varBinds in iterator:
        if errorIndication:
            print(f"{NOW_DATETIME} || SNMP operation failed: {errorIndication}")
            break
        elif errorStatus:
            print(f"{NOW_DATETIME} || SNMP error: {errorStatus} at {errorIndex}")
            break
        else:
            stack_count += 1
            # for varBind in varBinds:
            #     print(f"OID: {varBind[0]}, Value: {varBind[1]}")

    return stack_count

def testNetmiko():
    connection_info = {
        # 'device_type': 'cisco_nxos',
        # 'device_type': 'cisco_ios',
        'device_type': 'arista_eos',
        # 'device_type': 'netscaler',
        # 'host': '172.21.200.12', ## nx-os
        # 'host': '172.21.200.24', ## ios
        'host': '172.21.200.176',  ## eos
        # 'host': '172.21.200.115',  ## eos
        'username': NETWORK_ID,
        # 'username': 'nsroot',
        'password': NETWORK_PASSWD,
        'port': 22,
        # 'secret': NETWORK_PASSWD
    }

    ssh = ConnectHandler(**connection_info)
    ssh.enable()
    cmd_list = [
        'show ip route'
    ]

    for idx, cmd in enumerate(cmd_list):
        command = ssh.send_command(cmd, use_textfsm=True)
        print('{NOW_DATETIME} || success!')
        # json_data = json.loads(command)
        # print('command result all >>', {json.dumps(command, indent=2)})
        print(f"{NOW_DATETIME} || command.split('\\n')")
        # print('type >>', type(command))
        if type(command) is str: continue
        else:
            for idx, data in enumerate(command):
                # if data['proto'] != 'down' and data['ipaddr'] != 'unassigned' :
                print(f"{NOW_DATETIME} || data.split('\n')")
                # print(f'{json.dumps(data.split("\n"), indent=2)}')

def getNetmiko():
    file_name = '/home/tossinvest/lamp/gather/device_info.json'
    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(file_name, 'rt', encoding='UTF8') as json_file:
        json_data = json.load(json_file)
        # print(f'{json_data}')
    device_type = ''
    device_ip = ''
    result = []
    for index, value in enumerate(json_data['device_info']):
        print(f'{NOW_DATETIME} || Target idx/device >> {index} / {value}')
        ## oid 값 구분로직 추가 ##
        # if value['gubn'] == 'NX-OS': device_type = 'cisco_nxos'
        # elif value['gubn'] == 'IOS': device_type = 'cisco_ios'
        # elif value['gubn'] == 'EOS': device_type = 'arista_eos'
        if value['gubn'] == 'NX-OS':
            device_type = 'cisco_nxos'
        else : continue

        connection_info = {
            'device_type': device_type,
            'host': value['ip'],
            'username': NETWORK_ID,
            'password': NETWORK_PASSWD,
            'port': 22,
            'secret': NETWORK_PASSWD
        }

        ssh = ConnectHandler(**connection_info)
        ssh.enable()
        cmd_list = [
            'show ip interface brief'
        ]

        for idx, cmd in enumerate(cmd_list):
            output = ssh.send_command(cmd, use_textfsm=True)
            print(f'{NOW_DATETIME} || command result all >> {json.dumps(output, indent=2)}')
            if type(output) is str:continue
            else:
                for idx, data in enumerate(output):
                    print(f'{NOW_DATETIME} || command result >> {data}')
                    result.append({'ip':data['ipaddr'], 'hostname':value['hostname']})

            # if idx == 0:  # vlan 정보 get
            #     for idx, value in enumerate(command):
            #         if value['status'] == 'active':
            #             dicTemp = {'vlan_no': value['vlan_id'], 'name': value['name']}
            #             arr_vlan.append(dicTemp)
            # elif idx == 1:  # port vlan 정보 get
            #     # print(json.dumps(command, indent=2))
            #     arr_int_vlan = command

    print(f'{NOW_DATETIME} || result >> {json.dumps(result, indent=2)}')
    # return HttpResponse(json.dumps(result, ensure_ascii=False), content_type="application/json")

def get_netmiko_result():
    ip_info_file = '/home/tossinvest/lamp/gather/ip_info.json'
    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(ip_info_file, 'rt', encoding='UTF8') as json_file:
        ip_info_json_data = json.load(json_file)

    arp_info_file = '/home/tossinvest/lamp/gather/arp_info.json'
    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(arp_info_file, 'rt', encoding='UTF8') as json_file:
        arp_info_json_data = json.load(json_file)

    mac_info_file = '/home/tossinvest/lamp/gather/mac_info.json'
    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(mac_info_file, 'rt', encoding='UTF8') as json_file:
        mac_info_json_data = json.load(json_file)

    routing_info_file = '/home/tossinvest/lamp/gather/routing_info.json'
    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(routing_info_file, 'rt', encoding='UTF8') as json_file:
        routing_info_json_data = json.load(json_file)

    interface_info_file = '/home/tossinvest/lamp/gather/interface_info.json'
    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(interface_info_file, 'rt', encoding='UTF8') as json_file:
        interface_info_json_data = json.load(json_file)

    device_info_file = '/home/tossinvest/lamp/gather/device_info.json'
    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(device_info_file, 'rt', encoding='UTF8') as json_file:
        device_info_json_data = json.load(json_file)

    device_type, device_ip = '', ''
    ip_result, arp_info, mac_info, interface_status, route_info, host_info, location, hostname, vendor, model = [], [], [], [], [], [], [], [], [], []
    arista_ip_result, arista_arp_info, arista_mac_info, arista_interface_status, arista_route_info, arista_host_info, arista_location, arista_hostname, arista_vendor, arista_model = [], [], [], [], [], [], [], [], [], []

    ## cmd 순서대로 멀티스레드 진행
    ip_brief_table_id, interface_status_table_id, arp_table_id, mac_table_id, route_table_id = 1, 1, 1, 1, 1

    ##################################
    ## netmiko 장비 접속을 위한 대상 정의 ##
    ##################################
    for i, value in enumerate(device_info_json_data['device_info']):
        ## 유휴장비대역 예외처리 ##
        ## dc1 OP스위치 예외처리 => 방화벽 정책 오픈 안되어 임시 예외 editing ##
        if value['ip'][0:9] == '10.76.205' or value['ip'][0:10] == '172.21.205' : continue
        else:
            ## NXOS는 show ip interface brief 명령어로 MGMT IP 조회가 안됨 ##
            ## 그래서 device_info.json에 MGMT IP를 미리 가져옴 ##
            if value['gubn'] == 'NX-OS' :
                device_type = 'cisco_nxos'
                ip_result.append(
                    {
                        'id': ip_brief_table_id,
                        'location': value['location'],
                        'hostname': value['hostname'],
                        'ip': value['ip'],
                        'interface': 'MGMT'
                    }
                )
                ip_brief_table_id += 1
            elif value['gubn'] == 'IOS' :
                device_type = 'cisco_ios'
            ## arista는 api로 대체 개발
            ## arista일 경우 다른 쓰레드를 사용하도록 배열 분개
            elif value['gubn'] == 'EOS' :
                device_type = 'arista_eos'
                host = {
                    'device_type' : device_type,
                    'host': value['ip']
                }
                arista_host_info.append(host)
                arista_location.append(value['location'])
                arista_hostname.append(value['hostname'])
                arista_vendor.append(value['vendor'])
                arista_model.append(value['model'])
                continue
            else : continue
            host = {
                'device_type': device_type,
                'host': value['ip'],
                'username': NETWORK_ID,
                'password': NETWORK_PASSWD,
                'port': 22,
                'secret': NETWORK_PASSWD
                # 'hosname': value['hostname']
            }
            host_info.append(host)
            location.append(value['location'])
            hostname.append(value['hostname'])
            vendor.append(value['vendor'])
            model.append(value['model'])


    # starting_time = time.perf_counter()

    # cmd = [
    #     'show ip interface brief',
    #     'show int status',
    #     'show ip arp'
    # ]

    ## netmiko를 사용한 정보 수집 ##
    print(f'{NOW_DATETIME} || netmiko connect start >> ')

    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = executor.map(open_connection, host_info, location, hostname, vendor, model)
        print(f'{NOW_DATETIME} || [open_connection] results >> {results}')

        # print('results >> ', results)
        for idx, tuple in enumerate(results):
            # print('data >> ', tuple) ## data type >> tuple
            target_location, target_hostname, target_device_type, target_vendor, target_model = '', '', '', '', ''
            for idx, data in enumerate(tuple):
                ## 대상장비정보 index ##
                if idx == 0:
                    target_location = data['location']
                    target_hostname = data['hostname']
                    target_device_type = data['device_type']
                    target_vendor = data['vendor']
                    target_model = data['model']
                elif idx == 1:
                    i = 0
                    while i < len(data):
                        #################################
                        ## show ip interface brief 결과 ##
                        #################################
                        if i == 0 :
                            # print('interface 결과 >>>> ', target_hostname, target_device_type, data[i])
                            if type(data[i]) is list:
                                for idx, value in enumerate(data[i]):
                                    # print('show ip interface brief >> ', value)
                                    ip, interface = showIpInterfaceBrief(target_device_type, value)
                                    if ip != '' and interface != '':
                                        ip_result.append({'id':ip_brief_table_id, 'location':target_location, 'hostname':target_hostname, 'ip': ip, 'interface':interface})
                                        ip_brief_table_id += 1
                            i += 1
                        #########################
                        ## show int status 결과 ##
                        #########################
                        elif i == 1:
                            # print('int status 결과 >>>> ', target_hostname, target_device_type, data[i])
                            if type(data[i]) is list:
                                for idx, value in enumerate(data[i]):
                                    # print('show int status >> ', value)
                                    value['id'] = interface_status_table_id
                                    value['location'] = target_location
                                    value['hostname'] = target_hostname
                                    value['vendor'] = target_vendor
                                    value['model'] = target_model
                                    value['idx'] = idx
                                    interface_status.append(value)
                                    interface_status_table_id += 1
                            i += 1
                        #####################
                        ## show ip arp 결과 ##
                        #####################
                        elif i == 2:
                            # print('arp 결과 >>>> ', target_hostname, target_device_type, data[i])
                            if type(data[i]) is list:
                                for idx, value in enumerate(data[i]):
                                    # print('cisco arp >>> ', target_hostname, value)
                                    value['id'] = arp_table_id
                                    value['location'] = target_location
                                    value['hostname'] = target_hostname

                                    arp_info.append(value)
                                    arp_table_id += 1
                            elif target_device_type == 'arista_eos' and type(data[i]) is str and len(data[i]) > 10 :  ## nxos arp 없을 경우 str로 반환하기때문에device_type arista 지정
                                # print('arista arp >>> ', target_hostname, data[i])
                                for idx, row in enumerate(data[i].split('\n')):
                                    if idx != 0 :
                                        dicTemp = {
                                            'id' : arp_table_id,
                                            'location' : target_location,
                                            'hostname' : target_hostname,
                                            'address' : re.split('\s+', row)[0],
                                            'age' : re.split('\s+', row)[1],
                                            'mac' : re.split('\s+', row)[2],
                                            'interface': re.split('\s+', row)[3][-1:],
                                        }
                                        # print('conver data >> ', dicTemp)
                                        arp_info.append(dicTemp)
                                    arp_table_id += 1
                            i += 1
                        ##########################
                        ## show mac address 결과 ##
                        ##########################
                        elif i == 3:
                            # print('mac addr 결과 >>>> ', target_hostname, target_device_type, data[i])
                            if type(data[i]) is list:
                                for idx, value in enumerate(data[i]):
                                    mac, mac_type, vlan, port = showMacAddress(target_device_type, value)

                                    dicTemp = {
                                        'id': mac_table_id,
                                        'location': target_location,
                                        'hostname': target_hostname,
                                        'mac': mac,
                                        'type': mac_type,
                                        'vlan': vlan,
                                        'port': port,
                                    }
                                    # print('conver data >> ', dicTemp)

                                    mac_info.append(dicTemp)
                                    mac_table_id += 1
                            i += 1
                        #######################
                        ## show ip route 결과 ##
                        #######################
                        elif i == 4:
                            # print('route 결과 >>>> ', target_hostname, target_device_type, data[i])
                            if type(data[i]) is list:
                                for idx, value in enumerate(data[i]):
                                    network, mask, next_hop, interface, distance = showIpRoute(target_device_type, value)

                                    dicTemp = {
                                        'id': route_table_id,
                                        'location': target_location,
                                        'hostname': target_hostname,
                                        'network': network,
                                        'mask': mask,
                                        'next_hop': next_hop,
                                        'interface': interface,
                                        'distance': distance
                                    }
                                    # print('conver data >> ', dicTemp)

                                    route_info.append(dicTemp)
                                    route_table_id += 1
                            i += 1

    print(f'{NOW_DATETIME} || netmiko connect end >> ')
    # print('int status >> ', interface_status)
    # print('arp info >> ', json.dumps(arp_info, indent=2))

    ## ARISTA API를 사용한 정보 수집 ##
    print(f'{NOW_DATETIME} || ARISTA API start >> ')
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = executor.map(get_arista_api_result, arista_host_info, arista_location, arista_hostname, arista_vendor, arista_model)
        print(f'arista_api_test : {results}')

    ## 보안장비 등록정보 조회 후 관리IP 등록 ##
    nse_device_info_file = '/home/tossinvest/lamp/gather/nse_device_info.json'
    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(nse_device_info_file, 'rt', encoding='UTF8') as json_file:
        nse_device_info_json_data = json.load(json_file)

    ip_idx = len(ip_result)
    print(f'{NOW_DATETIME} || nse_data >> ', nse_device_info_json_data)
    for i, value in enumerate(nse_device_info_json_data['device_info']):
        ip_idx += 1
        nse_temp = {
            "id" : ip_idx,
            "location" : value['location'],
            "hostname" : value['hostname'],
            "ip" : value['ip'],
            "interface" : "MGMT"
        }
        ip_result.append(nse_temp)

    print(f'{NOW_DATETIME} || ip_result >> ', ip_result)
    temp = {
        'data':ip_result
    }
    with open(ip_info_file, 'w') as json_file:
        data = json.dump(temp, json_file, indent=4)

    temp = {
        'data':interface_status
    }
    with open(interface_info_file, 'w') as json_file:
        data = json.dump(temp, json_file, indent=4)

    temp = {
        'data':arp_info
    }
    with open(arp_info_file, 'w') as json_file:
        data = json.dump(temp, json_file, indent=4)

    temp = {
        'data':mac_info
    }
    with open(mac_info_file, 'w') as json_file:
        data = json.dump(temp, json_file, indent=4)

    temp = {
        'data': route_info
    }
    with open(routing_info_file, 'w') as json_file:
        data = json.dump(temp, json_file, indent=4)


def showIpInterfaceBrief(device_type, data):
    # print('data' >> data)
    ip, interface = '', ''
    if device_type == 'cisco_ios' or device_type == 'cisco_nxos':
        if data['proto'] != 'down' and data['ipaddr'] != 'unassigned':
            ip = data['ipaddr']
            interface = data['intf']
    elif device_type == 'arista_eos':
        ip = data['ip'][:data['ip'].find('/')]
        interface = data['interface']

    return ip, interface

def showMacAddress(device_type, data):
    # print('data' >> data)
    mac, mac_type, vlan, port = '', '', '', ''
    if device_type == 'cisco_ios':
        mac = data['destination_address']
        port = data['destination_port']
        mac_type = data['type']
        vlan = data['vlan']
    elif device_type == 'cisco_nxos':
        mac = data['mac']
        port = data['ports']
        mac_type = data['type'].upper()
        vlan = data['vlan']
    elif device_type == 'arista_eos':
        mac = data['mac_address']
        port = data['destination_port']
        mac_type = data['type']
        vlan = data['vlan']

    return mac, mac_type, vlan, port

def showIpRoute(device_type, data):
    # print('data' >> data)
    network, mask, next_hop, interface, distance = '', '', '', '', ''
    network = data['network']
    mask = data['mask']
    distance = data['distance']

    if device_type == 'cisco_ios' or device_type == 'cisco_nxos':
        if data['nexthop_ip'] == '':next_hop = 'DIRECT'
        else : next_hop = data['nexthop_ip']
        interface = data['nexthop_if']
    elif device_type == 'arista_eos':
        next_hop = data['next_hop']
        interface = data['interface']

    return network, mask, next_hop, interface, distance

def checkInterfaceUsage():
    print('')

def checkDeviceType():
    print('')


def get_arista_info_from_api():
    print(f"{NOW_DATETIME} get_arista_info_from_api >> {host}, {hostname}")
    arista_api_results = get_arista_info_from_api(host)
    results = arista_api_results['result'][1]['interfaceStatuses']

    print(f"arista_interface_statuses >> {results}")

def open_connection(host, location, hostname, vendor, model):
    # ssh connection 실패 시 총 3회 시도
    max_attempt = 3
    attempt = 0

    while attempt < max_attempt:
        try:
            # print(f"{NOW_DATETIME} open_connection_start : attempt{attempt} | {host['host']} | {hostname}")
            print(f"{NOW_DATETIME} open_connection_start | {host['host']} | {hostname} | {vendor} | {model}")
            output = []
            connection = ConnectHandler(**host)

            # print('Trying connection', host['host'], hostname)
            # print('Connection Established to host:', host['host'], hostname)
            connection.enable()
            cmd_list = [
                'show ip interface brief',
                'show int status',
                'show ip arp',
                'show mac address',
                'show ip route'
            ]

            for idx, cmd in enumerate(cmd_list):
                # print(f"{NOW_DATETIME} open_connection_idx_cmd >> {hostname}, {idx}, {cmd}")
                output.append(connection.send_command(cmd, use_textfsm=True))
                # print('output >> ', output)

            host['location'] = location
            host['hostname'] = hostname
            host['vendor'] = vendor
            host['model'] = model

            # print(f"{NOW_DATETIME} open_connection_established : attempt{attempt} | {host['host']} | {hostname}")
            print(f"{NOW_DATETIME} open_connection_established | {host['host']} | {hostname} | {vendor} | {model}")

            return host, output

        except (NetmikoTimeoutException, NetMikoAuthenticationException) as e:
            print(f"{NOW_DATETIME} Connection Failed to host : attempt{attempt} | {host['host']} | {hostname} | {vendor} | {model}")

            attempt += 1
            time.sleep(5)


@csrf_exempt
def getIP(request):
    print(f'{NOW_DATETIME} || request gather ip')
    ip_info_file = '/home/tossinvest/lamp/gather/ip_info.json'
    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(ip_info_file, 'rt', encoding='UTF8') as json_file:
        ip_info_json_data = json.load(json_file)

    for idx, data in enumerate(ip_info_json_data['data']):
        if data['hostname'] == '':
            ip_info_json_data['data'].pop(idx)

    return HttpResponse(json.dumps(ip_info_json_data, ensure_ascii=False), content_type="application/json")


def get_Interface_statistics():
    port_usage_submit_file = '/home/tossinvest/lamp/gather/port_usage_submit.json'
    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(port_usage_submit_file, 'rt', encoding='UTF8') as json_file:
        port_usage_submit_json_data = json.load(json_file)

    port_usage_file = '/home/tossinvest/lamp/gather/port_usage.json'
    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(port_usage_file, 'rt', encoding='UTF8') as json_file:
        port_usage_json_data = json.load(json_file)

    interface_info_file = '/home/tossinvest/lamp/gather/interface_info.json'
    d1_dz_10g_used_cnt, d1_dz_10g_unused_cnt, d1_dz_100g_used_cnt, d1_dz_100g_unused_cnt = 0, 0, 0, 0
    d1_ch_10g_used_cnt, d1_ch_10g_unused_cnt, d1_ch_100g_used_cnt, d1_ch_100g_unused_cnt = 0, 0, 0, 0
    d1_if_10g_used_cnt, d1_if_10g_unused_cnt, d1_if_100g_used_cnt, d1_if_100g_unused_cnt = 0, 0, 0, 0
    d1_db_10g_used_cnt, d1_db_10g_unused_cnt, d1_db_100g_used_cnt, d1_db_100g_unused_cnt = 0, 0, 0, 0
    d1_ex_10g_used_cnt, d1_ex_10g_unused_cnt, d1_ex_100g_used_cnt, d1_ex_100g_unused_cnt = 0, 0, 0, 0

    d2_dz_10g_used_cnt, d2_dz_10g_unused_cnt, d2_dz_100g_used_cnt, d2_dz_100g_unused_cnt = 0, 0, 0, 0
    d2_ch_10g_used_cnt, d2_ch_10g_unused_cnt, d2_ch_100g_used_cnt, d2_ch_100g_unused_cnt = 0, 0, 0, 0
    d2_if_10g_used_cnt, d2_if_10g_unused_cnt, d2_if_100g_used_cnt, d2_if_100g_unused_cnt = 0, 0, 0, 0
    d2_db_10g_used_cnt, d2_db_10g_unused_cnt, d2_db_100g_used_cnt, d2_db_100g_unused_cnt = 0, 0, 0, 0
    d2_ex_10g_used_cnt, d2_ex_10g_unused_cnt, d2_ex_100g_used_cnt, d2_ex_100g_unused_cnt = 0, 0, 0, 0

    ## JSON에 등록되어있는 정보를 기본 호출로 사용 ##
    with open(interface_info_file, 'rt', encoding='UTF8') as json_file:
        interface_info_json_data = json.load(json_file)

    for idx, value in enumerate(interface_info_json_data['data']):
        # print(f"location, hostname >> {value['location']}, {value['hostname']}")
        # print(f"{value['hostname'][3]} // {value['hostname'][5:7]} // {value['hostname'][13:15]}")
        #############
        #### DC1 ####
        #############
        if value['location'] == 'd1' and value['hostname'][3] == 'p' and value['hostname'][5:7] == 'dz' and (value['hostname'][13:15] == 'sw' or value['hostname'][13:15] == 'bs'):  ## dc1 운영 DMZ 존
            # print(f"location, hostname >> {value['location']}, {value['hostname']}")
            if value['model'] in DEVICE_10G_48 :
                if value['port'][0] == 'E' or value['port'][0:3] == 'Eth' or value['port'][0:2] == 'Gi':  ## 서비스 사용가능 인터페이스만 구분
                    if value['vendor'] == 'CISCO':
                        if value['idx'] > 48 :
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_dz_100g_used_cnt += 1
                            else:
                                d1_dz_100g_unused_cnt += 1
                        else :
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_dz_10g_used_cnt += 1
                            else:
                                d1_dz_10g_unused_cnt += 1
                    elif value['vendor'] == 'ARISTA':
                        if value['idx'] > 47:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_dz_100g_used_cnt += 1
                            else:
                                d1_dz_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_dz_10g_used_cnt += 1
                            else:
                                d1_dz_10g_unused_cnt += 1
                    # gubnInterface(idx, value['status'])
                    # print(f"{value['hostname']} // {value['port']}")

        elif value['location'] == 'd1' and value['hostname'][3] == 'p' and value['hostname'][5:7] == 'ch' and (value['hostname'][13:15] == 'sw' or value['hostname'][13:15] == 'bs'):  ## dc1 운영 채널계
            if value['port'][0] == 'E' or value['port'][0:3] == 'Eth' or value['port'][0:2] == 'Gi':  ## 서비스 사용가능 인터페이스만 구분
                if value['hostname'][13:15] == 'sw':
                    # print(f"location, hostname >> {value['location']}, {value['hostname']}")

                    if value['vendor'] == 'CISCO':
                        if value['idx'] > 48:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_ch_100g_used_cnt += 1
                            else:
                                d1_ch_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_ch_10g_used_cnt += 1
                            else:
                                # print(f"{value['hostname']}, {value['port']}")
                                d1_ch_10g_unused_cnt += 1
                    elif value['vendor'] == 'ARISTA':
                        if value['idx'] > 47:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_ch_100g_used_cnt += 1
                            else:
                                d1_ch_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_ch_10g_used_cnt += 1
                            else:
                                d1_ch_10g_unused_cnt += 1
                elif value['hostname'][13:15] == 'bs' :
                    r_index = value['port'].rindex('/') + 1
                    temp = int(value['port'][r_index:])

                    if temp > 48:
                        if value['status'] == "connected":  ## 사용중 여부 구분
                            d1_ch_100g_used_cnt += 1
                        else:
                            d1_ch_100g_unused_cnt += 1
                    else:
                        if value['status'] == "connected":  ## 사용중 여부 구분
                            d1_ch_10g_used_cnt += 1
                        else:
                            d1_ch_10g_unused_cnt += 1

        elif value['location'] == 'd1' and value['hostname'][3] == 'p' and (value['hostname'][5:7] == 'hd' or value['hostname'][5:7] == 'es') and (value['hostname'][13:15] == 'sw' or value['hostname'][13:15] == 'sp'):  ## dc1 운영 정보계

            if value['port'][0] == 'E' or value['port'][0:3] == 'Eth' or value['port'][0:2] == 'Gi':  ## 서비스 사용가능 인터페이스만 구분
                if value['hostname'][13:15] == 'sw':
                    if value['port'][0] == 'E' or value['port'][0:3] == 'Eth' or value['port'][0:2] == 'Gi':  ## 서비스 사용가능 인터페이스만 구분
                        if value['vendor'] == 'CISCO':
                            if value['idx'] > 48:
                                if value['status'] == "connected":  ## 사용중 여부 구분
                                    d1_if_100g_used_cnt += 1
                                else:
                                    d1_if_100g_unused_cnt += 1
                            else:
                                if value['status'] == "connected":  ## 사용중 여부 구분
                                    d1_if_10g_used_cnt += 1
                                else:
                                    d1_if_10g_unused_cnt += 1
                        elif value['vendor'] == 'ARISTA':
                            if value['idx'] > 47:
                                if value['status'] == "connected":  ## 사용중 여부 구분
                                    d1_if_100g_used_cnt += 1
                                else:
                                    d1_if_100g_unused_cnt += 1
                            else:
                                if value['status'] == "connected":  ## 사용중 여부 구분
                                    d1_if_10g_used_cnt += 1
                                else:
                                    d1_if_10g_unused_cnt += 1
                elif value['hostname'][13:15] == 'sp':
                    # print(f"{value['hostname']}, {value['port']}")
                    if value['idx'] > 32:
                        if value['status'] == "connected":  ## 사용중 여부 구분
                            d1_if_10g_used_cnt += 1
                        else:
                            d1_if_10g_unused_cnt += 1
                    else :
                        if value['status'] == "connected":  ## 사용중 여부 구분
                            d1_if_100g_used_cnt += 1
                        else:
                            d1_if_100g_unused_cnt += 1



        elif value['location'] == 'd1' and value['hostname'][3] == 'p' and value['hostname'][5:7] == 'db' and (value['hostname'][13:15] == 'sw' or value['hostname'][13:15] == 'bs'):  ## dc1 운영 원장계
            if value['port'][0] == 'E' or value['port'][0:3] == 'Eth' or value['port'][0:2] == 'Gi':  ## 서비스 사용가능 인터페이스만 구분
                if value['hostname'][13:15] == 'sw':
                    # print(f"location, hostname >> {value['location']}, {value['hostname']}")

                    if value['vendor'] == 'CISCO':
                        if value['idx'] > 48:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_db_100g_used_cnt += 1
                            else:
                                d1_db_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_db_10g_used_cnt += 1
                            else:
                                # print(f"{value['hostname']}, {value['port']}")
                                d1_db_10g_unused_cnt += 1
                    elif value['vendor'] == 'ARISTA':
                        if value['idx'] > 47:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_db_100g_used_cnt += 1
                            else:
                                d1_db_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_db_10g_used_cnt += 1
                            else:
                                d1_db_10g_unused_cnt += 1
                elif value['hostname'][13:15] == 'bs':
                    r_index = value['port'].rindex('/') + 1
                    temp = int(value['port'][r_index:])

                    if temp > 48:
                        if value['status'] == "connected":  ## 사용중 여부 구분
                            d1_db_100g_used_cnt += 1
                        else:
                            d1_db_100g_unused_cnt += 1
                    else:
                        if value['status'] == "connected":  ## 사용중 여부 구분
                            d1_db_10g_used_cnt += 1
                        else:
                            d1_db_10g_unused_cnt += 1

        elif value['location'] == 'd1' and value['hostname'][3] == 'p' and value['hostname'][5:7] == 'eb' and value['hostname'][13:15] == 'sw':  ## dc1 운영 대외계
            if value['port'][0] == 'E' or value['port'][0:3] == 'Eth' or value['port'][0:2] == 'Gi':  ## 서비스 사용가능 인터페이스만 구분
                if value['hostname'][13:15] == 'sw':
                    # print(f"location, hostname >> {value['location']}, {value['hostname']}")

                    if value['vendor'] == 'CISCO':
                        if value['idx'] > 48:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_ex_100g_used_cnt += 1
                            else:
                                d1_ex_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_ex_10g_used_cnt += 1
                            else:
                                # print(f"{value['hostname']}, {value['port']}")
                                d1_ex_10g_unused_cnt += 1
                    elif value['vendor'] == 'ARISTA':
                        if value['idx'] > 47:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_ex_100g_used_cnt += 1
                            else:
                                d1_ex_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d1_ex_10g_used_cnt += 1
                            else:
                                d1_ex_10g_unused_cnt += 1

        #############
        #### DC2 ####
        #############
        if value['location'] == 'd2' and value['hostname'][3] == 'p' and value['hostname'][5:7] == 'dz' and value['hostname'][13:15] == 'bs':  ## dc2 운영 DMZ 존
            # print(f"location, hostname >> {value['location']}, {value['hostname']}")
            if value['model'] in DEVICE_10G_48 :
                if value['port'][0] == 'E' or value['port'][0:3] == 'Eth' or value['port'][0:2] == 'Gi':  ## 서비스 사용가능 인터페이스만 구분
                    if value['vendor'] == 'CISCO':
                        if value['idx'] > 48 :
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_dz_100g_used_cnt += 1
                            else:
                                d2_dz_100g_unused_cnt += 1
                        else :
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_dz_10g_used_cnt += 1
                            else:
                                d2_dz_10g_unused_cnt += 1
                    elif value['vendor'] == 'ARISTA':
                        if value['idx'] > 47:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_dz_100g_used_cnt += 1
                            else:
                                d2_dz_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_dz_10g_used_cnt += 1
                            else:
                                d2_dz_10g_unused_cnt += 1

        elif value['location'] == 'd2' and value['hostname'][3] == 'p' and value['hostname'][5:7] == 'ch' and (value['hostname'][13:15] == 'sw' or value['hostname'][13:15] == 'bs'):  ## dc2 운영 채널계
            if value['port'][0] == 'E' or value['port'][0:3] == 'Eth' or value['port'][0:2] == 'Gi':  ## 서비스 사용가능 인터페이스만 구분
                if value['hostname'][13:15] == 'sw':
                    # print(f"location, hostname >> {value['location']}, {value['hostname']}")

                    if value['vendor'] == 'CISCO':
                        if value['idx'] > 48:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_ch_100g_used_cnt += 1
                            else:
                                d2_ch_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_ch_10g_used_cnt += 1
                            else:
                                # print(f"{value['hostname']}, {value['port']}")
                                d2_ch_10g_unused_cnt += 1
                    elif value['vendor'] == 'ARISTA':
                        if value['idx'] > 47:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_ch_100g_used_cnt += 1
                            else:
                                d2_ch_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_ch_10g_used_cnt += 1
                            else:
                                d2_ch_10g_unused_cnt += 1
                elif value['hostname'][13:15] == 'bs' :
                    if value['port'][0:4] == 'Eth1' or value['port'][0:4] == 'Eth3':    ## 40/100G 모듈
                        # print(f"{value['hostname']} // {value['port']}")
                        if value['status'] == "connected":  ## 사용중 여부 구분
                            d2_ch_100g_used_cnt += 1
                        else:
                            d2_ch_100g_unused_cnt += 1
                    else :                                                              ## 10G 모듈
                        r_index = value['port'].rindex('/') + 1
                        temp = int(value['port'][r_index:])

                        if temp > 48:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_ch_100g_used_cnt += 1
                            else:
                                d2_ch_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_ch_10g_used_cnt += 1
                            else:
                                d2_ch_10g_unused_cnt += 1

        elif value['location'] == 'd2' and value['hostname'][3] == 'p' and (value['hostname'][5:7] == 'hd' or value['hostname'][5:7] == 'es') and (value['hostname'][13:15] == 'sw' or value['hostname'][13:15] == 'sp'):  ## dc2 운영 정보계
            if value['port'][0] == 'E' or value['port'][0:3] == 'Eth' or value['port'][0:2] == 'Gi':  ## 서비스 사용가능 인터페이스만 구분
                if value['hostname'][13:15] == 'sw':
                    if value['port'][0] == 'E' or value['port'][0:3] == 'Eth' or value['port'][0:2] == 'Gi':  ## 서비스 사용가능 인터페이스만 구분
                        if value['vendor'] == 'CISCO':
                            if value['idx'] > 48:
                                if value['status'] == "connected":  ## 사용중 여부 구분
                                    d2_if_100g_used_cnt += 1
                                else:
                                    d2_if_100g_unused_cnt += 1
                            else:
                                if value['status'] == "connected":  ## 사용중 여부 구분
                                    d2_if_10g_used_cnt += 1
                                else:
                                    d2_if_10g_unused_cnt += 1
                        elif value['vendor'] == 'ARISTA':
                            if value['idx'] > 47:
                                if value['status'] == "connected":  ## 사용중 여부 구분
                                    d2_if_100g_used_cnt += 1
                                else:
                                    d2_if_100g_unused_cnt += 1
                            else:
                                if value['status'] == "connected":  ## 사용중 여부 구분
                                    d2_if_10g_used_cnt += 1
                                else:
                                    d2_if_10g_unused_cnt += 1
                elif value['hostname'][13:15] == 'sp':
                    # print(f"{value['hostname']}, {value['port']}")
                    if value['idx'] > 32:
                        if value['status'] == "connected":  ## 사용중 여부 구분
                            d1_if_10g_used_cnt += 1
                        else:
                            d1_if_10g_unused_cnt += 1
                    else :
                        if value['status'] == "connected":  ## 사용중 여부 구분
                            d1_if_100g_used_cnt += 1
                        else:
                            d1_if_100g_unused_cnt += 1

        elif value['location'] == 'd2' and value['hostname'][3] == 'p' and value['hostname'][5:7] == 'db' and (value['hostname'][13:15] == 'sw' or value['hostname'][13:15] == 'bs'):  ## d2 운영 원장계
            if value['port'][0] == 'E' or value['port'][0:3] == 'Eth' or value['port'][0:2] == 'Gi':  ## 서비스 사용가능 인터페이스만 구분
                if value['hostname'][13:15] == 'sw':
                    # print(f"location, hostname >> {value['location']}, {value['hostname']}")

                    if value['vendor'] == 'CISCO':
                        if value['idx'] > 48:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_db_100g_used_cnt += 1
                            else:
                                d2_db_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_db_10g_used_cnt += 1
                            else:
                                # print(f"{value['hostname']}, {value['port']}")
                                d2_db_10g_unused_cnt += 1
                    elif value['vendor'] == 'ARISTA':
                        if value['idx'] > 47:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_db_100g_used_cnt += 1
                            else:
                                d2_db_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_db_10g_used_cnt += 1
                            else:
                                d2_db_10g_unused_cnt += 1
                elif value['hostname'][13:15] == 'bs':
                    # print(f"{value['hostname']}, {value['port']}")
                    r_index = value['port'].rindex('/') + 1
                    temp = int(value['port'][r_index:])

                    if temp > 48:
                        if value['status'] == "connected":  ## 사용중 여부 구분
                            d2_db_100g_used_cnt += 1
                        else:
                            d2_db_100g_unused_cnt += 1
                    else:
                        if value['status'] == "connected":  ## 사용중 여부 구분
                            # print(f"{value['hostname']}, {value['port']}")
                            d2_db_10g_used_cnt += 1
                        else:
                            d2_db_10g_unused_cnt += 1

        elif value['location'] == 'd2' and value['hostname'][3] == 'p' and value['hostname'][5:7] == 'eb' and value['hostname'][13:15] == 'sw':  ## dc2 운영 대외계
            if value['port'][0] == 'E' or value['port'][0:3] == 'Eth' or value['port'][0:2] == 'Gi':  ## 서비스 사용가능 인터페이스만 구분
                if value['hostname'][13:15] == 'sw':
                    # print(f"location, hostname >> {value['location']}, {value['hostname']}")

                    if value['vendor'] == 'CISCO':
                        if value['idx'] > 48:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_ex_100g_used_cnt += 1
                            else:
                                d2_ex_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_ex_10g_used_cnt += 1
                            else:
                                # print(f"{value['hostname']}, {value['port']}")
                                d2_ex_10g_unused_cnt += 1
                    elif value['vendor'] == 'ARISTA':
                        if value['idx'] > 47:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_ex_100g_used_cnt += 1
                            else:
                                d2_ex_100g_unused_cnt += 1
                        else:
                            if value['status'] == "connected":  ## 사용중 여부 구분
                                d2_ex_10g_used_cnt += 1
                            else:
                                d2_ex_10g_unused_cnt += 1

    # print('d1_dz_10g_used_cnt >> ', d1_dz_10g_used_cnt)
    # print('d1_dz_10g_unused_cnt >> ', d1_dz_10g_unused_cnt)
    # print('d1_dz_100g_used_cnt >> ', d1_dz_100g_used_cnt)
    # print('d1_dz_100g_unused_cnt >> ', d1_dz_100g_unused_cnt)
    #
    # print('d1_ch_10g_used_cnt >> ', d1_ch_10g_used_cnt)
    # print('d1_ch_10g_unused_cnt >> ', d1_ch_10g_unused_cnt)
    # print('d1_ch_100g_used_cnt >> ', d1_ch_100g_used_cnt)
    # print('d1_ch_100g_unused_cnt >> ', d1_ch_100g_unused_cnt)
    #
    # print('d1_if_10g_used_cnt >> ', d1_if_10g_used_cnt)
    # print('d1_if_10g_unused_cnt >> ', d1_if_10g_unused_cnt)
    # print('d1_if_100g_used_cnt >> ', d1_if_100g_used_cnt)
    # print('d1_if_100g_unused_cnt >> ', d1_if_100g_unused_cnt)
    #
    # print('d1_db_10g_used_cnt >> ', d1_db_10g_used_cnt)
    # print('d1_db_10g_unused_cnt >> ', d1_db_10g_unused_cnt)
    # print('d1_db_100g_used_cnt >> ', d1_db_100g_used_cnt)
    # print('d1_db_100g_unused_cnt >> ', d1_db_100g_unused_cnt)
    #
    # print('d2_dz_10g_used_cnt >> ', d2_dz_10g_used_cnt)
    # print('d2_dz_10g_unused_cnt >> ', d2_dz_10g_unused_cnt)
    # print('d2_dz_100g_used_cnt >> ', d2_dz_100g_used_cnt)
    # print('d2_dz_100g_unused_cnt >> ', d2_dz_100g_unused_cnt)
    #
    # print('d2_ch_10g_used_cnt >> ', d2_ch_10g_used_cnt)
    # print('d2_ch_10g_unused_cnt >> ', d2_ch_10g_unused_cnt)
    # print('d2_ch_100g_used_cnt >> ', d2_ch_100g_used_cnt)
    # print('d2_ch_100g_unused_cnt >> ', d2_ch_100g_unused_cnt)
    #
    # print('d2_if_10g_used_cnt >> ', d2_if_10g_used_cnt)
    # print('d2_if_10g_unused_cnt >> ', d2_if_10g_unused_cnt)
    # print('d2_if_100g_used_cnt >> ', d2_if_100g_used_cnt)
    # print('d2_if_100g_unused_cnt >> ', d2_if_100g_unused_cnt)
    #
    # print('d2_db_10g_used_cnt >> ', d2_db_10g_used_cnt)
    # print('d2_db_10g_unused_cnt >> ', d2_db_10g_unused_cnt)
    # print('d2_db_100g_used_cnt >> ', d2_db_100g_used_cnt)
    # print('d2_db_100g_unused_cnt >> ', d2_db_100g_unused_cnt)

    d1_dz_10g_usage = round(d1_dz_10g_used_cnt / (d1_dz_10g_unused_cnt + d1_dz_10g_used_cnt) * 100, 0)
    d1_dz_100g_usage = round(d1_dz_100g_used_cnt / (d1_dz_100g_unused_cnt + d1_dz_100g_used_cnt) * 100, 0)
    d1_ch_10g_usage = round(d1_ch_10g_used_cnt / (d1_ch_10g_unused_cnt + d1_ch_10g_used_cnt) * 100, 0)
    d1_ch_100g_usage = round(d1_ch_100g_used_cnt / (d1_ch_100g_unused_cnt + d1_ch_100g_used_cnt) * 100, 0)
    d1_if_10g_usage = round(d1_if_10g_used_cnt / (d1_if_10g_unused_cnt + d1_if_10g_used_cnt) * 100, 0)
    d1_if_100g_usage = round(d1_if_100g_used_cnt / (d1_if_100g_unused_cnt + d1_if_100g_used_cnt) * 100, 0)
    d1_db_10g_usage = round(d1_db_10g_used_cnt / (d1_db_10g_unused_cnt + d1_db_10g_used_cnt) * 100, 0)
    d1_db_100g_usage = round(d1_db_100g_used_cnt / (d1_db_100g_unused_cnt + d1_db_100g_used_cnt) * 100, 0)
    d1_ex_10g_usage = round(d1_ex_10g_used_cnt / (d1_ex_10g_unused_cnt + d1_ex_10g_used_cnt) * 100, 0)
    d1_ex_100g_usage = 0

    d2_dz_10g_usage = round(d2_dz_10g_used_cnt / (d2_dz_10g_unused_cnt + d2_dz_10g_used_cnt) * 100, 0)
    d2_dz_100g_usage = round(d2_dz_100g_used_cnt / (d2_dz_100g_unused_cnt + d2_dz_100g_used_cnt) * 100, 0)
    d2_ch_10g_usage = round(d2_ch_10g_used_cnt / (d2_ch_10g_unused_cnt + d2_ch_10g_used_cnt) * 100, 0)
    d2_ch_100g_usage = round(d2_ch_100g_used_cnt / (d2_ch_100g_unused_cnt + d2_ch_100g_used_cnt) * 100, 0)
    d2_if_10g_usage = round(d2_if_10g_used_cnt / (d2_if_10g_unused_cnt + d2_if_10g_used_cnt) * 100, 0)
    d2_if_100g_usage = round(d2_if_100g_used_cnt / (d2_if_100g_unused_cnt + d2_if_100g_used_cnt) * 100, 0)
    d2_db_10g_usage = round(d2_db_10g_used_cnt / (d2_db_10g_unused_cnt + d2_db_10g_used_cnt) * 100, 0)
    d2_db_100g_usage = round(d2_db_100g_used_cnt / (d2_db_100g_unused_cnt + d2_db_100g_used_cnt) * 100, 0)
    d2_ex_10g_usage = round(d2_ex_10g_used_cnt / (d2_ex_10g_unused_cnt + d2_ex_10g_used_cnt) * 100, 0)
    d2_ex_100g_usage = 0

    all_dz_10g_usage = str(int((d1_dz_10g_used_cnt + d2_dz_10g_used_cnt) / (d1_dz_10g_unused_cnt + d1_dz_10g_used_cnt + d2_dz_10g_unused_cnt + d2_dz_10g_used_cnt) * 100)) + '%'
    all_ch_10g_usage = str(int((d1_ch_10g_used_cnt + d2_ch_10g_used_cnt) / (d1_ch_10g_unused_cnt + d1_ch_10g_used_cnt + d2_ch_10g_unused_cnt + d2_ch_10g_used_cnt) * 100)) + '%'
    all_if_10g_usage = str(int((d1_if_10g_used_cnt + d2_if_10g_used_cnt) / (d1_if_10g_unused_cnt + d1_if_10g_used_cnt + d2_if_10g_unused_cnt + d2_if_10g_used_cnt) * 100)) + '%'
    all_db_10g_usage = str(int((d1_db_10g_used_cnt + d2_db_10g_used_cnt) / (d1_db_10g_unused_cnt + d1_db_10g_used_cnt + d2_db_10g_unused_cnt + d2_db_10g_used_cnt) * 100)) + '%'
    all_ex_10g_usage = str(int((d1_ex_10g_used_cnt + d2_ex_10g_used_cnt) / (d1_ex_10g_unused_cnt + d1_ex_10g_used_cnt + d2_ex_10g_unused_cnt + d2_ex_10g_used_cnt) * 100)) + '%'

    arr_admin = [
        {
            'id':1,
            'gubn': 'dc1-DMZ',
            '10g_usage': d1_dz_10g_usage,
            '10g_used': d1_dz_10g_used_cnt,
            '10g_unused': d1_dz_10g_unused_cnt,
            '10g_total': d1_dz_10g_used_cnt + d1_dz_10g_unused_cnt,
            '100g_usage': d1_dz_100g_usage,
            '100g_used': d1_dz_100g_used_cnt,
            '100g_unused': d1_dz_100g_unused_cnt,
            '100g_total': d1_dz_100g_used_cnt + d1_dz_100g_unused_cnt
        },
        {
            'id': 2,
            'gubn': 'dc1-채널계',
            '10g_usage': d1_ch_10g_usage,
            '10g_used': d1_ch_10g_used_cnt,
            '10g_unused': d1_ch_10g_unused_cnt,
            '10g_total': d1_ch_10g_used_cnt + d1_ch_10g_unused_cnt,
            '100g_usage': d1_ch_100g_usage,
            '100g_used': d1_ch_100g_used_cnt,
            '100g_unused': d1_ch_100g_unused_cnt,
            '100g_total': d1_ch_100g_used_cnt + d1_ch_100g_unused_cnt
        },
        {
            'id': 3,
            'gubn': 'dc1-정보계',
            '10g_usage': d1_if_10g_usage,
            '10g_used': d1_if_10g_used_cnt,
            '10g_unused': d1_if_10g_unused_cnt,
            '10g_total': d1_if_10g_used_cnt + d1_if_10g_unused_cnt,
            '100g_usage': d1_if_100g_usage,
            '100g_used': d1_if_100g_used_cnt,
            '100g_unused': d1_if_100g_unused_cnt,
            '100g_total': d1_if_100g_used_cnt + d1_if_100g_unused_cnt
        },
        {
            'id': 4,
            'gubn': 'dc1-원장계',
            '10g_usage': d1_db_10g_usage,
            '10g_used': d1_db_10g_used_cnt,
            '10g_unused': d1_db_10g_unused_cnt,
            '10g_total': d1_db_10g_used_cnt + d1_db_10g_unused_cnt,
            '100g_usage': d1_db_100g_usage,
            '100g_used': d1_db_100g_used_cnt,
            '100g_unused': d1_db_100g_unused_cnt,
            '100g_total': d1_db_100g_used_cnt + d1_db_100g_unused_cnt
        },
        {
            'id': 5,
            'gubn': 'dc1-대외계',
            '10g_usage': d1_ex_10g_usage,
            '10g_used': d1_ex_10g_used_cnt,
            '10g_unused': d1_ex_10g_unused_cnt,
            '10g_total': d1_ex_10g_used_cnt + d1_ex_10g_unused_cnt,
            '100g_usage': d1_ex_100g_usage,
            '100g_used': d1_ex_100g_used_cnt,
            '100g_unused': d1_ex_100g_unused_cnt,
            '100g_total': d1_ex_100g_used_cnt + d1_ex_100g_unused_cnt
        },
        {
            'id': 6,
            'gubn': 'dc2-DMZ',
            '10g_usage': d2_dz_10g_usage,
            '10g_used': d2_dz_10g_used_cnt,
            '10g_unused': d2_dz_10g_unused_cnt,
            '10g_total': d2_dz_10g_used_cnt + d2_dz_10g_unused_cnt,
            '100g_usage': d2_dz_100g_usage,
            '100g_used': d2_dz_100g_used_cnt,
            '100g_unused': d2_dz_100g_unused_cnt,
            '100g_total': d2_dz_100g_used_cnt + d2_dz_100g_unused_cnt
        },
        {
            'id': 7,
            'gubn': 'dc2-채널계',
            '10g_usage': d2_ch_10g_usage,
            '10g_used': d2_ch_10g_used_cnt,
            '10g_unused': d2_ch_10g_unused_cnt,
            '10g_total': d2_ch_10g_used_cnt + d2_ch_10g_unused_cnt,
            '100g_usage': d2_ch_100g_usage,
            '100g_used': d2_ch_100g_used_cnt,
            '100g_unused': d2_ch_100g_unused_cnt,
            '100g_total': d2_ch_100g_used_cnt + d2_ch_100g_unused_cnt
        },
        {
            'id': 8,
            'gubn': 'dc2-정보계',
            '10g_usage': d2_if_10g_usage,
            '10g_used': d2_if_10g_used_cnt,
            '10g_unused': d2_if_10g_unused_cnt,
            '10g_total': d2_if_10g_used_cnt + d2_if_10g_unused_cnt,
            '100g_usage': d2_if_100g_usage,
            '100g_used': d2_if_100g_used_cnt,
            '100g_unused': d2_if_100g_unused_cnt,
            '100g_total': d2_if_100g_used_cnt + d2_if_100g_unused_cnt
        },
        {
            'id': 9,
            'gubn': 'dc2-원장계',
            '10g_usage': d2_db_10g_usage,
            '10g_used': d2_db_10g_used_cnt,
            '10g_unused': d2_db_10g_unused_cnt,
            '10g_total': d2_db_10g_used_cnt + d2_db_10g_unused_cnt,
            '100g_usage': d2_db_100g_usage,
            '100g_used': d2_db_100g_used_cnt,
            '100g_unused': d2_db_100g_unused_cnt,
            '100g_total': d2_db_100g_used_cnt + d2_db_100g_unused_cnt
        },
        {
            'id': 10,
            'gubn': 'dc2-대외계',
            '10g_usage': d2_ex_10g_usage,
            '10g_used': d2_ex_10g_used_cnt,
            '10g_unused': d2_ex_10g_unused_cnt,
            '10g_total': d2_ex_10g_used_cnt + d2_ex_10g_unused_cnt,
            '100g_usage': d2_ex_100g_usage,
            '100g_used': d2_ex_100g_used_cnt,
            '100g_unused': d2_ex_100g_unused_cnt,
            '100g_total': d2_ex_100g_used_cnt + d2_ex_100g_unused_cnt
        }
    ]

    arr_submit = [
        {
            'id' : 1,
            'gubn' : 'DMZ',
            'usage' : all_dz_10g_usage,
            'used' : d1_dz_10g_used_cnt + d2_dz_10g_used_cnt,
            'unused' : d1_dz_10g_unused_cnt + d2_dz_10g_unused_cnt,
            'total' : d1_dz_10g_unused_cnt + d1_dz_10g_used_cnt + d2_dz_10g_unused_cnt + d2_dz_10g_used_cnt
        },
        {
            'id': 2,
            'gubn': '채널계',
            'usage': all_ch_10g_usage,
            'used': d1_ch_10g_used_cnt + d2_ch_10g_used_cnt,
            'unused': d1_ch_10g_unused_cnt + d2_ch_10g_unused_cnt,
            'total': d1_ch_10g_unused_cnt + d1_ch_10g_used_cnt + d2_ch_10g_unused_cnt + d2_ch_10g_used_cnt
        },
        {
            'id': 3,
            'gubn': '정보계',
            'usage': all_if_10g_usage,
            'used': d1_if_10g_used_cnt + d2_if_10g_used_cnt,
            'unused': d1_if_10g_unused_cnt + d2_if_10g_unused_cnt,
            'total': d1_if_10g_unused_cnt + d1_if_10g_used_cnt + d2_if_10g_unused_cnt + d2_if_10g_used_cnt
        },
        {
            'id': 4,
            'gubn': '원장계',
            'usage': all_db_10g_usage,
            'used': d1_db_10g_used_cnt + d2_db_10g_used_cnt,
            'unused': d1_db_10g_unused_cnt + d2_db_10g_unused_cnt,
            'total': d1_db_10g_unused_cnt + d1_db_10g_used_cnt + d2_db_10g_unused_cnt + d2_db_10g_used_cnt
        },
        {
            'id': 5,
            'gubn': '대외계',
            'usage': all_ex_10g_usage,
            'used': d1_ex_10g_used_cnt + d2_ex_10g_used_cnt,
            'unused': d1_ex_10g_unused_cnt + d2_ex_10g_unused_cnt,
            'total': d1_ex_10g_unused_cnt + d1_ex_10g_used_cnt + d2_ex_10g_unused_cnt + d2_ex_10g_used_cnt
        }
    ]

    temp = {
        'data': arr_submit
    }
    with open(port_usage_submit_file, 'w') as json_file:
        data = json.dump(temp, json_file, indent=4)

    temp = {
        'data': arr_admin
    }
    with open(port_usage_file, 'w') as json_file:
        data = json.dump(temp, json_file, indent=4)


    payload = {
        "sender": "mg-net03",
        "webHookUrl": "https://hooks.slack.com/services/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",
        "payload": {
            "icon_emoji": ":robot:",
            "text": "네트워크 데일리점검",
            "username": "네트워크관리봇",
            "channel": SLACK_CHANNEL,
            # "channel": "network-webhook-test2",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": ":check_green: 네트워크 포트현황 :check_green:"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": "*dc1/dc2 포트사용현황 [합계/보고용]*"
                        },
                        {
                            "type": "mrkdwn",
                            "text": "`사용포트/미사용포트/전체포트(사용률)`"
                        }
                    ]
                },
                {
                    "type": "divider" ## dc1+dc2 합계
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"DMZ-10G : {arr_submit[0]['used']}/{arr_submit[0]['unused']}/{arr_submit[0]['total']} *({arr_submit[0]['usage']})*"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"채널-10G : {arr_submit[1]['used']}/{arr_submit[1]['unused']}/{arr_submit[1]['total']} *({arr_submit[1]['usage']})*"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"정보-10G : {arr_submit[2]['used']}/{arr_submit[2]['unused']}/{arr_submit[2]['total']} *({arr_submit[2]['usage']})*"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"원장-10G : {arr_submit[3]['used']}/{arr_submit[3]['unused']}/{arr_submit[3]['total']} *({arr_submit[3]['usage']})*"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"대외-10G : {arr_submit[4]['used']}/{arr_submit[4]['unused']}/{arr_submit[4]['total']} *({arr_submit[4]['usage']})*"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": "*dc1/dc2 상세 포트사용현황 [구분]*"
                        },
                        {
                            "type": "mrkdwn",
                            "text": "`사용포트/미사용포트 (사용률)`"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"d1-DMZ-10G : {d1_dz_10g_used_cnt}/{d1_dz_10g_unused_cnt} *({d1_dz_10g_usage}%)*"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"d1-DMZ-100G : {d1_dz_100g_used_cnt}/{d1_dz_100g_unused_cnt} *({d1_dz_100g_usage}%)*"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"d1-채널-10G : {d1_ch_10g_used_cnt}/{d1_ch_10g_unused_cnt} *({d1_ch_10g_usage}%)*"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"d1-채널-100G : {d1_ch_100g_used_cnt}/{d1_ch_100g_unused_cnt} *({d1_ch_100g_usage}%)*"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"d1-정보-10G : {d1_if_10g_used_cnt}/{d1_if_10g_unused_cnt} *({d1_if_10g_usage}%)*"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"d1-정보-100G : {d1_if_100g_used_cnt}/{d1_if_100g_unused_cnt} *({d1_if_100g_usage}%)*"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"d1-원장-10G : {d1_db_10g_used_cnt}/{d1_db_10g_unused_cnt} *({d1_db_10g_usage}%)*"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"d1-원장-100G : {d1_db_100g_used_cnt}/{d1_db_100g_unused_cnt} *({d1_db_100g_usage}%)*"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"d2-DMZ-10G : {d2_dz_10g_used_cnt}/{d2_dz_10g_unused_cnt} *({d2_dz_10g_usage}%)*"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"d2-DMZ-100G : {d2_dz_100g_used_cnt}/{d2_dz_100g_unused_cnt} *({d2_dz_100g_usage}%)*"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"d2-채널-10G : {d2_ch_10g_used_cnt}/{d2_ch_10g_unused_cnt} *({d2_ch_10g_usage}%)*"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"d2-채널-100G : {d2_ch_100g_used_cnt}/{d2_ch_100g_unused_cnt} *({d2_ch_100g_usage}%)*"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"d2-정보-10G : {d2_if_10g_used_cnt}/{d2_if_10g_unused_cnt} *({d2_if_10g_usage}%)*"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"d2-정보-100G : {d2_if_100g_used_cnt}/{d2_if_100g_unused_cnt} *({d2_if_100g_usage}%)*"
                        }
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"d2-원장-10G : {d2_db_10g_used_cnt}/{d2_db_10g_unused_cnt} *({d2_db_10g_usage}%)*"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"d2-원장-100G : {d2_db_100g_used_cnt}/{d2_db_100g_unused_cnt} *({d2_db_100g_usage}%)*"
                        }
                    ]
                }
            ]
        }
    }
    print(f'{NOW_DATETIME} || [MGMT] sended message to slack-channel!! >>>')
    requests.post(SLACK_PROXY_URL, json=payload)

def gubnInterface(idx, interface_status):
    print('')
    # if idx > 48 :                           ## 100G
    #     if value['status'] == "connected":  ## 사용중 여부 구분
    #         d1_dz_10g_used_cnt = d1_dz_10g_used_cnt + 1
    #     else:                               ## 10G
    #         d1_dz_10g_unused_cnt = d1_dz_10g_unused_cnt + 1
    # else :
    #     if value['status'] == "connected":  ## 사용중 여부 구분
    #         d1_dz_10g_used_cnt = d1_dz_10g_used_cnt + 1
    #     else:                               ## 10G
    #         d1_dz_10g_unused_cnt = d1_dz_10g_unused_cnt + 1


def get_netscaler_ip():
    for data in NETSCALER_ADDTIONAL_INFO:
        for idx, l7_device in enumerate(L7_IP):
            community = 'Wwfbs365%'  # Replace with your SNMP community string
            port = 161  # Default SNMP port
            oid = '.1.3.6.1.4.1.5951.4.1.3.1.1.1'
            # SNMP GETBULK operation
            iterator = nextCmd(
                SnmpEngine(),
                CommunityData(community),
                UdpTransportTarget((l7_device['ip'], port)),
                ContextData(),
                ObjectType(ObjectIdentity(data['oid'])),
                lexicographicMode=False  # Replace with the OID you want to start from
            )


            for errorIndication, errorStatus, errorIndex, varBinds in iterator:
                if errorIndication:
                    print(f"{NOW_DATETIME} || SNMP operation failed: {errorIndication}")
                    break
                elif errorStatus:
                    print(f"{NOW_DATETIME} || SNMP error: {errorStatus} at {errorIndex}")
                    break
                else:
                    for varBind in varBinds:
                        # print(f'[varBind contents] >>> {varBind}')
                        temp = ' ='.join([x.prettyPrint() for x in varBind])
                        idx = temp.find('=')
                        snmp_result = temp[idx + 1:]
                        print(f'{NOW_DATETIME} || {snmp_result}')

def send_Yesterday_Update_Asset():
    path = '/home/tossinvest/lamp/gather/updated_asset.json'
    # file_name = '../gather/device_info.json'
    with open(path, 'rt', encoding='UTF8') as json_file:
        json_data = json.load(json_file)

    print(f'{NOW_DATETIME} || {json_data}')

    for asset in json_data['data']:
        channel = SLACK_CHANNEL
        main_text = f":task-check-green-circle: 자빅스 업데이트 장비"
        attachment_color = "#3bc95c"
        message_body = {
            "color": attachment_color,
            "mrkdwn_in": ["fields"],
            "fields": [
                {
                    "title": "rule",
                    "value": f"`{asset['rule']}`",
                    "short": False,
                },
                {
                    "title": "ip",
                    "value": f"`{asset['ipaddress']}`",
                    "short": True,
                },
                {
                    "title": "status",
                    "value": f"`{asset['status']}`",
                    "short": True,
                },
                {
                    "title": "uptime",
                    "value": f"`{asset['uptime']}`",
                    "short": False,
                }
            ]
        }
        sendSlackChannel('zabbix', channel, main_text, message_body, '')

    # 모두 전송 후 삭제
    update_data = {
        "data":[]
    }
    with open(path, 'w') as json_file:
        data = json.dump(update_data, json_file, indent=4)

if __name__ == "__main__":
    main()