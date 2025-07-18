import json, logging, re, time, html, sys, asyncio, uvicorn, os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pprint import pprint
from urllib.parse import quote
from typing import List, Dict, Tuple, Union, Optional
## Netmiko 라이브러리
from netmiko import ConnectHandler
## 장비관리 라이브러리
from genie.testbed import load
## 장비정보 파싱 라이브러리리
## IOSXE
from genie.libs.parser.iosxe.show_interface import ShowInterfacesSwitchport
from genie.libs.parser.iosxe.show_interface import ShowInterfacesStatus
from genie.libs.parser.iosxe.show_mcast import ShowIpMroute
from genie.libs.parser.iosxe.show_pim import ShowPimNeighbor
## NXOS
from genie.libs.parser.nxos.show_interface import ShowInterfaceSwitchport
from genie.libs.parser.nxos.show_interface import ShowInterfaceStatus
from genie.libs.parser.nxos.show_mcast import ShowIpMrouteVrfAll
from genie.libs.parser.nxos.show_pim import ShowIpPimRp
## Router
from routers.webhook import router as webhook_router
from routers.network import router as network_router

# .env 파일에서 환경 변수 로드
load_dotenv()

# FastAPI 애플리케이션 생성
app = FastAPI(
    root_path="/api",
    title="Network Admin API",
    description="API for managing network devices and monitoring",
    version="1.0.0",
    openapi_tags=[
        {
            "name": "Network",
            "description": "API for network management and monitoring"
        },
        {
            "name": "Webhook",
            "description": "API for handling webhooks from external services"
        }
    ],
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    contract={
        "name": "Network Admin API",
        "email": "network@nextrade.co.kr"
    }
)

app.include_router(webhook_router)
app.include_router(network_router)

# fast api에서 router를 분리해서 기능별로 구성
# /api/webhook/
# /api/network/

# SLACK
slack_token = os.getenv("SLACK_TOKEN")
client = WebClient(token=slack_token)

# TIME
KST = timezone(timedelta(hours=9))
TODAY_TIME = datetime.today().strftime('%Y-%m-%d %H:%M')

# 스레드풀 생성
executor = ThreadPoolExecutor(max_workers=60)

TODAY_STR = datetime.today().strftime('%Y-%m-%d')
TS_DEVICES = load('../common/ts_member_mpr.yaml')
PR_DEVICES = load('../common/pr_member_mpr.yaml')
FILE_PATH = "./data/"

# pyATS 로거 설정 (로그 출력 비활성화)
logging.getLogger('pyats').setLevel(logging.CRITICAL)
logging.getLogger('genie').setLevel(logging.CRITICAL)
logging.getLogger('unicon').setLevel(logging.CRITICAL)

NXOS_CMDS = [
    {
        "key": "show_ip_mroute_source-tree",
        "value": "show ip mroute source-tree"
    },
    {
        "key": "show_ip_pim_rp",
        "value": "show ip pim rp"
    },
    {
        "key": "show_interface_status",
        "value": "show interface status"
    }
]

IOSXE_CMDS = [
    {
        "key": "show_ip_mroute",
        "value": "show ip mroute"
    },
    {
        "key": "show_interface_status",
        "value": "show interface status"
    }
]

KNOWN_MULTICAST_IP = [
    "224.0.0.1/32", 
    "224.0.0.2/32", 
    "224.0.0.5/32", 
    "224.0.0.6/32", 
    "224.0.0.9/32", 
    "224.0.0.13/32", 
    "224.0.0.18/32", 
    "224.0.0.22/32", 
    "224.0.1.1/32", 
    "224.0.1.2/32", 
    "224.0.1.39/32", 
    "224.0.1.40/32", 
    "224.0.0.32/32", 
    "224.0.0.41/32",
    "239.255.255.250/32"
]

SYSLOG_NORMAL_KEYWORD = [
    "Authentication",
    "PAM",
    "PWD",
    "COMMAND",
    "pam",
    "auth",
    "User",
    "nwcfg",
    "Login",
    "Unexpected message type has arrived. Terminating the connection from"
]

SYSLOG_ENDPOINT_MNEMONIC = [
    "IF_UP",
    "IF_DOWN",
    "IF_DUPLEX"
]

SYSLOG_NORMAL_FACILITY = [
    "USER"
]

ZABBIX_MUTE = [
    "memory"
]

