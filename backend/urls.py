"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.http import FileResponse, HttpResponseNotFound
from django.views.generic import RedirectView

from django.conf import settings
from django.conf.urls.static import static
from pathlib import Path
from users.views import PasswordResetView


def react_spa(request):
    """
    Serve React SPA entrypoint for client-side routes.
    Keep this as the *last* route so it won't shadow /api, /static, /media.
    """
    base = Path(getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent))
    candidates = [
        base.parent / "frontend" / "dist" / "index.html",
        base.parent / "frontend" / "build" / "index.html",
        base / "frontend" / "dist" / "index.html",
        base / "frontend" / "build" / "index.html",
    ]
    for p in candidates:
        try:
            if p.exists():
                return FileResponse(open(p, "rb"), content_type="text/html")
        except Exception:
            continue
    return HttpResponseNotFound("index.html not found")

urlpatterns = [
    # Convenience: allow /admin to open Django admin (actual mount is /api/admin/)
    path("admin/", RedirectView.as_view(url="/api/admin/", permanent=False)),
    path("django-admin/", RedirectView.as_view(url="/api/admin/", permanent=False)),
    path('api/admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/auth/password/reset/', PasswordResetView.as_view()),
    path('api/auth/', include('dj_rest_auth.urls')),
    path('api/stores/', include('stores.urls')),
    path('api/products/', include('products.urls')),
    path('api/orders/', include('orders.urls')),
]

# الوسائط على DigitalOcean Spaces لا تُخدم من Django
if not getattr(settings, 'USE_DO_SPACES', False):
    if settings.DEBUG:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    else:
        urlpatterns += [
            re_path(
                r'^media/(?P<path>.*)$',
                serve,
                {'document_root': str(settings.MEDIA_ROOT)},
            ),
        ]

# SPA catch-all (must be last): serve React index.html on refresh
urlpatterns += [
    re_path(r"^(?!api/|static/|media/).*$", react_spa),
]

