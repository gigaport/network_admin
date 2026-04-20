"""
Webhook 라우터 - 다양한 서비스로부터의 웹훅을 처리하고 Slack으로 알림 전송
"""
import json
import re
import logging
import threading
import time
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from utils.slack_client import slack_client, send_alert, send_structured
from utils.alarm_state import check_transition, get_alert_info

# 로깅 설정
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


# ── Zabbix 이벤트 중복 방지 캐시 ──
# key: "event_id:event_value", value: 수신 timestamp
_zabbix_sent_cache: Dict[str, float] = {}
_zabbix_cache_lock = threading.Lock()
ZABBIX_DEDUP_TTL = 600  # 동일 이벤트 무시 기간 (10분)


def _zabbix_is_duplicate(event_id: str, event_value: str) -> bool:
    """동일 event_id+event_value 조합이 TTL 내에 이미 처리되었으면 True"""
    key = f"{event_id}:{event_value}"
    now = time.time()

    with _zabbix_cache_lock:
        # 만료된 항목 정리 (100개 초과 시에만 수행하여 오버헤드 최소화)
        if len(_zabbix_sent_cache) > 100:
            expired = [k for k, t in _zabbix_sent_cache.items() if now - t > ZABBIX_DEDUP_TTL]
            for k in expired:
                del _zabbix_sent_cache[k]

        prev_time = _zabbix_sent_cache.get(key)
        if prev_time and now - prev_time < ZABBIX_DEDUP_TTL:
            return True

        _zabbix_sent_cache[key] = now
        return False

# 상수 정의
SYSLOG_NORMAL_KEYWORDS = [
    "Authentication", "PAM", "PWD", "COMMAND", "pam", "auth", 
    "User", "nwcfg", "Login", "Unexpected message type has arrived. Terminating the connection from"
]

SYSLOG_ENDPOINT_MNEMONICS = ["IF_UP", "IF_DOWN", "IF_DUPLEX"]

SYSLOG_NORMAL_FACILITIES = ["USER", "RADIUS"]

ZABBIX_MUTE_KEYWORDS = ["memory"]

# ── Plane 웹훅 설정 ──
PLANE_STATUS_CHANNEL_MAP = {
    "backlog": "network-업무-검토",
    "unstarted": "network-업무-검토",
    "started": "network-업무-진행",
    "completed": "network-업무-완료",
    # cancelled → 전송 안함
}

PLANE_PRIORITY_EMOJI = {
    "urgent": ":rotating_light:",
    "high": ":red_circle:",
    "medium": ":large_orange_circle:",
    "low": ":large_blue_circle:",
    "none": ":white_circle:",
}

PLANE_ACTION_LABEL = {
    "created": (":new:", "이슈 생성"),
    "updated": (":arrows_counterclockwise:", "이슈 변경"),
}

PLANE_STATE_COLOR = {
    "backlog": "#EAB308",
    "unstarted": "#EAB308",
    "started": "#3B82F6",
    "completed": "#22C55E",
}

PLANE_PROJECT_NAMES = {
    "31127685-bd13-4db3-a36e-2f2860e5b8d8": "네트워크 업무정리",
    "7c905f2d-4b4c-444b-88f3-480a6edb4914": "회원관리시스템_프로젝트",
}

# 프로젝트별 채널 고정 (상태 무관하게 단일 채널로 전송, cancelled 포함 모두 전송)
PLANE_PROJECT_CHANNEL_OVERRIDE = {
    "7c905f2d-4b4c-444b-88f3-480a6edb4914": "network-시스템개발",
}

# 채널 매핑 설정
CHANNEL_MAPPINGS = {
    "정보분배": {
        "예정": "정보분배-업무-예정",
        "진행": "정보분배-업무-진행", 
        "검토": "정보분배-업무-검토",
        "이슈": "정보분배-업무-이슈",
        "완료": "정보분배-업무-완료"
    },
    "네트워크": {
        "검토": "network-업무-검토",
        "계약": "network-업무-검토",
        "완료": "network-업무-완료",
        "진행": "network-업무-진행"
    },
    "데이터베이스": {
        "진행": "database-업무-진행",
        "완료": "database-업무-완료",
        "검토": "database-업무-검토",
        "이슈": "database-업무-이슈",
        "예정": "database-업무-예정",
        "기타": "database-업무-기타"
    },
    "정보보안": {
        "진행": "security-회원사-작업",
        "완료": "security-worknote"
    }
}


