"""
URL configuration for net_admin project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path('', include('app.urls')),
    path('multicast/', include('multicast.urls')),
    path('information/', include('information.urls')),
    path('pr_multicast/', include('multicast.urls')),
    path('ts_multicast/', include('multicast.urls')),
    path('pr_info_multicast/', include('multicast.urls')),
    path('info_lldp/', include('information.urls')),
    path('interface_vip/', include('information.urls')),
    path('pr_info_interface/', include('information.urls')),
    path('ts_info_interface/', include('information.urls')),
    path('pr_info_arp/', include('information.urls')),
    path('ts_info_arp/', include('information.urls')),
    path('info_ptp/', include('information.urls')),
    path('network_contracts/', include('business.urls')),
    path('subscriber_address/', include('setting.urls')),
    path('subscriber_codes/', include('setting.urls')),
    path('sise_products/', include('setting.urls')),
    path('sise_product_detail/', include('setting.urls')),
    path('fee_schedule/', include('setting.urls')),
    path('info_fee_schedule/', include('setting.urls')),
    path('circuits/', include('setting.urls')),
    path('info_company_circuits/', include('setting.urls')),
    path('revenue_summary/', include('setting.urls')),
    path('network_cost/', include('setting.urls')),
    path('purchase_contract/', include('setting.urls')),
    path('profit_summary/', include('setting.urls')),
    path('equipment_cost/', include('setting.urls')),
    path('index', include('app.urls')),
    path('netbox_devices/', include('app.urls')),
    path('dr_training/', include('app.urls')),
]
