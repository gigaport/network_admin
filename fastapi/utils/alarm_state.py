"""
멀티캐스트 알람 상태 관리 모듈

장비별 알람 상태를 추적하여 중복 알람을 방지합니다.
- 정상 → 확인필요: 장애 알람 발송 (1회)
- 확인필요 → 확인필요: SKIP (중복 방지)
- 확인필요 → 정상: 복구 알람 발송 (1회)
- 정상 → 정상: SKIP

상태는 메모리(dict) + 파일(/app/data/multicast_alarm_state.json)에 이중 저장됩니다.
FastAPI 프로세스 재시작 시 파일에서 복원합니다.
"""
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

STATE_FILE = Path("/app/data/multicast_alarm_state.json")

# 모듈 레벨 싱글톤 상태 딕셔너리
_alarm_state: Dict[str, dict] = {}
_lock = threading.Lock()

# 알람 대상 check_result 값
ALERT_RESULTS = {"확인필요"}
NORMAL_RESULTS = {"정상확인", "회원사연결서버없음", "정상그룹개수초과"}


def _load_state():
    """파일에서 알람 상태를 복원합니다."""
    global _alarm_state
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                _alarm_state = json.load(f)
            logger.info(f"알람 상태 복원 완료: {len(_alarm_state)}개 장비")
        else:
            _alarm_state = {}
            logger.info("알람 상태 파일 없음, 초기 상태로 시작")
    except Exception as e:
        logger.error(f"알람 상태 파일 로드 실패: {e}")
        _alarm_state = {}


def _save_state():
    """현재 알람 상태를 파일에 저장합니다."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(_alarm_state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"알람 상태 파일 저장 실패: {e}")


def check_transition(market_gubn: str, device_name: str, check_result: str, details: dict) -> dict:
    """
    장비의 현재 상태와 이전 상태를 비교하여 알람 전환 유형을 반환합니다.

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

    with _lock:
        prev = _alarm_state.get(key)
        prev_status = prev["status"] if prev else "normal"

        if is_alert and prev_status == "normal":
            # 정상 → 확인필요: 장애 알람 발송
            _alarm_state[key] = {
                "status": "alert",
                "first_alerted_at": now,
                "last_checked_at": now,
                "check_result": check_result,
                "details": _sanitize_details(details),
            }
            _save_state()
            logger.info(f"[ALARM] 장애 발생: {key} ({check_result})")
            return {"action": "send_alert", "alert_time": now}

        elif is_alert and prev_status == "alert":
            # 확인필요 → 확인필요: SKIP
            _alarm_state[key]["last_checked_at"] = now
            _alarm_state[key]["details"] = _sanitize_details(details)
            _save_state()
            logger.debug(f"[ALARM] 장애 지속 (SKIP): {key}")
            return {"action": "skip"}

        elif not is_alert and prev_status == "alert":
            # 확인필요 → 정상: 복구 알람 발송
            alert_time = prev["first_alerted_at"]
            _alarm_state[key] = {
                "status": "normal",
                "last_checked_at": now,
                "check_result": check_result,
                "details": _sanitize_details(details),
            }
            _save_state()
            logger.info(f"[ALARM] 복구 완료: {key} (장애시작: {alert_time}, 복구: {now})")
            return {"action": "send_recovery", "alert_time": alert_time, "recovery_time": now}

        else:
            # 정상 → 정상: SKIP
            if key in _alarm_state:
                _alarm_state[key]["last_checked_at"] = now
            return {"action": "skip"}


def get_alert_info(market_gubn: str, device_name: str) -> Optional[dict]:
    """특정 장비의 알람 상태 정보를 반환합니다."""
    key = f"{market_gubn}:{device_name}"
    return _alarm_state.get(key)


def get_active_alerts() -> Dict[str, dict]:
    """현재 장애 중인 장비 목록을 반환합니다."""
    return {k: v for k, v in _alarm_state.items() if v.get("status") == "alert"}


def _sanitize_details(details: dict) -> dict:
    """details에서 JSON 직렬화 불가능한 값을 제거합니다."""
    safe = {}
    for k, v in details.items():
        if k in ("member_name", "member_code", "device_name", "device_os",
                  "products", "pim_rp", "product_cnt", "mroute_cnt", "oif_cnt",
                  "rpf_nbr", "connected_server_cnt", "check_result", "market_gubn"):
            safe[k] = v
    return safe


# 모듈 로드 시 파일에서 상태 복원
_load_state()
