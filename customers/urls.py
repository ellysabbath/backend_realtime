from django.urls import path
from . import views

urlpatterns = [
    path('requests/', views.requests),
    path('requests/<str:rid>/', views.request_detail),
    path('requests/<str:rid>/pay/', views.pay),
    path('dashboard/', views.customer_dashboard),
    path('stream/', views.stream_customer_requests),
    path('requests/<str:rid>/location/', views.update_location),
    path('requests/<str:rid>/location/stream/', views.stream_location),
    path('requests/<str:rid>/location/', views.get_location),
    path('requests/<str:rid>/update-location/', views.update_location),
    path('requests/<str:rid>/location/stream/', views.stream_location),
]