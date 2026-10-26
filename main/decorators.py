from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

def role_required(required_role):
    def decorator(view_func):

        @login_required(login_url='main:show_login')
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            profile = getattr(request.user, 'profile', None)

            if profile is None or profile.role != required_role:
                raise PermissionDenied("Anda tidak memiliki izin untuk mengakses halaman ini.")
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator

personal_required = role_required('PERSONAL')
lembaga_required = role_required('LEMBAGA')