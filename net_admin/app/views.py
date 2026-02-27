import os
import json
import logging
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

FASTAPI_BASE_URL = os.environ.get('FASTAPI_BASE_URL', 'http://netview_fastapi:8000')

def index(request):
    return render(request, 'index.html', {'sub_menu': 'dashboard'})

def netbox_devices(request):
    return render(request, 'netbox_devices.html', {'parent_menu': 'network_asset', 'sub_menu': 'netbox_devices'})

def get_netbox_devices(request):
    try:
        qs = request.GET.urlencode()
        response = requests.get(f"{FASTAPI_BASE_URL}/api/v1/network/netbox/devices?{qs}", timeout=20)
        return JsonResponse(response.json())
    except Exception as e:
        logger.error(f"NetBox 디바이스 조회 실패: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

def get_netbox_device_detail(request, device_id):
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/api/v1/network/netbox/devices/{device_id}", timeout=15)
        return JsonResponse(response.json())
    except Exception as e:
        logger.error(f"NetBox 디바이스 상세 조회 실패: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

def get_netbox_filters(request):
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/api/v1/network/netbox/filters", timeout=15)
        return JsonResponse(response.json())
    except Exception as e:
        logger.error(f"NetBox 필터 조회 실패: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

def get_netbox_device_types(request):
    try:
        qs = request.GET.urlencode()
        response = requests.get(f"{FASTAPI_BASE_URL}/api/v1/network/netbox/device-types?{qs}", timeout=10)
        return JsonResponse(response.json())
    except Exception as e:
        logger.error(f"NetBox 디바이스 타입 조회 실패: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

def get_netbox_locations(request):
    try:
        qs = request.GET.urlencode()
        response = requests.get(f"{FASTAPI_BASE_URL}/api/v1/network/netbox/locations?{qs}", timeout=10)
        return JsonResponse(response.json())
    except Exception as e:
        logger.error(f"NetBox 위치 조회 실패: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

def get_netbox_racks(request):
    try:
        qs = request.GET.urlencode()
        response = requests.get(f"{FASTAPI_BASE_URL}/api/v1/network/netbox/racks?{qs}", timeout=10)
        return JsonResponse(response.json())
    except Exception as e:
        logger.error(f"NetBox 랙 조회 실패: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def create_netbox_device(request):
    try:
        data = json.loads(request.body)
        response = requests.post(f"{FASTAPI_BASE_URL}/api/v1/network/netbox/devices", json=data, timeout=15)
        return JsonResponse(response.json(), status=response.status_code)
    except Exception as e:
        logger.error(f"NetBox 디바이스 생성 실패: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def update_netbox_device(request, device_id):
    try:
        data = json.loads(request.body)
        response = requests.patch(f"{FASTAPI_BASE_URL}/api/v1/network/netbox/devices/{device_id}", json=data, timeout=15)
        return JsonResponse(response.json(), status=response.status_code)
    except Exception as e:
        logger.error(f"NetBox 디바이스 수정 실패: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def delete_netbox_device(request, device_id):
    try:
        response = requests.delete(f"{FASTAPI_BASE_URL}/api/v1/network/netbox/devices/{device_id}", timeout=15)
        if response.status_code == 200:
            return JsonResponse(response.json())
        return JsonResponse({"success": False, "error": response.text}, status=response.status_code)
    except Exception as e:
        logger.error(f"NetBox 디바이스 삭제 실패: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

def unified_search(request):
    try:
        q = request.GET.get('q', '')
        response = requests.get(f"{FASTAPI_BASE_URL}/api/v1/network/search", params={'q': q}, timeout=5)
        return JsonResponse(response.json())
    except Exception as e:
        logger.error(f"통합검색 실패: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

def get_dashboard(request):
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/api/v1/network/dashboard", timeout=10)
        return JsonResponse(response.json())
    except Exception as e:
        logger.error(f"대시보드 데이터 로드 실패: {e}")
        return JsonResponse({"success": False, "error": str(e)})
