# Web STREAK

La web se sirve desde `/` en el mismo servicio Django/Render. No necesita otro
hosting, dominio, base de datos, compilador frontend ni servicio de pago.
Usa las cuentas, equipos, torneos y reglas del backend existente.

## Usuarios

- Registro, inicio/cierre de sesión, recuperación por correo y cambio de contraseña.
- Una contraseña temporal obliga a cambiarla antes de jugar.
- Torneos, equipos, filtros por país, fases, calendario y resultados.
- Creación de quinielas, invitación con código y confirmación del ingreso tardío.
- Pronósticos con cierre cinco minutos antes del partido, clasificación y detalles
  de rivales con la visibilidad que permite el servidor.
- Perfil, foto, fecha de nacimiento, historial de quinielas y eliminación de cuenta
  mediante la página de confirmación existente.
- Plan actual, límites y pagos registrados. La compra PRO continúa en la app móvil;
  esta versión web no integra un formulario de cobro ni cambia el modo de Stripe.

## Administración

Después de entrar con una cuenta activa `is_staff`, aparece Administración. Los
módulos visibles se obtienen de los permisos del `ModelAdmin` existente. Sus enlaces
abren los formularios Django, con la misma sesión y una navegación de regreso a la web.
Ser jugador o PRO no concede acceso administrativo. No se crean administradores
ni se asignan permisos al registrar cuentas desde la web.

## Sesiones y compatibilidad

- `/web/sesion/`: identidad del navegador, indicador de personal y token CSRF.
- `/web/entrar/`: valida las mismas credenciales y caducidad temporal que el login
  móvil; crea una sesión Django con cookie HttpOnly. Requiere CSRF incluso anónimo.
- `/web/salir/`: cierra la sesión; requiere POST y CSRF.
- `/web/administracion/`: módulos autorizados; requiere personal activo y contraseña
  no temporal.
- La API conserva JWT como primera autenticación y añade `SessionAuthentication`.
  Las operaciones con sesión requieren CSRF; el móvil con Bearer sigue funcionando.
- No se guardan tokens ni contraseñas en localStorage/sessionStorage. Django invalida
  la sesión al cambiar la contraseña y renueva su identificador al entrar.
- La página usa CSP de mismo origen y recursos locales, sin analítica externa.

No hay migraciones nuevas. El comando existente de Render (`bash build.sh`) recoge
los estáticos. Con el nuevo commit desplegado, la raíz del dominio abre STREAK;
`/api/`, `/admin/` y las páginas de cuenta conservan sus rutas.

## Verificación

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=core.settings_test --noinput
node --check quinielas/static/quinielas/portal.js
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=core.settings_test
```

Las pruebas de portal cubren CSRF anónimo/autenticado, cierre de sesión, invalidación
por cambio de clave, credenciales temporales, permisos de administración, pronósticos
con sesión y compatibilidad JWT. Las pruebas de concurrencia necesitan PostgreSQL.

Render Free puede suspender el proceso por inactividad y tardar en responder al
primer acceso. La web comparte los límites del servicio existente. No cambiar el
plan ni contratar un dominio para publicar esta implementación.

## Ampliación PRO y filtros

La web incorpora `#estadisticas` (Mi rendimiento), exportaciones CSV y calendario
de cierres para cuentas PRO. Torneos permite filtrar por clubes/selecciones, temporada y formato;
el calendario de cada torneo y quiniela añade filtros por grupo y equipo.
El contrato compartido con la app y sus límites está en [PRO_Y_FILTROS.md](PRO_Y_FILTROS.md).
