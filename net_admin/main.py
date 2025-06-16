import json, logging, re, time, html, sys, asyncio, uvicorn
from repynery import Repynery
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


app = FastAPI(root_path="/api")

# SLACK
# slack_token = "***REMOVED***8455397334246-8462358192034-3F7aPVe7I0Jg686HyXzBtDU0"
slack_token = "***REMOVED***9015318325377-9019974153362-woHLnGBnxMBrwG9I1Z5EiPKX"
client = WebClient(token=slack_token)

# TIME
KST = timezone(timedelta(hours=9))
TODAY_TIME = datetime.today().strftime('%Y-%m-%d %H:%M')

# 스레드풀 생성
executor = ThreadPoolExecutor(max_workers=60)

TODAY_STR = datetime.today().strftime('%Y-%m-%d')
TS_DEVICES = load('../ts_member_mpr.yaml')
PR_DEVICES = load('../pr_member_mpr.yaml')
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

# === [ 사용자 설정 영역 ] ===
feedname = "COR_ASN"
tag_values = ["ALL_SECUTIES","KB","KR_HQ","KR_KT","MR", "KW", "SH","NH","SS","KRX","STOCK-NET"]  # 여러 태그 지정 (리스트로 작성)
bind_value = 121

# 서버 접속 및 로그인
print("Log in")
r1 = Repynery(False, "172.24.32.47", 8080, "lampad", "Sprtmxm1@3")
if not r1.login():
    print("Failed to login. Check connection information")
    exit(-1)
else:
    print(f'Logged in. Token: {r1.token}, Tag: {r1.tag}')



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

@app.post("/webhook/grafana")
async def send_zabbix_webhook_to_slack(request: Request):
    print(f'[grafana_alert_webhook_request] : {request}')

    data = await request.json()
    print(f'[grafana_alert_webhook_body] : {data}')

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"result": "success", "detail": "전송송처리가 완료되었습니다."}
    )

