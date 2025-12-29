"""
URL configuration for Reflekt project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('journal/', include('apps.journal.urls')),
    path('goals/', include('apps.goals.urls')),
    path('habits/', include('apps.habits.urls')),
    path('dashboard/', include('apps.analytics.urls')),
    path('blog/', include('apps.blog.urls')),
    path('', include('apps.journal.urls_home')),
]

# Debug toolbar and media serving in development
if settings.DEBUG:
    import debug_toolbar
    from django.conf.urls.static import static

    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

    # Serve media files in development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