class WebhookHandler:
    """웹훅 처리를 위한 핸들러 클래스"""
    
    @staticmethod
    def get_channel_for_project(project_name: str, list_name: str, board_name: str) -> str:
        """프로젝트와 리스트명에 따른 채널 결정"""
        if project_name in CHANNEL_MAPPINGS:
            # project_name이 "정보보안"일 경우는 보드명으로 전송할 채널을 구분
            # 보드명이 "WORK NOTE"일 경우는 "security-worknote"로 전송
            # 보드명이 "회원사 작업"일 경우는 "security-회원사-작업"로 전송
            if project_name == "정보보안":
                if board_name == "WORK NOTE":
                    return "security-worknote"
                elif board_name == "회원사 작업":
                    return "security-회원사-작업"
                else:
                    return "unknown"
            mappings = CHANNEL_MAPPINGS[project_name]
            for keyword, channel in mappings.items():
                if keyword in list_name:
                    return channel
                # 기본값 반환
                return mappings.get("기타", "unknown")
        return "unknown"
    
    @staticmethod
    def create_planka_attachment(event_type: str, data: Dict) -> Dict:
        """Planka 이벤트에 따른 첨부파일 생성"""
        base_info = {
            "사용자명": data['user']['name'],
            "보드명": data['data']['included']['boards'][0]['name'],
            "구분": data['data']['included']['lists'][0]['name']
        }
        
        if event_type in ['cardUpdate', 'cardCreate']:
            return {
                "color": "#90EE90",
                "text": (
                    f"사용자명: {base_info['사용자명']}\n"
                    f"보드명: {base_info['보드명']}\n"
                    f"구분: {base_info['구분']}\n"
                    f"카드명: {data['data']['item']['name']}\n"
                    f"카드설명: {data['data']['item']['description']}\n"
                    f"목표일: {data['data']['item']['dueDate']}"
                ),
                "mrkdwn_in": ["text"]
            }
        elif event_type in ['taskUpdate', 'taskCreate']:
            return {
                "color": "#faf697",
                "text": (
                    f"사용자명: {base_info['사용자명']}\n"
                    f"보드명: {base_info['보드명']}\n"
                    f"구분: {base_info['구분']}\n"
                    f"카드명: *{data['data']['included']['cards'][0]['name']}*\n"
                    f"Task명: *{data['data']['item']['name']}*\n"
                    f"완료여부: `{data['data']['item']['isCompleted']}`"
                ),
                "mrkdwn_in": ["text"]
            }
        elif event_type in ['commentUpdate', 'commentCreate']:
            return {
                "color": "#97f4fa",
                "text": (
                    f"사용자명: {base_info['사용자명']}\n"
                    f"보드명: {base_info['보드명']}\n"
                    f"구분: {base_info['구분']}\n"
                    f"카드명: *{data['data']['included']['cards'][0]['name']}*\n\n"
                    f"Comment: \n"
                    f"```{data['data']['item']['text']}```"
                ),
                "mrkdwn_in": ["text"]
            }
        return None


@router.post("/planka")
async def send_planka_webhook_to_slack(request: Request):
    """Planka 웹훅 처리"""
    try:
        data = await request.json()
        logger.info(f"Planka 웹훅 데이터: {data}")
        
        # 채널 결정
        project_name = data['data']['included']['projects'][0]['name']
        list_name = data['data']['included']['lists'][0]['name']
        board_name = data['data']['included']['boards'][0]['name']
        channel = WebhookHandler.get_channel_for_project(project_name, list_name, board_name)

        logger.info(f"프로젝트: {project_name}, 리스트: {list_name}, 보드: {board_name}, 채널: {channel}")
        
        # 이벤트 타입 확인
        event_type = data['event']
        if event_type not in ['cardUpdate', 'cardCreate', 'taskUpdate', 'taskCreate', 'commentUpdate', 'commentCreate']:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"result": "error", "detail": "지원하지 않는 이벤트입니다."}
            )
        
        # 메시지 구성
        attachment = WebhookHandler.create_planka_attachment(event_type, data)
        if not attachment:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"result": "error", "detail": "메시지 생성 실패"}
            )
        
        # Slack 메시지 전송 (백그라운드 스레드)
        def _send_planka():
            try:
                slack_client.send_message(
                    channel=channel,
                    text=f"Planka 이벤트: {event_type}",
                    attachments=[attachment]
                )
            except Exception as e:
                logger.error(f"Planka Slack 전송 오류: {e}")
        threading.Thread(target=_send_planka, daemon=True).start()

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"result": "success", "detail": "전송처리가 완료되었습니다."}
        )
        
    except Exception as e:
        logger.error(f"Planka 웹훅 처리 오류: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"result": "error", "detail": str(e)}
        )


