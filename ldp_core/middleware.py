from django.shortcuts import redirect
from django.urls import reverse

class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and getattr(request.user, 'must_change_password', False):
            # Allow admins to skip or bypass, but per instructions "all other users except Admin"
            # We'll allow superusers and ADMINs to skip for safety, or we enforce it.
            # "except the Administrator" - so we skip for Admin.
            if request.user.role != 'ADMIN' and not request.user.is_superuser:
                allowed_paths = [
                    reverse('ldp_core:change_password'),
                    reverse('logout'),
                ]
                if request.path not in allowed_paths and not request.path.startswith('/static/') and not request.path.startswith('/admin/'):
                    return redirect('ldp_core:change_password')
        
        response = self.get_response(request)
        return response