###### 전용회선 정보
LINE_INFO = [
    {'id':167343, 'name':'쿠콘 (메인회선)', 'isp':'KT', 'speed':'512K', 'no':'2507-2006-0025', 'owner':'쿠콘', 'location':'', 'manager':'임승주 대리', 'tel':'02-3779-9178', 'mobile':'010-2596-9259', 'email':'sjlim@cucon.net', 'isp_tel':'1588-0114'},
    {'id':167342, 'name':'예탁원 (메인회선)', 'isp':'KT', 'speed':'128K', 'no':'2500-3035-0065', 'owner':'예탁원', 'location':'일산', 'manager':'이광우 과장', 'tel':'031-900-7179', 'mobile':'', 'email':'gwangwu.yi@ksd.or.kr', 'isp_tel':'1588-0114'},
    {'id':167345, 'name':'KCB (메인회선)', 'isp':'KT', 'speed':'256K', 'no':'0103-4363-0012', 'owner':'KCB', 'location':'', 'manager':'조재호 대리', 'tel':'02-766-8912', 'mobile':'', 'email':'fodcar@koreacb.com', 'isp_tel':'1588-0114'},
    {'id':167344, 'name':'NICE (메인회선)', 'isp':'KT', 'speed':'256K', 'no':'0103-5420-3441', 'owner':'NICE', 'location':'', 'manager':'김종근 과장', 'tel':'02-331-7746', 'mobile':'', 'email':'kij7777777@niceinfo.co.kr', 'isp_tel':'1588-0114'},
    {'id':345439, 'name':'하나은행_환전 (메인회선)', 'isp':'KT', 'speed':'20M', 'no':'3420-4600-0038', 'owner':'토스증권', 'location':'', 'manager':'이승환 차장', 'tel':'02-3466-4863', 'mobile':'', 'email':'nuri1998@hanafn.com', 'isp_tel':'1588-0114'},
    {'id':41212, 'name':'연합인포 (메인회선)', 'isp':'KT', 'speed':'30M', 'no':'3420-4600-0028', 'owner':'토스증권', 'location':'', 'manager':'정진홍 차장', 'tel':'010-8722-5104', 'mobile':'', 'email':'jhjung2@yna.co.kr', 'isp_tel':'1588-0114'},

    {'id':167410, 'name':'쿠콘 (백업회선)', 'isp':'LGU+', 'speed':'512K', 'no':'5001-9149-2233', 'owner':'토스증권', 'location':'', 'manager':'임승주 대리', 'tel':'02-3779-9178', 'mobile':'010-2596-9259', 'email':'sjlim@cucon.net', 'isp_tel':'02-2089-8284'},
    {'id':167408, 'name':'예탁원 (백업회선)', 'isp':'LGU+', 'speed':'128K', 'no':'5002-0283-3711', 'owner':'토스증권', 'location':'일산', 'manager':'이광우 과장', 'tel':'031-900-7179', 'mobile':'', 'email':'gwangwu.yi@ksd.or.kr', 'isp_tel':'02-2089-8284'},
    {'id':167409, 'name':'KCB (백업회선)', 'isp':'LGU+', 'speed':'256K', 'no':'5001-8459-7648', 'owner':'토스증권', 'location':'', 'manager':'조재호 대리', 'tel':'02-766-8912', 'mobile':'', 'email':'fodcar@koreacb.com', 'isp_tel':'02-2089-8284'},
    {'id':167411, 'name':'NICE (백업회선)', 'isp':'LGU+', 'speed':'256K', 'no':'5002-1687-7670', 'owner':'토스증권', 'location':'', 'manager':'김종근 과장', 'tel':'02-331-7746', 'mobile':'', 'email':'kij7777777@niceinfo.co.kr', 'isp_tel':'02-2089-8284'},
    {'id':345443, 'name':'하나은행_환전 (백업회선)', 'isp':'LGU+', 'speed':'20M', 'no':'5002-5875-0288', 'owner':'토스증권', 'location':'', 'manager':'이승환 차장', 'tel':'02-3466-4863', 'mobile':'', 'email':'nuri1998@hanafn.com', 'isp_tel':'1588-0114'},
    {'id':41564, 'name':'연합인포 (백업회선)', 'isp':'LGU+', 'speed':'30M', 'no':'5002-2906-2603', 'owner':'토스증권', 'location':'', 'manager':'정진홍 차장', 'tel':'010-8722-5104', 'mobile':'', 'email':'jhjung2@yna.co.kr', 'isp_tel':'1588-0114'},
]


@app.get("/")
async def hello():
    return("message :hello from FastAPI + Gunicorn")