def _strip_html(html_str: str) -> str:
    """HTML 태그를 제거하고 순수 텍스트만 반환"""
    if not html_str:
        return ''
    text = re.sub(r'<br\s*/?>', '\n', html_str)
    text = re.sub(r'</?(p|li|div|ol|ul)[^>]*>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


@router.post("/plane")
async def send_plane_webhook_to_slack(request: Request):
    """Plane 웹훅 처리 - 이슈/댓글 이벤트를 Slack으로 전송"""
    try:
        data = await request.json()
        logger.info(f"Plane 웹훅 수신: event={data.get('event')}, action={data.get('action')}")
        logger.info(f"Plane 웹훅 전체 데이터: {json.dumps(data, ensure_ascii=False, default=str)}")

        event = data.get('event', '')
        action = data.get('action', '')

        # issue_comment 이벤트 처리
        if event == 'issue_comment' and action in ('created', 'updated'):
            return await _handle_plane_comment(data, action)

        # issue 이벤트의 created/updated만 처리
        if event != 'issue' or action not in ('created', 'updated'):
            logger.info(f"Plane 웹훅 무시: event={event}, action={action}")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"result": "skipped", "detail": f"이벤트 미처리: {event}/{action}"}
            )

        issue = data.get('data', {})
        activity = data.get('activity') or {}

        # state 필드에서 상태 그룹 추출 (Plane은 state_detail이 아닌 state 사용)
        state_info = issue.get('state') or {}
        state_group = state_info.get('group', '')
        project_id = issue.get('project', '')

        # 프로젝트별 채널 오버라이드 (상태 무관하게 단일 채널)
        channel = PLANE_PROJECT_CHANNEL_OVERRIDE.get(project_id)
        if not channel:
            # 기본: 상태 그룹별 채널 매핑 (cancelled은 전송 안함)
            channel = PLANE_STATUS_CHANNEL_MAP.get(state_group)
            if not channel:
                logger.info(f"Plane 웹훅 채널 미매핑 (state_group={state_group}), 전송 안함")
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={"result": "skipped", "detail": f"미매핑 상태: {state_group}"}
                )

        # 이슈 정보 추출
        issue_name = issue.get('name', '제목 없음')
        project_name = PLANE_PROJECT_NAMES.get(project_id, '')
        sequence_id = issue.get('sequence_id', '')
        priority = issue.get('priority') or 'none'
        description = (issue.get('description_stripped') or '').strip()
        target_date = issue.get('target_date') or ''
        start_date = issue.get('start_date') or ''
        state_name = state_info.get('name', state_group)

        # 작업자 (activity.actor에서 추출)
        actor = activity.get('actor') or {}
        actor_name = actor.get('display_name') or actor.get('first_name') or ''

        # 이모지/라벨
        action_emoji, action_label = PLANE_ACTION_LABEL.get(action, ('', action))
        priority_emoji = PLANE_PRIORITY_EMOJI.get(priority, ':white_circle:')
        color = PLANE_STATE_COLOR.get(state_group, '#439FE0')

        # 타이틀 (프로젝트명 포함)
        if project_name:
            title = f"{action_emoji} [{project_name}] {action_label}"
        else:
            title = f"{action_emoji} {action_label}"

        # 메시지 본문 구성
        text_lines = []
        text_lines.append(f"*{issue_name}*")
        text_lines.append(f"상태: `{state_name}`  |  우선순위: {priority_emoji} `{priority}`")
        if actor_name:
            text_lines.append(f"작업자: *{actor_name}*")
        if target_date:
            date_str = f"마감일: `{target_date}`"
            if start_date:
                date_str = f"기간: `{start_date}` ~ `{target_date}`"
            text_lines.append(date_str)
        if description:
            desc_preview = description[:200] + ('...' if len(description) > 200 else '')
            text_lines.append(f"\n{desc_preview}")

        attachment = {
            "color": color,
            "text": '\n'.join(text_lines),
            "mrkdwn_in": ["text"]
        }

        # Slack 전송 (백그라운드 스레드)
        def _send_plane():
            try:
                slack_client.send_message(
                    channel=channel,
                    text=f"{title}: {issue_name}",
                    attachments=[attachment]
                )
                logger.info(f"Plane Slack 전송 완료: {issue_name} -> {channel}")
            except Exception as e:
                logger.error(f"Plane Slack 전송 오류: {e}")
        threading.Thread(target=_send_plane, daemon=True).start()

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"result": "success", "detail": f"{channel}로 전송 완료"}
        )

    except Exception as e:
        logger.error(f"Plane 웹훅 처리 오류: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"result": "error", "detail": str(e)}
        )


async def _handle_plane_comment(data: dict, action: str):
    """Plane 이슈 댓글 이벤트 처리"""
    comment = data.get('data', {})
    activity = data.get('activity') or {}

    project_id = comment.get('project', '')
    issue_id = comment.get('issue', '')
    comment_html = comment.get('comment_html', '')
    comment_text = _strip_html(comment_html)

    # 작성자
    actor = activity.get('actor') or {}
    actor_name = actor.get('display_name') or actor.get('first_name') or '알 수 없음'

    # 채널 결정 (프로젝트 오버라이드 우선, 없으면 기본 채널)
    channel = PLANE_PROJECT_CHANNEL_OVERRIDE.get(project_id)
    if not channel:
        channel = PLANE_STATUS_CHANNEL_MAP.get('started', 'network-업무-진행')

    project_name = PLANE_PROJECT_NAMES.get(project_id, '')
    action_label = "댓글 추가" if action == 'created' else "댓글 수정"

    # 타이틀
    if project_name:
        title = f":speech_balloon: [{project_name}] {action_label}"
    else:
        title = f":speech_balloon: {action_label}"

    # 본문 구성
    text_lines = []
    text_lines.append(f"작성자: *{actor_name}*")
    if comment_text:
        preview = comment_text[:300] + ('...' if len(comment_text) > 300 else '')
        text_lines.append(f"\n{preview}")

    attachment = {
        "color": "#17A2B8",
        "text": '\n'.join(text_lines),
        "mrkdwn_in": ["text"]
    }

    def _send_comment():
        try:
            slack_client.send_message(
                channel=channel,
                text=f"{title}",
                attachments=[attachment]
            )
            logger.info(f"Plane 댓글 Slack 전송 완료: {actor_name} -> {channel}")
        except Exception as e:
            logger.error(f"Plane 댓글 Slack 전송 오류: {e}")
    threading.Thread(target=_send_comment, daemon=True).start()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"result": "success", "detail": f"댓글 {channel}로 전송 완료"}
    )


