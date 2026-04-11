import os
import json
import logging
import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

logger = logging.getLogger(__name__)

ARISTA_USERNAME = os.environ.get("NXAPI_USERNAME", "")
ARISTA_PASSWORD = os.environ.get("NXAPI_PASSWORD", "")
ARISTA_TIMEOUT = 15


def _call_eapi(ip: str, cmds: list, auth=None) -> dict:
    """Arista eAPI JSON-RPC 호출"""
    url = f"http://{ip}/command-api"
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "method": "runCmds",
        "params": {
            "version": 1,
            "cmds": cmds,
            "format": "json"
        },
        "id": 1
    }

    resp = requests.post(url, headers=headers, data=json.dumps(payload),
                         auth=auth or (ARISTA_USERNAME, ARISTA_PASSWORD),
                         verify=False, timeout=ARISTA_TIMEOUT)

    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}")

    data = resp.json()
    if "error" in data:
        raise Exception(data["error"].get("message", "eAPI 명령 실패"))

    return data


def query_config_checks(ip: str, checks: list) -> dict:
    """Arista eAPI로 설정(route, prefix-list 등) 존재 여부 확인"""
    result = {"success": False, "checks": [], "error": None}

    try:
        auth = (ARISTA_USERNAME, ARISTA_PASSWORD)

        for check in checks:
            check_result = {
                "type": check["type"],
                "description": check["description"],
                "expected": check.get("expected", ""),
                "found": False,
                "detail": ""
            }

            try:
                data = _call_eapi(ip, [check["command"]], auth)
                results_list = data.get("result", [])
                body_str = json.dumps(results_list)

                if check["type"] == "route":
                    check_result["found"] = check["expected"] in body_str
                    check_result["detail"] = "설정됨" if check_result["found"] else "미설정"
                elif check["type"] == "prefix_list":
                    check_result["found"] = check["expected"] in body_str
                    check_result["detail"] = "설정됨" if check_result["found"] else "미설정"

            except Exception as e:
                check_result["detail"] = str(e)

            result["checks"].append(check_result)

        result["success"] = True

    except requests.exceptions.ConnectTimeout:
        result["error"] = f"연결 타임아웃 ({ip})"
        logger.error(f"Arista eAPI 타임아웃: {ip}")
    except requests.exceptions.ConnectionError:
        result["error"] = f"연결 실패 ({ip})"
        logger.error(f"Arista eAPI 연결 실패: {ip}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Arista eAPI 오류 ({ip}): {e}")

    return result
