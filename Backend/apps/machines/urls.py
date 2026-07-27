from django.urls import path

from . import views

app_name = 'machines'

urlpatterns = [
    path('', views.machine_list, name='list'),
    path('default/', views.machine_default, name='default'),
    path('<str:serial_number>/', views.machine_detail, name='detail'),
]