@app.post("/webhook/zabbix")
async def send_zabbix_webhook_to_slack(request: Request):
    print(f'[zabbix_alert_webhook_request] : {request}')

    data = await request.json()
    print(f'[zabbix_alert_webhook_body] : {data}')

    channel = "network-alert-critical"
    
    if data['event_value'] == '0' : ## 장애해소
        main_text = f":green-check-mark: {data['hostname']} >> {data['event_name']}"
        attachment_color = "#3bc95c"
        message_body = {
                "color": attachment_color,
                "mrkdwn_in": ["fields"],
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
                    # {
                    #     "title": "발생내용",
                    #     "value": f"{data['event_name']}",
                    #     "short": False,
                    # },
                    # {
                    #     "title": "현재상태",
                    #     "value": f"`{data['opdata']}`",
                    #     "short": False,
                    # },
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
                "mrkdwn_in": ["fields"],
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
                "mrkdwn_in": ["fields"],
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


    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"result": "success", "detail": "전송송처리가 완료되었습니다."}
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
                    "color": "#439FE0",
                    "title": f"<회원사_1그룹>",
                    "text": (
                        f"`전체증권사` : {received_data['ALL_SECUTIES']['max_bps_unit']} ({received_data['ALL_SECUTIES']['diff_emoji']}{received_data['ALL_SECUTIES']['diff_unit']})\n"
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

    # try:
    #     response = client.chat_postMessage(
    #         channel=channel,  # 예: "#general" 또는 "C12345678"
    #         # text= f"*[{market}] 회원사 장시간 MAX 트래픽*",
    #         blocks=[
    #             {
    #                 "type": "section",
    #                 "text":{
    #                     "type": "mrkdwn",
    #                     "text": f"*{emoji} [{market}-{time_range}] 주문망 트래픽*"
    #                 }
    #             }
    #         ],
    #         attachments=[
    #             {
    #                 "color": "#439FE0",
    #                 "title": f"회원사_1그룹",
    #                 "text": (
    #                     f"`전체증권사` : {received_data['ALL_SECUTIES']['max_bps_unit']} ({received_data['ALL_SECUTIES']['diff_emoji']}{received_data['ALL_SECUTIES']['diff_unit']})\n"
    #                     f"`KB [100M]` : {received_data['KB']['max_bps_unit']} ({received_data['KB']['diff_emoji']}{received_data['KB']['diff_unit']})\n"
    #                     f"`KR_HQ [100M]` : {received_data['KR_HQ']['max_bps_unit']} ({received_data['KR_HQ']['diff_emoji']}{received_data['KR_HQ']['diff_unit']})\n"
    #                     f"`KR_KT [100M]` : {received_data['KR_KT']['max_bps_unit']} ({received_data['KR_KT']['diff_emoji']}{received_data['KR_KT']['diff_unit']})\n"
    #                     f"`MR [200M]` : {received_data['MR']['max_bps_unit']} ({received_data['MR']['diff_emoji']}{received_data['MR']['diff_unit']})\n"
    #                     f"`KW [100M]` : {received_data['KW']['max_bps_unit']} ({received_data['KW']['diff_emoji']}{received_data['KW']['diff_unit']})\n"
    #                     f"`SH [50M]` : {received_data['SH']['max_bps_unit']} ({received_data['SH']['diff_emoji']}{received_data['SH']['diff_unit']})\n"
    #                     f"`NH [50M]` : {received_data['NH']['max_bps_unit']} ({received_data['NH']['diff_emoji']}{received_data['NH']['diff_unit']})\n"
    #                     f"`SS [50M]` : {received_data['SS']['max_bps_unit']} ({received_data['SS']['diff_emoji']}{received_data['SS']['diff_unit']})\n"
    #                     f"`KY [50M]` : {received_data['KY']['max_bps_unit']} ({received_data['KY']['diff_emoji']}{received_data['KY']['diff_unit']})\n"
    #                     f"`YU [50M]` : {received_data['YU']['max_bps_unit']} ({received_data['YU']['diff_emoji']}{received_data['YU']['diff_unit']})\n"
    #                     f"`TS [50M]` : {received_data['TS']['max_bps_unit']} ({received_data['TS']['diff_emoji']}{received_data['TS']['diff_unit']})\n"
    #                 ),
    #                 "mrkdwn_in": ["text", "title"]
    #             },
    #             {
    #                 "color": "#90EE90",
    #                 "title": f"회원사_2그룹",
    #                 "text": (
    #                     f"`DA [50M]` : {received_data['DA']['max_bps_unit']} ({received_data['DA']['diff_emoji']}{received_data['DA']['diff_unit']})\n"
    #                     f"`DB [50M]` : {received_data['DB']['max_bps_unit']} ({received_data['DB']['diff_emoji']}{received_data['DB']['diff_unit']})\n"
    #                     f"`BN [50M]` : {received_data['BN']['max_bps_unit']} ({received_data['BN']['diff_emoji']}{received_data['BN']['diff_unit']})\n"
    #                     f"`EU [50M]` : {received_data['EU']['max_bps_unit']} ({received_data['EU']['diff_emoji']}{received_data['EU']['diff_unit']})\n"
    #                     f"`HD [50M]` : {received_data['HD']['max_bps_unit']} ({received_data['HD']['diff_emoji']}{received_data['HD']['diff_unit']})\n"
    #                     f"`HN [50M]` : {received_data['HN']['max_bps_unit']} ({received_data['HN']['diff_emoji']}{received_data['HN']['diff_unit']})\n"
    #                     f"`HW [50M]` : {received_data['HW']['max_bps_unit']} ({received_data['HW']['diff_emoji']}{received_data['HW']['diff_unit']})\n"
    #                     f"`KA [50M]` : {received_data['KA']['max_bps_unit']} ({received_data['KA']['diff_emoji']}{received_data['KA']['diff_unit']})\n"
    #                     f"`LS [50M]` : {received_data['LS']['max_bps_unit']} ({received_data['LS']['diff_emoji']}{received_data['LS']['diff_unit']})\n"
    #                     f"`ME [50M]` : {received_data['ME']['max_bps_unit']} ({received_data['ME']['diff_emoji']}{received_data['ME']['diff_unit']})\n"
    #                     f"`SK [50M]` : {received_data['SK']['max_bps_unit']} ({received_data['SK']['diff_emoji']}{received_data['SK']['diff_unit']})\n"                        
    #                     f"`SY [50M]` : {received_data['SY']['max_bps_unit']} ({received_data['SY']['diff_emoji']}{received_data['SY']['diff_unit']})\n"
    #                     f"`IM [50M]` : {received_data['IM']['max_bps_unit']} ({received_data['IM']['diff_emoji']}{received_data['IM']['diff_unit']})\n"
    #                 ),
    #                 "mrkdwn_in": ["text", "title"]
    #             },
    #             {
    #                 "color": "#9370DB",
    #                 "title": f"PB이용사",
    #                 "text": (
    #                     f"`BK [50M]` : {received_data['BK']['max_bps_unit']} ({received_data['BK']['diff_emoji']}{received_data['BK']['diff_unit']})\n"
    #                     f"`DO [50M]` : {received_data['DO']['max_bps_unit']} ({received_data['DO']['diff_emoji']}{received_data['DO']['diff_unit']})\n"
    #                     f"`DS [50M]` : {received_data['DS']['max_bps_unit']} ({received_data['DS']['diff_emoji']}{received_data['DS']['diff_unit']})\n"
    #                     f"`HY [50M]` : {received_data['HY']['max_bps_unit']} ({received_data['HY']['diff_emoji']}{received_data['HY']['diff_unit']})\n"
    #                     f"`IB [50M]` : {received_data['IB']['max_bps_unit']} ({received_data['IB']['diff_emoji']}{received_data['IB']['diff_unit']})\n"
    #                     f"`LD [50M]` : {received_data['LD']['max_bps_unit']} ({received_data['LD']['diff_emoji']}{received_data['LD']['diff_unit']})\n"
    #                     f"`WR [50M]` : {received_data['WR']['max_bps_unit']} ({received_data['WR']['diff_emoji']}{received_data['WR']['diff_unit']})\n"
    #                 ),
    #                 "mrkdwn_in": ["text", "title"]
    #             },
    #             {
    #                 "color": "#D2B48C",
    #                 "title": f"대외기관",
    #                 "text": (
    #                     f"`FIMS [1G]` : {received_data['FIMS']['max_bps_unit']} ({received_data['FIMS']['diff_emoji']}{received_data['FIMS']['diff_unit']})\n"                        
    #                     f"`KRX [2G]` : {received_data['KRX']['max_bps_unit']} ({received_data['KRX']['diff_emoji']}{received_data['KRX']['diff_unit']})\n"
    #                     f"`STOCK-NET [45M]` : {received_data['STOCK-NET']['max_bps_unit']} ({received_data['STOCK-NET']['diff_emoji']}{received_data['STOCK-NET']['diff_unit']})\n"
    #                 ),
    #                 "mrkdwn_in": ["text", "title"]
    #             }
    #         ]
    #     )

    # except SlackApiError as e:
    #     if e.response['status_code'] == 429:
    #         retry_after = int(e.response.headers.get("Retry-After", 1))
    #         print(f"Rate limited. Retrying after {retry_after} seconds...")
    #         time.sleep(retry_after)
    #     else:
    #         print(f"failed_message_sending: {e.response['error']}, {e.response['status_code']}")


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


@app.get("/collect/{target}")
async def collect_data(target: str):
    if target == "pr":
        targets = load('../pr_member_mpr.yaml')
    elif target == "ts":
        targets = load('../ts_member_mpr.yaml')
    else:
        return JSONResponse(content={"error": "알 수 없는 대상"}, status_code=404)

    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, execute_collection, device_info, device_name)
        for device_name, device_info in targets.devices.items()
    ]

    results = await asyncio.gather(*tasks)
    return results

