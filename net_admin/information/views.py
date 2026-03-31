import requests, json, logging, os
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

FASTAPI_BASE_URL = os.environ.get('FASTAPI_BASE_URL', 'http://netview_fastapi:8000')

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
            api_url = f"{FASTAPI_BASE_URL}/api/v1/network/collect/librenms/lldp"
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
            api_url = f"{FASTAPI_BASE_URL}/api/v1/network/collect/librenms/vlan_ips"
            logger.info(f"[CALL_API] ==> {api_url}")
            response = requests.get(api_url)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[API_RESPONSE] : {len(data)} items received")
                response_data = data
            else:
                logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
                return HttpResponse(status=response.status_code, content=response.text)

# [수정됨] PTP 통합 메뉴 (한 번만 호출하면 끝!)
        elif sub_menu == "info_ptp":
            try:
                # 이제 뒤에 'all' 이나 아무거나 붙여서 한 번만 호출하면 됩니다.
                api_url = f"{FASTAPI_BASE_URL}/api/v1/network/collect/ptp/arista/all"
                # logger.info(f"[CALL_API] ==> {api_url}")
                
                response = requests.get(api_url, timeout=15)
                
                if response.status_code == 200:
                    response_data = response.json()
                    logger.info(f"[PTP] All data collected: {len(response_data)} items")
                else:
                    logger.error(f"[PTP] API Error: {response.status_code}")

            except Exception as e:
                logger.error(f"[PTP] Connection Failed: {e}")

        elif sub_menu == "network_contracts":
            api_url = f"{FASTAPI_BASE_URL}/api/v1/network/contracts"
            logger.info(f"[CALL_API] ==> {api_url}")
            response = requests.get(api_url)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[API_RESPONSE] : {len(data.get('data', []))} items received")
                response_data = data.get('data', [])
            else:
                logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
                return HttpResponse(status=response.status_code, content=response.text)

    return HttpResponse(json.dumps(response_data, ensure_ascii=False, indent=4), content_type="application/json")


@csrf_exempt
def update_contract(request):
    """계약 정보 업데이트"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            contract_id = data.get('id')
            contract_data = data.get('data', {})

            logger.info(f"[UPDATE_CONTRACT] ID={contract_id}, Data={contract_data}")

            api_url = f"{FASTAPI_BASE_URL}/api/v1/network/contracts/{contract_id}"
            response = requests.put(api_url, json=contract_data)

            if response.status_code == 200:
                logger.info(f"[UPDATE_CONTRACT] Success: {response.json()}")
                return HttpResponse(
                    json.dumps({"success": True, "message": "업데이트 완료"}, ensure_ascii=False),
                    content_type="application/json"
                )
            else:
                logger.error(f"[UPDATE_CONTRACT] Error: {response.status_code} - {response.text}")
                return HttpResponse(
                    json.dumps({"success": False, "error": response.text}, ensure_ascii=False),
                    status=response.status_code,
                    content_type="application/json"
                )
        except Exception as e:
            logger.error(f"[UPDATE_CONTRACT] Exception: {e}")
            return HttpResponse(
                json.dumps({"success": False, "error": str(e)}, ensure_ascii=False),
                status=500,
                content_type="application/json"
            )

    return HttpResponse(status=405)


@csrf_exempt
def delete_contract(request):
    """계약 정보 삭제"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            contract_id = data.get('id')

            logger.info(f"[DELETE_CONTRACT] ID={contract_id}")

            api_url = f"{FASTAPI_BASE_URL}/api/v1/network/contracts/{contract_id}"
            response = requests.delete(api_url)

            if response.status_code == 200:
                logger.info(f"[DELETE_CONTRACT] Success: {response.json()}")
                return HttpResponse(
                    json.dumps({"success": True, "message": "삭제 완료"}, ensure_ascii=False),
                    content_type="application/json"
                )
            else:
                logger.error(f"[DELETE_CONTRACT] Error: {response.status_code} - {response.text}")
                return HttpResponse(
                    json.dumps({"success": False, "error": response.text}, ensure_ascii=False),
                    status=response.status_code,
                    content_type="application/json"
                )
        except Exception as e:
            logger.error(f"[DELETE_CONTRACT] Exception: {e}")
            return HttpResponse(
                json.dumps({"success": False, "error": str(e)}, ensure_ascii=False),
                status=500,
                content_type="application/json"
            )

    return HttpResponse(status=405)
