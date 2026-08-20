"""
URL configuration for the LDP project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import TemplateView
from django.contrib.auth.decorators import login_required
from django.conf import settings
from ldp_core.storage import get_file

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path(
        'files/download/',
        get_file,
        {'add_attachment_headers': True},
        name='db_file_storage.download_file',
    ),
    path(
        'files/get/',
        get_file,
        {'add_attachment_headers': False},
        name='db_file_storage.get_file',
    ),
    path('', include('ldp_core.urls')),
    path('', TemplateView.as_view(template_name='registration/login.html')),
]