#!/usr/bin/env python3
"""회원사-운영시세(API) 멀티캐스트 수집 cron 스크립트.

기존 batch.py (SSH/pyATS) 와 별개로, NX-API HTTP 한 번 호출로 멀티캐스트 정보를
수집해 multicast_status 테이블의 market_type='pr_members_api' 행으로 저장한다.

- FastAPI 신규 엔드포인트 `/api/v1/network/collect/multicast/cisco_api/pr` 호출
- 결과를 batch.save_multicast_to_db("pr_api", ...) 로 DB 저장
- 알람 발송은 OFF (기존 SSH 결과와 비교 검증 목적, 사용자 정책)
- 1분 주기 cron 실행 (/etc/cron.d/netview)
"""
import sys
import logging
import requests

sys.path.insert(0, "/app")

from batch import save_multicast_to_db, save_json_with_validation, get_collection_meta, FILE_PATH  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("cisco_multicast_api_collect")

FASTAPI_COLLECT_URL = "http://fastapi:8000/api/v1/network/collect/multicast/cisco_api/pr"
MARKET_GUBN = "pr_api"


def main():
    logger.info("[NXAPI-COLLECT] 시작")
    try:
        resp = requests.get(FASTAPI_COLLECT_URL, timeout=60)
    except Exception as e:
        logger.error(f"[NXAPI-COLLECT] FastAPI 호출 실패: {e}")
        return 1

    if resp.status_code != 200:
        logger.error(f"[NXAPI-COLLECT] HTTP {resp.status_code}: {resp.text[:300]}")
        return 1

    try:
        body = resp.json()
    except Exception as e:
        logger.error(f"[NXAPI-COLLECT] JSON 파싱 실패: {e}")
        return 1

    devices = body.get("data") or []
    if not devices:
        logger.warning("[NXAPI-COLLECT] 수집 결과 없음")
        return 0

    # 수집 결과 통계
    ok = sum(1 for d in devices if d.get("_collect_status") == "ok")
    failed = sum(1 for d in devices if d.get("_collect_status") in ("collect_failed", "exception", "definition_error"))
    unsupported = sum(1 for d in devices if d.get("_collect_status") == "unsupported_os")
    total = len(devices)
    logger.info(
        f"[NXAPI-COLLECT] 수집 결과: ok={ok}, failed={failed}, unsupported_os={unsupported}, total={total}"
    )

    # 디버깅/추적용 JSON 스냅샷 저장
    meta = {
        "status": "success" if ok > 0 else "failed",
        "total_devices": total,
        "success_devices": ok,
        "failed_devices": failed,
    }
    try:
        save_json_with_validation(
            f"{FILE_PATH}pr_members_api_mroute.json",
            {"data": devices, "_meta": meta},
            dict(meta),
        )
    except Exception as e:
        logger.warning(f"[NXAPI-COLLECT] JSON 저장 실패(무시): {e}")

    # DB 저장 (multicast_status.market_type = 'pr_members_api')
    # 알람 OFF - check_multicast_info / webhook 호출하지 않음
    try:
        save_multicast_to_db(MARKET_GUBN, devices)
    except Exception as e:
        logger.error(f"[NXAPI-COLLECT] DB 저장 실패: {e}", exc_info=True)
        return 1

    logger.info("[NXAPI-COLLECT] 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
