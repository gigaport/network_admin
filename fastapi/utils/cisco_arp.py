import time, re, json
from datetime import datetime, timezone, timedelta
from utils.cisco_common import Execute_GenieParser, ConnectToDevice, Execute_Command, ParsePyatsToJson, GetParserByCommand


def ProcessCiscoArpInfo(data:dict, market_gubn:str):
    # print(f"[DEBUG] PROCESS_CISCO_ARP_START: {data}", flush=True)
    arp_list = []
    for key, item in data.items():
        # print(f"[DEBUG] ITEM: {item}", flush=True)

        device_name = key
        device_os = item['device_os']
        device_ip = item['device_ip']
        cmd_response_list = item['cmd_response_list']

        cmd_nxos_arp = 'show_ip_arp_nxos'
        cmd_iosxe_arp = 'show_ip_arp_iosxe'

        # 아래와 같은 리스트 형태로 저장
        # 리스트의 필드명 device_name, device_ip, device_os, interface, arp_ip, link_layer_address, origin
        # interface 필드는 show_ip_arp_iosxe, show_ip_arp_nxos 명령어 결과에서 interfaces 필드의 key값
        # arp_ip 필드는 ipv4 => neighbors => 키값 => ip 필드의 값
        # link_layer_address 필드는 ipv4 => neighbors => 키값 => link_layer_address 필드의 값
        # origin 필드는 ipv4 => neighbors => 키값 => origin 필드의 값

        for cmd in cmd_response_list:
            if cmd['cmd'] == cmd_iosxe_arp or cmd['cmd'] == cmd_nxos_arp:
                for interface, arp_info in cmd['parsed_output']['interfaces'].items():
                    for arp_ip, arp_info in arp_info['ipv4']['neighbors'].items():
                        arp_list.append({
                            'device_name': device_name,
                            'device_ip': device_ip,
                            'device_os': device_os,
                            'interface': interface,
                            'arp_ip': arp_ip,
                            'link_layer_address': arp_info['link_layer_address'],
                            'origin': arp_info['origin']
                        })

    data = {'data': arp_list}
    # print(f"[DEBUG] PROCESS_CISCO_ARP_INFO_RESULT: {json.dumps(data, indent=4, ensure_ascii=False)}", flush=True)

    # # pretty print
    # # print(f"[DEBUG] PROCESS_CISCO_INTERFACE_INFO_RESULT: {json.dumps(data, indent=4, ensure_ascii=False)}", flush=True)
    # data = ConvertToTableSet(data)

    return data