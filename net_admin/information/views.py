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

    today_str = datetime.today().strftime('%Y-%m-%d')

    if request.method == "GET":
        sub_menu = request.GET.get("sub_menu")

        if sub_menu == "pr_info_interface":
            # data 폴더의 pr_cisco_interface.json 파일을 읽어온다.
            with open(f'../data/pr_cisco_interface_info_{today_str}.json', 'r') as f:
                response_data = json.load(f)
        elif sub_menu == "ts_info_interface":
            # data 폴더의 ts_cisco_interface.json 파일을 읽어온다.
            with open(f'../data/ts_cisco_interface_info_{today_str}.json', 'r') as f:
                response_data = json.load(f)
        elif sub_menu == "pr_info_arp":
            # data 폴더의 pr_cisco_arp.json 파일을 읽어온다.
            with open(f'../data/pr_cisco_arp_info_{today_str}.json', 'r') as f:
                response_data = json.load(f)
        elif sub_menu == "ts_info_arp":
            # data 폴더의 ts_cisco_arp.json 파일을 읽어온다.
            with open(f'../data/ts_cisco_arp_info_{today_str}.json', 'r') as f:
                response_data = json.load(f)

    return HttpResponse(json.dumps(response_data, ensure_ascii=False, indent=4), content_type="application/json")
