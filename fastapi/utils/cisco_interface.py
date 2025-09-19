import time, re, json
from datetime import datetime, timezone, timedelta
from utils.cisco_common import Execute_GenieParser, ConnectToDevice, Execute_Command, ParsePyatsToJson, GetParserByCommand


def ProcessCiscoInterfaceInfo(data:dict, market_gubn:str):
    for key, item in data.items():
        # print(f"[DEBUG] ITEM: {item}", flush=True)

        device_name = key
        device_os = item['device_os']
        device_ip = item['device_ip']
        cmd_response_list = item['cmd_response_list']

        if device_os == 'iosxe':
            cmd_status_gubn = 'show_interfaces_status'
            cmd_description_gubn = 'show_interfaces_description'
        elif device_os == 'nxos':
            cmd_status_gubn = 'show_interface_status'
            cmd_description_gubn = 'show_interface_description'

        # show interface description 결과에서 description 정보를 추출하여 
        # show interface status 결과에 description을 추가하는 작업

        # show interface description 결과를 별도 변수에 저장
        # cmd키의 value값이 show interfaces description
        interface_descriptions = {}
        for cmd in cmd_response_list:
            if cmd['cmd'] == cmd_description_gubn:
                interface_descriptions = cmd['parsed_output']['interfaces']
                # print(f"[DEBUG] INTERFACE_DESCRIPTIONS: {interface_descriptions}", flush=True)

        for cmd in cmd_response_list:
            # print(f"[DEBUG] CMD: {cmd}", flush=True)
            if cmd['cmd'] == cmd_status_gubn:
                # print(f"[DEBUG] SHOW_INTERFACES_STATUS: {device_name} {device_os} {device_ip} {cmd['cmd']} {cmd['parsed_output']}", flush=True)
                for status_interface_no, interface in cmd['parsed_output']['interfaces'].items():
                    # print(f"[DEBUG] INTERFACE_INFO: {interface}", flush=True)
                    for description_interface_no, interface_description in interface_descriptions.items():
                        if status_interface_no == description_interface_no: 
                            interface['description'] = interface_description['description']
                            # print(f"[DEBUG] MATCHED_INTERFACE: {status_interface_no}", flush=True)

    # pretty print
    # print(f"[DEBUG] PROCESS_CISCO_INTERFACE_INFO_RESULT: {json.dumps(data, indent=4, ensure_ascii=False)}", flush=True)
    data = ConvertToTableSet(data)

    return data

def ConvertToTableSet(data):
    # print(f"[DEBUG] CONVERT_TO_TABLE_SET_DATA: {data}", flush=True)
    result_list = []
    id = 1
    for key, item in data.items():
        # print(f"[DEBUG] ITEM: {item}", flush=True)

        device_name = key
        device_os = item['device_os']
        device_ip = item['device_ip']
        cmd_response_list = item['cmd_response_list']

        if device_os == 'iosxe':
            cmd_gubn = 'show_interfaces_status'
        elif device_os == 'nxos':
            cmd_gubn = 'show_interface_status'


        for cmd in cmd_response_list:
            if cmd['cmd'] == cmd_gubn:
                for key, interface in cmd['parsed_output']['interfaces'].items():
                    # print(f"[DEBUG] FILTERED_INTERFACE: {interface}", flush=True)
                    # print(f"[DEBUG] FILTERED_INTERFACE_KEY: {key}", flush=True)
                    # print(f"[DEBUG] FILTERED_INTERFACE_STATUS: {interface['status']}", flush=True)
                    # print(f"[DEBUG] FILTERED_INTERFACE_VLAN: {interface['vlan']}", flush=True)
                    # print(f"[DEBUG] FILTERED_INTERFACE_DUPLEX: {interface['duplex_code']}", flush=True)
                    # print(f"[DEBUG] FILTERED_INTERFACE_SPEED: {interface['port_speed']}", flush=True)
                    # print(f"[DEBUG] FILTERED_INTERFACE_TYPE: {interface['type']}", flush=True)
                    # print(f"[DEBUG] FILTERED_INTERFACE_DESCRIPTION: {interface['description']}", flush=True)

                    # nxos경우 show interface status 결과가 notconnec => notconnect으로 표현되어 보정필요
                    if device_os == 'nxos':
                        if interface['status'] == 'notconnec':
                            interface['status'] = 'notconnect'

                    # 인터페이스 상태 클래스 정의
                    if interface['status'] == 'connected':
                        interface_class = 'text-primary'
                    elif interface['status'] == 'notconnect':
                        interface_class = 'text-danger'
                    else:
                        interface_class = 'text-warning'

                    temp = {
                        "id": id,
                        "device_name": device_name,
                        "device_os": device_os,
                        "device_ip": device_ip,
                        "interface_no": key,
                        "interface_description": interface['description'],
                        "interface_status": interface['status'],
                        "interface_vlan": interface['vlan'],
                        "interface_duplex": interface['duplex_code'],
                        "interface_speed": interface['port_speed'],
                        "interface_type": interface['type'],
                        "interface_class": interface_class
                    }
                    result_list.append(temp)
                    id += 1

    data = {'data': result_list}
    # print(f"[DEBUG] CONVERT_TO_TABLE_SET_RESULT: {result_list}", flush=True)

    return data