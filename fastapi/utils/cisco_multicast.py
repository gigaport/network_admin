## Cisco Common

import time, re, json
from datetime import datetime, timezone, timedelta
from utils.cisco_common import Execute_GenieParser, ConnectToDevice, Execute_Command, ParsePyatsToJson, GetParserByCommand
from utils.common_methods import OpenJsonFile

EXCEPTION_MULTICAST_IP = [
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
    "239.255.255.250/32",
    "239.1.", # 리커버리 운영 멀티캐스트 IP prefix
    "239.3.", # 리커버리 DR 멀티캐스트 IP prefix
    "239.5." # 리커버리 테스트 멀티캐스트 IP prefix
]


def ProcessMulticastInfo(data:dict, market_gubn:str):
    # 회원사/정보이용사 + 시세정보를 가져와서 회원사별 멀티캐스트 정보에 필요한 내용을 삽입
    path = f"/app/common/members_info.json"
    client_info:Dict = OpenJsonFile(path)
    # client_info 정상 체크
    if not client_info:
        print(f"[ERROR] client_info is empty")
        return {"error": "client_info is empty"}

    print(f"[DEBUG] CLIENT_INFO: {client_info}")
    
    if market_gubn == "pr": 
        path = f"/app/common/pr_mpr_multicast_info.json"
    elif market_gubn == "ts": 
        path = f"/app/common/ts_mpr_multicast_info.json"
    else:
        print(f"[ERROR] Unsupported market_gubn: {market_gubn}")
        return {"error": f"Unsupported market_gubn: {market_gubn}"}

    sise_info:Dict = OpenJsonFile(path)
    # sise_info 정상 체크
    if not sise_info:
        print(f"[ERROR] sise_info is empty")
        return {"error": "sise_info is empty"}

    combined_data = []
    # data 인자 타입은 딕셔너리 형태로 전달됨
    # data 딕셔너리 값들을 반복문 처리하여 멀티캐스트 정보 수집 결과를 저장
    for key, item in data.items():
        # print(f"[DEBUG] ITEM: {item}", flush=True)
        device_name = key
        device_os = item['device_os']
        device_ip = item['device_ip']
        device_join_products = item['device_join_products']
        cmd_response_list = item['cmd_response_list']


        print(f"[05.PROCESSING MULTICAST INFO] {device_name} PROCESSING...")

        ## cisco pyats return key값이 os마다 다름 별도 처리 필요

        if device_os == 'iosxe':
            device_os_key = ''
        elif device_os == 'nxos':
            device_os_key = 'default'
        else:
            print(f"[ERROR] Unsupported OS: {device_os}")
            return {"error": f"Unsupported OS: {ddevice_os}"}
        
        ## 멀티캐스트 정보 수집 결과를 저장할 변수 초기화
        today_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        valid_source_address_count = 0
        valid_oif_count = 0
        connected_server_count = 0
        min_uptime = '확인필요'
        rpf_nbrs = '확인필요'
        rp_addresses = []


        for data in cmd_response_list:
            if data['cmd'] == 'show_ip_mroute_source-tree' or data['cmd'] == 'show_ip_mroute':
                print(f"[SHOW_IP_MROUTE_SOURCE-TREE] {device_name} PROCESSING MULTICAST INFO...")

                ## show ip mroute에 대한 테이블이 있을경우
                if data['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']:
                    multicast_group = data['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']['multicast_group']

                    ## 유요한 (S,G) 및 VLAN 1100 개수를 계산하여 기존 데이터에 삽입
                    valid_source_address_count = CountValidSourceAddress(multicast_group, device_os)

                    #####################==>> RP Address os별 삽입 기준 정리 해야됨!!!!!
                    valid_multicast_data = CountValidOifAndGetMinUptime(multicast_group, device_os)

                    ## 유효한 멀티캐스트 데이터가 있는지 확인
                    if not valid_multicast_data:
                        print(f"[ERROR] NO VALID MULTICAST DATA FOUND FOR {device_name} in {data['cmd']}", flush=True)
                        # return {"error": f"No valid multicast data found for {device_name} in {data['cmd']}"}
                    else:
                        # print(f"[vaild_multicast_data] => {valid_multicast_data}")
                        valid_source_address_count = valid_source_address_count
                        valid_oif_count = valid_multicast_data['valid_oif_count']
                        min_uptime = valid_multicast_data['min_uptime']
                        rpf_nbrs = valid_multicast_data['rpf_nbrs']
                        
                        if device_os == 'iosxe':
                            rp_addresses = valid_multicast_data['rp_addresses']
                else:
                    print(f"[ERROR] No multicast group data found for {device_name} in {data['cmd']}", flush=True)
                    # return {"error": f"No multicast group data found for {device_name} in {data['cmd']}"}   

            elif data['cmd'] == 'show_ip_pim_rp':
                print("[SHOW IP PIM RP]\n")
                rp_addresses.append(list(data['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']['rp']['static_rp'].keys())[0])

            elif data['cmd'] == 'show_interface_status':
                print("[SHOW INTERFACE STATUS]\n")
                # print(f"{data['parsed_output']}")

                for interface, details in data['parsed_output']['interfaces'].items():
                    # access_vlan 값과 인터페이스 상태 확인
                    access_vlan = details.get('vlan')
                    oper_status = details.get('status')

                    if access_vlan == '1100' and oper_status == 'connected':
                        connected_server_count += 1
                        # print(f"Matched interfaces: {interface} Deivice: {device_name}\n\n")
                # print(f"[VLAN1100 UP interfaces total COUNT] : {device_name}{device_os} ==> {connected_server_count}")

        # print(f"device_info_join_products >> {device_join_products}")

        temp = {
            "device_name": device_name,
            "updated_time":today_time,
            "device_os": device_os,
            "products": device_join_products,
            "mgmt_ip": device_ip,
            "valid_source_address_count": valid_source_address_count,
            "valid_oif_count": valid_oif_count,
            "min_uptime": min_uptime,
            "rp_addresses": rp_addresses,
            "rpf_nbrs": rpf_nbrs,
            "connected_server_count": connected_server_count,
            "mroute": cmd_response_list
        }
        
        combined_data.append(temp)

    result = {"data": combined_data}
    return result

