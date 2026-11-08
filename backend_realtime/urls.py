from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/chat/', include('chats.urls')),
    path('api/auth/', include('auths.urls')),
    path('api/customer/', include('customers.urls')),
    path('api/technician/', include('technicians.urls')),
    path('api/owner/', include('owners.urls')),
    path('api/admin/', include('admins.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/ms/', include('api.urls')),
]