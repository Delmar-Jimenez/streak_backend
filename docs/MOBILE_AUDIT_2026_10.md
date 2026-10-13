# Entrega de correcciones para Flutter

## Integracion necesaria en la app

- Ajustes: mostrar Eliminacion de cuenta, pedir contrasena y confirmacion y usar
  DELETE /api/usuarios/me/. Registrar la URL web /eliminar-cuenta/ en Google Play.
- Leer /usuarios/me/ aun cuando pass_temporal_flag=true. Ante PASSWORD_TEMPORAL,
  abrir cambio de contrasena; no tratarlo como una sesion caducada.
- Antes de unirse: POST /quinielas/validar-codigo/. Mostrar advertencia y obtener
  aceptacion cuando requiere_confirmacion=true. Despues POST /quinielas/unirse/.
- Usar cierre_pronosticos (inicio menos cinco minutos), sin cambiar la visibilidad
  de los rivales: sus pronosticos permanecen ocultos hasta el inicio.
- Mostrar OCULTO y NO_REGISTRADO como estados distintos.
- Crear quinielas con 2..50 participantes, o 2..100 si el creador tiene PRO.
- Usar fotos/es_pro de participantes, resumen de historial y equipos anidados.
- Leer importe/moneda de /pro/estado/. Recuperar compras pendientes mediante
  /pro/pago-pendiente/; ofrecer cancelacion con /pro/pagos/{id}/cancelar/.
- Eliminar referencias locales a usuario/token despues de eliminar la cuenta.

El contrato completo y ejemplos de entradas estan en API.md. Se conservaron los
IDs y campos anteriores; los cambios intencionales son el plazo de pronosticos,
los limites, la confirmacion de ingreso tardio y el permiso para consultar perfil.

## Decisiones pendientes

- No existe formula aprobada de penalizacion por ingreso tardio. Se informa null;
  no hay descuentos inventados. Se requiere definirla antes de certificar esa RN.
- Resend sin dominio propio solo envia desde onboarding@resend.dev al correo de
  la cuenta Resend. Un mensaje Hello World entregado no comprueba recuperacion.
- La integracion de pagos sigue en modo prueba y conserva compra unica PRO.
- Negocio debe definir plazos de retencion financiera/respaldos y su aviso de
  privacidad. El borrado conserva referencias financieras sin vinculo al usuario;
  no borra automaticamente datos almacenados por Stripe ni ejecuta reembolsos.
- Las reglas RN-01 a RN-74 completas no fueron suministradas; no se certifica su
  cumplimiento integral ni la aprobacion de Google Play.

## Datos de demostracion

La carga es explicita y solo para superusuarios, nunca una ruta publica. Se marca
todo como DEMO y no se reemplazan datos anteriores. Incluye torneos activos y
finalizado, equipos con escudos persistentes, fases, encuentros futuros y terminados,
pronosticos y tablas con puntos. Cuatro usuarios sin claves predeterminadas; el
titular configura las claves en el administrador. demo_streak_ana tiene PRO.

La fecha de los partidos se establece al crear la DEMO por primera vez. Repetir la
carga no mueve partidos, sobrescribe resultados ni cambia contrasenas.
