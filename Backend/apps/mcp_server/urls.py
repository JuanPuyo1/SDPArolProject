from django.urls import path

from . import views

app_name = 'mcp_server'

urlpatterns = [
    path('tools/', views.list_tools_view, name='list_tools'),
    path('tools/<str:tool_name>/invoke/', views.invoke_tool_view, name='invoke_tool'),
]
