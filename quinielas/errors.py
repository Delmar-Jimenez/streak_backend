from django.http import JsonResponse
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.exceptions import APIException


class BusinessError(APIException):
    def __init__(self, codigo, mensaje, status_code=400):
        self.status_code = status_code
        super().__init__(mensaje, code=codigo)


def exception_handler(exc, context):
    from rest_framework.views import exception_handler as drf_exception_handler
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    codes = {
        400: 'DATOS_INVALIDOS', 401: 'NO_AUTENTICADO', 403: 'ACCESO_DENEGADO',
        404: 'NO_ENCONTRADO', 405: 'METODO_NO_PERMITIDO', 415: 'FORMATO_NO_SOPORTADO',
        429: 'DEMASIADAS_SOLICITUDES',
    }
    detail = response.data
    message = detail.get('detail') if isinstance(detail, dict) else None
    code = str(exc.get_codes()) if isinstance(exc, BusinessError) else codes.get(response.status_code, 'ERROR_API')
    response.data = {'error': {'codigo': code, 'mensaje': str(message or 'Revisa los datos enviados.')}}
    if message is None:
        response.data['error']['detalles'] = detail
    return response


def error_response(code, message, status):
    return JsonResponse({'error': {'codigo': code, 'mensaje': message}}, status=status)


def bad_request(request, exception=None):
    return error_response('SOLICITUD_INVALIDA', 'Solicitud invalida.', 400)


def permission_denied(request, exception=None):
    return error_response('ACCESO_DENEGADO', 'Acceso denegado.', 403)


def not_found(request, exception=None):
    return error_response('NO_ENCONTRADO', 'Recurso no encontrado.', 404)


def server_error(request):
    return error_response('ERROR_INTERNO', 'No se pudo completar la solicitud.', 500)
