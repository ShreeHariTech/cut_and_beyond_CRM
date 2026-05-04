from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def super_admin_required(view_func):
    """
    Only Super Admins (is_super_admin=True) can access decorated views.
    Branch Admins are redirected to dashboard with a permission error.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_super_admin:
            messages.error(request, "Permission denied. Super Admin access required.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


def branch_access_required(model_class, pk_kwarg='id', branch_field='branch'):
    """
    Decorator factory that verifies the requested object belongs to the
    current user's branch (Branch Admins only).  Super Admins skip this check.

    Usage:
        @branch_access_required(Bill)
        def edit_bill(request, id): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            # Super admins can access anything
            if request.user.is_super_admin:
                return view_func(request, *args, **kwargs)

            # Branch admin: verify ownership
            pk = kwargs.get(pk_kwarg)
            if pk:
                try:
                    obj = model_class.objects.get(pk=pk)
                    obj_branch = getattr(obj, branch_field, None)
                    if obj_branch and obj_branch != request.user.branch:
                        messages.error(request, "Access denied: this record belongs to another branch.")
                        return redirect('dashboard')
                except model_class.DoesNotExist:
                    pass  # Let the view handle 404

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
