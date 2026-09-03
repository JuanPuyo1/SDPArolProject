from django.urls import path

from . import views

urlpatterns = [
    path('chat/', views.chat_view, name='agents-chat'),
    path('fleet-chat/', views.fleet_chat_view, name='agents-fleet-chat'),
]
