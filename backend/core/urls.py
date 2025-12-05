from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def root_view(request):
    """Root endpoint - API info"""
    return JsonResponse({
        "status": "ok",
        "service": "Facebook Page Generator API",
        "endpoints": {
            "tasks": "/api/tasks/",
            "pages": "/api/pages/",
            "profiles": "/api/profiles/",
            "invites": "/api/invites/",
        }
    })


urlpatterns = [
    path('', root_view, name='root'),
    path('admin/', admin.site.urls),
    path('api/', include('pages.urls')),
    path('api/automation/', include('automation.urls')),
]
