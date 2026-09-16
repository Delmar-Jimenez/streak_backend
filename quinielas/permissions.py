from rest_framework.permissions import BasePermission

class IsPasswordNotTemporal(BasePermission):
    """
    Permite el acceso solo a usuarios cuya contraseña no sea temporal.
    Esta clase se debe usar en todas las vistas protegidas del proyecto, 
    excepto en la de cambiar-password y las públicas (login, register).
    """
    message = "Debes cambiar tu contraseña temporal antes de continuar realizando acciones."

    def has_permission(self, request, view):
        # Si el usuario no está autenticado, dejamos que IsAuthenticated o AllowAny decidan,
        # pero si está autenticado, verificamos que su flag sea False.
        if request.user and request.user.is_authenticated:
            return not getattr(request.user, 'pass_temporal_flag', False)
        return True
