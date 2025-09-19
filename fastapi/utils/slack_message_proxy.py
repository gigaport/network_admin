"""
Slack 메시지 프록시 모듈 - 기존 코드와의 호환성을 위한 래퍼
"""
import logging
from typing import Dict, Any, List
from utils.slack_client import slack_client

logger = logging.getLogger(__name__)


def SendMulticastNotificationToSlack(message_title: str, attachments: Dict[str, Any]):
    """
    멀티캐스트 알림을 Slack으로 전송
    
    Args:
        message_title: 메시지 제목
        attachments: 첨부파일 정보
    """
    try:
        logger.info(f"멀티캐스트 알림 전송: {message_title}")
        
        response = slack_client.send_message(
            channel="#network-alert-multicast",
            text=message_title,
            attachments=[attachments]
        )
        
        logger.info(f"메시지 전송 성공: {response['ts']}")
        
    except Exception as e:
        logger.error(f"멀티캐스트 알림 전송 실패: {e}")


def SendSlackMessage(channel: str, message_title: str, message_body: Dict[str, Any]):
    """
    Slack 메시지 전송 (기존 호환성 유지)
    
    Args:
        channel: 채널명
        message_title: 메시지 제목
        message_body: 메시지 본문 (color, fields, mrkdwn_in 포함)
    """
    try:
        logger.info(f"Slack 메시지 전송: {message_title}")
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message_title
                }
            }
        ]
        
        attachment = {
            "color": message_body.get('color', 'warning'),
            "fields": message_body.get('fields', []),
            "mrkdwn_in": message_body.get('mrkdwn_in', [])
        }
        
        response = slack_client.send_message(
            channel=channel,
            text=message_title,
            blocks=blocks,
            attachments=[attachment]
        )
        
        logger.info(f"메시지 전송 성공: {response['ts']}")
        
    except Exception as e:
        logger.error(f"Slack 메시지 전송 실패: {e}")