"""
멀티캐스트 알람 상태 관리 모듈

장비별 알람 상태를 추적하여 중복 알람을 방지합니다.
- 정상 → 확인필요: 장애 알람 발송 (1회)
- 확인필요 → 확인필요: SKIP (중복 방지)
- 확인필요 → 정상: 복구 알람 발송 (1회)
- 정상 → 정상: SKIP

상태는 파일(/app/data/multicast_alarm_state.json)에 저장됩니다.
멀티워커 환경에서 파일 잠금(fcntl.flock)을 사용하여 워커 간 상태를 동기화합니다.
"""
import fcntl
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

STATE_FILE = Path("/app/data/multicast_alarm_state.json")

# 알람 대상 check_result 값
ALERT_RESULTS = {"확인필요"}
NORMAL_RESULTS = {"정상확인", "회원사연결서버없음", "정상그룹개수초과"}


def _read_state() -> dict:
    """파일에서 알람 상태를 읽습니다. (파일 잠금 내부에서 호출)"""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"알람 상태 파일 로드 실패: {e}")
    return {}


def _write_state(state: dict):
    """알람 상태를 파일에 저장합니다. (파일 잠금 내부에서 호출)"""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"알람 상태 파일 저장 실패: {e}")


def _get_lock_path() -> Path:
    """파일 잠금용 경로를 반환합니다."""
    return STATE_FILE.with_suffix(".lock")


def check_transition(market_gubn: str, device_name: str, check_result: str, details: dict) -> dict:
    """
    장비의 현재 상태와 이전 상태를 비교하여 알람 전환 유형을 반환합니다.

    파일 잠금(flock)을 사용하여 멀티워커 환경에서 안전하게 상태를 관리합니다.

    Args:
        market_gubn: 시장 구분 (pr, ts, pr_information)
        device_name: 장비명
        check_result: 현재 체크 결과 (정상확인, 확인필요, 회원사연결서버없음 등)
        details: 알람 상세 정보 (member_name, mroute_cnt 등)

    Returns:
        dict with keys:
            "action": "send_alert" | "send_recovery" | "skip"
            "alert_time": 장애 발생 시간 (send_alert, send_recovery 시)
            "recovery_time": 복구 시간 (send_recovery 시)
    """
    key = f"{market_gubn}:{device_name}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_alert = check_result in ALERT_RESULTS

    lock_path = _get_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_path, "w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            state = _read_state()
            prev = state.get(key)
            prev_status = prev["status"] if prev else "normal"

            if is_alert and prev_status == "normal":
                # 정상 → 확인필요: 장애 알람 발송
                state[key] = {
                    "status": "alert",
                    "first_alerted_at": now,
                    "last_checked_at": now,
                    "check_result": check_result,
                    "details": _sanitize_details(details),
                }
                _write_state(state)
                logger.info(f"[ALARM] 장애 발생: {key} ({check_result})")
                return {"action": "send_alert", "alert_time": now}

            elif is_alert and prev_status == "alert":
                # 확인필요 → 확인필요: SKIP
                state[key]["last_checked_at"] = now
                state[key]["details"] = _sanitize_details(details)
                _write_state(state)
                logger.debug(f"[ALARM] 장애 지속 (SKIP): {key}")
                return {"action": "skip"}

            elif not is_alert and prev_status == "alert":
                # 확인필요 → 정상: 복구 알람 발송
                alert_time = prev["first_alerted_at"]
                state[key] = {
                    "status": "normal",
                    "last_checked_at": now,
                    "check_result": check_result,
                    "details": _sanitize_details(details),
                }
                _write_state(state)
                logger.info(f"[ALARM] 복구 완료: {key} (장애시작: {alert_time}, 복구: {now})")
                return {"action": "send_recovery", "alert_time": alert_time, "recovery_time": now}

            else:
                # 정상 → 정상: SKIP
                if key in state:
                    state[key]["last_checked_at"] = now
                    _write_state(state)
                return {"action": "skip"}
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)


def get_alert_info(market_gubn: str, device_name: str) -> Optional[dict]:
    """특정 장비의 알람 상태 정보를 반환합니다."""
    key = f"{market_gubn}:{device_name}"
    state = _read_state()
    return state.get(key)


def get_active_alerts() -> Dict[str, dict]:
    """현재 장애 중인 장비 목록을 반환합니다."""
    state = _read_state()
    return {k: v for k, v in state.items() if v.get("status") == "alert"}


def _sanitize_details(details: dict) -> dict:
    """details에서 JSON 직렬화 불가능한 값을 제거합니다."""
    safe = {}
    for k, v in details.items():
        if k in ("member_name", "member_code", "device_name", "device_os",
                  "products", "pim_rp", "product_cnt", "mroute_cnt", "oif_cnt",
                  "rpf_nbr", "connected_server_cnt", "check_result", "market_gubn"):
            safe[k] = v
    return safe