## 유효한 멀티캐스트 IP를 선별하기는 과정
def CountValidSourceAddress(data, device_os:str='iosxe'):
    count = 0

    for multicast_ip, info in data.items():
        # 유효한 멀티캐스트 IP를 선별하기는 과정
        # 예외 멀티캐스트 IP 제외 처리 (공인 멀티캐스트 IP + 회원사 리커버리 멀티캐스트 IP)
        if all(not multicast_ip.startswith(ip_prefix) for ip_prefix in EXCEPTION_MULTICAST_IP):
            source = info.get('source_address',{})
            for key, addr_info in source.items():
                if '*' in key:
                    continue
                # nxos: Incoming interface가 Null인 (S,G)는 RPF 실패로 유효 라우팅이 아니므로 카운트 제외
                if device_os == 'nxos':
                    iil = addr_info.get('incoming_interface_list', {}) if isinstance(addr_info, dict) else {}
                    if not iil or all(k == 'Null' for k in iil.keys()):
                        continue
                count += 1

    return count

def CountValidOifAndGetMinUptime(data, device_os:str):
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
                    iil = addr_info.get('incoming_interface_list', {})
                    # Incoming interface가 Null인 (S,G)는 RPF 실패로 유효 라우팅이 아니므로 OIF 카운트 / RPF 대상에서 제외
                    if not iil or all(k == 'Null' for k in iil.keys()):
                        continue
                    first_key = next(iter(iil))
                    first_value = iil[first_key]
                    # print(f"rpf {first_key}, {first_value}")
                    if first_value.get('rpf_nbr') and first_value['rpf_nbr'] not in rpf_nbrs:
                        rpf_nbrs.append(first_value['rpf_nbr'])
                
                outgoing_interface = addr_info.get("outgoing_interface_list", {})
                ## OIF가 Vlan1100일 때 (정상수신)
                if "Vlan1100" in outgoing_interface:
                    ## 특정 멀티캐스트그룹IP : uptime 값 가져오기
                    if device_os == 'iosxe':
                        uptimes.append(outgoing_interface['Vlan1100']['uptime'])
                    elif device_os == 'nxos':
                        uptimes.append(outgoing_interface['Vlan1100']['oil_uptime'])
                    # print(f"addr_info: {addr_info}")

                    # print(f"total_uptime_days: {total_uptime_days}")
                    valid_oif_count += 1 


    if vaild_check:
        # uptimes 리스트가 비어있지 않은 경우에만 min_uptime 계산
        if uptimes:
            min_uptime = min(uptimes, key=ParseUptime)
        else:
            min_uptime = '확인필요'
            print(f"[WARNING] No valid uptime data found. uptimes list is empty.")

        # print("vlan1100 개수", valid_oif_count)
        # print(f"min_uptimes : {min_uptime}")
        # print(f"rp_addresses: {rp_addresses}")
        # print(f"rpf_nbrs: {rpf_nbrs}")
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


# def OpenJsonFile(path):
#     data = {}
#     try:
#         with open(path, 'rt', encoding='UTF8') as json_file:
#             data = json.load(json_file)
#     except FileNotFoundError:
#         print(f"파일이 존재하지 않습니다: {path}")
#     except json.JSONDecodeError:
#         print(f"JSON 형식이 잘못되었습니다.: {path}")

#     return data