@router.post("/syslog")
async def send_syslog_webhook_to_slack(request: Request):
    """Syslog 웹훅 처리"""
    try:
        # JSON 데이터 파싱
        try:
            data = await request.json()
        except Exception as json_error:
            logger.error(f"JSON 파싱 오류: {json_error}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "result": False,
                    "error": "Invalid JSON format",
                    "detail": str(json_error)
                }
            )
        
        logger.info(f"Syslog 수신: {data}")
        
        # 필수 필드 검증
        required_fields = ['device', 'host_ip', 'timestamp_trans', 'severity', 'facility', 'mnemonic', 'message']
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        
        if missing_fields:
            logger.warning(f"필수 필드 누락: {missing_fields}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "result": False,
                    "error": "Missing required fields",
                    "detail": f"Required fields missing: {missing_fields}"
                }
            )
        
        # 채널 결정 로직
        channel = "#network-alert-syslog"
        
        message = data.get("message", "")
        facility = data.get("facility", "")
        mnemonic = data.get("mnemonic", "")
        
        if (any(keyword in message for keyword in SYSLOG_NORMAL_KEYWORDS) or
            any(keyword in facility for keyword in SYSLOG_NORMAL_FACILITIES)):
            channel = "#network-alert-normal"

        
        
        # 메시지 전송 (백그라운드 스레드로 처리하여 이벤트 루프 블로킹 방지)
        threading.Thread(target=_send_syslog_to_slack, args=(channel, data), daemon=True).start()

        return JSONResponse(
            content={
                "result": True,
                "status": "ok",
                "message": "Syslog processed successfully"
            }
        )
        
    except Exception as e:
        logger.error(f"Syslog 처리 오류: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "result": False,
                "error": "Internal server error",
                "detail": str(e)
            }
        )


@router.post("/grafana")
async def send_grafana_webhook_to_slack(request: Request):
    """Grafana 웹훅 처리 - 알림을 Slack으로 전송"""
    try:
        data = await request.json()
        logger.info(f"Grafana 웹훅 수신: status={data.get('status')}, title={data.get('title', '')[:80]}")

        alerts = data.get('alerts', [])
        if not alerts:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"result": "skipped", "detail": "알림 없음"}
            )

        channel = "network-alert-critical"
        sent_count = 0

        for alert in alerts:
            alert_status = alert.get('status', 'firing')
            labels = alert.get('labels', {})
            annotations = alert.get('annotations', {})
            values = alert.get('values', {})

            alertname = labels.get('alertname', 'Unknown Alert')
            company = labels.get('company', '')
            host = labels.get('host', '')
            item = labels.get('item', '')
            severity = labels.get('severity', 'warning')
            alert_type = labels.get('alert_type', '')
            folder = labels.get('grafana_folder', '')
            summary = annotations.get('summary', '')
            description = annotations.get('description', '')
            starts_at = alert.get('startsAt', '')

            # 시간 포맷 (ISO → 읽기 쉬운 형식)
            time_str = starts_at[:19].replace('T', ' ') if starts_at else ''

            # firing/resolved 구분
            if alert_status == 'resolved':
                emoji = ":white_check_mark:"
                status_label = "복구"
                color = "#22C55E"
                ends_at = alert.get('endsAt', '')
                end_time_str = ends_at[:19].replace('T', ' ') if ends_at and not ends_at.startswith('0001') else ''
            else:
                emoji = ":rotating_light:"
                status_label = "장애"
                color = "#EF4444"
                end_time_str = ''

            # 측정값 포맷 (ms 단위)
            def _fmt_val(k, v):
                try:
                    return f"{k}={round(float(v), 3)}ms"
                except (ValueError, TypeError):
                    return f"{k}={v}"
            values_str = ', '.join(_fmt_val(k, v) for k, v in values.items()) if values else ''

            title = f"{emoji} [{status_label}] {alertname}"

            # 메시지 필드 구성
            fields = [
                {"title": "알림명", "value": f"*{alertname}*", "short": False},
            ]
            if company:
                fields.append({"title": "회원사", "value": f"`{company}`", "short": True})
            if host:
                fields.append({"title": "호스트", "value": f"`{host}`", "short": True})
            if item:
                fields.append({"title": "항목", "value": f"`{item}`", "short": False})
            if severity:
                fields.append({"title": "심각도", "value": f"`{severity}`", "short": True})
            if folder:
                fields.append({"title": "폴더", "value": folder, "short": True})
            if time_str:
                fields.append({"title": "발생시간", "value": f"`{time_str}`", "short": True})
            if end_time_str:
                fields.append({"title": "복구시간", "value": f"`{end_time_str}`", "short": True})
            if values_str:
                fields.append({"title": "측정값", "value": f"`{values_str}`", "short": False})

            message_text = description or summary or ''

            def _send_grafana(ch=channel, t=title, msg=message_text, c=color, f=fields):
                try:
                    send_alert(channel=ch, title=t, message=msg, color=c, fields=f)
                    logger.info(f"Grafana Slack 전송 완료: {t[:60]} -> {ch}")
                except Exception as e:
                    logger.error(f"Grafana Slack 전송 오류: {e}")

            threading.Thread(target=_send_grafana, daemon=True).start()
            sent_count += 1

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"result": "success", "detail": f"{sent_count}건 전송 완료"}
        )

    except Exception as e:
        logger.error(f"Grafana 웹훅 처리 오류: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"result": "error", "detail": str(e)}
        )


