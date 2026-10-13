# Actualizacion de la instancia publicada

## Antes del despliegue

- Respaldar PostgreSQL y los archivos subidos. Conservar una copia antes de migrar.
- Cambiar inmediatamente la contrasena del administrador expuesto mediante
  `python manage.py changepassword delmar`, si esa cuenta existe. Revisar usuarios
  con permisos de administrador y registros de acceso. Eliminar la ruta no elimina
  una cuenta que ya haya sido creada ni invalida su contrasena.
- Generar una SECRET_KEY nueva fuera del repositorio. Rotarla invalida las sesiones
  y JWT firmados con la clave que estaba publicada en el codigo.
- Cargar las variables de .env.example en los secretos del hosting. No subir .env.
- Configurar PostgreSQL. Si la instancia usa SQLite, transferir sus datos a PostgreSQL
  con respaldo y validacion antes de cambiar DATABASE_URL; estas migraciones no
  transfieren datos entre motores.
- Revisar correos duplicados sin distinguir mayusculas antes de migrar. La migracion
  0004 se detiene con un mensaje si existen; resolver la titularidad de esas cuentas
  sin borrarlas ni fusionarlas automaticamente.

## Publicar

```text
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
gunicorn core.wsgi:application --bind 0.0.0.0:$PORT
```

El comando Gunicorn es para un servidor Linux y PORT debe ser provisto por el
hosting. Configurar los comandos equivalentes en el servicio existente.
La aplicacion rechaza produccion sin SECRET_KEY segura, dominios explicitos y
DATABASE_URL PostgreSQL. DEBUG es falso por defecto.

La migracion 0003 recalcula puntos historicos, inscribe a creadores ausentes
y convierte pagos APROBADO a COMPLETADO. Si una quiniela antigua ya estaba llena,
amplia su capacidad solo lo necesario para conservar a sus miembros e inscribir
al creador. En tablas grandes, usar una ventana de mantenimiento.
La reversa de esta reparacion no reconstruye los valores incorrectos anteriores.

La puntuacion se actualiza mediante save/delete y el administrador Django.
Importaciones con QuerySet.update/bulk_create/bulk_update omiten las senales:
ejecutar `python manage.py recalcular_puntos` al terminar.

## Servicios externos

- HTTPS: terminar TLS en el proxy; activar TRUST_PROXY_HTTPS solo si ese proxy
  sobrescribe X-Forwarded-Proto. Esto evita bucles de redireccion.
- CORS_ALLOWED_ORIGINS: origenes web completos autorizados; no usar asteriscos.
  Flutter nativo no depende de CORS, pero Flutter Web si.
- CSRF_TRUSTED_ORIGINS: origen HTTPS del administrador.
- HSTS para subdominios/preload: activar solo cuando todos los dominios correspondientes
  sirvan exclusivamente HTTPS. check --deploy puede avisar si no se activan.
- Correo: Resend por HTTPS mediante Anymail (ver la seccion siguiente). No usar
  SMTP 25/465/587 en Render Free, que bloquea esos puertos. No activar recuperacion
  hasta verificar el remitente y probar la pagina HTTPS de recuperacion incluida.
- Stripe: claves del mismo entorno y endpoint HTTPS /api/pro/webhook/ con los cuatro
  eventos documentados. Copiar su secreto de firma a STRIPE_WEBHOOK_SECRET.
  Primero validar el flujo completo con Stripe en modo prueba y la app.
- Media: fotos y escudos pequenos se normalizan a WebP y se guardan en
  ImagenArchivo de la misma Supabase. /media/ los sirve con DEBUG=False.
  Limites: 5 MB de entrada, 16 megapixeles y 1024px por lado tras normalizar.
  Esto evita perder archivos al reiniciar Render Free; vigilar la cuota de Supabase.
  La migracion 0008 importa archivos antiguos disponibles en MEDIA_ROOT o el
  repositorio sin cambiar sus nombres. Archivos ya perdidos requieren volver a cargarse.
