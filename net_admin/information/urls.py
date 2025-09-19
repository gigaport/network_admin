from . import views
from django.urls import path

app_name = 'information'

urlpatterns = [
    path('', views.index, name='index'),
    path('init', views.init, name='init'),
]