@router.post("/zabbix")
async def send_zabbix_webhook_to_slack(request: Request):
    """Zabbix 웹훅 처리"""
    try:
        # JSON 데이터 파싱
        try:
            data = await request.json()
        except Exception as json_error:
            logger.error(f"JSON 파싱 오류: {json_error}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "result": False,
                    "error": "Invalid JSON format",
                    "detail": str(json_error)
                }
            )
        
        logger.info(f"Zabbix 웹훅 수신: {data}")

        # 필수 필드 검증
        required_fields = ['hostname', 'event_name', 'event_value', 'severity', 'host_group', 'event_date', 'event_time', 'opdata']
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]

        if missing_fields:
            logger.warning(f"필수 필드 누락: {missing_fields}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "result": False,
                    "error": "Missing required fields",
                    "detail": f"Required fields missing: {missing_fields}"
                }
            )

        # 중복 이벤트 체크 (event_id + event_value 기반)
        event_id = data.get('event_id', '')
        event_value = data.get('event_value', '')

        if event_id and _zabbix_is_duplicate(event_id, event_value):
            logger.info(f"Zabbix 중복 이벤트 스킵: event_id={event_id}, event_value={event_value}")
            return JSONResponse(
                content={
                    "result": True,
                    "response": {
                        "code": 200,
                        "message": "[OK]duplicate event skipped."
                    }
                },
                headers={"Content-Type": "application/json; charset=utf-8"}
            )

        # 채널 결정
        channel = "network-alert-critical"

        # 회원사 스위치 구분
        hostname = data.get('hostname', '')
        event_name = data.get('event_name', '')
        severity = data.get('severity', '')

        logger.info(f"Zabbix 웹훅 수신: {hostname} - {event_name} - {severity}")

        if any(keyword in hostname for keyword in ["mpr", "ord", "com"]):
            if bool(re.search(r'\(\s*\)', event_name)):
                channel = "network-alert-endpoint"

        if any(keyword in event_name for keyword in ["**"]):
            channel = "network-alert-endpoint"
            logger.info(f"endpoint 채널로 전송 : {event_name}")

        # severity가 Informational이면 network-alert-normal 채널로 전송
        if severity == "Information":
            channel = "network-alert-normal"

        # 메시지 구성 및 전송 (백그라운드 스레드로 처리)
        if not any(keyword in event_name for keyword in ZABBIX_MUTE_KEYWORDS):
            threading.Thread(target=send_zabbix_message, args=(channel, data), daemon=True).start()
        
        return JSONResponse(
            content={
                "result": True,
                "response": {
                    "code": 200,
                    "message": "[OK]send to message."
                }
            },
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except Exception as e:
        logger.error(f"Zabbix 웹훅 처리 오류: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "result": False,
                "error": "Internal server error",
                "detail": str(e)
            }
        )


def _send_syslog_to_slack(channel: str, message_info: Dict):
    """Syslog 메시지를 Slack으로 직접 전송 (최적화된 통합 함수)"""
    try:
        # 특정 장비 예외 처리 (한국투자증권 여의도 DMA용 시세스위치 MAC FLAP 메세지)
        device = message_info.get('device', '')
        facility = message_info.get('facility', '')

        if device in ["kr_1_px_ydkt_n_mpr_01", "kr_1_px_ydkt_n_mpr_02"] and facility == "L2FM":
            logger.info(f"특정 장비 예외 처리로 메시지 스킵: {device} - {facility}")
            return

        # 메시지 데이터 안전성 검증
        device = message_info.get('device', 'Unknown')
        host_ip = message_info.get('host_ip', 'Unknown')
        timestamp = message_info.get('timestamp_trans', 'Unknown')
        severity = message_info.get('severity', 'unknown')
        facility = message_info.get('facility', 'Unknown')
        mnemonic = message_info.get('mnemonic', 'Unknown')
        msg_type = message_info.get('type', 'unknown')
        message = message_info.get('message', 'No message')

        # Slack 메시지 필드 구성
        fields = [
            {"title": "장비이름", "value": f"*{device}*", "short": True},
            {"title": "장비IP", "value": f"`{host_ip}`", "short": True},
            {"title": "발생일시", "value": f"`{timestamp}`", "short": True},
            {"title": "Level", "value": f"`{severity.upper()}`", "short": True},
            {"title": "Facility", "value": facility, "short": True},
            {"title": "Mnemonic", "value": mnemonic, "short": True},
            {"title": "Type", "value": msg_type.upper(), "short": True}
        ]

        # 메시지 내용
        message_text = f"Message: ```{message}```"

        # 심각도에 따른 색상 결정
        color_map = {
            "emergency": "#8B0000",    # 다크레드
            "alert": "#FF0000",        # 레드
            "critical": "#FF4500",     # 오렌지레드
            "error": "#FFA500",        # 오렌지
            "warning": "#FFFF00",      # 옐로우
            "notice": "#00CED1",       # 다크터콰이즈
            "info": "#87CEEB",         # 스카이블루
            "debug": "#D3D3D3"         # 라이트그레이
        }
        alert_color = color_map.get(severity.lower(), "warning")

        # Slack 알림 전송
        send_alert(
            channel=channel,
            title=f":warning: {severity.upper()}>>{device} :warning:",
            message=message_text,
            color=alert_color,
            fields=fields
        )

        logger.info(f"Syslog 메시지 전송 완료: {device} -> {channel}")

    except Exception as e:
        logger.error(f"Syslog 메시지 전송 오류: {e}")
        # 전송 실패해도 웹훅은 성공으로 처리 (Slack 장애 시 서비스 중단 방지)


