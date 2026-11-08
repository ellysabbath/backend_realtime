from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register),
    path('me/', views.me),
    path('requests/', views.available_requests),
    path('requests/<str:rid>/accept/', views.accept_request),
    path('jobs/', views.my_jobs),
    path('revenue/', views.revenue),
    path('dashboard/', views.tech_dashboard),
    path('stream/', views.stream_technician_requests),
]