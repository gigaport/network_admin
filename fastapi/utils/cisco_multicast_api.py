"""Cisco NX-API 기반 멀티캐스트 수집/파싱 모듈.

기존 cisco_multicast.py 는 pyATS/Genie SSH 로 정보를 수집하지만, 본 모듈은
NX-API HTTP 한 번 호출로 mroute/pim-rp/interface-status 를 받아 파싱한다.
- 결과 구조는 cisco_multicast.ProcessMulticastInfo() 의 출력과 동일하게 맞춰
  기존 후처리(merge_multicast_group_count, create_member_sise_info, DB 저장 등)를 그대로 재사용.
- NXOS 만 지원. IOS-XE 장비는 "API미지원" 으로 마킹.

사용 위치: fastapi/routers/network.py 의 신규 /multicast/collect_api 엔드포인트.
"""
import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from utils.nxapi_client import query_multicast_info
from utils.cisco_multicast import EXCEPTION_MULTICAST_IP, ParseUptime

logger = logging.getLogger(__name__)

# valid_oif/min_uptime 계산 대상 멀티캐스트그룹 prefix (cisco_multicast.py 와 동일 정책)
TARGET_GROUP_PREFIX = "239.29.30."


def _as_list(maybe_list_or_dict):
    """NX-API JSON 구조에서 항목 1개면 dict, 2개 이상이면 list 로 오는 경우를 list 로 정규화."""
    if maybe_list_or_dict is None:
        return []
    if isinstance(maybe_list_or_dict, list):
        return maybe_list_or_dict
    return [maybe_list_or_dict]


def _parse_mcast_addrs(mcast_addrs: str):
    """'(*, 232.0.0.0/8)' 형식에서 (source, group) 추출."""
    m = re.match(r"\(\s*([^,]+)\s*,\s*([^)]+)\s*\)", mcast_addrs or "")
    if not m:
        return None, None
    src = m.group(1).strip()
    grp = m.group(2).strip()
    return src, grp


def _is_excepted_group(group_addr_with_mask: str) -> bool:
    """EXCEPTION_MULTICAST_IP prefix 에 매칭되면 제외 대상."""
    for prefix in EXCEPTION_MULTICAST_IP:
        if group_addr_with_mask.startswith(prefix):
            return True
    return False


def _parse_mroute_routes(mroute_body) -> list:
    """NX-API show ip mroute body → 정규화된 route list 반환.

    각 항목: {
      "group": "239.x.x.x/32",
      "source": "*" or unicast,
      "iif": "Ethernet1/20" or "Null",
      "rpf_nbr": "...",
      "uptime": "5w5d",
      "oif_list": ["Vlan140", "Ethernet1/3", ...],
    }
    """
    routes = []
    if not isinstance(mroute_body, dict):
        return routes

    vrf_rows = _as_list(mroute_body.get("TABLE_vrf", {}).get("ROW_vrf"))
    for vrf in vrf_rows:
        if not isinstance(vrf, dict):
            continue
        one_route_rows = _as_list(vrf.get("TABLE_one_route", {}).get("ROW_one_route"))
        for row in one_route_rows:
            if not isinstance(row, dict):
                continue
            source, group = _parse_mcast_addrs(row.get("mcast-addrs", ""))
            if not group:
                continue

            oif_list = []
            oif_rows = _as_list(row.get("TABLE_oif", {}).get("ROW_oif"))
            for oif in oif_rows:
                if isinstance(oif, dict):
                    name = oif.get("oif-name")
                    if name:
                        oif_list.append({
                            "name": name,
                            "uptime": oif.get("oif-uptime", ""),
                        })

            routes.append({
                "group": group,
                "source": source,
                "iif": row.get("route-iif", "Null"),
                "rpf_nbr": row.get("rpf-nbr", ""),
                "uptime": row.get("uptime", ""),
                "oif_list": oif_list,
            })
    return routes


def _count_valid_source_address(routes: list) -> int:
    """유효한 (S, G) 개수: 예외 그룹 제외, IIF 가 Null 인 (S,G) 제외, source='*' 제외."""
    count = 0
    for r in routes:
        group = r.get("group", "")
        source = r.get("source", "")
        if source == "*":
            continue
        if _is_excepted_group(group):
            continue
        if r.get("iif", "Null") == "Null":
            continue
        count += 1
    return count


def _extract_valid_sg_pairs(routes: list) -> list:
    """배치 후처리(_compute_received_products) 입력용 (source, group) 페어 리스트 추출.

    구조는 [(src_ip_without_mask, group_ip_without_mask), ...].
    예외 IP / source='*' / IIF Null 은 제외 — _count_valid_source_address 와 동일 정책.
    """
    pairs = []
    for r in routes:
        group_full = r.get("group", "")
        source = r.get("source", "")
        if source == "*":
            continue
        if _is_excepted_group(group_full):
            continue
        if r.get("iif", "Null") == "Null":
            continue
        # "239.29.30.81/32" → "239.29.30.81", "177.21.180.18/32" → "177.21.180.18"
        g = group_full.split("/")[0]
        s = source.split("/")[0]
        pairs.append([s, g])
    return pairs