# ## netmiko connection info
# connection_info = {
#     "device_type": "cisco_xe",
#     "host": "50.5.1.51",
#     "username": "125003",
#     "password": "Swr278577@",
#     "port": 22
# }
# 1. pyATS 로그 끄기 또는 분리
def configure_pyats_logging():
    for name in ["pyats", "genie"]:
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL)  # 로그 완전 비활성화

# 2. FastAPI 실행 시 초기 설정
@app.on_event("startup")
async def startup_event():
    configure_pyats_logging()

@app.get("/member_mkd/status")
async def member_mkd():
    return {"status":"ok"}

@app.post("/logs")
async def receive_syslog(request: Request):
    data = await request.json()
    print(f"Received log: {data}")
    channel = "#network-alert-syslog"
    
    if any(keyword in data["message"] for keyword in SYSLOG_NORMAL_KEYWORD) or any(keyword in data["facility"] for keyword in SYSLOG_NORMAL_FACILITY):
        channel = "#network-alert-normal"
    
    if any(keyword in data["mnemonic"] for keyword in SYSLOG_ENDPOINT_MNEMONIC) :
        channel = "#network-alert-endpoint"

    send_message_to_slack(channel, data)

    return {"status": "ok"}

@app.post("/webhook/planka")
async def send_planka_webhook_to_slack(request: Request):
    print(f'[planka_alert_webhook_request] : {request}')
    print(f'[slack_token] : {slack_token}')

    data = await request.json()
    print(f'[planka_alert_webhook_body] : {data}')

    channel = "network-업무-진행"
    
    # 리스트 명칭안에 '검토'라는 단어가 포함되어 있는지 확인
    if '검토' in data['data']['included']['lists'][0]['name'] or '계약' in data['data']['included']['lists'][0]['name']:
        channel = "network-업무-검토"
    # 리스트 명칭안에 '완료'라는 단어가 포함되어 있는지 확인
    elif '완료' in data['data']['included']['lists'][0]['name']:
        channel = "network-업무-완료"

    blocks=[
        {
            "type": "section",
            "text":{
                "type": "mrkdwn",
                "text": f"*{data['event']}*"
            }
        }
    ]

    if data['event'] == 'cardUpdate' or data['event'] == 'cardCreate':
        attachments=[
            {
                "color": "#90EE90",
                "text": (
                    f"사용자명: {data['user']['name']}\n"
                    f"보드명: {data['data']['included']['boards'][0]['name']}\n"
                    f"구분: {data['data']['included']['lists'][0]['name']}\n"
                    f"카드명: {data['data']['item']['name']}\n"
                    f"카드설명: {data['data']['item']['description']}\n"
                    f"목표일: {data['data']['item']['dueDate']}\n"

                ),
                "mrkdwn_in": ["text", "title"]
            }
        ]
    elif data['event'] == 'taskUpdate' or data['event'] == 'taskCreate':
        attachments=[
            {
                "color": "#faf697",
                "text": (
                    f"사용자명: {data['user']['name']}\n"
                    f"보드명: {data['data']['included']['boards'][0]['name']}\n"
                    f"구분: {data['data']['included']['lists'][0]['name']}\n"
                    f"카드명: *{data['data']['included']['cards'][0]['name']}*\n"
                    f"Task명: *{data['data']['item']['name']}*\n"
                    f"완료여부: `{data['data']['item']['isCompleted']}`\n"
                ),
                "mrkdwn_in": ["text", "title"]
            }
        ]
    elif data['event'] == 'commentUpdate' or data['event'] == 'commentCreate':
        attachments=[
            {
                "color": "#97f4fa",
                "text": (
                    f"사용자명: {data['user']['name']}\n"
                    f"보드명: {data['data']['included']['boards'][0]['name']}\n"
                    f"구분: {data['data']['included']['lists'][0]['name']}\n"
                    f"카드명: *{data['data']['included']['cards'][0]['name']}*\n\n"
                    f"Comment: \n"
                    f"```{data['data']['item']['text']}```"
                ),
                "mrkdwn_in": ["text", "title"]
            }
        ]
    else:
        return JSONResponse(   
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"result": "error", "detail": "지원하지 않는 이벤트입니다."}
        )

    try:
        response = client.chat_postMessage(channel=channel, blocks=blocks, attachments=attachments)

    except SlackApiError as e:
        if e.response['status_code'] == 429:
            retry_after = int(e.response.headers.get("Retry-After", 1))
            print(f"Rate limited. Retrying after {retry_after} seconds...")
            time.sleep(retry_after)
        else:
            print(f"failed_message_sending: {e.response['error']}, {e.response['status_code']}")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"result": "success", "detail": "전송처리가 완료되었습니다."}
    )