- Limites: usar cache compartido/proxy para limitar solicitudes entre replicas.

## Resend y recuperacion de contrasena

El backend usa `anymail.backends.resend.EmailBackend` por defecto. Anymail envia
por `https://api.resend.com/emails`, con timeout de 10 segundos, sin SMTP.
No se configuran webhooks de correo ni se solicitan permisos de recepcion.

Durante el desarrollo sin dominio propio se puede usar
`DEFAULT_FROM_EMAIL=STREAK <onboarding@resend.dev>`. Resend solo entrega desde ese
dominio al correo de su propia cuenta (puede ser Gmail), no a una lista arbitraria
de destinatarios. No usar Gmail como remitente de Resend ni redirigir tokens de
otros usuarios al buzon de pruebas. El modo sandbox de SendGrid no entrega mensajes.
El backend incluye una pagina HTTPS propia de recuperacion; ya no depende de Flutter.

1. Confirmar un dominio propio y el acceso a su DNS. `soporte@streak.com` fue solo
   un ejemplo: no usarlo sin confirmar propiedad. Agregar el dominio a Resend y
   copiar exactamente los registros DNS indicados por ese servicio; esperar la
   verificacion. No inventar registros ni reemplazar los de correo existentes.
2. El titular crea una clave con permiso de envio limitado al dominio y la guarda
   directamente como `RESEND_API_KEY` en Render. No subirla a Git ni al chat.
3. Configurar `DEFAULT_FROM_EMAIL` con el remitente verificado y, opcionalmente,
   `EMAIL_BACKEND=anymail.backends.resend.EmailBackend` para dejarlo explicito.
