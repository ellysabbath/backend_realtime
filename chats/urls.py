from django.urls import path
from . import views

urlpatterns = [
    path('messages/', views.messages),
    path('messages/send/', views.send_message),
    path('messages/<str:request_id>/read/', views.mark_read),
    path('stream/', views.stream_messages),
    path('typing/', views.typing),
    path('presence/', views.stream_presence),
]