def send_zabbix_message(channel: str, data: Dict):
    """Zabbix 메시지 전송"""
    try:
        # 데이터 안전성 검증
        hostname = data.get('hostname', 'Unknown')
        event_name = data.get('event_name', 'Unknown Event')
        event_value = data.get('event_value', '1')
        severity = data.get('severity', 'Unknown')
        host_group = data.get('host_group', 'Unknown')
        event_date = data.get('event_date', 'Unknown')
        event_time = data.get('event_time', 'Unknown')
        opdata = data.get('opdata', 'No data')
        event_duration = data.get('event_duration', 'Unknown')
        
        is_resolved = str(event_value) == '0'

        logger.info(f"Zabbix 메시지 수신: {hostname} - {event_name} - {event_value} - {severity} - {host_group} - {event_date} - {event_time} - {opdata} - {event_duration}")
        
        if is_resolved:
            title = f":green-check-mark: {hostname} >> {event_name}"
            color = "#3bc95c"
            fields = [
                {"title": "대상장비", "value": f"`{hostname}`", "short": True},
                {"title": "대상그룹", "value": f"`{host_group}`", "short": True},
                {"title": "LEVEL", "value": f"`{severity}`", "short": True},
                {"title": "발생일시", "value": f"{event_date} {event_time}", "short": True},
                {"title": "경과시간", "value": f"`{event_duration}`", "short": False}
            ]
        else:
            title = f":critical: {hostname} >> {event_name}"
            color = "#e71c1c"
            fields = [
                {"title": "대상장비", "value": f"`{hostname}`", "short": True},
                {"title": "대상그룹", "value": f"`{host_group}`", "short": True},
                {"title": "LEVEL", "value": f"`{severity}`", "short": True},
                {"title": "발생일시", "value": f"{event_date} {event_time}", "short": True}
            ]

        # 구조화된 메시지 전송
        sections = [
            {
                "fields": fields
            },
            {
                "title": "발생내용",
                "text": f"```{event_name}```",
                "color": color
            },
            {
                "title": "현재상태",
                "text": f"```{opdata}```",
                "color": color
            }
        ]
        
        # Slack 메시지 전송
        result = send_structured(
            channel=channel,
            title=title,
            sections=sections,
            color=color
        )
        
        logger.info(f"Zabbix 메시지 전송 완료: {result}")
        
    except Exception as e:
        logger.error(f"Zabbix 메시지 전송 오류: {e}")
        # 에러가 발생해도 웹훅은 성공으로 처리 (Slack 전송 실패는 로그만 남김)


# 네트워크 모니터링 관련 함수들
def create_network_monitoring_sections(received_data: Dict, net_gubn: str) -> List[Dict]:
    """네트워크 모니터링 섹션 생성"""
    sections = []
    
    if net_gubn == "ord":
        # Top 10 처리
        excluded_tags = ['KRX', 'FIMS', 'STOCK-NET', 'ALL_SECUTIES']
        top_10_data = []
        
        for tag, data in received_data.items():
            if 'max_bps' in data and tag not in excluded_tags:
                try:
                    max_bps = float(data['max_bps'])
                    bd_usage = float(data.get('bd_usage', 0.0))
                    top_10_data.append({
                        'tag': tag, 'max_bps': max_bps, 'bd_usage': bd_usage,
                        'max_bps_unit': data.get('max_bps_unit', 'N/A'),
                        'diff_emoji': data.get('diff_emoji', ''),
                        'diff_unit': data.get('diff_unit', '')
                    })
                except (ValueError, TypeError):
                    continue
        
        top_10_data.sort(key=lambda x: x['max_bps'], reverse=True)
        top_10_data = top_10_data[:10]
        
        # Top 10 섹션
        top_10_text = "📊 *Top 10 Bandwidth Usage (ORD):*\n"
        for i, item in enumerate(top_10_data, 1):
            bd_usage_formatted = f"{item['bd_usage']:.1f}" if isinstance(item['bd_usage'], (int, float)) else str(item['bd_usage'])
            top_10_text += f"top{i:02d}: `{item['tag']}` {item['max_bps_unit']} ({bd_usage_formatted}%) {item['diff_emoji']}{item['diff_unit']}\n"
        
        sections.extend([
            {"title": "<Top 10 Bandwidth Usage>", "text": top_10_text, "color": "#FFA500"},
            {"title": "<전체증권사>", "text": f"`전체증권사 [{received_data['ALL_SECURITIES']['bd_usage']}/40G]` : {received_data['ALL_SECURITIES']['max_bps_unit']} ({received_data['ALL_SECURITIES']['diff_emoji']}{received_data['ALL_SECURITIES']['diff_unit']})", "color": "#FF6666"},
            {"title": "<회원사_1그룹>", "text": _format_group_data(received_data, ["KB", "KR_HQ", "KR_KT", "MR", "KW", "SH", "NH", "SS", "KY", "YU", "TS"]), "color": "#439FE0"},
            {"title": "<회원사_2그룹>", "text": _format_group_data(received_data, ["DA", "DB", "EU", "HD", "HN", "HW", "KA", "LS", "ME", "SK", "SY", "IM"]), "color": "#90EE90"},
            {"title": "<PB이용사>", "text": _format_group_data(received_data, ["BN", "BK", "DO", "DS", "HY", "IB", "LD", "WR"]), "color": "#9370DB"},
            {"title": "<대외기관>", "text": _format_group_data(received_data, ["FIMS", "KRX", "STOCK-NET"]), "color": "#D2B48C"}
        ])
    
    elif net_gubn == "mpr":
        sections.append({
            "title": "<시세상품>",
            "text": _format_group_data(received_data, ["NXTA-COM", "NXTA-10", "NXTA-5", "NXTA-3", "NXTB-COM", "NXTB-10", "NXTB-5", "NXTB-3"]),
            "color": "#90EE90"
        })
    
    return sections