def execute_collection(device_info, device_name):

    ## 명령어01, 명렁어02 결과를 LIST 타입으로 수신신
    cmd_response_list:List = connect_device_and_execute_cmd(device_info)

    ## 멀티캐스트 관련 데이터 정제 시작 ##
    print(f"device_info : {device_info}")
    processed_data = process_multicast_info(cmd_response_list, device_info, device_name)
    # print(f"[06.PROCESSED_DATA] ==> {json.dumps(processed_data, indent=4, ensure_ascii=False)}")

    data = {"data": processed_data}

    return data


def process_multicast_info(cmd_response_list, device_info, device_name):
    print("[05.processing...]")

    ## cisco pyats return key값이 os마다 다름 별도 처리 필요
    if device_info.os == 'iosxe':
        device_os_key = ''
    elif device_info.os == 'nxos':
        device_os_key = 'default'

    valid_source_address_count = 0
    valid_oif_count = 0
    connected_server_count = 0
    min_uptime = '확인필요'
    rpf_nbrs = '확인필요'
    rp_addresses = []

    result = {}
    for data in cmd_response_list:
        if data['cmd'] == 'show_ip_mroute_source-tree' or data['cmd'] == 'show_ip_mroute':
            print("[06.PROCESSING SHOW IP MROUTE]\n\n")

            ## show ip mroute에 대한 테이블이 있을경우만 진행
            if data['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']:
                multicast_group = data['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']['multicast_group']

                ## 유요한 (S,G) 및 VLAN 1100 개수를 계산하여 기존 데이터에 삽입
                valid_source_address_count = count_valid_source_address(multicast_group)

                #####################==>> RP Address os별 삽입 기준 정리 해야됨!!!!!
                valid_multicast_data = count_valid_oif_and_get_min_uptime(multicast_group, device_info.os)

                # print(f"[valid count] : {valid_source_address_count}\n")
                if not valid_multicast_data:
                    print('비어있음')
                else:
                    # print(f"[vaild_multicast_data] => {valid_multicast_data}")
                    valid_source_address_count = valid_source_address_count
                    valid_oif_count = valid_multicast_data['valid_oif_count']
                    min_uptime = valid_multicast_data['min_uptime']
                    rpf_nbrs = valid_multicast_data['rpf_nbrs']
                    
                    if device_info.os == 'iosxe':
                        rp_addresses = valid_multicast_data['rp_addresses']
            else:
                print("[!!!데이터 없음!!!]")

        elif data['cmd'] == 'show_ip_pim_rp':
            print("[show ip pim rp logic]\n")
            rp_addresses.append(list(data['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']['rp']['static_rp'].keys())[0])

        elif data['cmd'] == 'show_interface_status':
            print("[show interface status]\n")
            print(f"{data['parsed_output']}")

            for interface, details in data['parsed_output']['interfaces'].items():
                # access_vlan 값과 인터페이스 상태 확인
                access_vlan = details.get('vlan')
                oper_status = details.get('status')

                if access_vlan == '1100' and oper_status == 'connected':
                    connected_server_count += 1
                    print(f"Matched interfaces: {interface} Deivice: {device_name}\n\n")
            print(f"[VLAN1100 UP interfaces total COUNT] : {device_name}{device_info.os} ==> {connected_server_count}")

    print(f"device_info_join_products >> {device_info.custom.get('join_products', [])}")

    result = {
        "device_name": device_name,
        "updated_time":TODAY_TIME,
        "device_os": device_info.os,
        "products": device_info.custom.get('join_products', []),
        "mgmt_ip": str(device_info.connections.default.ip),
        "valid_source_address_count": valid_source_address_count,
        "valid_oif_count": valid_oif_count,
        "min_uptime": min_uptime,
        "rp_addresses": rp_addresses,
        "rpf_nbrs": rpf_nbrs,
        "connected_server_count": connected_server_count,
        "mroute": cmd_response_list
    }

    return result


