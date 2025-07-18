## Cisco Common

import time, re
from datetime import datetime, timezone, timedelta
from utils.cisco_common import Execute_GenieParser, ConnectToDevice, Execute_Command, ParsePyatsToJson, GetParserByCommand

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
        "key": "show_interfaces_status",
        "value": "show interfaces status"
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

# 멀티캐스트 정보수집 시작
def GetCiscoMulticastInfo(device_info, device_name):
    """
    멀티캐스트 정보를 수집하는 함수
    device_info: pyATS Device 객체
    device_name: 장비 이름
    """
    print(f"[01.GetMulticastInfo] {device_name} connecting...")

    ## pyATS Device 연결
    device_info = ConnectToDevice(device_info)

    if not device_info:
        return {"error": f"Failed to connect to {device_name}"}

    print(f"[02.connected] {device_name} connected...")

    if device_info.os == 'nxos':
        cmds = NXOS_CMDS
    elif device_info.os == 'iosxe':
        cmds = IOSXE_CMDS
    else:
        print(f"[ERROR] Unsupported OS: {device_info.os}")
        return {"error": f"Unsupported OS: {device_info.os}"}   

    print(f"[03.cmds] {device_name} commands to execute: {cmds}")
    
    ## 명령어 실행 및 결과 수집
    # cmds 리스트에 정의된 명령어를 순차적으로 실행
    # result 리스트에 cmd키에는 명령어, parsed_output에는 파싱된 결과를 저장, org_output에는 원본 출력 저장
    cmd_response_list: list = []

    for cmd in cmds:
        cmd_response:str = Execute_Command(device_info, cmd['value'])

        ## 할당한 명령어 순차적 실행
        parser = GetParserByCommand(cmd['key'])

        if parser is None:
            print(f"[ERROR] Unsupported command: {cmd['key']}")
            continue

        parsed_output, org_output = ParsePyatsToJson(parser, cmd_response)

        if parsed_output is None:
            print(f"[ERROR] Failed to parse command output for {cmd['key']}")
            continue

        # 결과를 result 리스트에 저장
        print(f"[04.cmd_response] {device_name} command {cmd['key']} executed successfully.")
        print(f"[04.cmd_response] {device_name} command response collected...") 
        #print(f"[04.cmd_response] {device_name} command response: {parsed_output}")
        ## 결과를 딕셔너리 형태로 저장
        ## cmd_response는 GenieParser로 파싱된 결과, org_output은 원본 출력
        ## parsed_output는 GenieParser로 파싱된 결과, org_output은 원본 출력
        
        cmd_response_list.append({
            "cmd": cmd['key'],
            "parsed_output": parsed_output,
            "org_output": org_output
        })

    print(f"[03.cmd_response] {device_name} command response collected...")

    ## 멀티캐스트 정보 처리
    processed_data = ProcessMulticastInfo(cmd_response_list, device_info, device_name)
    data = {"data": processed_data}

    ## 연결 해제
    if device_info.connected:
        device_info.disconnect()
        print(f"{device_name} disconnected...")

    return data


def ProcessMulticastInfo(cmd_response_list, device_info, device_name):
    print(f"[05.PROCESSING MULTICAST INFO] {device_name} processing multicast info...")

    ## cisco pyats return key값이 os마다 다름 별도 처리 필요

    if device_info.os == 'iosxe':
        device_os_key = ''
    elif device_info.os == 'nxos':
        device_os_key = 'default'
    else:
        print(f"[ERROR] Unsupported OS: {device_info.os}")
        return {"error": f"Unsupported OS: {device_info.os}"}
    
    ## 멀티캐스트 정보 수집 결과를 저장할 변수 초기화
    today_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    valid_source_address_count = 0
    valid_oif_count = 0
    connected_server_count = 0
    min_uptime = '확인필요'
    rpf_nbrs = '확인필요'
    rp_addresses = []
    result = {}

    for data in cmd_response_list:
        if data['cmd'] == 'show_ip_mroute_source-tree' or data['cmd'] == 'show_ip_mroute':
            print(f"[show_ip_mroute_source-tree] {device_name} processing multicast info...")

            ## show ip mroute에 대한 테이블이 있을경우
            if data['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']:
                multicast_group = data['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']['multicast_group']

                ## 유요한 (S,G) 및 VLAN 1100 개수를 계산하여 기존 데이터에 삽입
                valid_source_address_count = CountValidSourceAddress(multicast_group)

                #####################==>> RP Address os별 삽입 기준 정리 해야됨!!!!!
                valid_multicast_data = CountValidOifAndGetMinUptime(multicast_group, device_info.os)

                ## 유효한 멀티캐스트 데이터가 있는지 확인
                if not valid_multicast_data:
                    print(f"[ERROR] No valid multicast data found for {device_name} in {data['cmd']}", flush=True)
                    # return {"error": f"No valid multicast data found for {device_name} in {data['cmd']}"}
                else:
                    # print(f"[vaild_multicast_data] => {valid_multicast_data}")
                    valid_source_address_count = valid_source_address_count
                    valid_oif_count = valid_multicast_data['valid_oif_count']
                    min_uptime = valid_multicast_data['min_uptime']
                    rpf_nbrs = valid_multicast_data['rpf_nbrs']
                    
                    if device_info.os == 'iosxe':
                        rp_addresses = valid_multicast_data['rp_addresses']
            else:
                print(f"[ERROR] No multicast group data found for {device_name} in {data['cmd']}", flush=True)
                # return {"error": f"No multicast group data found for {device_name} in {data['cmd']}"}   

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
        "updated_time":today_time,
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

def CountValidSourceAddress(data):
    count = 0
    for multicast_ip, info in data.items():
        print(f"multicast_group_ip : {multicast_ip}")
        if multicast_ip not in KNOWN_MULTICAST_IP :
            source = info.get('source_address',{})
            for key in source:
                if '*' not in key:
                    count += 1
    
    return count

def CountValidOifAndGetMinUptime(data, device_os:str):
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
        min_uptime = min(uptimes, key=ParseUptime)

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

def ParseUptime(uptime:str):
    ## 정규식으로 9w3d 같은 포맷에서 숫자를 추출
    match = re.match(r"(?:(\d+)w)?(?:(\d+)d)?", uptime)

    if not match:
        return 0
    
    weeks = int(match.group(1)) if match.group(1) else 0
    days = int(match.group(2)) if match.group(2) else 0
    total_days = weeks * 7 + days

    return total_days
