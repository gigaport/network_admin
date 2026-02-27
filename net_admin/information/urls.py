from . import views
from django.urls import path

app_name = 'information'

urlpatterns = [
    path('', views.index, name='index'),
    path('init', views.init, name='init'),
    path('update_contract', views.update_contract, name='update_contract'),
    path('delete_contract', views.delete_contract, name='delete_contract'),
]