def _format_group_data(received_data: Dict, group_keys: List[str]) -> str:
    """그룹 데이터 포맷팅"""
    bandwidth_map = {
        "KB": "100M", "KR_HQ": "100M", "KR_KT": "100M", "MR": "200M", "KW": "100M", "SH": "100M",
        "NH": "50M", "SS": "50M", "KY": "50M", "YU": "50M", "TS": "50M", "DA": "100M", "DB": "50M",
        "EU": "50M", "HD": "50M", "HN": "50M", "HW": "50M", "KA": "50M", "LS": "100M", "ME": "50M",
        "SK": "50M", "SY": "50M", "IM": "50M", "BN": "50M", "BK": "50M", "DO": "50M", "DS": "50M",
        "HY": "50M", "IB": "50M", "LD": "50M", "WR": "50M", "FIMS": "1G", "KRX": "2G", "STOCK-NET": "45M",
        "NXTA-COM": "100M", "NXTA-10": "100M", "NXTA-5": "100M", "NXTA-3": "100M",
        "NXTB-COM": "100M", "NXTB-10": "100M", "NXTB-5": "100M", "NXTB-3": "100M"
    }
    
    text_lines = []
    for key in group_keys:
        if key in received_data:
            bandwidth = bandwidth_map.get(key, "N/A")
            data = received_data[key]
            text_lines.append(
                f"`{key} [{data['bd_usage']}/{bandwidth}]` : {data['max_bps_unit']} ({data['diff_emoji']}{data['diff_unit']})"
            )
    
    return "\n".join(text_lines)


@router.post("/batch/multicast")
async def send_batch_multicast_alert(request: Request):
    """배치 작업 멀티캐스트 알림 웹훅 처리"""
    try:
        data = await request.json()
        logger.info(f"배치 멀티캐스트 알림 수신: {data}")
        
        # 필수 필드 검증
        required_fields = ['market_gubn', 'member_name', 'device_name', 'pim_rp', 'products', 'product_cnt', 'mroute_cnt', 'oif_cnt', 'rpf_nbr']
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        
        if missing_fields:
            logger.warning(f"필수 필드 누락: {missing_fields}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "result": False,
                    "error": "Missing required fields",
                    "detail": f"Required fields missing: {missing_fields}"
                }
            )
        
        # 시장 구분 한글 변환
        market_gubn = data['market_gubn']
        if market_gubn == "pr":
            market_name = "가동"
        elif market_gubn == "ts":
            market_name = "테스트"
        elif market_gubn == "dr":
            market_name = "DR"
        else:
            market_name = market_gubn
        
        # 채널 설정
        channel = "#network-alert-multicast"
        
        # 메시지 구성
        title = f":alert: *({market_name}){data['member_name']} 시세수신 이상* :alert:"
        
        fields = [
            {"title": "대상회원사", "value": f"`{data['member_name']}`", "short": True},
            {"title": "장비이름", "value": f"*{data['device_name']}*", "short": True},
            {"title": "가입상품", "value": f"`{data['products']}`", "short": True},
            {"title": "PIM_RP", "value": f"{data['pim_rp']}", "short": True},
            {"title": "기준 mroute", "value": f"{data['product_cnt']}", "short": True},
            {"title": "현재 mroute", "value": f"{data['mroute_cnt']}", "short": True},
            {"title": "현재 oif_cnt", "value": f"{data['oif_cnt']}", "short": True},
            {"title": "RPF_NBR", "value": f"`{data['rpf_nbr']}`", "short": True}
        ]
        
        # Slack 메시지 전송 (백그라운드 스레드)
        threading.Thread(target=send_alert, kwargs={"channel": channel, "title": title, "message": "", "color": "danger", "fields": fields}, daemon=True).start()

        logger.info(f"배치 멀티캐스트 알림 전송 완료: {data['member_name']} -> {channel}")
        
        return JSONResponse(
            content={
                "result": True,
                "status": "success",
                "message": "멀티캐스트 알림이 성공적으로 전송되었습니다."
            }
        )
        
    except Exception as e:
        logger.error(f"배치 멀티캐스트 알림 처리 오류: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "result": False,
                "error": "Internal server error",
                "detail": str(e)
            }
        )


@router.post("/slack/{net_gubn}")
async def send_monitor_webhook_to_slack(net_gubn: str, request: Request):
    """네트워크 모니터링 웹훅 처리"""
    try:
        received_data = await request.json()
        logger.info(f"네트워크 모니터링 데이터 수신: {received_data}")
        
        # 시장 정보 처리
        market_info = {
            "프리": {"name": "프리장", "time_range": "07:58~08:01", "emoji": ":sun:"},
            "정규": {"name": "정규장", "time_range": "08:58~09:01", "emoji": ":gogo_dancer:"},
            "에프터": {"name": "에프터장", "time_range": "15:38~15:41", "emoji": ":sunset:"}
        }
        
        market = received_data.get("market", "정규")
        market_data = market_info.get(market, market_info["정규"])
        
        # 섹션 생성
        sections = create_network_monitoring_sections(received_data, net_gubn)
        
        # 메시지 전송
        title = f"{market_data['emoji']} [{market_data['name']}-{market_data['time_range']}] {'주문망' if net_gubn == 'ord' else '시세망'} 트래픽"
        
        threading.Thread(target=send_structured, kwargs={"channel": "network-monitor", "title": title, "sections": sections}, daemon=True).start()

        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"네트워크 모니터링 웹훅 처리 오류: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"result": "error", "detail": str(e)}
        )


