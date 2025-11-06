"""
Slack 메시지 전송을 위한 공통 모듈
"""
import os
import time
import logging
from typing import Dict, List, Optional, Any
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
# 로깅 설정
logger = logging.getLogger(__name__)

class SlackClient:
    """Slack 메시지 전송을 위한 클라이언트 클래스"""
    
    def __init__(self, token: Optional[str] = None):
        """
        SlackClient 초기화
        
        Args:
            token: Slack Bot Token (없으면 환경변수에서 가져옴)
        """
        self.token = token or os.getenv("SLACK_TOKEN")
        if not self.token:
            logger.warning("SLACK_TOKEN이 설정되지 않았습니다. Slack 기능이 비활성화됩니다.")
            self.client = None
            return
        
        self.client = WebClient(
            token=self.token,
            proxy="http://172.16.4.217:5001"
        )
    
    def send_message(
        self, 
        channel: str, 
        text: str, 
        blocks: Optional[List[Dict]] = None,
        attachments: Optional[List[Dict]] = None,
        thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Slack 메시지 전송
        
        Args:
            channel: 채널명 또는 채널 ID
            text: 메시지 텍스트 (fallback용)
            blocks: Slack Block Kit 블록들
            attachments: Slack 첨부파일들
            thread_ts: 스레드에 답글을 달 때 사용
            
        Returns:
            Slack API 응답
            
        Raises:
            SlackApiError: Slack API 오류
        """
        if not self.client:
            logger.warning("Slack 클라이언트가 초기화되지 않았습니다. 메시지를 전송하지 않습니다.")
            return {"ts": "mock_timestamp", "ok": False, "warning": "Slack client not initialized"}
        
        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=text,
                blocks=blocks,
                attachments=attachments,
                thread_ts=thread_ts
            )
            logger.info(f"메시지 전송 성공: {response['ts']}")
            return response
            
        except SlackApiError as e:
            if e.response['status_code'] == 429:
                # Rate limit 처리
                retry_after = int(e.response.headers.get("Retry-After", 1))
                logger.warning(f"Rate limited. {retry_after}초 후 재시도...")
                time.sleep(retry_after)
                # 재시도
                return self.send_message(channel, text, blocks, attachments, thread_ts)
            else:
                logger.error(f"메시지 전송 실패: {e.response['error']}, {e.response['status_code']}")
                raise
    
    def send_simple_message(self, channel: str, text: str) -> Dict[str, Any]:
        """
        간단한 텍스트 메시지 전송
        
        Args:
            channel: 채널명 또는 채널 ID
            text: 메시지 텍스트
            
        Returns:
            Slack API 응답
        """
        return self.send_message(channel, text)
    
    def send_alert_message(
        self, 
        channel: str, 
        title: str, 
        message: str, 
        color: str = "warning",
        fields: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        알림 메시지 전송
        
        Args:
            channel: 채널명 또는 채널 ID
            title: 메시지 제목
            message: 메시지 내용
            color: 메시지 색상 (good, warning, danger, 또는 hex 코드)
            fields: 추가 필드들
            
        Returns:
            Slack API 응답
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*"
                }
            }
        ]
        
        attachment = {
            "color": color,
            "text": message,
            "mrkdwn_in": ["text"]
        }
        
        if fields:
            attachment["fields"] = fields
        
        return self.send_message(
            channel=channel,
            text=title,
            blocks=blocks,
            attachments=[attachment]
        )
    
    def _detect_section_type(self, section: Dict[str, Any]) -> str:
        """
        섹션 타입을 감지합니다.

        Args:
            section: 섹션 데이터

        Returns:
            섹션 타입 ('block_text', 'block_fields', 'attachment')
        """
        if section.get("fields"):
            return "block_fields"
        elif section.get("text") and not section.get("attachment", False):
            return "block_text"
        else:
            return "attachment"

    def _create_block_section(self, section: Dict[str, Any]) -> Dict[str, Any]:
        """
        Block Kit 섹션을 생성합니다.

        Args:
            section: 섹션 데이터

        Returns:
            Block Kit 섹션
        """
        block = {
            "type": "section"
        }

        # text 필드 처리
        if section.get("text"):
            block["text"] = {
                "type": "mrkdwn",
                "text": section["text"]
            }

        # fields 필드 처리
        if section.get("fields"):
            block["fields"] = []
            for field in section["fields"]:
                if isinstance(field, dict):
                    block["fields"].append({
                        "type": "mrkdwn",
                        "text": field.get("value", str(field))
                    })
                else:
                    block["fields"].append({
                        "type": "mrkdwn",
                        "text": str(field)
                    })

        return block

    def _create_attachment_section(self, section: Dict[str, Any], default_color: str) -> Dict[str, Any]:
        """
        Attachment 섹션을 생성합니다.

        Args:
            section: 섹션 데이터
            default_color: 기본 색상

        Returns:
            Attachment 섹션
        """
        attachment = {
            "color": section.get("color", default_color),
            "title": section.get("title", ""),
            "text": section.get("text", ""),
            "mrkdwn_in": ["text", "title"]
        }

        if section.get("fields"):
            attachment["fields"] = section["fields"]

        return attachment

    def send_structured_message(
        self,
        channel: str,
        title: str,
        sections: List[Dict[str, Any]],
        color: str = "#439FE0"
    ) -> Dict[str, Any]:
        """
        구조화된 메시지 전송 (여러 섹션으로 구성) - 기존 호환성 유지

        Args:
            channel: 채널명 또는 채널 ID
            title: 메시지 제목
            sections: 섹션 리스트 (각 섹션은 title, text, color 포함)
            color: 기본 색상

        Returns:
            Slack API 응답
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*"
                }
            }
        ]

        attachments = []
        for section in sections:
            attachment = {
                "color": section.get("color", color),
                "title": section.get("title", ""),
                "text": section.get("text", ""),
                "mrkdwn_in": ["text", "title"],
                "fields": section.get("fields", [])
            }
            attachments.append(attachment)

        return self.send_message(
            channel=channel,
            text=title,
            blocks=blocks,
            attachments=attachments
        )

    def send_adaptive_message(
        self,
        channel: str,
        title: str,
        sections: List[Dict[str, Any]],
        color: str = "#439FE0"
    ) -> Dict[str, Any]:
        """
        적응형 메시지 전송 (섹션 내용에 따라 구조 자동 선택)

        Args:
            channel: 채널명 또는 채널 ID
            title: 메시지 제목
            sections: 섹션 리스트
                - text만 있는 경우: Block Kit section 사용
                - fields가 있는 경우: Block Kit section with fields 사용
                - attachment=True인 경우: Attachment 사용
            color: 기본 색상

        Returns:
            Slack API 응답

        Example:
            sections = [
                {"text": "간단한 텍스트"},  # Block Kit section
                {"text": "제목", "fields": [{"title": "필드1", "value": "값1"}]},  # Block Kit with fields
                {"text": "첨부파일", "attachment": True, "color": "danger"}  # Attachment
            ]
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*"
                }
            }
        ]

        attachments = []

        for section in sections:
            section_type = self._detect_section_type(section)

            if section_type in ["block_text", "block_fields"]:
                # Block Kit 섹션으로 추가
                block_section = self._create_block_section(section)
                blocks.append(block_section)

            else:
                # Attachment로 추가
                attachment = self._create_attachment_section(section, color)
                attachments.append(attachment)

        return self.send_message(
            channel=channel,
            text=title,
            blocks=blocks,
            attachments=attachments if attachments else None
        )


# 전역 인스턴스 생성 (안전하게 처리)
try:
    slack_client = SlackClient()
except Exception as e:
    logger.warning(f"Slack 클라이언트 초기화 실패: {e}")
    slack_client = None


# 편의 함수들
def send_message(channel: str, text: str, **kwargs) -> Dict[str, Any]:
    """간단한 메시지 전송 함수"""
    if not send_message:
        logger.warning("Slack 클라이언트가 사용할 수 없습니다.")
        return {"ok": False, "warning": "Slack client not available"}
    return slack_client.send_message(channel, text, **kwargs)


def send_alert(channel: str, title: str, message: str, color: str = "warning", **kwargs) -> Dict[str, Any]:
    """알림 메시지 전송 함수"""
    if not slack_client:
        logger.warning("Slack 클라이언트가 사용할 수 없습니다.")
        return {"ok": False, "warning": "Slack client not available"}
    return slack_client.send_alert_message(channel, title, message, color, **kwargs)


def send_structured(channel: str, title: str, sections: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
    """구조화된 메시지 전송 함수 (기존 호환성)"""
    if not slack_client:
        logger.warning("Slack 클라이언트가 사용할 수 없습니다.")
        return {"ok": False, "warning": "Slack client not available"}
    return slack_client.send_structured_message(channel, title, sections, **kwargs)


def send_adaptive(channel: str, title: str, sections: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
    """적응형 메시지 전송 함수 (자동 구조 선택)"""
    if not slack_client:
        logger.warning("Slack 클라이언트가 사용할 수 없습니다.")
        return {"ok": False, "warning": "Slack client not available"}
    return slack_client.send_adaptive_message(channel, title, sections, **kwargs)
