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
# 수집실패는 1회성 일시 오류일 가능성이 높아 즉시 알람은 보류.
# 단 PERSISTENT_FAILURE_THRESHOLD_MINUTES 이상 연속 지속되면 1회 알람 발송 (사각지대 방지).
SKIP_RESULTS = {"수집실패"}
PERSISTENT_FAILURE_THRESHOLD_MINUTES = 10


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
            "action": "send_alert" | "send_recovery" | "send_failure_alert" | "send_failure_recovery" | "skip"
            "alert_time": 장애 발생 시간 (send_alert, send_recovery 시)
            "recovery_time": 복구 시간 (send_recovery, send_failure_recovery 시)
            "failure_first_at": 수집실패 첫 발생 시각 (send_failure_alert, send_failure_recovery 시)
            "elapsed_minutes": 수집실패 지속 분 (send_failure_alert 시)
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
            prev_failure_first_at = prev.get("failure_first_at") if prev else None
            prev_failure_alerted = bool(prev.get("failure_alerted")) if prev else False

            # ── 수집실패 처리 (지속 시 1회 알람) ──
            # 첫 수집실패는 일시 오류일 수 있어 SKIP. 그러나 PERSISTENT_FAILURE_THRESHOLD_MINUTES
            # 이상 연속되면 운영 사각지대 방지 목적으로 1회 알람 발송.
            if check_result in SKIP_RESULTS:
                base = dict(prev) if prev else {}
                base["last_checked_at"] = now
                base["check_result"] = check_result

                if not prev_failure_first_at:
                    # 수집실패 첫 발생 - 시작 시각만 기록하고 SKIP
                    base["failure_first_at"] = now
                    base["failure_alerted"] = False
                    state[key] = base
                    _write_state(state)
                    logger.info(f"[ALARM] 수집실패 첫 발생 (SKIP): {key}")
                    return {"action": "skip"}

                # 수집실패 지속 중 - 임계 시간 초과 + 아직 알람 안 보냈으면 발송
                try:
                    elapsed = (datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
                               - datetime.strptime(prev_failure_first_at, "%Y-%m-%d %H:%M:%S")
                               ).total_seconds() / 60.0
                except Exception:
                    elapsed = 0

                if not prev_failure_alerted and elapsed >= PERSISTENT_FAILURE_THRESHOLD_MINUTES:
                    base["failure_alerted"] = True
                    base["details"] = _sanitize_details(details)
                    state[key] = base
                    _write_state(state)
                    logger.warning(
                        f"[ALARM] 수집실패 지속 알람 발송: {key} (지속 {int(elapsed)}분, "
                        f"시작 {prev_failure_first_at})"
                    )
                    return {
                        "action": "send_failure_alert",
                        "failure_first_at": prev_failure_first_at,
                        "elapsed_minutes": int(elapsed),
                    }

                # 임계 미만이거나 이미 알람 보낸 상태 - SKIP
                state[key] = base
                _write_state(state)
                return {"action": "skip"}

            # ── 수집실패 → 정상/확인필요 전환: 수집실패 복구 알람 발송 ──
            # (이전에 send_failure_alert 까지 도달했던 경우만 복구 알람 의미가 있음)
            failure_recovered = prev_failure_alerted
            failure_first_at_snapshot = prev_failure_first_at

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
                # 수집실패 알람 보낸 적 있으면 복구 알람도 같이 발송하도록 alert 와 별개로 signal
                if failure_recovered:
                    return {
                        "action": "send_alert_with_failure_recovery",
                        "alert_time": now,
                        "failure_first_at": failure_first_at_snapshot,
                        "recovery_time": now,
                    }
                return {"action": "send_alert", "alert_time": now}

            elif is_alert and prev_status == "alert":
                # 확인필요 → 확인필요: SKIP
                state[key]["last_checked_at"] = now
                state[key]["details"] = _sanitize_details(details)
                state[key].pop("failure_first_at", None)
                state[key].pop("failure_alerted", None)
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
                # 정상 → 정상: SKIP. 단 직전 수집실패 알람이 발송된 적 있다면 수집실패 복구 알람 발송.
                new_entry = dict(prev) if prev else {"status": "normal"}
                new_entry["last_checked_at"] = now
                new_entry["check_result"] = check_result
                new_entry.pop("failure_first_at", None)
                new_entry.pop("failure_alerted", None)
                state[key] = new_entry
                _write_state(state)

                if failure_recovered:
                    logger.info(
                        f"[ALARM] 수집실패 복구 알람 발송: {key} (시작 {failure_first_at_snapshot}, 복구 {now})"
                    )
                    return {
                        "action": "send_failure_recovery",
                        "failure_first_at": failure_first_at_snapshot,
                        "recovery_time": now,
                    }
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
                  "products", "received_products", "missing_products",
                  "pim_rp", "product_cnt", "mroute_cnt", "oif_cnt",
                  "rpf_nbr", "connected_server_cnt", "check_result", "market_gubn"):
            safe[k] = v
    return safe


# ── DR 훈련 통신불가 알람 상태 ──────────────────────────────────────────
# 통신불가 알람을 발송한 장비를 영구 추적하여 reachable 복귀 시 복구 알람을 발송할 수 있게 한다.
# key: f"{procedure_code}_{device_name}", value: {"proc":..., "dev":..., "ip":..., "label":..., "alerted_at":..., "error":...}
DR_UNREACHABLE_STATE_FILE = Path("/app/data/dr_training_alarm_state.json")


def _read_dr_unreachable_state() -> dict:
    """DR 훈련 통신불가 알람 상태를 파일에서 읽기. 손상/빈 파일은 빈 dict 로 fallback."""
    try:
        if DR_UNREACHABLE_STATE_FILE.exists():
            with open(DR_UNREACHABLE_STATE_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                return {}
            return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"DR 알람 상태 파일 손상 - 빈 dict fallback: {e}")
    except Exception as e:
        logger.error(f"DR 알람 상태 파일 로드 실패: {e}")
    return {}


def _write_dr_unreachable_state(state: dict):
    """DR 훈련 통신불가 알람 상태를 파일에 원자적으로 저장."""
    try:
        import os as _os
        DR_UNREACHABLE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = DR_UNREACHABLE_STATE_FILE.with_suffix(DR_UNREACHABLE_STATE_FILE.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
            f.flush()
            _os.fsync(f.fileno())
        _os.replace(tmp_path, DR_UNREACHABLE_STATE_FILE)
    except Exception as e:
        logger.error(f"DR 알람 상태 파일 저장 실패: {e}")


def dr_load_unreachable_alerted() -> dict:
    """DR 훈련에서 통신불가 알람을 이미 발송한 장비 dict 반환.

    Returns:
        { "proc_dev_key": {"proc":..., "dev":..., "ip":..., "label":..., "alerted_at":..., "error":...}, ... }
    """
    return _read_dr_unreachable_state()


def dr_save_unreachable_alerted(state: dict):
    """DR 훈련 통신불가 알람 상태 영구 저장."""
    _write_dr_unreachable_state(state)
