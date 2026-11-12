# VetCare: ejecución local en Windows

## Adopciones y evaluación de adoptantes

Desde **Adopciones** registra una mascota de un cliente activo y selecciona al
encargado. Registra al posible adoptante como otro cliente, completa su evaluación
y revisa el resultado antes de confirmar la transferencia. El propietario anterior,
el encargado, la evaluación, las fechas y el usuario que confirma quedan registrados.
Las citas conservan su cliente original; el historial clínico sigue a la mascota.

La evaluación calcula un puntaje de 0 a 100 en el servidor. **Solo aprueba si es
mayor de 70; 70 exactos no aprueba.** No se admite un porcentaje enviado por el
navegador ni una evaluación de otra publicación, otro cliente o una versión anterior
a la evaluación más reciente de ese cliente para esa publicación.

| Criterio | Puntos máximos |
| --- | ---: |
| Tiempo diario disponible | 25 |
| Presupuesto sostenible (ingresos menos gastos) | 25 |
| Vivienda apta | 10 |
| Permiso para tener la mascota | 10 |
| Acceso veterinario | 10 |
| Experiencia | 5 |
| Apoyo durante ausencias | 5 |
| Compromiso de cuidado permanente | 10 |

Tiempo: 3 horas o más obtiene 25; desde 2 horas, 20; desde 1 hora, 10; un tiempo
positivo inferior a 1 hora, 5; cero horas, 0. Presupuesto: el saldo mensual debe
cubrir un presupuesto positivo para la mascota; si cubre al menos el doble obtiene
25, si solo lo cubre obtiene 20 y, si no lo cubre, obtiene 0. Las respuestas
afirmativas suman los puntos de los demás criterios. Los importes del formulario
se expresan en pesos colombianos al mes.

Estas son reglas operativas iniciales, versionadas como `vetcare-v1`, no una
garantía de idoneidad ni un estándar veterinario. La suma es aditiva: puede aprobar
con 75 puntos aunque el componente económico obtenga 0. El encargado debe revisar
las respuestas, el desglose y las necesidades concretas de la mascota antes de
confirmar. Una evaluación aprobada no transfiere la mascota automáticamente.

Se puede cancelar una publicación disponible o registrar una nueva posteriormente.
El historial de adopciones y evaluaciones está protegido contra borrado accidental.

## Comprobaciones reproducibles

```powershell
.\.venv\Scripts\python.exe manage.py test
powershell -ExecutionPolicy Bypass -File scripts\check_project.ps1
powershell -ExecutionPolicy Bypass -File scripts\start_local.ps1
```

`manage.py test` usa por defecto SQLite en memoria y no carga `.env` ni crea una
base de pruebas en Railway. El arranque local habilita `DEBUG=True` solo en su
proceso y comprueba que las migraciones estén aplicadas. Es un servidor de
desarrollo local; la configuración de HTTPS y publicación debe revisarse antes
de exponer el proyecto a Internet.

Proyecto Django 5.2 con MySQL. Ejecuta los comandos de PowerShell desde la carpeta
que contiene `manage.py`. La base sigue alojada en Railway: las operaciones de la
aplicación local utilizarán los datos del servicio al que configures la conexión.

## 1. Python y dependencias

