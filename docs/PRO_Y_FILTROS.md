# PRO y filtros de competición

La cuenta gratuita conserva sus funciones y el límite de 50 participantes. PRO
conserva 100 participantes, el precio configurado y el pago único, y añade:

- Estadísticas personales: porcentaje de aciertos, marcadores exactos, desglose
  de puntuación y resultados por torneo. Solo cuentan pronósticos propios en
  partidos finalizados con resultado. Cada pronóstico por quiniela cuenta una vez.
- Exportación CSV de los pronósticos propios.
- Exportación CSV de la clasificación de una quiniela en la que se participa.
- Calendario ICS de cierres futuros, con aviso 30 minutos antes del cierre.
  Es una descarga puntual. El calendario del teléfono debe permitir alertas;
  cuando cambien horarios hay que sustituir la importación anterior.
- Distintivo PRO ya existente.

Todos los beneficios se comprueban en el servidor con `es_pro`; no otorgan acceso
a pronósticos rivales antes del inicio, a otras quinielas ni a administración.
El plan no cambia la puntuación ni da ventaja en los resultados.

## Integración móvil (JWT) y web (sesión)

Los siguientes endpoints aceptan los mismos JWT que usa la app. La web utiliza
la sesión existente. Las respuestas privadas llevan `Cache-Control: private, no-store`.

| Método y ruta | Respuesta |
| --- | --- |
| GET `/api/pro/estado/` | Conserva `es_pro` y `plan`; añade `capacidades` y `plan.beneficios` con códigos estables y valores gratis/PRO. |
| GET `/api/pro/estadisticas/` | `resumen`, `torneos`, `unidad`, `nota`. |
| GET `/api/pro/pronosticos/exportar/` | Archivo CSV UTF-8 con BOM, solo pronósticos propios. |
| GET `/api/quinielas/{id}/tabla/exportar/` | Archivo CSV con posición, usuario y puntos; conserva empates. |
| GET `/api/pro/calendario/` | Archivo ICS; deduplica partidos compartidos entre quinielas. |

Estadísticas, pronósticos CSV y calendario admiten `?torneo={id}`. El usuario debe
participar en ese torneo. El error `PRO_REQUERIDO` (403) permite mostrar la página
de planes. `PASSWORD_TEMPORAL` sigue requiriendo cambiar la contraseña.

Para Flutter: leer el catálogo al abrir los planes; mostrar las herramientas según
`capacidades`; descargar CSV/ICS con el encabezado Authorization Bearer y guardar
o compartir los bytes con el nombre indicado en Content-Disposition. No abrir
una URL pública con el token en parámetros. El calendario no solicita acceso al
calendario del dispositivo desde el backend ni envía correos automáticos.

## Filtros gratuitos, incluidos los torneos con grupos

`GET /api/torneos/` admite `buscar`, `temporada`, `formato`, `estado` y el filtro
`pais` existente. `tipo_participantes` acepta `CLUBES`, `SELECCIONES` o `SIN_CLASIFICAR`, independientemente del formato. `formato` acepta `LIGA` o `GRUPOS_ELIMINATORIA`. No se deduce
que un torneo sea un Mundial o que sea internacional solo por no tener país.

1. Elegir una competición de la lista real, por ejemplo una Copa del Mundo que
   el administrador haya creado y publicado.
2. Consultar `GET /api/torneos/{id}/filtros/`: devuelve fases, grupos, equipos y
   estados disponibles para ese torneo.
3. Usar `fase`, `estado`, `grupo` y `equipo` en
   `/api/torneos/{id}/partidos/` o `/api/quinielas/{id}/partidos/`.

`grupo=A` solo incluye partidos de fase GRUPOS cuyos dos equipos pertenecen a A
en ese torneo. No incluye eliminatorias ni equipos de otro torneo. Cada partido
incluye el campo adicional `grupo` (nulo cuando no corresponde).

En Django, seleccionar el tipo de participantes (clubes o selecciones), configurar el formato Grupos y Eliminatoria, las fases de tipo GRUPOS
o ELIMINATORIA e inscribir los equipos asignando su grupo en EquipoTorneo. No se
crean calendarios, selecciones ni resultados oficiales automáticamente.

La migración 0012 añade únicamente tipo_participantes a Torneo. Los torneos existentes conservan sus IDs, equipos y resultados y quedan SIN_CLASIFICAR para que el administrador indique su categoría real. Respaldar PostgreSQL antes de aplicar la migración. No modifica el precio ni el proveedor de
pagos. La compra PRO sigue por la app móvil; la web añade las herramientas.
El alcance móvil de esta entrega es el backend compartido: las capacidades y los filtros se consumen desde la app con JWT. Publicar el backend no añade automáticamente controles nuevos a una app ya instalada.

Formato de calendario: [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545).
