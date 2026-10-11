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
- Correo: configurar SMTP real y DEFAULT_FROM_EMAIL. PASSWORD_RESET_URL debe llevar
  a la pantalla/enlace de la app que procesa uid y token. Probar entrega real.
- Stripe: claves del mismo entorno y endpoint HTTPS /api/pro/webhook/ con los cuatro
  eventos documentados. Copiar su secreto de firma a STRIPE_WEBHOOK_SECRET.
  Primero validar el flujo completo con Stripe en modo prueba y la app.
- Media: MEDIA_ROOT debe estar en almacenamiento persistente y publicarse por el
  servidor/CDN. WhiteNoise sirve estaticos, no las fotos de usuarios. Si hay archivos
  antiguos en escudos/ o perfiles/, conservarlos y trasladarlos al volumen configurado
  manteniendo las rutas guardadas en la base.
- Limites: usar cache compartido/proxy para limitar solicitudes entre replicas.

## Verificacion posterior

Confirmar que /crear-admin/ devuelve 404; login/perfil funcionan por HTTPS;
un pronostico anterior al inicio se guarda y uno posterior se rechaza;
finalizar/corregir un partido actualiza la tabla; el correo llega sin aparecer en
logs; y Stripe activa PRO solo tras webhook firmado, incluso con reenvios.

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

Si el plan no ofrece Pre-Deploy Command, ejecutar las migraciones desde una
sesion administrativa del servicio antes de activar la version; programar una
ventana de mantenimiento para la reparacion historica.
No crear otro servicio ni otra base para reemplazar los existentes sin transferir datos.
Configurar primero los secretos y respaldos, y luego desplegar el commit actualizado
desde la rama conectada. Un push puede activar autodeploy: no publicarlo antes
de completar la configuracion requerida.

Subir el commit a GitHub puede activar el despliegue automatico de Render. La
verificacion local no confirma el estado del despliegue ni modifica la base publicada.
Referencia: [Django en Render](https://render.com/docs/deploy-django) y
[comandos de despliegue](https://render.com/docs/deploys).
