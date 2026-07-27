from django.urls import path

from . import views

app_name = 'authentication'

urlpatterns = [
    path('csrf/', views.csrf_view, name='csrf'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.profile_update_view, name='profile_update'),
]
