from django.urls import path
from . import views

urlpatterns = [
    path('users/', views.users),
    path('users/create/', views.create_user),
    path('users/<str:uid>/', views.update_user),
    path('users/<str:uid>/status/', views.user_status),
    path('users/<str:uid>/delete/', views.delete_user),
    path('garages/', views.garages),
    path('garages/<str:gid>/status/', views.garage_status),
    path('technicians/', views.technicians),
    path('technicians/<str:tid>/status/', views.technician_status),
    path('technicians/<str:tid>/delete/', views.delete_technician),
    path('requests/', views.requests),
    path('requests/<str:rid>/', views.update_request),
    path('requests/<str:rid>/delete/', views.delete_request),
    path('stats/', views.stats),
]