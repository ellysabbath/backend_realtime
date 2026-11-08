from django.urls import path
from . import views
urlpatterns = [
    path('', views.list_for_user),
    path('<str:nid>/read/', views.mark_read),
]