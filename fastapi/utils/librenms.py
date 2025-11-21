import pytz, sys, logging
import requests, json, codecs, threading, asyncio, paramiko, time, concurrent.futures, re, os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
# from deepdiff import DeepDiff
from pathlib import Path

# env 파일에서 환경 변수 로드
load_dotenv()

# 로거 설정
logger = logging.getLogger(__name__)

BASE_URL = "http://172.30.32.199:1521/api/v0"
LIMIT = 100000
LIBRENMS_TOKEN = os.getenv('LIBRENMS_TOKEN')
HEADERS = {
    "X-Auth-Token": f"{LIBRENMS_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def GetLibrenmsLldp():
    # 1) 전체 수집
    devices = RequestLibrenms("/devices", params={"columns": "device_id, hostname, sysName"}, array_key="devices")
    ports   = RequestLibrenms("/ports", params={"columns":"port_id,device_id,ifName,ifAlias,ifDescr"}, array_key="ports")
    links   = RequestLibrenms("/resources/links", array_key="links")

    # sysName으로 지정한 장비들만 필터링
    # 대상장비
    # - sysName에 "asn"이 포함된 장비
    # - sysName에 "mpr"이 포함된 장비
    # - sysName에 "ord"이 포함된 장비
    # - sysName에 "com"이 포함된 장비

    target_devices = []
    for d in devices:
        if "asn" in d["sysName"]:
            target_devices.append(d)
        elif "mpr" in d["sysName"]:
            target_devices.append(d)
        elif "ord" in d["sysName"]:
            target_devices.append(d)
        elif "com" in d["sysName"]:
            target_devices.append(d)

    # target_devices의 sysName만 출력
    logger.info(f"Target devices count: {len(target_devices)}")
    for d in target_devices:
        logger.debug(f"target_devices_sysName: {d['sysName']}")

    # 2) 맵 구성
    # target_devices의 device_id 집합
    target_device_ids = {str(d["device_id"]) for d in target_devices}
    
    devmap  = {str(d["device_id"]): {"hostname": d.get("hostname"), "sysName": d.get("sysName")} for d in target_devices}
    
    # portmap을 target_devices의 포트만으로 제한
    portmap = {
        str(p["port_id"]): {
            "device_id": p["device_id"],
            "ifName": p.get("ifName"),
            "ifAlias": p.get("ifAlias"),
            "ifDescr": p.get("ifDescr"),
        } for p in ports if str(p["device_id"]) in target_device_ids
    }

    # json pretty print
    logger.debug(f"target_devmap count: {len(devmap)}")
    logger.debug(f"target_portmap count: {len(portmap)}")

    # 3) 조인
    out = []
    for L in links:
        if L.get("protocol") != "lldp":  # LLDP만 원한다면
            continue

        local_port_id = str(L.get("local_port_id"))
        local_port = portmap.get(local_port_id, {})
        
        # portmap에 없으면 skip (target_devices가 아닌 장비)
        if not local_port:
            continue
        
        local_dev_id = str(local_port.get("device_id") or L.get("local_device_id"))
        local_dev_info = devmap.get(local_dev_id, {})
        
        # devmap에 없으면 skip (target_devices가 아닌 장비)
        if not local_dev_info:
            continue

        # 문자열만 대입!
        local_hostname = local_dev_info.get("hostname")
        local_sysname  = local_dev_info.get("sysName")


        # 원격 장비: 관리 내면 devmap, 아니면 원격 텍스트 사용
        remote_dev_id = str(L.get("remote_device_id")) if L.get("remote_device_id") else None
        remote_hostname = (
            devmap.get(remote_dev_id, {}).get("hostname")
            if remote_dev_id in devmap
            else L.get("remote_hostname")
        )
        remote_port = L.get("remote_port")

        out.append({
            "device_id": int(local_dev_id) if local_dev_id.isdigit() else None,
            "device_ip": local_hostname,
            "hostname": local_sysname,
            "local_ifname": local_port.get("ifName"),
            "local_ifdesc": local_port.get("ifAlias") or local_port.get("ifDescr"),
            "remote_hostname": remote_hostname,
            "remote_port": remote_port
        })
    # 4️⃣ JSON 출력
    logger.info(f"LLDP links collected: {len(out)}")
    logger.debug(f"LLDP output: {json.dumps(out, indent=2, ensure_ascii=False)}")

    # out 데이터를 dictionary 형태로 저장
    # data 키값에 out 데이터를 저장
    data = {
        "data": out
    }

    return data

def GetLibrenmsVlanIps():
    """
    LibreNMS API를 사용하여 VLAN 인터페이스의 IP 할당 정보 수집
    """
    # 1) 전체 데이터 수집
    devices = RequestLibrenms("/devices", params={"columns": "device_id,hostname,sysName"}, array_key="devices")
    ports = RequestLibrenms("/ports", params={"columns": "port_id,device_id,ifName,ifAlias"}, array_key="ports")

    # IP 주소 정보 수집 - 여러 방법 시도
    ip_addresses = []
    try:
        # 방법 1: /resources/ip/addresses
        ip_addresses = RequestLibrenms("/resources/ip/addresses", array_key="addresses")
        logger.info(f"Method 1 - /resources/ip/addresses: {len(ip_addresses)} addresses")
    except Exception as e:
        logger.warning(f"Method 1 failed: {e}")

    if not ip_addresses:
        try:
            # 방법 2: 모든 장비의 IP 조회
            logger.info(f"Method 2 starting - collecting IP addresses from {len(devices)} devices")
            for device in devices:
                device_id = device.get('device_id')
                try:
                    device_ips = RequestLibrenms(f"/devices/{device_id}/ip", array_key="addresses")
                    ip_addresses.extend(device_ips)
                except Exception as e:
                    logger.debug(f"Failed to get IPs for device {device_id}: {e}")
            logger.info(f"Method 2 - /devices/*/ip: {len(ip_addresses)} addresses from {len(devices)} devices")
        except Exception as e:
            logger.warning(f"Method 2 failed: {e}")

    logger.info(f"Collected devices: {len(devices)}, ports: {len(ports)}, ip_addresses: {len(ip_addresses)}")

    # 2) 맵 구성
    devmap = {str(d["device_id"]): {"hostname": d.get("hostname"), "sysName": d.get("sysName")} for d in devices}
    portmap = {str(p["port_id"]): {
        "device_id": p["device_id"],
        "ifName": p.get("ifName"),
        "ifAlias": p.get("ifAlias")
    } for p in ports}

    # 3) VLAN 인터페이스만 필터링하여 데이터 조합
    # device_id + vlan을 키로 사용하여 IP 주소 그룹화
    vlan_ip_map = {}

    for addr in ip_addresses:
        port_id = str(addr.get("port_id"))
        port_info = portmap.get(port_id)

        if not port_info:
            continue

        ifname = port_info.get("ifName", "")

        # VLAN 인터페이스만 필터링 (ifName에 "Vlan" 포함)
        if "Vlan" not in ifname:
            continue

        # VLAN 번호 추출 (예: "Vlan2432" -> "2432")
        vlan_match = re.search(r'Vlan(\d+)', ifname)
        if not vlan_match:
            continue

        vlan_id = vlan_match.group(1)
        device_id = str(port_info["device_id"])
        ip_address = addr.get("ipv4_address")

        if not ip_address:
            continue

        # device_id + vlan을 키로 사용
        key = f"{device_id}_{vlan_id}"

        if key not in vlan_ip_map:
            dev_info = devmap.get(device_id, {})
            vlan_ip_map[key] = {
                "device_id": int(device_id) if device_id.isdigit() else None,
                "device_ip": dev_info.get("hostname"),
                "hostname": dev_info.get("sysName"),
                "vlan": vlan_id,
                "ip": []
            }

        vlan_ip_map[key]["ip"].append(ip_address)

    # 4) main 필드 추가 (IP 중 .1 또는 .254로 끝나는 것이 있는지 체크)
    out = []
    for vlan_data in vlan_ip_map.values():
        # IP 배열에서 마지막 octet이 1 또는 254인 것이 있는지 확인
        has_main_ip = False
        for ip in vlan_data["ip"]:
            last_octet = ip.split('.')[-1]
            if last_octet == '1' or last_octet == '254':
                has_main_ip = True
                break

        vlan_data["main"] = "y" if has_main_ip else "n"
        out.append(vlan_data)

    logger.info(f"VLAN IP information collected: {len(out)} VLANs")
    logger.debug(f"VLAN IP output: {json.dumps(out, indent=2, ensure_ascii=False)}")

    return {"data": out}

def RequestLibrenms(path, params=None, array_key=None):
    # LibreNMS API는 보통 count/limit/offset + 배열키 형태를 씁니다.
    params = params.copy() if params else {}
    params.setdefault("limit", LIMIT)
    offset = 0
    result = []

    logger.debug(f"LibreNMS Request - URL: {BASE_URL}{path}, params: {params}, array_key: {array_key}")

    while True:
        params["offset"] = offset
        r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        items = data.get(array_key) if array_key else data
        if not items:
            break
        result.extend(items)
        if len(items) < LIMIT:
            break
        offset += LIMIT
    return result