@router.post("/batch/multicast/check")
async def check_multicast_alarm_state(request: Request):
    """
    멀티캐스트 알람 상태 체크 엔드포인트

    전체 장비의 check_result를 받아 상태 전환을 판단하고,
    장애 발생/복구 시에만 Slack 알람을 발송합니다.

    요청 형식:
    {
        "market_gubn": "pr",
        "devices": [
            {"device_name": "...", "check_result": "정상확인|확인필요", "member_name": "...", ...}
        ]
    }
    """
    try:
        data = await request.json()
        market_gubn = data.get("market_gubn", "")
        devices = data.get("devices", [])

        if not market_gubn or not devices:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"result": False, "error": "market_gubn and devices are required"}
            )

        # 시장 구분 한글 변환
        market_name_map = {"pr": "가동", "ts": "테스트", "dr": "DR", "pr_information": "정보사-가동"}
        market_name = market_name_map.get(market_gubn, market_gubn)

        channel = "#network-alert-multicast"
        alerts_sent = 0
        recoveries_sent = 0
        skipped = 0

        for device in devices:
            if device is None:
                continue

            device_name = device.get("device_name", "")
            check_result = device.get("check_result", "")

            if not device_name or not check_result:
                skipped += 1
                continue

            # 알람 상태 전환 확인
            result = check_transition(market_gubn, device_name, check_result, device)
            action = result["action"]

            if action == "send_alert":
                # 장애 발생 알람
                alert_time = result.get("alert_time", "")
                member_name = device.get("member_name", "N/A")
                title = f":rotating_light: *({market_name}) {member_name} 시세수신 이상* :rotating_light:"

                # 누락 시세상품 (신청 - 수신)
                applied_list = device.get("products") or []
                if isinstance(applied_list, str):
                    applied_list = [p.strip() for p in applied_list.split(",") if p.strip()]
                received_list = device.get("received_products") or []
                if isinstance(received_list, str):
                    received_list = [p.strip() for p in received_list.split(",") if p.strip()]
                missing_list = device.get("missing_products")
                if missing_list is None:
                    missing_list = [p for p in applied_list if p not in received_list]
                elif isinstance(missing_list, str):
                    missing_list = [p.strip() for p in missing_list.split(",") if p.strip()]
                missing_text = ", ".join(missing_list) if missing_list else "없음"

                fields = [
                    {"title": "대상회원사", "value": f"`{member_name}`", "short": True},
                    {"title": "장비이름", "value": f"*{device_name}*", "short": True},
                    {"title": "가입상품", "value": f"`{device.get('products', 'N/A')}`", "short": True},
                    {"title": "누락상품", "value": f"`{missing_text}`", "short": True},
                    {"title": "PIM_RP", "value": f"{device.get('pim_rp', 'N/A')}", "short": True},
                    {"title": "기준 mroute", "value": f"{device.get('product_cnt', 0)}", "short": True},
                    {"title": "현재 mroute", "value": f"{device.get('mroute_cnt', 0)}", "short": True},
                    {"title": "현재 oif_cnt", "value": f"{device.get('oif_cnt', 0)}", "short": True},
                    {"title": "RPF_NBR", "value": f"`{device.get('rpf_nbr', 'N/A')}`", "short": True},
                    {"title": "발생시간", "value": f"*{alert_time}*", "short": True},
                ]

                threading.Thread(target=send_alert, kwargs={"channel": channel, "title": title, "message": "", "color": "danger", "fields": fields}, daemon=True).start()
                alerts_sent += 1
                logger.info(f"[ALARM SENT] 장애 알람: {market_gubn}:{device_name}")

            elif action == "send_recovery":
                # 복구 알람 - 발생시간 + 복구시간 포함
                alert_time = result.get("alert_time", "")
                recovery_time = result.get("recovery_time", "")
                member_name = device.get("member_name", "N/A")
                title = f":white_check_mark: *({market_name}) {member_name} 시세수신 복구* :white_check_mark:"

                fields = [
                    {"title": "대상회원사", "value": f"`{member_name}`", "short": True},
                    {"title": "장비이름", "value": f"*{device_name}*", "short": True},
                    {"title": "발생시간", "value": f"*{alert_time}*", "short": True},
                    {"title": "복구시간", "value": f"*{recovery_time}*", "short": True},
                ]

                threading.Thread(target=send_alert, kwargs={"channel": channel, "title": title, "message": "", "color": "good", "fields": fields}, daemon=True).start()
                recoveries_sent += 1
                logger.info(f"[ALARM SENT] 복구 알람: {market_gubn}:{device_name}")

            else:
                skipped += 1

        logger.info(f"[ALARM CHECK] {market_gubn}: alerts={alerts_sent}, recoveries={recoveries_sent}, skipped={skipped}")

        return JSONResponse(content={
            "result": True,
            "alerts_sent": alerts_sent,
            "recoveries_sent": recoveries_sent,
            "skipped": skipped
        })

    except Exception as e:
        logger.error(f"멀티캐스트 알람 상태 체크 오류: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"result": False, "error": str(e)}
        )