@app.post("/webhook/grafana")
async def send_grafana_webhook_to_slack(request: Request):
    print(f'[grafana_alert_webhook_request] : {request}')

    data = await request.json()
    print(f'[grafana_alert_webhook_body]ß : {data}')

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"result": "success", "detail": "전송처리가 완료되었습니다."}
    )

@app.post("/webhook/zabbix")
async def send_zabbix_webhook_to_slack(request: Request):
    print(f'[zabbix_alert_webhook_request] : {request}')

    data = await request.json()
    print(f'[zabbix_alert_webhook_body] : {data}')

    channel = "network-alert-critical"

    # event_name 필드가 "*"가 아닌 경우에만 채널을 변경
    if data['event_name'] not in "*" :
        channel = "network-alert-endpoint"
    
    if data['event_value'] == '0' : ## 장애해소
        main_text = f":green-check-mark: {data['hostname']} >> {data['event_name']}"
        attachment_color = "#3bc95c"
        message_body = {
                "color": attachment_color,
                "mrkdwn_in": ["text", "fields"],
                "fields": [
                    {
                        "title": "대상장비",
                        "value": f"`{data['hostname']}`",
                        "short": True,
                    },
                    {
                        "title": "대상그룹",
                        "value": f"`{data['host_group']}`",
                        "short": True,
                    },
                    {
                        "title": "LEVEL",
                        "value": f"`{data['severity']}`",
                        "short": True,
                    },
                    {
                        "title": "발생일시",
                        "value": f"{data['event_date']} {data['event_time']}",
                        "short": True,
                    },
                    {
                        "title": "경과시간",
                        "value": f"`{data['event_duration']}`",
                        "short": False,
                    }
                ],
                "event_name":{
                    "title": "발생내용",
                    "text": f"```{data['event_name']}```"
                },
                "opdata":{
                    "title": "현재상태",
                    "text": f"```{data['opdata']}```"
                }
            }
    else: ## 장애발생
        main_text = f":critical: {data['hostname']} >> {data['event_name']}"
        attachment_color = "#e71c1c"

        ## 전용회선 다운 시 정보 추가 ##
        trigger_id = int(data['trigger_id'])
        dic_problem_line = next((sub for sub in LINE_INFO if sub['id'] == trigger_id), None)
        print(f'[problem_line] : {dic_problem_line}')

        if dic_problem_line is None: ## 일반 장애 시
            message_body = {
                "color": attachment_color,
                "mrkdwn_in": ["text", "fields"],
                "fields": [
                    {
                        "title": "대상장비",
                        "value": f"`{data['hostname']}`",
                        "short": True,
                    },
                    {
                        "title": "대상그룹",
                        "value": f"`{data['host_group']}`",
                        "short": True,
                    },
                    {
                        "title": "LEVEL",
                        "value": f"`{data['severity']}`",
                        "short": True,
                    },
                    {
                        "title": "발생일시",
                        "value": f"{data['event_date']} {data['event_time']}",
                        "short": True,
                    }
                #     {
                #         "title": "발생내용",
                #         "value": f"{data['event_name']}",
                #         "short": False,
                #     },
                #     {
                #         "title": "현재상태",
                #         "value": f"`{data['opdata']}`",
                #         "short": False,
                #     },
                ],
                "event_name":{
                    "title": "발생내용",
                    "text": f"```{data['event_name']}```"
                },
                "opdata":{
                    "title": "현재상태",
                    "text": f"```{data['opdata']}```"
                }
            }
        else : ## 회선 장애 시
            message_body = {
                "color": attachment_color,
                "mrkdwn_in": ["text", "fields"],
                "fields": [
                    {
                        "title": "대상장비",
                        "value": f"`{data['hostname']}`",
                        "short": True,
                    },
                    {
                        "title": "대상그룹",
                        "value": f"`{data['host_group']}`",
                        "short": True,
                    },
                    {
                        "title": "LEVEL",
                        "value": f"`{data['severity']}`",
                        "short": True,
                    },
                    {
                        "title": "발생일시",
                        "value": f"{data['event_date']} {data['event_time']}",
                        "short": True,
                    },
                    {
                        "title": "발생내용",
                        "value": f"```{data['event_name']}```",
                        "short": False,
                    },
                    {
                        "title": "현재상태",
                        "value": f"```{data['opdata']}```",
                        "short": False,
                    },
                    {
                        "title": "통신사",
                        "value": f"`{dic_problem_line['isp']}`",
                        "short": True,
                    },
                    {
                        "title": "청약회사",
                        "value": f"`{dic_problem_line['owner']}`",
                        "short": True,
                    },
                    {
                        "title": "회선번호/속도",
                        "value": f"`{dic_problem_line['no']} ({dic_problem_line['speed']})`",
                        "short": True,
                    },
                    {
                        "title": "담당자",
                        "value": f"{dic_problem_line['manager']} ({dic_problem_line['tel']})",
                        "short": True,
                    },
                    {
                        "title": "통신사 연락처",
                        "value": f"{dic_problem_line['isp_tel']}",
                        "short": True,
                    }
                ],
            }

    print(f'[slack_message_body] : {message_body}')
    
    if any(keyword not in data["event_name"] for keyword in ZABBIX_MUTE) :
        send_to_slack_message(channel, main_text, message_body)

    response_data = {
        "result": True,
        "response": {
            "code": 200,
            "message": "[OK]send to message."
        }
    }

    return JSONResponse(
        content=response_data,
        headers={"Content-Type": "application/json; charset=utf-8"}
    )


