import logging
import json
import os
import requests
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

FASTAPI_BASE_URL = os.environ.get('FASTAPI_BASE_URL', 'http://netview_fastapi:8000')

def index(request):
    org_path = request.path.strip('/')
    path = f"{org_path}.html"

    # circuits, revenue_summary, purchase_contract는 회선계약 관리 메뉴 하위
    if org_path in ("circuits", "revenue_summary", "purchase_contract"):
        parent_menu = "network_contracts"
    elif org_path == "network_cost":
        parent_menu = "subscriber_management"
    else:
        parent_menu = "subscriber_management"

    context = {
        "parent_menu": parent_menu,
        "sub_menu": org_path
    }

    return render(request, path, context=context)

def get_subscriber_addresses(request):
    """회원사 주소 데이터 조회 (FastAPI 호출)"""
    try:
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/subscriber_addresses"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.get(api_url)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"[API_RESPONSE] : {len(data.get('data', []))} items received")
            return JsonResponse(data)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def create_address(request):
    """회원사 주소 정보 추가 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/subscriber_addresses"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.post(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"[API_RESPONSE] : Success")
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def update_address(request):
    """회원사 주소 정보 수정 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        address_id = data.get('id')

        if not address_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/subscriber_addresses/{address_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.put(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"[API_RESPONSE] : Success")
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def delete_address(request):
    """회원사 주소 정보 삭제 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        address_id = data.get('id')

        if not address_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/subscriber_addresses/{address_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.delete(api_url)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"[API_RESPONSE] : Success")
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error deleting address: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def get_subscriber_codes(request):
    """회원사 코드 데이터 조회 (FastAPI 호출)"""
    try:
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/subscriber_codes"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.get(api_url)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"[API_RESPONSE] : {len(data.get('data', []))} items received")
            return JsonResponse(data)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def create_subscriber_code(request):
    """회원사 코드 정보 추가 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/subscriber_codes"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.post(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"[API_RESPONSE] : Success")
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def update_subscriber_code(request):
    """회원사 코드 정보 수정 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        code_id = data.get('id')

        if not code_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/subscriber_codes/{code_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.put(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"[API_RESPONSE] : Success")
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def delete_subscriber_code(request):
    """회원사 코드 정보 삭제 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        code_id = data.get('id')

        if not code_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/subscriber_codes/{code_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.delete(api_url)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"[API_RESPONSE] : Success")
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==================== 시세상품 관리 ====================

def get_sise_products(request):
    """시세상품 데이터 조회 (FastAPI 호출)"""
    try:
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/sise_products"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.get(api_url)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"[API_RESPONSE] : {len(data.get('data', []))} items received")
            return JsonResponse(data)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_sise_product(request):
    """시세상품 추가 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/sise_products"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.post(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"[API_RESPONSE] : Success")
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_sise_product(request):
    """시세상품 수정 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        product_id = data.get('id')

        if not product_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/sise_products/{product_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.put(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"[API_RESPONSE] : Success")
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_sise_product(request):
    """시세상품 삭제 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        product_id = data.get('id')

        if not product_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/sise_products/{product_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.delete(api_url)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"[API_RESPONSE] : Success")
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ==================== 시세 채널 관리 ====================

def get_sise_channels(request):
    """시세 채널 데이터 조회 (FastAPI 호출)"""
    try:
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/sise_channels"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.get(api_url)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"[API_RESPONSE] : {len(data.get('data', []))} items received")
            return JsonResponse(data)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def create_sise_channel(request):
    """시세 채널 정보 추가 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/sise_channels"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.post(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"[API_RESPONSE] : Success")
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def update_sise_channel(request):
    """시세 채널 정보 수정 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        channel_id = data.get('id')

        if not channel_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/sise_channels/{channel_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.put(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"[API_RESPONSE] : Success")
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ==================== 과금기준 (Fee Schedule) 관리 ====================

def get_fee_schedule(request):
    """과금기준 목록 조회 (FastAPI 호출)"""
    try:
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/fee_schedule"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.get(api_url)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"[API_RESPONSE] : {len(data.get('data', []))} items received")
            return JsonResponse(data)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_fee_schedule(request):
    """과금기준 추가 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/fee_schedule"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.post(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_fee_schedule(request):
    """과금기준 수정 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        fee_id = data.get('id')

        if not fee_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/fee_schedule/{fee_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.put(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_fee_schedule(request):
    """과금기준 삭제 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        fee_id = data.get('id')

        if not fee_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/fee_schedule/{fee_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.delete(api_url)

        if response.status_code == 200:
            result = response.json()
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==================== 회선내역 (Circuit) 관리 ====================

def get_circuits(request):
    """회선내역 데이터 조회 (FastAPI 호출)"""
    try:
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/circuits"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.get(api_url)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"[API_RESPONSE] : {len(data.get('data', []))} items received")
            return JsonResponse(data)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def create_circuit(request):
    """회선내역 추가 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/circuits"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.post(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def update_circuit(request):
    """회선내역 수정 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        circuit_id = data.get('id')

        if not circuit_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/circuits/{circuit_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.put(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def delete_circuit(request):
    """회선내역 삭제 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        circuit_id = data.get('id')

        if not circuit_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/circuits/{circuit_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.delete(api_url)

        if response.status_code == 200:
            result = response.json()
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==================== 매출내역 (Revenue Summary) ====================

def get_revenue_summary(request):
    """매출내역 데이터 조회 (FastAPI 호출)"""
    try:
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/revenue_summary"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.get(api_url)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"[API_RESPONSE] : summary={len(data.get('summary', []))} items, details={len(data.get('details', []))} items")
            return JsonResponse(data)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def get_revenue_monthly(request):
    """월별 매출내역 데이터 조회 (FastAPI 호출)"""
    try:
        year_month = request.GET.get('year_month', '')
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/revenue_monthly?year_month={year_month}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.get(api_url)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"[API_RESPONSE] : trend={len(data.get('trend', []))} items, summary={len(data.get('summary', []))} items")
            return JsonResponse(data)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def download_revenue_pdf(request):
    """월별 매출 보고서 PDF 다운로드 (FastAPI 호출)"""
    try:
        year_month = request.GET.get('year_month', '')
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/revenue_report_pdf?year_month={year_month}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.get(api_url, stream=True)

        if response.status_code == 200:
            django_response = HttpResponse(
                response.content,
                content_type='application/pdf'
            )
            django_response['Content-Disposition'] = response.headers.get(
                'Content-Disposition', f'attachment; filename=revenue_report_{year_month}.pdf'
            )
            return django_response
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_sise_channel(request):
    """시세 채널 정보 삭제 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        channel_id = data.get('id')

        if not channel_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/sise_channels/{channel_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.delete(api_url)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"[API_RESPONSE] : Success")
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==================== 통신사 원가정보 (Network Cost) ====================

def get_network_cost(request):
    """통신사 원가정보 조회 (FastAPI 호출)"""
    try:
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/network_cost"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.get(api_url)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"[API_RESPONSE] : {len(data.get('data', []))} items received")
            return JsonResponse(data)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_network_cost(request):
    """통신사 원가정보 추가 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/network_cost"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.post(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_network_cost(request):
    """통신사 원가정보 수정 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        cost_id = data.get('id')

        if not cost_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/network_cost/{cost_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.put(api_url, json=data)

        if response.status_code == 200:
            result = response.json()
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_network_cost(request):
    """통신사 원가정보 삭제 (FastAPI 호출)"""
    try:
        data = json.loads(request.body)
        cost_id = data.get('id')

        if not cost_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)

        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/network_cost/{cost_id}"
        logger.info(f"[CALL_API] ==> {api_url}")

        response = requests.delete(api_url)

        if response.status_code == 200:
            result = response.json()
            return JsonResponse(result)
        else:
            logger.error(f"[API_ERROR] : {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return JsonResponse({'success': False, 'error': error_data.get('detail', response.text)}, status=response.status_code)
            except:
                return JsonResponse({'success': False, 'error': response.text}, status=response.status_code)

    except Exception as e:
        logger.error(f"Error calling FastAPI: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==================== 회원사 매입내역 (Purchase Contract) ====================

def get_purchase_contract(request):
    """회원사 매입내역 조회"""
    try:
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/purchase_contract"
        logger.info(f"[CALL_API] ==> {api_url}")
        response = requests.get(api_url)
        return JsonResponse(response.json())
    except Exception as e:
        logger.error(f"회원사 매입내역 조회 실패: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def get_cost_codes(request):
    """원가코드 목록 조회"""
    try:
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/network_cost/codes"
        logger.info(f"[CALL_API] ==> {api_url}")
        response = requests.get(api_url)
        return JsonResponse(response.json())
    except Exception as e:
        logger.error(f"원가코드 목록 조회 실패: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_purchase_contract(request):
    """회원사 매입내역 추가"""
    try:
        data = json.loads(request.body)
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/purchase_contract"
        logger.info(f"[CALL_API] ==> {api_url}")
        response = requests.post(api_url, json=data)
        return JsonResponse(response.json())
    except Exception as e:
        logger.error(f"회원사 매입내역 추가 실패: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_purchase_contract(request):
    """회원사 매입내역 수정"""
    try:
        data = json.loads(request.body)
        item_id = data.get('id')
        if not item_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/purchase_contract/{item_id}"
        logger.info(f"[CALL_API] ==> {api_url}")
        response = requests.put(api_url, json=data)
        return JsonResponse(response.json())
    except Exception as e:
        logger.error(f"회원사 매입내역 수정 실패: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_purchase_contract(request):
    """회원사 매입내역 삭제"""
    try:
        data = json.loads(request.body)
        item_id = data.get('id')
        if not item_id:
            return JsonResponse({'success': False, 'error': 'ID가 필요합니다.'}, status=400)
        api_url = f"{FASTAPI_BASE_URL}/api/v1/network/purchase_contract/{item_id}"
        logger.info(f"[CALL_API] ==> {api_url}")
        response = requests.delete(api_url)
        return JsonResponse(response.json())
    except Exception as e:
        logger.error(f"회원사 매입내역 삭제 실패: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
