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
| POST | auth/register/ | username, email, password; telefono, first_name, last_name y fecha_nacimiento (ISO `YYYY-MM-DD`, opcional, no futura, edad <= 120 anios) opcionales. 201, sin password. |
| POST | auth/login/ | username, password; devuelve access y refresh. |
| POST | auth/login/refresh/ | refresh; devuelve access. |
| POST | auth/recuperar/ | email; respuesta generica 200 y contrasena temporal por correo si existe (RN-06). |
| POST | auth/restablecer/ | uid, token, new_password del enlace; 200. |
| POST | auth/cambiar-password/ | old_password, new_password; 200, iniciar sesion nuevamente. |
| GET, PUT, PATCH | usuarios/me/ | Perfil; expone fecha_nacimiento (`YYYY-MM-DD` o null). PUT/PATCH permiten first_name, last_name, telefono, fecha_nacimiento (misma validacion que el registro; null la borra), foto. |
| DELETE | usuarios/me/ | password actual y confirmar: true. Eliminacion permanente; 204. |
| GET | torneos/ | Torneos activos/finalizados. |
| GET | torneos/{id}/ | Detalle del torneo. |
| GET | torneos/{id}/equipos/ | Equipos y escudos. |
| GET | torneos/{id}/fases/ | Fases ordenadas. |
| GET | torneos/{id}/partidos/ | Filtros opcionales estado y fase. |
| GET | partidos/{id}/ | Detalle del partido. |
| POST | quinielas/ | nombre, torneo, max_participantes; 201. Creador inscrito automaticamente. |
| GET | quinielas/mias/ | Quinielas creadas o en las que participa el usuario. |
| GET | quinielas/historial/ | Quinielas propias cuyo torneo esta FINALIZADO. |
| POST | quinielas/validar-codigo/ | codigo; consulta previa sin inscribir. |
| POST | quinielas/unirse/ | codigo; acepta tambien codigo_unico. aceptar_ingreso_tardio: true cuando lo requiere la consulta previa. 201: datos del participante (id, usuario, ...) mas `quiniela_id` y `quiniela` (mismo objeto que GET quinielas/{id}/). |
| GET | quinielas/{id}/ | Detalle accesible a miembros. |
| GET | quinielas/{id}/participantes/ | Miembros con id de participante, usuario, username, puntos y fecha_union. |
| GET | quinielas/{id}/tabla/ | Participantes por puntos descendentes y campo posicion. |
| GET | quinielas/{id}/partidos/ | Partidos del torneo con mi_pronostico y mis_puntos. Filtros estado/fase. |
| GET | quinielas/{id}/partidos/{pid}/detalle/ | Objeto partido y lista participantes con pronostico y puntos_obtenidos. |
| GET | quinielas/{id}/participantes/{uid}/detalle/ | uid es ID de usuario; devuelve participante y partidos con pronostico/puntos_obtenidos. |
| GET, POST | quinielas/{id}/pronosticos/ | GET propios. POST partido, goles_local_pred, goles_visita_pred; 201 nuevo o 200 actualizado. |
| GET | quinielas/{id}/participantes/{participante_id}/pronosticos/ | Pronosticos del participante de la misma quiniela. |
| GET | pro/estado/ | es_pro y plan: monto_centavos, moneda, tipo, modo_prueba, max_participantes y max_participantes_gratis. |
| POST | pro/suscribir/ | Header Idempotency-Key; devuelve pago_id, referencia, client_secret y estado Stripe. |
| GET | pro/pagos/ | Historial propio: id, monto, moneda, estado, referencia, fecha. |
| GET | pro/pago-pendiente/ | pago, clave_idempotencia, estado Stripe y client_secret; pago:null si no existe. |
| POST | pro/pagos/{id}/cancelar/ | Cancela una orden propia no liquidada cuando Stripe lo permite. |
| POST | pro/webhook/ | Cuerpo original de Stripe y Stripe-Signature; uso exclusivo del proveedor. |

El perfil no permite modificar privilegios ni correo; cambiar correo requiere un
flujo de verificacion que no forma parte del informe recibido. Fotos se envian
como multipart/form-data. No se publican emails ni telefonos de otros miembros.
Los detalles incluyen todos los participantes/partidos aunque no tengan pronostico.
Un pronostico ausente u oculto se representa con null y puntos_obtenidos=0.
`estado_pronostico` distingue VISIBLE, NO_REGISTRADO y OCULTO. Antes del inicio,
todos los rivales son OCULTO, sin revelar si ya pronosticaron.
Participantes y tablas incluyen foto y es_pro. Los partidos incluyen
equipo_local_detalle/equipo_visita_detalle con nombre y escudo, manteniendo los IDs.
`mias` e `historial` incluyen torneo_nombre, cantidad_inscritos, mis_puntos y mi_posicion.
Las tres consultas de partidos/detalle requieren pertenecer a la quiniela.
`mias` conserva todas las propias; `historial` es el subconjunto finalizado.

## Pronosticos y puntuacion