def convert_to_message_format(received_data, net_gubn, market, time_range, emoji):
    channel = "network-monitor"

    if net_gubn == "ord":
        blocks=[
            {
                "type": "section",
                "text":{
                    "type": "mrkdwn",
                    "text": f"*{emoji} [{market}-{time_range}] 주문망 트래픽*"
                }
            }
        ]
        attachments=[
                {
                    "color": "#FF6666",
                    "title": f"<전체증권사>",
                    "text": (
                        f"`전체증권사 [{received_data['ALL_SECUTIES']['bd_usage']}/40G]` : {received_data['ALL_SECUTIES']['max_bps_unit']} ({received_data['ALL_SECUTIES']['diff_emoji']}{received_data['ALL_SECUTIES']['diff_unit']})"
                    ),
                    "mrkdwn_in": ["text", "title"]
                },
                {
                    "color": "#439FE0",
                    "title": f"<회원사_1그룹>",
                    "text": (
                        f"`KB [{received_data['KB']['bd_usage']}/100M]` : {received_data['KB']['max_bps_unit']} ({received_data['KB']['diff_emoji']}{received_data['KB']['diff_unit']})\n"
                        f"`KR_HQ [{received_data['KR_HQ']['bd_usage']}/100M]` : {received_data['KR_HQ']['max_bps_unit']} ({received_data['KR_HQ']['diff_emoji']}{received_data['KR_HQ']['diff_unit']})\n"
                        f"`KR_KT [{received_data['KR_KT']['bd_usage']}/100M]` : {received_data['KR_KT']['max_bps_unit']} ({received_data['KR_KT']['diff_emoji']}{received_data['KR_KT']['diff_unit']})\n"
                        f"`MR [{received_data['MR']['bd_usage']}/200M]` : {received_data['MR']['max_bps_unit']} ({received_data['MR']['diff_emoji']}{received_data['MR']['diff_unit']})\n"
                        f"`KW [{received_data['KW']['bd_usage']}/100M]` : {received_data['KW']['max_bps_unit']} ({received_data['KW']['diff_emoji']}{received_data['KW']['diff_unit']})\n"
                        f"`SH [{received_data['SH']['bd_usage']}/100M]` : {received_data['SH']['max_bps_unit']} ({received_data['SH']['diff_emoji']}{received_data['SH']['diff_unit']})\n"
                        f"`NH [{received_data['NH']['bd_usage']}/50M]` : {received_data['NH']['max_bps_unit']} ({received_data['NH']['diff_emoji']}{received_data['NH']['diff_unit']})\n"
                        f"`SS [{received_data['SS']['bd_usage']}/50M]` : {received_data['SS']['max_bps_unit']} ({received_data['SS']['diff_emoji']}{received_data['SS']['diff_unit']})\n"
                        f"`KY [{received_data['KY']['bd_usage']}/50M]` : {received_data['KY']['max_bps_unit']} ({received_data['KY']['diff_emoji']}{received_data['KY']['diff_unit']})\n"
                        f"`YU [{received_data['YU']['bd_usage']}/50M]` : {received_data['YU']['max_bps_unit']} ({received_data['YU']['diff_emoji']}{received_data['YU']['diff_unit']})\n"
                        f"`TS [{received_data['TS']['bd_usage']}/50M]` : {received_data['TS']['max_bps_unit']} ({received_data['TS']['diff_emoji']}{received_data['TS']['diff_unit']})\n"
                    ),
                    "mrkdwn_in": ["text", "title"]
                },
                {
                    "color": "#90EE90",
                    "title": f"<회원사_2그룹>",
                    "text": (
                        f"`DA [{received_data['DA']['bd_usage']}/100M]` : {received_data['DA']['max_bps_unit']} ({received_data['DA']['diff_emoji']}{received_data['DA']['diff_unit']})\n"
                        f"`DB [{received_data['DB']['bd_usage']}/50M]` : {received_data['DB']['max_bps_unit']} ({received_data['DB']['diff_emoji']}{received_data['DB']['diff_unit']})\n"
                        f"`EU [{received_data['TS']['bd_usage']}/50M]` : {received_data['EU']['max_bps_unit']} ({received_data['EU']['diff_emoji']}{received_data['EU']['diff_unit']})\n"
                        f"`HD [{received_data['HD']['bd_usage']}/50M]` : {received_data['HD']['max_bps_unit']} ({received_data['HD']['diff_emoji']}{received_data['HD']['diff_unit']})\n"
                        f"`HN [{received_data['HN']['bd_usage']}/50M]` : {received_data['HN']['max_bps_unit']} ({received_data['HN']['diff_emoji']}{received_data['HN']['diff_unit']})\n"
                        f"`HW [{received_data['HW']['bd_usage']}/50M]` : {received_data['HW']['max_bps_unit']} ({received_data['HW']['diff_emoji']}{received_data['HW']['diff_unit']})\n"
                        f"`KA [{received_data['KA']['bd_usage']}/50M]` : {received_data['KA']['max_bps_unit']} ({received_data['KA']['diff_emoji']}{received_data['KA']['diff_unit']})\n"
                        f"`LS [{received_data['LS']['bd_usage']}/100M]` : {received_data['LS']['max_bps_unit']} ({received_data['LS']['diff_emoji']}{received_data['LS']['diff_unit']})\n"
                        f"`ME [{received_data['ME']['bd_usage']}/50M]` : {received_data['ME']['max_bps_unit']} ({received_data['ME']['diff_emoji']}{received_data['ME']['diff_unit']})\n"
                        f"`SK [{received_data['SK']['bd_usage']}/50M]` : {received_data['SK']['max_bps_unit']} ({received_data['SK']['diff_emoji']}{received_data['SK']['diff_unit']})\n"                        
                        f"`SY [{received_data['SY']['bd_usage']}/50M]` : {received_data['SY']['max_bps_unit']} ({received_data['SY']['diff_emoji']}{received_data['SY']['diff_unit']})\n"
                        f"`IM [{received_data['IM']['bd_usage']}/50M]` : {received_data['IM']['max_bps_unit']} ({received_data['IM']['diff_emoji']}{received_data['IM']['diff_unit']})\n"
                    ),
                    "mrkdwn_in": ["text", "title"]
                },
                {
                    "color": "#9370DB",
                    "title": f"<PB이용사>",
                    "text": (
                        f"`BN [{received_data['BN']['bd_usage']}/50M]` : {received_data['BN']['max_bps_unit']} ({received_data['BN']['diff_emoji']}{received_data['BN']['diff_unit']})\n"
                        f"`BK [{received_data['BK']['bd_usage']}/50M]` : {received_data['BK']['max_bps_unit']} ({received_data['BK']['diff_emoji']}{received_data['BK']['diff_unit']})\n"
                        f"`DO [{received_data['DO']['bd_usage']}/50M]` : {received_data['DO']['max_bps_unit']} ({received_data['DO']['diff_emoji']}{received_data['DO']['diff_unit']})\n"
                        f"`DS [{received_data['DS']['bd_usage']}/50M]` : {received_data['DS']['max_bps_unit']} ({received_data['DS']['diff_emoji']}{received_data['DS']['diff_unit']})\n"
                        f"`HY [{received_data['HY']['bd_usage']}/50M]` : {received_data['HY']['max_bps_unit']} ({received_data['HY']['diff_emoji']}{received_data['HY']['diff_unit']})\n"
                        f"`IB [{received_data['IB']['bd_usage']}/50M]` : {received_data['IB']['max_bps_unit']} ({received_data['IB']['diff_emoji']}{received_data['IB']['diff_unit']})\n"
                        f"`LD [{received_data['LD']['bd_usage']}/50M]` : {received_data['LD']['max_bps_unit']} ({received_data['LD']['diff_emoji']}{received_data['LD']['diff_unit']})\n"
                        f"`WR [{received_data['WR']['bd_usage']}/50M]` : {received_data['WR']['max_bps_unit']} ({received_data['WR']['diff_emoji']}{received_data['WR']['diff_unit']})\n"
                    ),
                    "mrkdwn_in": ["text", "title"]
                },
                {
                    "color": "#D2B48C",
                    "title": f"<대외기관>",
                    "text": (
                        f"`FIMS [{received_data['FIMS']['bd_usage']}/1G]` : {received_data['FIMS']['max_bps_unit']} ({received_data['FIMS']['diff_emoji']}{received_data['FIMS']['diff_unit']})\n"                        
                        f"`KRX [{received_data['KRX']['bd_usage']}/2G]` : {received_data['KRX']['max_bps_unit']} ({received_data['KRX']['diff_emoji']}{received_data['KRX']['diff_unit']})\n"
                        f"`STOCK-NET [{received_data['STOCK-NET']['bd_usage']}/45M]` : {received_data['STOCK-NET']['max_bps_unit']} ({received_data['STOCK-NET']['diff_emoji']}{received_data['STOCK-NET']['diff_unit']})\n"
                    ),
                    "mrkdwn_in": ["text", "title"]
                }
            ]

    elif net_gubn == "mpr":
        blocks=[
            {
                "type": "section",
                "text":{
                    "type": "mrkdwn",
                    "text": f"*{emoji} [{market}-{time_range}] 시세망 트래픽*"
                }
            }
        ]
        attachments=[
            {
                "color": "#90EE90",
                "title": f"<시세상품>",
                "text": (
                    f"`NXTA-COM [{received_data['NXTA-COM']['bd_usage']}/100M]` : {received_data['NXTA-COM']['max_bps_unit']} ({received_data['NXTA-COM']['diff_emoji']}{received_data['NXTA-COM']['diff_unit']})\n"
                    f"`NXTA-10 [{received_data['NXTA-10']['bd_usage']}/100M]` : {received_data['NXTA-10']['max_bps_unit']} ({received_data['NXTA-10']['diff_emoji']}{received_data['NXTA-10']['diff_unit']})\n"
                    f"`NXTA-5 [{received_data['NXTA-5']['bd_usage']}/100M]` : {received_data['NXTA-5']['max_bps_unit']} ({received_data['NXTA-5']['diff_emoji']}{received_data['NXTA-5']['diff_unit']})\n"
                    f"`NXTA-3 [{received_data['NXTA-3']['bd_usage']}/100M]` : {received_data['NXTA-3']['max_bps_unit']} ({received_data['NXTA-3']['diff_emoji']}{received_data['NXTA-3']['diff_unit']})\n"
                    f"`NXTB-COM [{received_data['NXTB-COM']['bd_usage']}/100M]` : {received_data['NXTB-COM']['max_bps_unit']} ({received_data['NXTB-COM']['diff_emoji']}{received_data['NXTB-COM']['diff_unit']})\n"
                    f"`NXTB-10 [{received_data['NXTB-10']['bd_usage']}/100M]` : {received_data['NXTB-10']['max_bps_unit']} ({received_data['NXTB-10']['diff_emoji']}{received_data['NXTB-10']['diff_unit']})\n"
                    f"`NXTB-5 [{received_data['NXTB-5']['bd_usage']}/100M]` : {received_data['NXTB-5']['max_bps_unit']} ({received_data['NXTB-5']['diff_emoji']}{received_data['NXTB-5']['diff_unit']})\n"
                    f"`NXTB-3 [{received_data['NXTB-3']['bd_usage']}/100M]` : {received_data['NXTB-3']['max_bps_unit']} ({received_data['NXTB-3']['diff_emoji']}{received_data['NXTB-3']['diff_unit']})\n"
                ),
                "mrkdwn_in": ["text", "title"]
            }
        ]
    try:
        response = client.chat_postMessage(channel=channel, blocks=blocks, attachments=attachments)

    except SlackApiError as e:
        if e.response['status_code'] == 429:
            retry_after = int(e.response.headers.get("Retry-After", 1))
            print(f"Rate limited. Retrying after {retry_after} seconds...")
            time.sleep(retry_after)
        else:
            print(f"failed_message_sending: {e.response['error']}, {e.response['status_code']}")