def _calc_valid_oif_and_min_uptime(routes: list, client_vlan: str) -> dict:
    """239.29.30.x 대역 (S,G) 중 OIF=Vlan{client_vlan} 인 항목 카운트 + 최소 uptime + rpf_nbr 집계.

    cisco_multicast.CountValidOifAndGetMinUptime 의 로직과 동일한 정책:
    - 239.29.30.x 대역만 대상
    - (*, G) 는 rp/rpf 수집만 (count 제외)
    - (S, G) 중 OIF 에 Vlan{client_vlan} 포함 → valid_oif_count++
    """
    oif_vlan_key = f"Vlan{client_vlan}"
    valid_oif_count = 0
    uptimes = []
    rpf_nbrs = []

    has_target_group = False
    for r in routes:
        group = r.get("group", "")
        if not group.startswith(TARGET_GROUP_PREFIX):
            continue
        has_target_group = True

        source = r.get("source", "")
        if source == "*":
            # rpf_nbr 만 수집
            nbr = r.get("rpf_nbr", "")
            if nbr and nbr != "0.0.0.0" and nbr not in rpf_nbrs:
                rpf_nbrs.append(nbr)
            continue

        # (S, G) - IIF Null 제외
        if r.get("iif", "Null") == "Null":
            continue

        # rpf_nbr 수집
        nbr = r.get("rpf_nbr", "")
        if nbr and nbr != "0.0.0.0" and nbr not in rpf_nbrs:
            rpf_nbrs.append(nbr)

        # OIF 가 Vlan{client_vlan} 인지 확인
        for oif in r.get("oif_list", []):
            if oif.get("name") == oif_vlan_key:
                valid_oif_count += 1
                if oif.get("uptime"):
                    uptimes.append(oif["uptime"])
                break

    if not has_target_group:
        return {
            "valid_oif_count": 0,
            "min_uptime": "확인필요",
            "rpf_nbrs": "확인필요",
        }

    min_uptime = "확인필요"
    if uptimes:
        try:
            min_uptime = min(uptimes, key=ParseUptime)
        except Exception:
            min_uptime = uptimes[0]

    return {
        "valid_oif_count": valid_oif_count,
        "min_uptime": min_uptime,
        "rpf_nbrs": rpf_nbrs if rpf_nbrs else "확인필요",
    }


def _parse_pim_rp(pim_rp_body) -> list:
    """show ip pim rp body → RP 주소 리스트.

    NX-API 응답 구조: TABLE_vrf > ROW_vrf > TABLE_rp > ROW_rp > rp-addr (또는 유사)
    static RP / BSR RP 모두 포함.
    """
    rps = []
    if not isinstance(pim_rp_body, dict):
        return rps

    vrf_rows = _as_list(pim_rp_body.get("TABLE_vrf", {}).get("ROW_vrf"))
    for vrf in vrf_rows:
        if not isinstance(vrf, dict):
            continue
        # NX-OS 응답은 TABLE_rp > ROW_rp 또는 TABLE_anycast_rp > ... 등 OS 별로 다소 변형 있음
        for key, value in vrf.items():
            if not key.startswith("TABLE_"):
                continue
            inner_key = key.replace("TABLE_", "ROW_")
            rows = _as_list(value.get(inner_key) if isinstance(value, dict) else None)
            for row in rows:
                if not isinstance(row, dict):
                    continue
                # 다양한 키 후보
                for cand in ("rp-addr", "rp-address", "static_rp_addr"):
                    addr = row.get(cand)
                    if addr and addr not in rps:
                        rps.append(addr)
    return rps


def _count_connected_servers(intf_body, client_vlan: str) -> int:
    """show interface status body → access_vlan == client_vlan AND oper=connected/up 인 interface 수."""
    if not isinstance(intf_body, dict):
        return 0
    rows = _as_list(intf_body.get("TABLE_interface", {}).get("ROW_interface"))
    count = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        vlan = str(r.get("vlan", "")).strip()
        state = str(r.get("state", "")).strip().lower()
        if vlan == str(client_vlan) and state in ("connected", "up"):
            count += 1
    return count


