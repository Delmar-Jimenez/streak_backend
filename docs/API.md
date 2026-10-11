# API STREAK

Prefijo: `/api/`. Se admiten rutas con y sin barra final sin redireccionar.
Las mismas rutas estan disponibles sin el prefijo /api para el catalogo A2.
Fechas ISO 8601 en UTC. Listados devuelven arrays.
Salvo catalogo, registro, login, refresh, recuperacion, restablecimiento y webhook,
las rutas requieren JWT y haber cambiado cualquier contrasena temporal.
Los errores 4xx/5xx de la aplicacion siguen RN-72:

```json
{"error":{"codigo":"DATOS_INVALIDOS","mensaje":"Revisa los datos enviados.","detalles":{"campo":["Motivo"]}}}
```

`detalles` es opcional. Codigos comunes: `NO_AUTENTICADO`, `ACCESO_DENEGADO`,
`NO_ENCONTRADO`, `METODO_NO_PERMITIDO`, `DEMASIADAS_SOLICITUDES`,
`ERROR_INTERNO`. Errores propios incluyen `QUINIELA_LLENA`, `YA_PARTICIPA`,
`PRONOSTICOS_CERRADOS`, `PAGO_INCONSISTENTE`, `TOKEN_INVALIDO`.
Los errores generados por el proxy o proveedor de hosting requieren configuracion
en esa infraestructura, fuera de Django.

## Rutas

| Metodo | Ruta | Entrada / resultado |
| --- | --- | --- |
| POST | auth/register/ | username, email, password; telefono, first_name, last_name opcionales. 201, sin password. |
| POST | auth/login/ | username, password; devuelve access y refresh. |
| POST | auth/login/refresh/ | refresh; devuelve access. |
| POST | auth/recuperar/ | email; respuesta generica 200 y enlace por correo si existe. |
| POST | auth/restablecer/ | uid, token, new_password del enlace; 200. |
| POST | auth/cambiar-password/ | old_password, new_password; 200, iniciar sesion nuevamente. |
| GET, PUT, PATCH | usuarios/me/ | Perfil. PUT/PATCH permiten first_name, last_name, telefono, foto. |
| GET | torneos/ | Torneos activos/finalizados. |
| GET | torneos/{id}/ | Detalle del torneo. |
| GET | torneos/{id}/equipos/ | Equipos y escudos. |
| GET | torneos/{id}/fases/ | Fases ordenadas. |
| GET | torneos/{id}/partidos/ | Filtros opcionales estado y fase. |
| GET | partidos/{id}/ | Detalle del partido. |
| POST | quinielas/ | nombre, torneo, max_participantes; 201. Creador inscrito automaticamente. |
| GET | quinielas/mias/ | Quinielas creadas o en las que participa el usuario. |
| GET | quinielas/historial/ | Quinielas propias cuyo torneo esta FINALIZADO. |
| POST | quinielas/unirse/ | codigo; acepta tambien codigo_unico por compatibilidad. 201. |
| GET | quinielas/{id}/ | Detalle accesible a miembros. |
| GET | quinielas/{id}/participantes/ | Miembros con id de participante, usuario, username, puntos y fecha_union. |
| GET | quinielas/{id}/tabla/ | Participantes por puntos descendentes y campo posicion. |
| GET | quinielas/{id}/partidos/ | Partidos del torneo con mi_pronostico y mis_puntos. Filtros estado/fase. |
| GET | quinielas/{id}/partidos/{pid}/detalle/ | Objeto partido y lista participantes con pronostico y puntos_obtenidos. |
| GET | quinielas/{id}/participantes/{uid}/detalle/ | uid es ID de usuario; devuelve participante y partidos con pronostico/puntos_obtenidos. |
| GET, POST | quinielas/{id}/pronosticos/ | GET propios. POST partido, goles_local_pred, goles_visita_pred; 201 nuevo o 200 actualizado. |
| GET | quinielas/{id}/participantes/{participante_id}/pronosticos/ | Pronosticos del participante de la misma quiniela. |
| GET | pro/estado/ | es_pro. |
| POST | pro/suscribir/ | Header Idempotency-Key; devuelve pago_id, referencia, client_secret y estado Stripe. |
| GET | pro/pagos/ | Historial propio: id, monto, moneda, estado, referencia, fecha. |
| POST | pro/webhook/ | Cuerpo original de Stripe y Stripe-Signature; uso exclusivo del proveedor. |

