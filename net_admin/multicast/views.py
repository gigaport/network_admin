import requests, json
from datetime import datetime
from typing import List, Dict, Tuple, Union, Optional
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render, redirect
from django.utils.timezone import localtime, now
from django.utils import timezone
from django.http import HttpResponse, Http404, QueryDict

# TODAY_STR = localtime(now()).strftime('%Y-%m-%d')
NOW = timezone.localtime()
# TODAY_STR = NOW.date()
TODAY_STR = datetime.today().strftime('%Y-%m-%d')
TODAY_TIME = datetime.today().strftime('%Y-%m-%d %H:%M')

def index (request):
    org_path = request.path.strip('/')
    path = f"{org_path}.html"
    
    context = {
        "parent_menu": "network_status_check",
        "sub_menu": org_path
    }

    return render(request, path, context=context)

def init (request):
    now = timezone.localtime()
    # TODAY_STR = NOW.date()
    today_str = datetime.today().strftime('%Y-%m-%d')
    today_time = datetime.today().strftime('%Y-%m-%d %H:%M')

    print(f'[CALL_INIT_TODAY] : {today_str}, {today_time}, {now} \n')
    response_data = []

    if request.method == "GET":
        sub_menu = request.GET.get("sub_menu")
        market_gubn = ""
        
        if sub_menu == "pr_multicast":
            market_gubn = "pr_members"
        elif sub_menu == "ts_multicast":
            market_gubn = "ts_members"
        elif sub_menu == "pr_info_multicast":
            market_gubn = "pr_information"

        print(f"[SUB_MENU] : {sub_menu}, [MARKET_GUBN] : {market_gubn}")

        # market_gubn이 pr_information인 경우 (Arista 멀티캐스트 정보 수집)
        if market_gubn == "pr_information":
            api_url = "http://fastapi:8000/api/v1/network/collect/multicast/arista/pr"
            print(f"[CALL_API] ==> {api_url}")
            response = requests.get(api_url)
            if response.status_code == 200:
                data = response.json()
                print(f"[API_RESPONSE] : {data}")
                response_data = data
            else:
                print(f"[API_ERROR] : {response.status_code} - {response.text}")
                return HttpResponse(status=response.status_code, content=response.text)
        # market_gubn이 pr_members 또는 ts_members인 경우 (cisco 멀티캐스트 정보 수집)
        else:
            path = f"../data/{market_gubn}_mroute.json"
            print(f"PATH : {path}")
            members_mroute:Dict = openJsonFile(path)

            ## 회원사 or 정보이용사 정보 가져오기 ##
            if sub_menu == "pr_multicast" or sub_menu == "ts_multicast":
                path = f"../common/members_info.json"
            elif sub_menu == "pr_info_multicast":
                path = f"../common/information_info.json"

            client_info:Dict = openJsonFile(path)
            
            if sub_menu == "pr_multicast" or sub_menu == "pr_info_multicast": 
                path = f"../common/pr_mpr_multicast_info.json"
            elif sub_menu == "ts_multicast": 
                path = f"../common/ts_mpr_multicast_info.json"

            mpr_multicast_info:Dict = openJsonFile(path)

            ## 데이터 유무 검증
            if members_mroute and client_info and mpr_multicast_info:
            ## 01. member_info <- 시세 멀티캐스트그룹 수신 개수 삽입
            ## 02. member_mroute <- member_info 정보 삽입
                merge_members_mroute = merge_multicast_group_count(members_mroute['data'], mpr_multicast_info)
                # print(f"[merge_members_info]\n{merge_members_info}\n\n")
                # print(f"[members_mroute['data']]\n{members_mroute['data']}")

                response_data = create_member_sise_info(merge_members_mroute, client_info, today_time)

        print(f"SUB_MENU => {sub_menu}, MARKET_GUBN => {market_gubn}")
    
    # data meta info setting
    # meta = {'page': 1, 'pages': 1, 'perpage': -1, 'total': len(json_data['device_info']), 'sort': 'asc', 'field': 'id'}
    # result: Dict[str, str] = {'meta': meta}
    # result['data'] = json_data['device_info']

    return HttpResponse(json.dumps(response_data, ensure_ascii=False, indent=4), content_type="application/json")
   

