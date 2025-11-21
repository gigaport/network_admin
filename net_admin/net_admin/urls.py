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
    path('index', include('app.urls')),
]
