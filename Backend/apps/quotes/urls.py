from django.urls import path

from . import views

app_name = 'quotes'

urlpatterns = [
    path('orders/', views.order_list, name='order-list'),
]
