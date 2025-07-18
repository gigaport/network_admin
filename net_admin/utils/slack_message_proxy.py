import os, time
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# .env 파일에서 환경 변수 로드
load_dotenv()
# SLACK
slack_token = os.getenv("SLACK_TOKEN")
client = WebClient(token=slack_token)

def SendMulticastNotificationToSlack(message_title, attachments):
    print(message_title, attachments)
    channel = "#network-alert-multicast"
    try:
        response = client.chat_postMessage(
            channel=channel,  # 예: "#general" 또는 "C12345678"
            text= message_title,
            attachments=[
                attachments
            ]
        )
        print("메시지 전송 성공:", response["ts"])

    except SlackApiError as e:
        print("메시지 전송 실패:", e.response["error"])

    time.sleep(1)

def SendSlackMessage(channel, message_title, message_body):
    # 메세지 전송 성공유무와 상관없이 time.sleep(1)을 줘서 무분별한 전송을 방지
    try:
        response = client.chat_postMessage(
            channel=channel,
            blocks=[
                {
                    "type": "section",
                    "text":{
                        "type": "mrkdwn",
                        "text": message_title
                    }
                }
            ],
            attachments=[
                {
                    "color": message_body['color'],
                    # "pretext": message_title,
                    "fields": message_body['fields'],
                    "mrkdwn_in": message_body['mrkdwn_in']
                }
            ]
            # blocks=message_body['blocks']
        )
        print(f"Message sent successfully: {response['message']['text']}")


    except SlackApiError as e:
        if e.response['status_code'] == 429:
            retry_after = int(e.response.headers.get("Retry-After", 1))
            print(f"Rate limited. Retrying after {retry_after} seconds...")
            time.sleep(retry_after)
        else:
            print(f"failed_message_sending: {e.response['error']}, {e.response['status_code']}")

    time.sleep(1)
