from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register),
    path('me/', views.me),
    path('dashboard/', views.dashboard),
    path('garages/<str:gid>/pay-fee/', views.pay_fee),
    path('treaty/<str:gid>/download/', views.download_treaty),
    path('garages/<str:gid>/documents/', views.garage_documents),
    path('garages/<str:gid>/upload-treaty/', views.upload_treaty),
    path('garages/active/', views.list_active_garages),
    path('technicians/', views.get_garage_technicians),
    path('technicians/<str:tid>/approve/', views.approve_technician),   
]