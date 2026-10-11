# Alcance de la correccion

Se verifico el checkout disponible (77eacca), posterior al commit 6586a6f citado
por el informe. Se recibio el resumen y posteriormente el catalogo A2 de endpoints.
Todas las rutas de ese catalogo quedan implementadas, incluido PUT de perfil,
historial, partidos de quiniela y detalle de puntuacion por partido y por usuario.
No se recibio el texto de las 74 reglas de negocio.

| Hallazgo recibido | Correccion implementada |
| --- | --- |
| Ruta publica que crea superusuario | Eliminada. Administradores mediante comando Django. |
| Contrasenas en logs | Recuperacion por token de uso unico enviado via SMTP. |
| Totales siempre cero | Recalculo transaccional, correcciones/reversiones y migracion historica. |
| Falta perfil | GET/PUT/PATCH usuarios/me/ con privilegios de solo lectura. |
| Faltan mis quinielas y tabla | Listado propio, detalle, participantes y posiciones privados. |
| Falta consulta rival | Consulta entre miembros, oculta antes del inicio. |
| API de catalogo incompleta | Detalle de torneos, equipos, fases y partidos. |
| Errores incompatibles RN-72 | Handler global DRF y handlers Django JSON 400/403/404/500. |
| Charge obsoleto y sin webhook | PaymentIntents, idempotencia y webhook firmado; historial propio. |
| DEBUG, hosts y clave fija | Variables de entorno y comprobaciones al arrancar produccion. |
| SQLite y CORS | PostgreSQL obligatorio en produccion y lista explicita de origenes CORS. |

Ademas: cierre por hora de inicio; marcadores no negativos; validacion de torneo;
inscripcion automatica del creador; limite de cupo con bloqueo de fila; bloqueo de
cuentas con password temporal; invalidacion de JWT tras cambio de password;
correo unico sin distinguir mayusculas; campos sensibles fuera de la API.

## Lo que no se puede certificar con el resumen

- Cumplimiento integral RN-01 a RN-74, cuyos textos completos no fueron proporcionados.
- Limites del plan gratuito/PRO, vigencia, renovacion, cancelacion de suscripciones
  y reglas exactas para devoluciones. Se conserva compra unica del codigo existente.
- Momento exacto de revelacion de rivales y desempates oficiales.
- Seguridad y disponibilidad del despliegue publicado, servicios SMTP/Stripe reales,
  distribucion de medios y transferencia de datos SQLite a PostgreSQL si aplica.

Las decisiones provisionales estan descritas en API.md. Estos cambios corrigen
los defectos comprobables del informe, pero no equivalen a una certificacion de
las reglas que no fueron proporcionadas.

## Verificacion local

Resultado: 45 pruebas descubiertas, 43 aprobadas y 2 de concurrencia omitidas
por requerir PostgreSQL. Django check y makemigrations --check no reportan errores
ni cambios pendientes. collectstatic genero correctamente los archivos estaticos.

La suite cubre contrato A2, permisos, privacidad de pronosticos, cierre por hora,
puntajes/reversiones, migracion desde 0001, recuperacion, invalidacion JWT,
CORS y webhooks firmados con reintentos/reembolsos. Usa SQLite en memoria y
simula las llamadas remotas de Stripe; no prueba cobros ni correo reales.
Las dos pruebas de concurrencia requieren PostgreSQL y se omiten en SQLite.
Se intento ejecutarlas con PostgreSQL temporal local, pero el entorno impidio
la conexion (permiso de red/timeout); no se presentan como verificadas.
check --deploy no encontro errores con variables de produccion de prueba; aviso
solo por HSTS de subdominios/preload, opciones que dependen del dominio real.