def connect_device_and_execute_cmd(device_info):
    print(f"[01.network device {device_info.name} connecting...]")

    """
    pyATS는 connect메서드 실행 시 자동으로 terminal timeout 설정을 무한(0)으로 설정한다.
    이를 방지하기위해 init_exec_commands, init_config_commands 기본 명령을 제거."
    """
    device_info.connect(
        init_exec_commands=['terminal length 0', 'terminal width 511'],
        init_config_commands=[],
        log_stdout=False,
        prompt_recovery=False,
        learn_hostname=False,
        logfile=None
    ) 

    result = []

    try:
        if device_info.os == "nxos":
            for cmd in NXOS_CMDS:
                cmd_response:str = device_info.execute(cmd['value'])
                # print(f"\n\n[02.CMD_RESPONSE] ==> \n {cmd_response}\n")

                ## 할당한 명령어 순차적 실행
                if cmd['key'] == 'show_ip_mroute_source-tree':
                    parser = ShowIpMrouteVrfAll(device=None)
                elif cmd['key'] == 'show_ip_pim_rp':
                    parser = ShowIpPimRp(device=None)
                elif cmd['key'] == 'show_interface_status':
                    parser = ShowInterfaceStatus(device=None)
                
                parsed_output, org_output = parse_pyats_to_json(parser, cmd_response)
                
                temp = {
                    "cmd": cmd['key'],
                    "parsed_output": parsed_output,
                    "org_output": org_output
                }
                result.append(temp)

        elif device_info.os == "iosxe":
            for cmd in IOSXE_CMDS:
                cmd_response:str = device_info.execute(cmd['value'])

                ## 할당한 명령어 순차적 실행
                if cmd['key'] == 'show_ip_mroute':
                    parser = ShowIpMroute(device=None)
                elif cmd['key'] == 'show_interface_status':
                    parser = ShowInterfacesStatus(device=None)

                parsed_output, org_output = parse_pyats_to_json(parser, cmd_response)

                temp = {
                    "cmd": cmd['key'],
                    "parsed_output": parsed_output,
                    "org_output": org_output
                }
                result.append(temp)

        # print(f"[04.RESULT] ==> \n {result}\n")
        
        return result
        
    except Exception as e:
        print(f"error: {e}")

    finally:
        # 연결된 경우만 disconnect 실행
        if device_info.connected:
            device_info.disconnect()
            print("network device disconnected...")


