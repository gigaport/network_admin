import requests, json, logging
from datetime import datetime
from typing import List, Dict, Tuple, Union, Optional
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render, redirect
from django.utils.timezone import localtime, now
from django.utils import timezone
from django.http import HttpResponse, Http404, QueryDict

# 로거 설정
logger = logging.getLogger(__name__)

def index (request):
    org_path = request.path.strip('/')
    path = f"{org_path}.html"
    
    context = {
        "parent_menu": "network_information",
        "sub_menu": org_path
    }

    return render(request, path, context=context)

def init (request):
    response_data = []
    logger.info(f"request : {request}")
    # today_str = datetime.today().strftime('%Y-%m-%d')

    if request.method == "GET":
        sub_menu = request.GET.get("sub_menu")

        if sub_menu == "pr_info_interface":
            # data 폴더의 pr_cisco_interface.json 파일을 읽어온다.
            with open(f'../data/pr_cisco_interface_info.json', 'r') as f:
                response_data = json.load(f)

        elif sub_menu == "ts_info_interface":
            # data 폴더의 ts_cisco_interface.json 파일을 읽어온다.
            with open(f'../data/ts_cisco_interface_info.json', 'r') as f:
                response_data = json.load(f)

        elif sub_menu == "pr_info_arp":
            # data 폴더의 pr_cisco_arp.json 파일을 읽어온다.
            with open(f'../data/pr_cisco_arp_info.json', 'r') as f:
                response_data = json.load(f)

        elif sub_menu == "ts_info_arp":
            # data 폴더의 ts_cisco_arp.json 파일을 읽어온다.
            with open(f'../data/ts_cisco_arp_info.json', 'r') as f:
                response_data = json.load(f)

        elif sub_menu == "info_lldp":
            api_url = "http://fastapi:8000/api/v1/network/collect/librenms/lldp"
            logger.info(f"[CALL_API] ==> {api_url}")
            response = requests.get(api_url)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[API_RESPONSE] : {len(data)} items received")
                response_data = data
            else:
                logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
                return HttpResponse(status=response.status_code, content=response.text)
            
        elif sub_menu == "interface_vip":
            api_url = "http://fastapi:8000/api/v1/network/collect/librenms/vlan_ips"
            logger.info(f"[CALL_API] ==> {api_url}")
            response = requests.get(api_url)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[API_RESPONSE] : {len(data)} items received")
                response_data = data
            else:
                logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
                return HttpResponse(status=response.status_code, content=response.text)

    return HttpResponse(json.dumps(response_data, ensure_ascii=False, indent=4), content_type="application/json")
