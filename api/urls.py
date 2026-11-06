from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health, name='health'),
    path('messages/', views.add_message, name='add-message'),
    path('messages/list/', views.list_messages, name='list-messages'),
]