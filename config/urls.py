"""
URL configuration for the LDP project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import TemplateView
from django.contrib.auth.decorators import login_required
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('files/', include('db_file_storage.urls')),
    path('', include('ldp_core.urls')),
    path('', TemplateView.as_view(template_name='registration/login.html')),
]