from django.urls import path
from . import views

urlpatterns = [
    path('register/start/', views.register_start),
    path('register/verify/', views.register_verify),
    path('otp/send/', views.send_otp),
    path('otp/resend/', views.resend_otp),
    path('otp/verify/', views.verify_otp),
    path('me/', views.me),
    path('logout/', views.logout),
    path('users/<str:uid>/role/', views.set_role),
]