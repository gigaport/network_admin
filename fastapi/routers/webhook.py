"""
Webhook 라우터 - 다양한 서비스로부터의 웹훅을 처리하고 Slack으로 알림 전송
"""
import json
import re
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from utils.slack_client import slack_client, send_alert, send_structured

# 로깅 설정
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])

# 상수 정의
SYSLOG_NORMAL_KEYWORDS = [
    "Authentication", "PAM", "PWD", "COMMAND", "pam", "auth", 
    "User", "nwcfg", "Login", "Unexpected message type has arrived. Terminating the connection from"
]

SYSLOG_ENDPOINT_MNEMONICS = ["IF_UP", "IF_DOWN", "IF_DUPLEX"]

SYSLOG_NORMAL_FACILITIES = ["USER", "RADIUS"]

ZABBIX_MUTE_KEYWORDS = ["memory"]

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
        "진행": "security-업무-진행",
        "완료": "security-업무-완료",
        "검토": "security-업무-검토",
        "예정": "security-업무-예정",
        "기타": "security-업무-기타"
    }
}


class WebhookHandler:
    """웹훅 처리를 위한 핸들러 클래스"""
    
    @staticmethod
    def get_channel_for_project(project_name: str, list_name: str) -> str:
        """프로젝트와 리스트명에 따른 채널 결정"""
        if project_name in CHANNEL_MAPPINGS:
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
        logger.info(f"Planka 웹훅 수신: {data}")
        
        # 채널 결정
        project_name = data['data']['included']['projects'][0]['name']
        list_name = data['data']['included']['lists'][0]['name']
        channel = WebhookHandler.get_channel_for_project(project_name, list_name)
        
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
        
        # Slack 메시지 전송
        slack_client.send_message(
            channel=channel,
            text=f"Planka 이벤트: {event_type}",
            attachments=[attachment]
        )
        
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
        required_fields = ['device', 'host_ip', 'timestamp_trans', 'severity', 'facility', 'mnemonic', 'type', 'message']
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
        
        if any(keyword in mnemonic for keyword in SYSLOG_ENDPOINT_MNEMONICS):
            channel = "#network-alert-endpoint"
        
        # 메시지 전송
        _send_syslog_to_slack(channel, data)
        
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
    """Grafana 웹훅 처리"""
    try:
        data = await request.json()
        logger.info(f"Grafana 웹훅 수신: {data}")
        
        # TODO: Grafana 알림 처리 로직 구현
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"result": "success", "detail": "전송처리가 완료되었습니다."}
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
        
        # 채널 결정
        channel = "network-alert-critical"
        
        # 회원사 스위치 구분
        hostname = data.get('hostname', '')
        event_name = data.get('event_name', '')
        
        if any(keyword in hostname for keyword in ["mpr", "ord", "com"]):
            if bool(re.search(r'\(\s*\)', event_name)):
                channel = "network-alert-endpoint"
        
        # 메시지 구성 및 전송
        if not any(keyword in event_name for keyword in ZABBIX_MUTE_KEYWORDS):
            send_zabbix_message(channel, data)
        
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
                "title": "",
                "fields": fields,
                "color": color,
                "mrkdwn_in": ["text", "fields"]
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
            {"title": "<전체증권사>", "text": f"`전체증권사 [{received_data['ALL_SECUTIES']['bd_usage']}/40G]` : {received_data['ALL_SECUTIES']['max_bps_unit']} ({received_data['ALL_SECUTIES']['diff_emoji']}{received_data['ALL_SECUTIES']['diff_unit']})", "color": "#FF6666"},
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
        
        send_structured(
            channel="network-monitor",
            title=title,
            sections=sections
        )
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"네트워크 모니터링 웹훅 처리 오류: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"result": "error", "detail": str(e)}
        )