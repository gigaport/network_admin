import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

NXAPI_USERNAME = os.environ.get("NXAPI_USERNAME", "")
NXAPI_PASSWORD = os.environ.get("NXAPI_PASSWORD", "")
NXAPI_TIMEOUT = 15


def query_interfaces(ip: str, interfaces: list) -> dict:
    """NX-API로 특정 인터페이스 상태 조회

    HTTP 4xx/5xx (인증/권한 실패 등) 응답이 하나라도 발생하면 success=False로 반환하여
    상위에서 reachable=False 처리되도록 한다. 부분 실패 데이터를 정상으로 오인하여
    오탐 알림(예: HTTP 401 → 모든 oper_state=unknown → DR 전환 오탐)을 막기 위함.
    """
    result = {"success": False, "interfaces": [], "error": None}

    try:
        url = f"http://{ip}/ins"
        headers = {"Content-Type": "application/json"}
        auth = (NXAPI_USERNAME, NXAPI_PASSWORD)

        any_http_error = False
        for intf in interfaces:
            payload = {
                "ins_api": {
                    "version": "1.0",
                    "type": "cli_show",
                    "chunk": "0",
                    "sid": "1",
                    "input": f"show interface {intf}",
                    "output_format": "json"
                }
            }

            resp = requests.post(url, json=payload, headers=headers, auth=auth, timeout=NXAPI_TIMEOUT)

            if resp.status_code != 200:
                any_http_error = True
                if not result["error"]:
                    result["error"] = f"HTTP {resp.status_code} ({ip})"
                logger.error(f"NX-API HTTP {resp.status_code}: {ip} {intf}")
                result["interfaces"].append({
                    "name": intf,
                    "admin_state": "-",
                    "oper_state": "unknown",
                    "speed": "-",
                    "mtu": "-",
                    "description": "",
                    "last_link_flapped": "-",
                    "error": f"HTTP {resp.status_code}"
                })
                continue

            data = resp.json()
            body = data.get("ins_api", {}).get("outputs", {}).get("output", {}).get("body", {})
            row = body.get("TABLE_interface", {}).get("ROW_interface", {})

            if isinstance(row, list):
                row = row[0] if row else {}

            result["interfaces"].append({
                "name": row.get("interface", intf),
                "admin_state": row.get("admin_state", "-"),
                "oper_state": row.get("state", "unknown"),
                "speed": row.get("eth_speed", "-"),
                "mtu": row.get("eth_mtu", "-"),
                "description": row.get("desc", ""),
                "last_link_flapped": row.get("eth_link_flapped", "-")
            })

        # 모든 호출이 HTTP 200 이었을 때만 success=True
        result["success"] = not any_http_error

    except requests.exceptions.ConnectTimeout:
        result["error"] = f"연결 타임아웃 ({ip})"
        logger.error(f"NX-API 연결 타임아웃: {ip}")
    except requests.exceptions.ConnectionError:
        result["error"] = f"연결 실패 ({ip})"
        logger.error(f"NX-API 연결 실패: {ip}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"NX-API 조회 오류 ({ip}): {e}")

    return result


def query_config_checks(ip: str, checks: list) -> dict:
    """NX-API로 설정(route, prefix-list 등) 존재 여부 확인

    HTTP 4xx/5xx 가 발생한 경우 success=False 로 반환하여 상위에서 reachable=False
    처리되도록 한다 (HTTP 401 → config_found=False → DR 전환 오탐 방지).
    """
    result = {"success": False, "checks": [], "error": None}

    try:
        url = f"http://{ip}/ins"
        headers = {"Content-Type": "application/json"}
        auth = (NXAPI_USERNAME, NXAPI_PASSWORD)

        any_http_error = False
        for check in checks:
            payload = {
                "ins_api": {
                    "version": "1.0",
                    "type": "cli_show",
                    "chunk": "0",
                    "sid": "1",
                    "input": check["command"],
                    "output_format": "json"
                }
            }

            check_result = {
                "type": check["type"],
                "description": check["description"],
                "expected": check.get("expected", ""),
                "found": False,
                "detail": ""
            }

            try:
                resp = requests.post(url, json=payload, headers=headers, auth=auth, timeout=NXAPI_TIMEOUT)

                if resp.status_code != 200:
                    any_http_error = True
                    if not result["error"]:
                        result["error"] = f"HTTP {resp.status_code} ({ip})"
                    logger.error(f"NX-API HTTP {resp.status_code}: {ip} config check")
                    check_result["detail"] = f"HTTP {resp.status_code}"
                    result["checks"].append(check_result)
                    continue

                data = resp.json()
                output = data.get("ins_api", {}).get("outputs", {}).get("output", {})
                body = output.get("body", {})
                code = output.get("code", "")

                # 에러 응답 처리 (명령 실패 = 설정 없음)
                if code and str(code) != "200":
                    check_result["found"] = False
                    check_result["detail"] = output.get("msg", "설정 없음")
                elif check["type"] == "route":
                    # show ip route에서 expected gateway 포함 여부
                    body_str = str(body)
                    check_result["found"] = check["expected"] in body_str
                    check_result["detail"] = "설정됨" if check_result["found"] else "미설정"
                elif check["type"] == "prefix_list":
                    # show ip prefix-list에서 expected prefix 포함 여부
                    body_str = str(body)
                    check_result["found"] = check["expected"] in body_str
                    check_result["detail"] = "설정됨" if check_result["found"] else "미설정"

            except Exception as e:
                check_result["detail"] = str(e)

            result["checks"].append(check_result)

        # 모든 config check 가 HTTP 200 이었을 때만 success=True
        result["success"] = not any_http_error

    except requests.exceptions.ConnectTimeout:
        result["error"] = f"연결 타임아웃 ({ip})"
        logger.error(f"NX-API config check 타임아웃: {ip}")
    except requests.exceptions.ConnectionError:
        result["error"] = f"연결 실패 ({ip})"
        logger.error(f"NX-API config check 연결 실패: {ip}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"NX-API config check 오류 ({ip}): {e}")

    return result


def query_pim_sparse_check(ip: str, groups: list) -> dict:
    """
    NX-API로 ip pim sparse-mode 설정 여부를 그룹별로 확인

    groups = [
        {"description": "Ethernet1/41", "interfaces": ["Ethernet1/41"]},
        {"description": "Ethernet1/45.3801~3825", "interfaces": ["Ethernet1/45.3801", ..., "Ethernet1/45.3825"]},
    ]
    """
    result = {"success": False, "checks": [], "error": None}

    try:
        url = f"http://{ip}/ins"
        headers = {"Content-Type": "application/json"}
        auth = (NXAPI_USERNAME, NXAPI_PASSWORD)

        payload = {
            "ins_api": {
                "version": "1.0",
                "type": "cli_show",
                "chunk": "0",
                "sid": "1",
                "input": "show ip pim interface brief vrf all",
                "output_format": "json"
            }
        }

        resp = requests.post(url, json=payload, headers=headers, auth=auth, timeout=NXAPI_TIMEOUT)

        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result

        data = resp.json()
        output = data.get("ins_api", {}).get("outputs", {}).get("output", {})
        pim_interfaces = set()

        def _extract_pim_names(body):
            """PIM 인터페이스명 추출 (다양한 NX-OS 응답 구조 지원)"""
            if not isinstance(body, dict):
                return
            # 구조1: TABLE_vrf > ROW_vrf > TABLE_brief > ROW_brief
            vrf_table = body.get("TABLE_vrf", {}).get("ROW_vrf", {})
            if vrf_table:
                if isinstance(vrf_table, dict):
                    vrf_table = [vrf_table]
                for vrf in vrf_table:
                    rows = vrf.get("TABLE_brief", {}).get("ROW_brief", [])
                    if isinstance(rows, dict):
                        rows = [rows]
                    for row in rows:
                        name = row.get("if-name", "")
                        if name:
                            pim_interfaces.add(name)
                return
            # 구조2: TABLE_iod > ROW_iod
            rows = body.get("TABLE_iod", {}).get("ROW_iod", [])
            if isinstance(rows, dict):
                rows = [rows]
            for row in rows:
                name = row.get("if-name", "")
                if name:
                    pim_interfaces.add(name)

        if isinstance(output, list):
            for o in output:
                _extract_pim_names(o.get("body", {}))
        else:
            _extract_pim_names(output.get("body", {}))

        # 그룹별 체크
        for group in groups:
            total = len(group["interfaces"])
            found_count = 0
            for intf in group["interfaces"]:
                if intf in pim_interfaces:
                    found_count += 1

            all_found = found_count == total
            result["checks"].append({
                "type": "pim_sparse",
                "description": group["description"] + " ip pim sparse-mode",
                "expected": f"{total}개",
                "found": all_found,
                "detail": f"{found_count}/{total} 설정됨" if total > 1 else ("설정됨" if all_found else "미설정")
            })

        result["success"] = True

    except requests.exceptions.ConnectTimeout:
        result["error"] = f"연결 타임아웃 ({ip})"
        logger.error(f"NX-API PIM check 타임아웃: {ip}")
    except requests.exceptions.ConnectionError:
        result["error"] = f"연결 실패 ({ip})"
        logger.error(f"NX-API PIM check 연결 실패: {ip}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"NX-API PIM check 오류 ({ip}): {e}")

    return result


def query_multicast_info(ip: str) -> dict:
    """NX-API 로 회원사-운영시세(API) 메뉴용 멀티캐스트 정보 일괄 조회.

    한 번의 HTTP 호출로 다음 3개 명령을 cli_show 묶음 실행:
      - show ip mroute
      - show ip pim rp
      - show interface status

    반환 구조:
      {
        "success": True/False,
        "error": "..." (실패 시),
        "mroute_body": <NX-API outputs.body for mroute>,
        "pim_rp_body": <... for pim rp>,
        "intf_status_body": <... for interface status>,
      }
    """
    result = {
        "success": False, "error": None,
        "mroute_body": None, "pim_rp_body": None, "intf_status_body": None,
    }

    cmds = ["show ip mroute", "show ip pim rp", "show interface status"]

    try:
        url = f"http://{ip}/ins"
        headers = {"Content-Type": "application/json"}
        auth = (NXAPI_USERNAME, NXAPI_PASSWORD)
        payload = {
            "ins_api": {
                "version": "1.0",
                "type": "cli_show",
                "chunk": "0",
                "sid": "1",
                "input": " ; ".join(cmds),
                "output_format": "json",
            }
        }

        resp = requests.post(url, json=payload, headers=headers, auth=auth, timeout=NXAPI_TIMEOUT)
        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code} ({ip})"
            logger.error(f"NX-API multicast HTTP {resp.status_code}: {ip}")
            return result

        data = resp.json()
        outputs = data.get("ins_api", {}).get("outputs", {}).get("output", [])
        if isinstance(outputs, dict):
            outputs = [outputs]

        bodies = []
        for out in outputs:
            code = out.get("code", "")
            if code and str(code) != "200":
                bodies.append(None)
            else:
                bodies.append(out.get("body"))

        # 명령 순서 보장: cmds 순서대로 응답이 옴
        if len(bodies) >= 1:
            result["mroute_body"] = bodies[0]
        if len(bodies) >= 2:
            result["pim_rp_body"] = bodies[1]
        if len(bodies) >= 3:
            result["intf_status_body"] = bodies[2]

        result["success"] = True

    except requests.exceptions.ConnectTimeout:
        result["error"] = f"연결 타임아웃 ({ip})"
        logger.error(f"NX-API multicast 연결 타임아웃: {ip}")
    except requests.exceptions.ConnectionError:
        result["error"] = f"연결 실패 ({ip})"
        logger.error(f"NX-API multicast 연결 실패: {ip}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"NX-API multicast 오류 ({ip}): {e}")

    return result
