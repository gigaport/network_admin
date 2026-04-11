from . import views
from django.urls import path

app_name = 'app'

urlpatterns = [
    path('', views.index, name='index'),
    path('search', views.unified_search, name='unified_search'),
    path('get_dashboard', views.get_dashboard, name='get_dashboard'),
    path('netbox_devices', views.netbox_devices, name='netbox_devices'),
    path('get_system_metrics', views.get_system_metrics, name='get_system_metrics'),
    path('dr_training', views.dr_training, name='dr_training'),
    path('get_dr_training_status', views.get_dr_training_status, name='get_dr_training_status'),
    path('get_netbox_devices', views.get_netbox_devices, name='get_netbox_devices'),
    path('get_netbox_device_detail/<int:device_id>', views.get_netbox_device_detail, name='get_netbox_device_detail'),
    path('get_netbox_filters', views.get_netbox_filters, name='get_netbox_filters'),
    path('get_netbox_device_types', views.get_netbox_device_types, name='get_netbox_device_types'),
    path('get_netbox_locations', views.get_netbox_locations, name='get_netbox_locations'),
    path('get_netbox_racks', views.get_netbox_racks, name='get_netbox_racks'),
    path('create_netbox_device', views.create_netbox_device, name='create_netbox_device'),
    path('update_netbox_device/<int:device_id>', views.update_netbox_device, name='update_netbox_device'),
    path('delete_netbox_device/<int:device_id>', views.delete_netbox_device, name='delete_netbox_device'),
]