def openJsonFile(path):
    data = {}
    try:
        with open(path, 'rt', encoding='UTF8') as json_file:
            data = json.load(json_file)
    except FileNotFoundError:
        print(f"파일이 존재하지 않습니다: {path}")
    except json.JSONDecodeError:
        print(f"JSON 형식이 잘못되었습니다.: {path}")

    return data

def merge_multicast_group_count(members_mroute:list, mpr_multicast_info:Dict):
    for idx, device in enumerate(members_mroute):
        products = device["products"]
        total = 0

        for product in products:
            if product in mpr_multicast_info:
                total += mpr_multicast_info[product].get("multicast_group_count", 0)

        members_mroute[idx]["multicast_group_count"] = total

    return members_mroute



def create_member_sise_info(members_mroute:list, members_info:Dict, updated_time:str):
    result = []
    member_no = 0
    member_code = ""
    member_name = ""
    device_name = ""
    device_os = ""
    products = ""
    pim_rp = ""
    product_cnt = 0
    mroute_cnt = 0
    oif_cnt = 0
    min_update = ""
    bfd_nbr = ""
    rpf_nbr = ""
    connected_server_cnt = 0
    org_output = ""
    alarm = True
    member_note = ""
    check_result = ""
    type = ""
    icon = ""


    for idx, device in enumerate(members_mroute):
        if device['device_os'] == 'iosxe':
            device_os_key = ''
        elif device['device_os'] == 'nxos':
            device_os_key = 'default'
        
        device_name = device['device_name']
        device_os = device['device_os']
        pim_rp = device['rp_addresses']
        products = device['products']
        product_cnt = device['multicast_group_count']
        connected_server_cnt = device['connected_server_count']
        org_output = device['mroute'][0]['org_output'] ## show ip mroute 정보만 표기하기 위함 show ip pim neighbor는 X
        # updated_time = device['updated_time']

        # print(f"[multicast_group] : {device['mroute']['vrf'][device_os_key]['address_family']['ipv4']['multicast_group']}")
        # multicast_group = device['mroute']['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']['multicast_group']
    
        mroute_cnt = device['valid_source_address_count'] if 'valid_source_address_count' in device else 0
        oif_cnt = device['valid_oif_count'] if 'valid_oif_count' in device else 0
        min_update = device['min_uptime'] if 'min_uptime' in device else '확인필요'
        rpf_nbr = device['rpf_nbrs'] if 'rpf_nbrs' in device else '확인필요'

        second_octet = device['mgmt_ip'].split(".")[1] # IP두번째 자리 코드값 추출
        if second_octet in members_info:
            member_no = second_octet
            member_code = members_info[second_octet]['member_code']
            member_name = members_info[second_octet]['member_name']
            alarm = members_info[second_octet]['alarm']
            member_note = members_info[second_octet]['member_note']

        ## 멀티캐스트 시세 정상 확인
        ## 시세상품 멀티캐스트 그룹 카운트 == 장비 mroute 카운트 == vlan 1100 OIF 카운트 비교
        if product_cnt == mroute_cnt == oif_cnt:
            check_result = '정상확인'
            type = "success"
            icon = "fas fa-check"
        elif connected_server_cnt == 0:
            check_result = '회원사연결서버없음'
            type = "primary"
            icon = "fas fa-check"
        else:
            check_result = '확인필요'
            type = "danger"
            icon = "fas fa-x-square"


        print(f"ALARM: {alarm}")

        if alarm:
            alarm_icon = "fa-bell"
            print("true")
        else:
            alarm_icon = "fa-bell-slash"
            print("false")

        print(f"ALARM_ICON: {alarm_icon}")
        
        temp = {
            # "id" : idx+1,
            "updated_time": updated_time,
            "member_no": member_no,
            "member_code": member_code,
            "member_name": member_name,
            "device_name": device_name,
            "device_os": device_os,
            "products": products,
            "pim_rp": pim_rp,
            "product_cnt": product_cnt,
            "mroute_cnt": mroute_cnt,
            "oif_cnt": oif_cnt,
            "min_update": min_update,
            "bfd_nbr": bfd_nbr,
            "rpf_nbr": rpf_nbr,
            "org_output": org_output,
            "connected_server_cnt": connected_server_cnt,
            "alarm":alarm,
            "alarm_icon": alarm_icon,
            "member_note": member_note,
            "check_result": check_result,
            "check_result_badge": { "type": type, "icon": icon }
        }

        result.append(temp)

        print(temp)

    # print(result)
    return result