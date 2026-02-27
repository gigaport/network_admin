from . import views
from django.urls import path

app_name = 'business'

urlpatterns = [
    path('', views.index, name='index'),
    path('create_contract', views.create_contract, name='create_contract'),
]
