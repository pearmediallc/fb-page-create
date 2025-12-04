from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('pages.urls')),
    path('api/automation/', include('automation.urls')),
]