@app.post("/webhook/slack/{net_gubn}")
async def send_monitor_webhook_to_slack(net_gubn:str, request: Request):
    received_data = await request.json()
    print(f"daily_data: {received_data}")
    market = received_data["market"]
    time_range = ""
    emoji = ""
    if market == "프리":
        market = "프리장"
        time_range = "07:58~08:01"
        emoji = ":sun:"
    elif market == "정규":
        market = "정규장"
        time_range = "08:58~09:01"
        emoji = ":gogo_dancer:"
    elif market == "에프터":
        market = "에프터장"
        time_range = "15:38~15:41"
        emoji = ":sunset:"

    # data = received_data["data"]
    # print(f"Received data: {data}")
    # channel = "network-test"
    channel = "network-monitor"

    convert_to_message_format(received_data, net_gubn, market, time_range, emoji)


def send_to_slack_message(channel, message_title, message_body):
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
                },
                {   # 발생내용블럭
                    "color": message_body['color'],
                    "title": message_body['event_name']['title'],
                    "text": message_body['event_name']['text']
                },
                {   # 현재상태블럭럭
                    "color": message_body['color'],
                    "title": message_body['opdata']['title'],
                    "text": message_body['opdata']['text']
                }
            ]
            # blocks=message_body['blocks']
        )

    except SlackApiError as e:
        if e.response['status_code'] == 429:
            retry_after = int(e.response.headers.get("Retry-After", 1))
            print(f"Rate limited. Retrying after {retry_after} seconds...")
            time.sleep(retry_after)
        else:
            print(f"failed_message_sending: {e.response['error']}, {e.response['status_code']}")