def parse_pyats_to_json(parser, cmd_response):

    parsed_output = parser.parse(output=cmd_response)
    # print(f"[02-1.PARSED_OUTPUT] ==> {json.dumps(parsed_output, indent=4, ensure_ascii=False)}\n")
        
    ## json 포맷으로 파싱된 데이터와 명령어로 실행한 아웃풋 값을 리턴
    ## html에 CLI값을 출력하기위해 \r, \n 포맷을 변경
    org_output = cmd_response.replace('\n', '\\n').replace('\r', '\\r')
    org_output = html.escape(org_output)

    return parsed_output, org_output


def count_valid_source_address(data):
    count = 0
    for multicast_ip, info in data.items():
        print(f"multicast_group_ip : {multicast_ip}")
        if multicast_ip not in KNOWN_MULTICAST_IP :
            source = info.get('source_address',{})
            for key in source:
                if '*' not in key:
                    count += 1
    
    return count

def count_valid_oif_and_get_min_uptime(data, device_os:str):
    print(f'device_os {device_os}')
    valid_oif_count = 0
    uptimes = []
    rp_addresses = []
    rpf_nbrs = []
    vaild_check = False

    for ip, ip_info in data.items():
        ## 멀티캐스트그룹 239.29.30.x 대역 필터링
        if ip.startswith("239.29.30."):
            vaild_check = True
            source_addresses = ip_info.get("source_address", {})

            for addr, addr_info in source_addresses.items():
                if addr == "*": ## (*, G)인 경우만 rp KEY가 존재하고, rpf_neighbor도 이 기준으로로 수집
                    # 특정 멀티캐스트그룹IP : rp_address 값 모두 가져오기
                    if device_os == 'iosxe':
                        if addr_info['rp'] not in rp_addresses:
                            rp_addresses.append(addr_info['rp'])
                    
                    # 특정 멀티캐스트그룹IP : rpf_neighbor 값 모두 가져오기
                    if device_os == 'iosxe':
                        if addr_info['rpf_nbr'] not in rpf_nbrs:
                            rpf_nbrs.append(addr_info['rpf_nbr'])
                    continue

                if device_os == 'nxos':
                    ## nxos ex
                    # "239.29.30.62/32": {
                    #     "source_address": {
                    #         "177.21.180.101/32": {
                    #             "uptime": "2w4d",
                    #             "flags": "ip mrib pim",
                    #             "incoming_interface_list": {
                    #                 "Ethernet1/23": {
                    #                     "rpf_nbr": "99.3.3.9"
                    #                 }
                    #             },
                    #             "oil_count": 1,
                    #             "outgoing_interface_list": {
                    #                 "Vlan1100": {
                    #                     "oil_uptime": "2w4d",
                    #                     "oil_flags": "mrib"
                    #                 }
                    #             }
                    #         }
                    #     }
                    # }
                    first_key = next(iter(addr_info['incoming_interface_list']))
                    first_value = addr_info['incoming_interface_list'][first_key]
                    print(f"rpf {first_key}, {first_value}")
                    if first_value['rpf_nbr'] not in rpf_nbrs:
                        rpf_nbrs.append(first_value['rpf_nbr'])
                
                outgoing_interface = addr_info.get("outgoing_interface_list", {})
                ## OIF가 Vlan1100일 때 (정상수신)
                if "Vlan1100" in outgoing_interface:
                    ## 특정 멀티캐스트그룹IP : uptime 값 가져오기
                    if device_os == 'iosxe':
                        uptimes.append(outgoing_interface['Vlan1100']['uptime'])
                    elif device_os == 'nxos':
                        uptimes.append(outgoing_interface['Vlan1100']['oil_uptime'])
                    print(f"addr_info: {addr_info}")

                    # print(f"total_uptime_days: {total_uptime_days}")
                    valid_oif_count += 1 


    if vaild_check:
        min_uptime = min(uptimes, key=parse_uptime)

        print("vlan1100 개수", valid_oif_count)
        print(f"min_uptimes : {min_uptime}")
        print(f"rp_addresses: {rp_addresses}")
        print(f"rpf_nbrs: {rpf_nbrs}")
        return_data = {
            "valid_oif_count": valid_oif_count,
            "min_uptime": min_uptime,
            "rp_addresses": rp_addresses,
            "rpf_nbrs": rpf_nbrs
        }
    else:
        return_data = {}

    return return_data 