def collect_device_multicast_via_api(device_name: str, device_ip: str, device_os: str,
                                     join_products: list, client_vlan: str = "1100") -> dict:
    """단일 NXOS 장비에 대해 NX-API 로 멀티캐스트 정보를 수집하고 cisco_multicast 호환 dict 반환.

    IOS-XE 장비는 NX-API 미지원이므로 즉시 미지원 상태 반환.
    """
    today_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # IOS-XE 는 NX-API 미지원
    if device_os != "nxos":
        return {
            "device_name": device_name,
            "updated_time": today_time,
            "device_os": device_os,
            "products": join_products,
            "mgmt_ip": device_ip,
            "valid_source_address_count": 0,
            "valid_oif_count": 0,
            "min_uptime": "확인필요",
            "rp_addresses": [],
            "rpf_nbrs": "확인필요",
            "connected_server_count": 0,
            "mroute": [],
            "_collect_status": "unsupported_os",
            "_error": f"NX-API 미지원 OS: {device_os}",
        }

    # NX-API 호출
    nxapi = query_multicast_info(device_ip)

    if not nxapi.get("success"):
        return {
            "device_name": device_name,
            "updated_time": today_time,
            "device_os": device_os,
            "products": join_products,
            "mgmt_ip": device_ip,
            "valid_source_address_count": 0,
            "valid_oif_count": 0,
            "min_uptime": "확인필요",
            "rp_addresses": [],
            "rpf_nbrs": "확인필요",
            "connected_server_count": 0,
            "mroute": [],
            "_collect_status": "collect_failed",
            "_error": nxapi.get("error") or "NX-API 호출 실패",
        }

    # 파싱
    routes = _parse_mroute_routes(nxapi.get("mroute_body"))
    valid_src_cnt = _count_valid_source_address(routes)
    oif_data = _calc_valid_oif_and_min_uptime(routes, client_vlan)
    rps = _parse_pim_rp(nxapi.get("pim_rp_body"))
    conn_srv_cnt = _count_connected_servers(nxapi.get("intf_status_body"), client_vlan)
    sg_pairs = _extract_valid_sg_pairs(routes)

    return {
        "device_name": device_name,
        "updated_time": today_time,
        "device_os": device_os,
        "products": join_products,
        "mgmt_ip": device_ip,
        "valid_source_address_count": valid_src_cnt,
        "valid_oif_count": oif_data["valid_oif_count"],
        "min_uptime": oif_data["min_uptime"],
        "rp_addresses": rps,
        "rpf_nbrs": oif_data["rpf_nbrs"],
        "connected_server_count": conn_srv_cnt,
        "mroute": [{"cmd": "show_ip_mroute", "parsed_output": nxapi.get("mroute_body")}],
        # batch._extract_valid_sg_pairs() 가 Genie 형식만 파싱하므로, NX-API 결과를
        # 그쪽에서 다시 파싱 못함 → 우리가 미리 계산한 결과를 우선 사용하도록 키로 동봉
        "valid_sg_pairs": sg_pairs,
        "_collect_status": "ok",
    }


def collect_all_devices_via_api(testbed_devices: dict, max_workers: int = 20) -> list:
    """testbed.devices 딕셔너리(yaml 로드 결과) → NXOS 장비만 NX-API 수집 후 결과 list 반환 (병렬).

    IOS-XE 등 NX-API 미지원 OS 는 본 함수에서 **수집 대상에서 제외** (결과 리스트에 포함 안 됨).
    회원사-운영시세(API) 메뉴는 NX-API 수집 가능 장비만 노출하는 정책.

    testbed_devices 구조 (genie.testbed.load 결과의 devices):
      { "device_name": <Device object with .os, .connections.default.ip, .custom>, ... }
    """
    # NX-API 호출 대상 장비만 미리 선별 (IOS-XE 등 제외)
    target_list = []  # [(name, ip, os, products, vlan), ...]
    for name in testbed_devices.keys():
        dev = testbed_devices[name]
        try:
            os_name = str(dev.os)
        except Exception as e:
            logger.error(f"[NXAPI] device {name} 정의 파싱 실패: {e}")
            continue
        if os_name != "nxos":
            # IOS-XE 등 NX-API 미지원 OS 는 본 메뉴 수집 대상에서 제외
            continue
        try:
            ip = str(dev.connections.default.ip)
            join_products = dev.custom.get("join_products", []) if hasattr(dev, "custom") else []
            client_vlan = str(dev.custom.get("client_vlan", 1100)) if hasattr(dev, "custom") else "1100"
        except Exception as e:
            logger.error(f"[NXAPI] device {name} 정의 파싱 실패: {e}")
            continue
        target_list.append((name, ip, os_name, join_products, client_vlan))

    results = [None] * len(target_list)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(collect_device_multicast_via_api, name, ip, os_name, products, vlan): idx
            for idx, (name, ip, os_name, products, vlan) in enumerate(target_list)
        }
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                results[idx] = fut.result(timeout=30)
            except Exception as e:
                results[idx] = {
                    "device_name": target_list[idx][0],
                    "_collect_status": "exception",
                    "_error": str(e),
                }

    return [r for r in results if r is not None]