@app.post("/send_message_to_slack")
def send_message_to_slack(channel:str, message_info: Dict):
    # if channel == "#network-alert-syslog":
    #     print(f"IOSDATE : {message_info['kst_time_formatted']}")
    #     # dt = datetime.fromisoformat(message_info['timestamp'])
    #     dt_kst = dt.astimezone(KST)
    #     formatted_date = dt_kst.strftime("%Y-%m-%d %H:%M:%S")
    # else:
    #     formatted_date = message_info['kst_time_formatted']


    try:
        response = client.chat_postMessage(
            channel=channel,  # 예: "#general" 또는 "C12345678"
            text= f":warning: {message_info['severity'].upper()}>>{message_info['device']} :warning:",
            attachments=[
                {
                    "color": "warning",
                    # "title": f"{message_info['device']} // LEVEL:{message_info['severity']}",
                    "text": (
                        f"*-장비이름: {message_info['device']}*\n"
                        f"-장비IP: `{message_info['host_ip']}`\n"
                        f"-발생일시: `{message_info['timestamp_trans']}`\n"
                        f"-level: `{message_info['severity'].upper()}`\n"
                        f"-facility: {message_info['facility']}\n"
                        f"-mnemonic: {message_info['mnemonic']}\n"
                        f"-type: {message_info['type'].upper()}\n"
                        f"-message: ```{message_info['message']}```\n"
                    ),
                    "mrkdwn_in": ["text", "title"]
                }
            ]
            # blocks=[
            #     {
            #         "type": "section",
            #         "text": {
            #             "type": "mrkdwn",
            #             "text": f":alert:*{message_info['member_name']} 멀티캐스트수신 이상*:alert:"
            #         }
            #     },
            #     {
            #         "type": "context",
            #         "elements": [
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"장비이름: {message_info['device_name']}"
            #             },
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"가입상품: {message_info['products']}"
            #             },
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"PIM_RP: {message_info['pim_rp']}"
            #             },
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"기준 mroute: {message_info['product_cnt']}"
            #             },
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"헌재 mroute: {message_info['mroute_cnt']}"
            #             },
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"현재 oif_cnt: {message_info['oif_cnt']}"
            #             },
            #             {
            #                 "type": "mrkdwn",
            #                 "text": f"RPF_NBR: {message_info['rpf_nbr']}"
            #             },
            #         ]
            #     },
            #     {
            #         "type":"divider"
            #     }
            # ]
        )
        print("success_message_sending:", response["ts"])
        time.sleep(1)

    except SlackApiError as e:
        if e.response["status_code"] == 429:
            retry_after = int(e.response.headers.get("Retry-After", 1))
            print(f"Rate limited. Retrying after {retry_after} seconds...")
            time.sleep(retry_after)
        else:
            print(f"failed_message_sending: {e.response['error']}, {e.response['status_code']}")

