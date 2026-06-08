from . import views
from django.urls import path

app_name = 'multicast'

urlpatterns = [
    path('', views.index, name='index'),
    path('init', views.init, name='init'),
    path('mroute_output', views.mroute_output, name='mroute_output'),
    # 대상장비 CRUD (회원사-운영시세(API) 메뉴 전용)
    path('target_devices', views.target_devices_list, name='target_devices_list'),
    path('target_devices/create', views.target_devices_create, name='target_devices_create'),
    path('target_devices/<int:device_id>/update', views.target_devices_update, name='target_devices_update'),
    path('target_devices/<int:device_id>/delete', views.target_devices_delete, name='target_devices_delete'),
]