4. Dejar `PASSWORD_RESET_URL` vacio para usar /recuperar-acceso/ de este backend.
   La API devuelve 503 CORREO_NO_CONFIGURADO si falta remitente o clave.
   Si se configura otra pagina HTTPS, debe leer uid/token del fragmento (#).
5. Probar con una cuenta propia: recepcion, apertura del enlace, cambio y rechazo
   del token usado. PASSWORD_RESET_APP_URL es opcional cuando Flutter tenga su deep link.

Las excepciones del proveedor no se exponen ni se imprimen con sus detalles,
para no filtrar correos, claves o tokens. Un rechazo o timeout conserva la respuesta
generica para cuentas existentes e inexistentes. La aceptacion de Resend no prueba
entrega: verificar tambien su registro de entrega y la bandeja del destinatario.

## Stripe en modo prueba

`STRIPE_LIVE_MODE=False` es el valor por defecto. Solo acepta claves `sk_test_`
o `rk_test_`, y eventos firmados con `livemode=false`. Una clave real no se usa
accidentalmente para crear cobros. Los eventos del entorno incorrecto devuelven
400 `MODO_PAGO_INVALIDO` sin modificar pagos ni acceso PRO.

En el entorno de pruebas de la misma cuenta Stripe, registrar este destino:
`https://streak-api-6cl2.onrender.com/api/pro/webhook/`.
Seleccionar `payment_intent.succeeded`, `payment_intent.payment_failed`,
`payment_intent.canceled` y `charge.refunded`. El titular guarda la clave de prueba
y el secreto de firma de ese destino en `STRIPE_SECRET_KEY` y `STRIPE_WEBHOOK_SECRET`
de Render. No usar el secreto temporal de Stripe CLI para el destino del Dashboard.

Probar con usuarios exclusivos de pruebas: los eventos de prueba tambien actualizan
el acceso PRO de su usuario en esta base. No usar cuentas reales de clientes.
No mezclar pedidos de prueba y reales ni cambiar a modo real con ordenes de prueba
pendientes; antes de cobrar hace falta un entorno separado o una migracion explicita
de los datos de prueba, ademas de validar la configuracion comercial.

## Administradores expuestos

Revisar las cuentas administrativas `delmar` y `administrador`, si existen, y
cualquier otra cuenta con privilegios. La ruta publica y el antiguo comando de
build que creaba un administrador con clave fija ya no deben estar activos.
Eliminar esos mecanismos no cambia las contrasenas de cuentas existentes.
El titular debe iniciar sesion en `/admin/`, cambiar las claves desde Django y
completar personalmente su ingreso y guardado. No compartir las nuevas claves.

## Verificacion posterior

Confirmar que /crear-admin/ devuelve 404; login/perfil funcionan por HTTPS;
un pronostico anterior al cierre de cinco minutos se guarda y uno posterior se rechaza;
finalizar/corregir un partido actualiza la tabla; el correo llega sin aparecer en
logs; y Stripe activa PRO solo tras webhook firmado, incluso con reenvios.

## Migracion movil y demostracion

0006 agrega imagenes, marcadores de prorroga/penales y conserva grupos/pagos cuando
se elimina su creador. 0007 normaliza tipos de fase; los valores numericos antiguos
solo se convierten a LIGA si el torneo ya es LIGA. Valores desconocidos detienen
la migracion para revision, sin inventar un tipo. 0008 importa imagenes disponibles.
Estas migraciones no cambian DATABASE_URL ni el proveedor de base de datos.

Con autorizacion del titular y respaldo previo, ejecutar `python manage.py cargar_demo`
o abrir /admin/quinielas/torneo/demo/ como superusuario y confirmar. Es repetible,
no sobrescribe datos existentes. Crea tres torneos DEMO (dos activos, uno finalizado),
ocho equipos con escudos por torneo, fases, 24 partidos y cuatro usuarios marcados DEMO.
Los usuarios demo_streak_ana, demo_streak_bruno, demo_streak_carla y demo_streak_diego
no reciben contrasenas predeterminadas. El titular debe asignarlas personalmente
desde el administrador para iniciar sesion en la app; Ana tiene PRO de demostracion.
Sus quinielas usan DMALFA, DMBETA y DMGAMA. No se hacen cobros ni se envian correos.

## Render y GitHub

Repositorio identificado: https://github.com/Delmar-Jimenez/streak_backend.
En el Web Service existente de Render, configurar:

| Ajuste | Valor |
| --- | --- |
| Build Command | bash build.sh |
| Pre-Deploy Command | python manage.py migrate --noinput |
| Start Command | gunicorn core.wsgi:application --bind 0.0.0.0:$PORT |
| Environment | Variables de .env.example con valores reales |
| ALLOWED_HOSTS | Nombre-del-servicio.onrender.com y dominio propio, separados por coma |
| TRUST_PROXY_HTTPS | True para el proxy HTTPS de Render |
| DATABASE_URL | Conexion de PostgreSQL del servicio existente |

En el servicio gratuito actual, sin Pre-Deploy Command, se configuro el inicio:
`python manage.py migrate --noinput && gunicorn core.wsgi:application --bind 0.0.0.0:$PORT`.
Esto aplica migraciones antes de atender trafico y no inicia Gunicorn si fallan.
Antes de publicar migraciones nuevas, respaldar y revisar compatibilidad con la
version anterior; usar una ventana de mantenimiento para reparaciones grandes.
En multiples instancias, usar un paso unico de migracion antes del despliegue.
No crear otro servicio ni otra base para reemplazar los existentes sin transferir datos.
Configurar primero los secretos y respaldos, y luego desplegar el commit actualizado
desde la rama conectada. Un push puede activar autodeploy: no publicarlo antes
de completar la configuracion requerida.

Subir el commit a GitHub puede activar el despliegue automatico de Render. La
verificacion local no confirma el estado del despliegue ni modifica la base publicada.
Referencia: [Django en Render](https://render.com/docs/deploy-django) y
[comandos de despliegue](https://render.com/docs/deploys).
Correo: [Anymail y Resend](https://anymail.dev/en/stable/esps/resend/),
[restricciones de Render Free](https://render.com/docs/free),
[dominio de pruebas de Resend](https://resend.com/docs/knowledge-base/403-error-resend-dev-domain).