El entorno revisado tiene Python 3.14.10, Django 5.2.19, mysqlclient 2.3.0 y
python-dotenv 1.2.4. Django admite Python 3.14 desde 5.2.8
([notas oficiales](https://docs.djangoproject.com/en/5.2/releases/5.2.8/)).
`requirements.txt` mantiene Django en la rama 5.2 y permite sus actualizaciones.

Si ya existe `.venv`, úsalo directamente; no es necesario activar el entorno:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Solo si todavía no existe el entorno:

```powershell
py -3.14 -m venv .venv
```

## 2. Completar el `.env` de la raíz

Se carga únicamente el `.env` junto a `manage.py`. `.venv/.env` no se utiliza.
Si no tienes `.env`, créalo con:

```powershell
Copy-Item .env.example .env
```

No sobrescribas un `.env` existente: conserva sus credenciales y completa sus
campos vacíos. Para generar una `SECRET_KEY` cuando falte:

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

En Railway, abre el servicio **MySQL → Settings → Networking** y busca su
**TCP Proxy / Public Access**. Copia el dominio y el puerto **externos**. El puerto
interno de MySQL suele ser 3306; el del proxy es el asignado por Railway.
Consulta [MySQL en Railway](https://docs.railway.com/databases/mysql) y
[TCP Proxy](https://docs.railway.com/networking/tcp-proxy).

| Variable | Contenido |
| --- | --- |
| `SECRET_KEY` | Clave de Django, entre comillas simples |
| `DEBUG` | `True` para desarrollo local |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` |
| `DB_NAME` | Nombre real de la base, normalmente `railway` |
| `DB_USER` | Usuario real de MySQL |
| `DB_PASSWORD` | Contraseña real, conservando todos sus caracteres |
| `DB_HOST` | Solo el dominio público o la IP, sin puerto |
| `DB_PORT` | Puerto externo del TCP Proxy |

Esta configuración usa variables separadas; no lee `DATABASE_URL`, `MYSQL_URL`
ni `MYSQL_PUBLIC_URL`. Si el panel muestra una URL, usa sus campos de conexión
resueltos por separado. Una contraseña codificada dentro de una URL puede diferir
de su valor literal: copia preferentemente el valor real de `MYSQLPASSWORD`.

No pegues `mysql://usuario:contraseña@host:puerto/base` en `DB_HOST` ni expresiones
`${{MYSQLUSER}}`, `${{MYSQLPASSWORD}}` o `${{RAILWAY_TCP_PROXY_DOMAIN}}`.
Esas referencias se resuelven dentro de Railway, no en este archivo local.
`mysql.railway.internal` solo funciona dentro de la red privada de Railway.

Usa comillas simples para conservar espacios y `#` en secretos, por ejemplo:
`DB_PASSWORD='valor-real'`. Si el valor contiene una comilla simple, escápala como
`\'`; una barra invertida literal se escribe `\\`. La interpolación `${...}` está
desactivada para conservar contraseñas literalmente.

Las variables ya definidas en el proceso tienen prioridad sobre `.env`, conforme
al comportamiento de [python-dotenv](https://bbc2.github.io/python-dotenv/).
Para detectar nombres definidos en PowerShell sin mostrar sus valores:

```powershell
Get-ChildItem Env:DB_* | Select-Object -ExpandProperty Name
```

Si una variable antigua está ocultando el valor de `.env`, elimínala de esa sesión
con `Remove-Item Env:DB_HOST` (o el nombre correspondiente) y vuelve a ejecutar.
Reinicia también el servidor tras cambiar `.env`.

Si los estilos devuelven 404, comprueba también `Get-Item Env:DEBUG`:
un valor heredado como `release` tiene prioridad sobre el archivo y desactiva
el modo de desarrollo. Para ejecutar localmente con archivos estáticos, establece
`$env:DEBUG = 'True'` en la terminal desde la que vas a iniciar el servidor.

## 3. Diagnosticar y arrancar

```powershell
.\.venv\Scripts\python.exe scripts\diagnose_database.py
.\.venv\Scripts\python.exe manage.py check --database default
.\.venv\Scripts\python.exe manage.py showmigrations
.\.venv\Scripts\python.exe manage.py migrate --plan
```

El diagnóstico valida la configuración, ejecuta `SELECT 1`, comprueba los nombres
de las tablas esperadas y revisa el historial de migraciones. No muestra
contraseñas, no escribe datos y no crea una base de pruebas. Un resultado correcto
no sustituye una comparación completa de columnas ni pruebas de todos los módulos.

Si la base está vacía o el plan muestra cambios esperados para la base elegida,
aplica las migraciones y luego inicia el servidor:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
$env:DEBUG = 'True'
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Si ya están aplicadas las migraciones, ejecuta solamente `runserver`.
Abre <http://127.0.0.1:8000/>. La autenticación usa usuarios de Django (`auth_user`),
no registros de las tablas `empleado` o `administrador`. Si necesitas crear un
usuario administrador en la base elegida:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

El dashboard está en `/inicio/` y el administrador Django en `/admin/`.
Los CSS y JavaScript locales se sirven con `runserver` y `DEBUG=True`.
Para cerrar la sesión, pulsa **Cerrar sesión** en la esquina superior derecha
del dashboard. El botón termina la sesión y vuelve al login.

En `/admin/empleado/empleado/` puedes gestionar el personal, su cargo y su teléfono
opcional. En `/admin/empl_veterinario/veterinario/` puedes asociar empleados con
sus especialidades. El selector de la agenda muestra nombre, apellido y
especialidad de cada veterinario.

## 4. Errores frecuentes

| Error | Revisión |
| --- | --- |
| Faltan `DB_HOST` / `DB_PORT` | Completar dominio y puerto públicos en `.env` |
| Referencias sin resolver | Sustituir `${{...}}` por sus valores reales |
| 2005: Unknown server host | Revisar dominio y resolución DNS |
| 2002 / 2003: no conecta | Revisar TCP Proxy, puerto externo, servicio, red y firewall |
| 1045: Access denied | Revisar usuario y contraseña literales |
| 1049: Unknown database | Revisar `DB_NAME` |
| Tablas o migraciones pendientes | Revisar `migrate --plan` antes de modificar la base |
| Falta `historial_de_vacunas` tras crear la base | Aplicar la migración `historial_de_vacunas.0002`, que corrige las mayúsculas del nombre original |
| CSS o JavaScript local devuelve 404 | Iniciar el servidor con `DEBUG=True`; revisar si el entorno del proceso reemplaza `.env` |
| 403: CSRF token from POST incorrect | Si el login ya fue aceptado, abrir `/inicio/` directamente; de lo contrario, volver a `/` para cargar un formulario nuevo |

Django renueva el token CSRF al iniciar sesión. El formulario de acceso bloquea
envíos duplicados, se sirve sin caché y redirige al dashboard cuando la sesión
ya está iniciada. La validación CSRF permanece activa.

El error original `Unknown server host '}:}@}:}/}'` se reprodujo: `DB_HOST`
contenía una plantilla completa con referencias de Railway, y la expansión de
python-dotenv consumía parcialmente esas referencias. Ahora se conserva el texto
y se rechaza con un error de configuración antes de intentar conectar.

## 5. Copia de datos y credenciales

`backup.sql` procede de MariaDB 10.11 y contiene 19 instrucciones `DROP TABLE`.
No lo importes sobre la base existente para resolver este error de conexión.
Para recuperar sus datos, prepara primero una base separada y revisa la
compatibilidad con el servidor destino. No se ha ejecutado ninguna restauración.

`.gitignore` excluye `.env`, `.venv`, cachés y copias SQL. El archivo encontrado
contenía credenciales en vez de reglas; se sustituyó por reglas reales. Si esas
credenciales se compartieron o subieron a un repositorio, rota la contraseña en
Railway y actualiza `.env`: borrarlas del archivo no las elimina de un historial
publicado. Esta carpeta no tiene un repositorio Git inicializado.

## 6. Pruebas de configuración sin base de datos

```powershell
.\.venv\Scripts\python.exe -m unittest veterinaria.test_config -v
.\.venv\Scripts\python.exe manage.py test login
```

Cubren el fallo original, hosts inválidos, puerto externo obligatorio, rechazo de
hosts privados fuera de Railway, mensajes sin credenciales, conservación de
contraseñas y carga exclusiva del `.env` de la raíz con prioridad del proceso.