Se admiten marcadores enteros no negativos, de partidos del torneo de la quiniela.
El torneo debe estar ACTIVO y el partido PROGRAMADO.
La escritura se cierra exactamente cinco minutos antes de fecha_hora, aunque el administrador no
haya cambiado el estado. Cada participante tiene un pronostico por partido.
El partido publica cierre_pronosticos y pronosticos_abiertos. Un partido cierra
al llegar a fecha_hora menos cinco minutos, o al cambiar a EN_JUEGO, lo que ocurra
primero. FINALIZADO, SUSPENDIDO y CANCELADO no aceptan nuevos pronosticos. Las fases admiten
LIGA, GRUPOS y ELIMINATORIA. goles_local/goles_visita son siempre el marcador
reglamentario que se puntua; goles_local_prorroga/goles_visita_prorroga y
penales_local/penales_visita son informativos y no se suman a esos campos.

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

RN-06: auth/recuperar/ genera una contrasena temporal aleatoria de 10 caracteres (sin 0, O, 1, l, I),
la envia al correo registrado, marca pass_temporal_flag y la hace vencer a las 24 horas
(pass_temporal_expira). Si el correo no se entrega, el cambio se revierte y la contrasena anterior
sigue sirviendo. La contrasena temporal nunca se imprime ni se registra en logs.
Resend entrega el correo por HTTPS. Mientras falte clave o remitente,
auth/recuperar/ devuelve 503 `CORREO_NO_CONFIGURADO` para cualquier correo.
Con una temporal vencida, auth/login/ y auth/cambiar-password/ responden 400
`PASSWORD_TEMPORAL_VENCIDA`: hay que solicitar una nueva. Una temporal marcada a mano desde el
admin (sin fecha de vencimiento) no vence.
auth/restablecer/ y la pagina /recuperar-acceso/ siguen disponibles para enlaces ya emitidos.
GET usuarios/me/ funciona con contrasena temporal y expone pass_temporal_flag.
Las operaciones restringidas devuelven 403 PASSWORD_TEMPORAL. El usuario puede
cambiar su clave o eliminar su propia cuenta sin desbloquear el resto de la API.
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
5. Si el dispositivo pierde su clave, consultar pro/pago-pendiente/. Se recupera
   la orden existente y su secreto sin crear un segundo cobro; nunca guardar ese
   secreto en logs. La consulta puede conciliar el estado desde Stripe.
6. Para abandonar una orden pendiente, POST pro/pagos/{id}/cancelar/. Si ya se
   liquido devuelve 409 PAGO_NO_CANCELABLE, no ejecuta un reembolso.

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
Una orden sin referencia mayor a 23 horas se busca por sus metadatos en Stripe;
si no hay exactamente una coincidencia, devuelve PAGO_REQUIERE_REVISION sin recrearla.

## Ingreso y limites

max_participantes debe ser 2..50 para creadores gratuitos o 2..100 para PRO.
Los nuevos codigos no contienen 0, 1, I, L ni O; codigos existentes siguen validos.
POST quinielas/validar-codigo/ devuelve quiniela_id, nombre, torneo_nombre,
cantidad_inscritos, max_participantes, ingreso_tardio, requiere_confirmacion,
partidos_cerrados, penalizacion_puntos y advertencia. No crea participantes.
Si hay partidos cerrados, mostrar la advertencia y solicitar aceptacion antes de
POST unirse/ con aceptar_ingreso_tardio:true. Omitirla devuelve 409
CONFIRMACION_INGRESO_TARDIO con la consulta actualizada en error.detalles.
Al ingresar, cada usuario solo puede pronosticar partidos que sigan abiertos.
Los cerrados anteriores a su ingreso no crean pronosticos y por tanto aportan 0;
no se descuenta puntaje por ingresar tarde. SUSPENDIDO y CANCELADO quedan fuera
de `partidos_cerrados`, porque ya valen 0 para todos. `penalizacion_puntos` es
siempre 0. El total del nuevo participante inicia en 0 y suma normalmente con
sus pronosticos posteriores, usando la escala 5/4/3/0 y el desempate habitual.

## Eliminacion de cuenta

URL publica para la ficha de la app: https://streak-api-6cl2.onrender.com/eliminar-cuenta/.
La web verifica usuario, contrasena actual y confirmacion; protege el formulario con CSRF.
La app debe ofrecer una opcion visible y llamar DELETE usuarios/me/ con JWT y
{"password":"...","confirmar":true}. No hay borrado de otras cuentas por ID.
Se eliminan perfil, foto almacenada, participaciones y pronosticos; JWT dejan de
funcionar. Quinielas compartidas permanecen con creador:null. Pagos conservan
importe, fecha, estado y referencia de Stripe, sin usuario ni clave de idempotencia.
Eliminar la cuenta no reembolsa ni cancela por si solo un pago en procesamiento.
El equipo debe definir y publicar plazos de retencion de registros financieros y
respaldos, y gestionar los datos del proveedor de pagos conforme a esa politica.
Esta implementacion no sustituye la integracion Flutter ni la revision de Google Play.

Referencias: [PaymentIntents](https://docs.stripe.com/api/payment_intents),
[SDK Python](https://github.com/stripe/stripe-python),
[errores DRF](https://www.django-rest-framework.org/api-guide/exceptions/).
