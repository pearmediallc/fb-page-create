from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
import os


# Serve React index.html for frontend routes
class ReactAppView(TemplateView):
    template_name = 'index.html'

    def get(self, request, *args, **kwargs):
        # Check if React build exists
        react_index = settings.BASE_DIR / 'staticfiles' / 'frontend' / 'index.html'
        if os.path.exists(react_index):
            return super().get(request, *args, **kwargs)
        else:
            # Fallback to API info if frontend not built
            from django.http import JsonResponse
            return JsonResponse({
                "status": "ok",
                "service": "Facebook Page Generator API",
                "message": "Frontend not built. API available at /api/",
                "endpoints": {
                    "tasks": "/api/tasks/",
                    "pages": "/api/pages/",
                    "profiles": "/api/profiles/",
                    "invites": "/api/invites/",
                }
            })


urlpatterns = [
    # API routes (must come first)
    path('admin/', admin.site.urls),
    path('api/', include('pages.urls')),
    path('api/automation/', include('automation.urls')),

    # React frontend (catch-all for client-side routing)
    re_path(r'^(?!api|admin|static).*$', ReactAppView.as_view(), name='react'),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
