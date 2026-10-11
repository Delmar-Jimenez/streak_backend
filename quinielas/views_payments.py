from decimal import Decimal
from datetime import timedelta
import re

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .errors import BusinessError
from .models import Pago, Usuario


def stripe_is_configured():
    mode = 'live' if settings.STRIPE_LIVE_MODE else 'test'
    return bool(settings.STRIPE_WEBHOOK_SECRET) and settings.STRIPE_SECRET_KEY.startswith(
        (f'sk_{mode}_', f'rk_{mode}_')
    )


@api_view(['POST'])
def pro_suscribir(request):
    if not stripe_is_configured():
        raise BusinessError('PAGOS_NO_CONFIGURADOS', 'Los pagos no estan disponibles.', 503)
    key = request.headers.get('Idempotency-Key', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,128}', key):
        raise BusinessError('IDEMPOTENCIA_REQUERIDA', 'Envia Idempotency-Key (8 a 128 letras, numeros, guiones).')
    # Persist the order before contacting Stripe; a webhook may arrive before the response.
    with transaction.atomic():
        user = Usuario.objects.select_for_update().get(pk=request.user.pk)
        pago = Pago.objects.filter(usuario=user, clave_idempotencia=key).first()
        if pago is None:
            if user.es_pro:
                raise BusinessError('YA_ES_PRO', 'El usuario ya tiene acceso PRO.')
            if user.pagos.filter(estado__in=[Pago.Estado.PENDIENTE, Pago.Estado.FALLIDO]).exists():
                raise BusinessError('PAGO_PENDIENTE', 'Reintenta el pago pendiente con su misma Idempotency-Key.', 409)
            pago = Pago.objects.create(
                usuario=user, clave_idempotencia=key, referencia='',
                monto=Decimal(settings.STRIPE_PRO_AMOUNT) / 100, moneda=settings.STRIPE_CURRENCY,
            )
    try:
        client = stripe.StripeClient(settings.STRIPE_SECRET_KEY)
        if pago.referencia:
            intent = client.v1.payment_intents.retrieve(pago.referencia)
        else:
            if pago.fecha < timezone.now() - timedelta(hours=23):
                raise BusinessError('PAGO_REQUIERE_REVISION', 'El pago pendiente requiere conciliacion antes de reintentarlo.', 409)
            intent = client.v1.payment_intents.create({
                'amount': int(pago.monto * 100),
                'currency': pago.moneda,
                'automatic_payment_methods': {'enabled': True},
                'metadata': {'pago_id': str(pago.pk), 'usuario_id': str(pago.usuario_id)},
                'description': 'Acceso PRO STREAK',
            }, options={'idempotency_key': f'streak-pro-{pago.pk}'})
        with transaction.atomic():
            locked = Pago.objects.select_for_update().get(pk=pago.pk)
            if locked.referencia and locked.referencia != intent.id:
                raise BusinessError('PAGO_INCONSISTENTE', 'No se pudo verificar el pago.', 409)
            locked.referencia = intent.id
            locked.save(update_fields=['referencia'])
    except stripe.StripeError:
        raise BusinessError('PROVEEDOR_PAGO_NO_DISPONIBLE', 'No se pudo iniciar el pago. Reintenta con la misma clave.', 502)
    response = Response({
        'pago_id': pago.pk, 'referencia': intent.id,
        'client_secret': intent.client_secret, 'estado': intent.status,
    })
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def stripe_webhook(request):
    if not stripe_is_configured():
        raise BusinessError('PAGOS_NO_CONFIGURADOS', 'Los pagos no estan disponibles.', 503)
    try:
        event = stripe.Webhook.construct_event(
            request.body, request.headers.get('Stripe-Signature', ''), settings.STRIPE_WEBHOOK_SECRET,
        ).to_dict()
    except (ValueError, stripe.SignatureVerificationError):
        raise BusinessError('FIRMA_INVALIDA', 'Firma de webhook invalida.')
    if event.get('livemode') is not settings.STRIPE_LIVE_MODE:
        raise BusinessError('MODO_PAGO_INVALIDO', 'El evento no corresponde al entorno de pagos.')
    event_type = event['type']
    if event_type not in ('payment_intent.succeeded', 'payment_intent.payment_failed', 'payment_intent.canceled', 'charge.refunded'):
        return Response({'recibido': True})
    obj = event['data']['object']
    metadata = obj.get('metadata', {})
    pago_id = metadata.get('pago_id')
    if not str(pago_id).isdigit():
        return Response({'recibido': True})
    with transaction.atomic():
        order = Pago.objects.filter(pk=pago_id).first()
        if order is None:
            return Response({'recibido': True})
        # All orders for one account share a lock so refunds cannot race with activation.
        user = Usuario.objects.select_for_update().get(pk=order.usuario_id)
        pago = Pago.objects.select_for_update().get(pk=order.pk)
        reference = obj.get('payment_intent') if event_type == 'charge.refunded' else obj['id']
        if (
            metadata.get('usuario_id') != str(user.pk)
            or obj.get('currency') != pago.moneda
            or obj.get('amount') != int(pago.monto * 100)
            or (pago.referencia and pago.referencia != reference)
        ):
            raise BusinessError('PAGO_INCONSISTENTE', 'Los datos del pago no coinciden.')
        if event_type == 'payment_intent.succeeded':
            if obj.get('status') != 'succeeded' or obj.get('amount_received') != int(pago.monto * 100):
                raise BusinessError('PAGO_INCONSISTENTE', 'El pago no esta liquidado.')
            if pago.estado != Pago.Estado.REEMBOLSADO:
                pago.estado = Pago.Estado.COMPLETADO
        elif event_type == 'charge.refunded':
            if not obj.get('refunded') or obj.get('amount_refunded') != obj.get('amount'):
                return Response({'recibido': True})
            pago.estado = Pago.Estado.REEMBOLSADO
        elif event_type == 'payment_intent.canceled' and pago.estado not in (Pago.Estado.COMPLETADO, Pago.Estado.REEMBOLSADO):
            pago.estado = Pago.Estado.CANCELADO
        elif pago.estado not in (Pago.Estado.COMPLETADO, Pago.Estado.REEMBOLSADO, Pago.Estado.CANCELADO):
            pago.estado = Pago.Estado.FALLIDO
        pago.referencia = reference
        pago.save(update_fields=['referencia', 'estado'])
        user.es_pro = user.pagos.filter(estado=Pago.Estado.COMPLETADO).exists()
        user.save(update_fields=['es_pro'])
    return Response({'recibido': True})