El perfil no permite modificar privilegios ni correo; cambiar correo requiere un
flujo de verificacion que no forma parte del informe recibido. Fotos se envian
como multipart/form-data. No se publican emails ni telefonos de otros miembros.
Los detalles incluyen todos los participantes/partidos aunque no tengan pronostico.
Un pronostico ausente u oculto se representa con null y puntos_obtenidos=0.
Las tres consultas de partidos/detalle requieren pertenecer a la quiniela.
`mias` conserva todas las propias; `historial` es el subconjunto finalizado.

## Pronosticos y puntuacion

Se admiten marcadores enteros no negativos, de partidos del torneo de la quiniela.
El torneo debe estar ACTIVO y el partido PROGRAMADO con fecha_hora futura.
La escritura se cierra al llegar la hora de inicio, aunque el administrador no
haya cambiado el estado. Cada participante tiene un pronostico por partido.

Pronosticos propios son visibles siempre. Los rivales solo son visibles para
miembros de la misma quiniela desde fecha_hora del partido. Esta interpretacion
de RN-40 requiere confirmacion contra el documento completo.

Se conserva el sistema existente: 5 exacto; 4 resultado y diferencia;
3 solo resultado; 0 fallo. Un empate no exacto vale 4 por tener diferencia cero.
Solo FINALIZADO con ambos marcadores suma puntos. Corregir el marcador recalcula;
reabrir, suspender o cancelar devuelve a cero los puntos de ese partido.
La tabla comparte posicion entre empates (1, 1, 3) y usa fecha_union/id para
un orden estable. Validar ese desempate cuando se reciban las reglas completas.

## Recuperacion y sesiones

No se genera ni imprime una contrasena temporal. Se envia un enlace de uso unico
valido por una hora; la contrasena permanece intacta hasta confirmar el token.
La app recibe uid/token del enlace y los envia a auth/restablecer/.
Resend entrega el correo por HTTPS. Mientras falte clave, remitente o enlace de
la app, auth/recuperar/ devuelve 503 `CORREO_NO_CONFIGURADO` para cualquier correo.
La URL definitiva esta pendiente del equipo Flutter; `streak://reset-password`
es solo un ejemplo, no un enlace habilitado. La pantalla debe leer los parametros
de consulta `uid` y `token`, pedir `new_password` y enviarlos a auth/restablecer/.
No registrar el enlace, el token ni la nueva contrasena en logs o analitica.
Mostrar errores de enlace invalido/expirado y volver al login tras el cambio.
Cambiar o restablecer la contrasena invalida JWT access y refresh anteriores.
Access dura 15 minutos y refresh 7 dias.
Login/registro/refresh/cambio tienen limite de 10/min por IP y recuperacion 5/h.
Los limites DRF usan el cache configurado; para multiples procesos conviene
un cache compartido y limitacion adicional en el proxy.

## Pago movil

1. Generar una Idempotency-Key unica por intento de compra y conservarla.
2. POST pro/suscribir/ con esa cabecera. Reintentar fallos de red con la misma clave.
3. Confirmar el client_secret mediante el SDK Stripe de la app. No registrarlo en logs.
4. Consultar pro/estado/ tras completar el SDK; el webhook firmado activa PRO.

Monto inicial conservado: USD 5.00, configurable desde el servidor.
Esta version conserva una compra unica de acceso PRO. No crea una suscripcion
recurrente, periodo de vigencia ni renovaciones: requieren la especificacion del
plan y configuracion de productos/precios en Stripe.
No se acepta token_pago ni se usa tok_visa por defecto.
Stripe queda en modo prueba (`STRIPE_LIVE_MODE=False`): usar una clave publicable
de prueba en Flutter. Una clave secreta real en el backend deja el inicio del pago
no disponible (503); un webhook de otro entorno se rechaza con
`MODO_PAGO_INVALIDO`. Usar usuarios de prueba, no cuentas de clientes, porque un
pago de prueba aprobado tambien cambia el acceso PRO del usuario correspondiente.

Eventos: payment_intent.succeeded, payment_intent.payment_failed,
payment_intent.canceled, charge.refunded. La firma, usuario, referencia, moneda y
monto se verifican antes de activar. Repeticiones son idempotentes y fallos tardios
no revierten pagos completos. Un reembolso total retira el acceso si no hay otro
pago completo; uno parcial lo conserva. Confirmar esta politica con negocio.
Una orden pendiente o con un fallo de pago recuperable impide crear otra con
distinta clave (409); se reintenta la misma orden hasta completarla o cancelarla
en Stripe. Cancelaciones confirmadas se registran como CANCELADO.
Una orden sin referencia mayor
a 23 horas requiere conciliacion en Stripe antes de reintentarse.

Referencias: [PaymentIntents](https://docs.stripe.com/api/payment_intents),
[SDK Python](https://github.com/stripe/stripe-python),
[errores DRF](https://www.django-rest-framework.org/api-guide/exceptions/).