def parse_uptime(uptime:str):
    ## 정규식으로 9w3d 같은 포맷에서 숫자를 추출
    match = re.match(r"(?:(\d+)w)?(?:(\d+)d)?", uptime)

    if not match:
        return 0
    
    weeks = int(match.group(1)) if match.group(1) else 0
    days = int(match.group(2)) if match.group(2) else 0
    total_days = weeks * 7 + days

    return total_days


@app.get("/lampad")
async def execute_collect():
    kst = timezone(timedelta(hours=9))
    kst_now = datetime.now(kst)
    epoch_kst_now = int(kst_now.timestamp())
    kst_from = kst_now - timedelta(seconds=120)
    epoch_kst_from = int(kst_from.timestamp())

    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, collect_data, tag, epoch_kst_from, epoch_kst_now)
        for tag in tag_values
    ]

    results = await asyncio.gather(*tasks)
    return results

def collect_data(tag, epoch_kst_from, epoch_kst_now):
    print(f"\n=== Processing Tag: {tag} ===")
#    print(f"kst_now : {E_NOW_DATETIME}, E_THIRTY_SECONDS_AGO : {E_THIRTY_SECONDS_AGO}")

    # 데이터 요청
    error = r1.request_data_generation(feedname, {
        'from': epoch_kst_from,
        'to': epoch_kst_now,
        'type': 'bps',
        'base': 'bytes',
        'tags': tag
    })
    if error != '':
        print(f"Error for tag {tag}: {error}")

    # 결과 조회
    get_parameters = {'bind': bind_value}
    status = r1.get_result({})
    while status != 200:
        if status < 300:
            status = r1.get_result(get_parameters)
        else:
            print(f"Failed to get result for tag {tag}. Status code: {status}")
            continue

    # 결과 저장
    try:
        decoded = r1.result.decode('utf-8')
        fixed_json = re.sub(r'(\w+):"', r'"\1":"', decoded)
        fixed_json = re.sub(r'(\w+):', r'"\1":', fixed_json)
        data = json.loads(fixed_json)
        data[0]['tag'] = tag
        print(f">> {tag} : {data[0]}")

        return data[0]
    
    except Exception as e:
        print(f"❌ Failed to process result for tag {tag}: {e}")