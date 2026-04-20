from . import views
from django.urls import path

app_name = 'multicast'

urlpatterns = [
    path('', views.index, name='index'),
    path('init', views.init, name='init'),
    path('mroute_output', views.mroute_output, name='mroute_output'),
    # path('multicast', views.multicast, name='multicast'),
]