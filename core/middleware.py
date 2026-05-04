from django.shortcuts import redirect
from django.contrib import messages


# URLs that don't require branch enforcement
EXEMPT_URLS = [
    '/',           # login
    '/logout/',
    '/dashboard/',
    '/generate-bill/',
    '/customer-search/',
    '/clients/',
    '/service/',
]


class BranchAccessMiddleware:
    """
    Middleware that prevents Branch Admins from accessing URLs that would
    expose data outside their assigned branch.

    Super Admins bypass all checks.
    Unauthenticated requests are handled by @login_required on views.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip if not logged in (login_required handles it)
        if not request.user.is_authenticated:
            return None

        # Super admins bypass all checks
        if request.user.is_super_admin:
            return None

        # Branch admin: block access to super-admin-only paths
        protected_prefixes = [
            '/add-admin/',
            '/edit-admin/',
            '/delete-admin/',
            '/manage-branches/',
            '/manage-users/',
        ]

        path = request.path
        for prefix in protected_prefixes:
            if path.startswith(prefix):
                messages.error(request, "Permission denied.")
                return redirect('dashboard')

        return None
