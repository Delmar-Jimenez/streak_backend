# STREAK Backend

API Django/DRF para torneos, quinielas, pronosticos y acceso PRO.
Las versiones instaladas en este repositorio son Django 6.1.1 y DRF 3.18.1.
El informe recibido menciona Django 5/Python 3.13; esta correccion conserva las
dependencias del proyecto y se verifica con el Python disponible, 3.14.6.

## Desarrollo

1. Crear un entorno virtual e instalar `pip install -r requirements.txt`.
2. Configurar las variables descritas en [.env.example](.env.example). Para desarrollo:
   `DEBUG=True`, una `SECRET_KEY` propia y `ALLOWED_HOSTS=localhost,127.0.0.1`.
   Sin `DATABASE_URL`, SQLite se permite solo en desarrollo.
3. Ejecutar `python manage.py migrate`.
4. Crear administradores con `python manage.py createsuperuser`.
5. Iniciar `python manage.py runserver`.

La API tiene prefijo `/api/` y acepta URLs con y sin barra final.
La autenticacion usa `Authorization: Bearer <access>`.

## Verificacion

```text
python -B manage.py test --settings=core.settings_test
python -B manage.py makemigrations --check --dry-run --settings=core.settings_test
python manage.py check --deploy
```

Las pruebas usan SQLite en memoria, correo en memoria y simulaciones del cliente
Stripe. La firma del webhook se valida con el SDK real. No se cobran tarjetas.
Para ejecutar tambien las pruebas de concurrencia, configurar `TEST_DATABASE_URL`
con una base PostgreSQL exclusiva de pruebas y permisos para crear la base temporal.
Nunca usar credenciales de produccion para las pruebas.

## Documentacion

- [Contrato de API para la app](docs/API.md).
- [Despliegue y correccion de la instancia publicada](docs/DEPLOYMENT.md).
- [Cobertura del informe y decisiones pendientes](docs/AUDIT_FIXES.md).

Los cambios locales no actualizan por si solos la instancia publicada.
