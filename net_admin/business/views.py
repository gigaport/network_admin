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
        "parent_menu": "network_contracts",
        "sub_menu": org_path
    }

    return render(request, path, context=context)


@csrf_exempt
def create_contract(request):
    """계약 정보 생성"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            contract_data = data.get('data', {})

            logger.info(f"[CREATE_CONTRACT] Data={contract_data}")

            api_url = f"{FASTAPI_BASE_URL}/api/v1/network/contracts"
            response = requests.post(api_url, json=contract_data)

            if response.status_code == 200:
                logger.info(f"[CREATE_CONTRACT] Success: {response.json()}")
                return HttpResponse(
                    json.dumps({"success": True, "message": "생성 완료"}, ensure_ascii=False),
                    content_type="application/json"
                )
            else:
                logger.error(f"[CREATE_CONTRACT] Error: {response.status_code} - {response.text}")
                return HttpResponse(
                    json.dumps({"success": False, "error": response.text}, ensure_ascii=False),
                    status=response.status_code,
                    content_type="application/json"
                )
        except Exception as e:
            logger.error(f"[CREATE_CONTRACT] Exception: {e}")
            return HttpResponse(
                json.dumps({"success": False, "error": str(e)}, ensure_ascii=False),
                status=500,
                content_type="application/json"
            )

    return HttpResponse(status=405)
