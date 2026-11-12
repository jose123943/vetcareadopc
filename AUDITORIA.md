# Auditoría funcional y técnica de VetCare

Fecha: 12 de noviembre de 2026, zona America/Bogota.

## Alcance y evidencia

Se revisaron autenticación, clientes, mascotas, citas, vacunas, tratamientos,
facturación, personal y el nuevo flujo de adopción con evaluación del candidato.
Las pruebas automáticas usan SQLite aislada; las comprobaciones visuales usan un
servidor independiente en `127.0.0.1:8765` con datos ficticios. No utilizan la
sesión del usuario. Además se comprobó en MySQL el registro, evaluación a 100
puntos y transferencia dentro de una transacción exterior que se revirtió:
no quedaron registros de prueba en Railway.

La validación visual final está pendiente mientras termina la integración de la
interfaz. Este documento se actualizará con las capturas y resultados finales.

## Hallazgos identificados y correcciones

| Prioridad | Hallazgo inicial | Corrección / evidencia |
| --- | --- | --- |
| Alta | Las APIs de gestión no exigían sesión de forma uniforme. | Decorador compartido de API; pruebas de acceso anónimo y métodos HTTP. |
| Alta | Interpolaciones de datos de clientes en HTML podían interpretarse como marcado. | Revisión de renderizado y pruebas de cadenas de usuario en interfaz; comprobación final pendiente. |
| Alta | La eliminación de una mascota podía eliminar citas, tratamientos, facturas y al cliente. | Protección de historiales y separación de la gestión de clientes; pruebas de integridad. |
| Alta | El registro de cliente y mascota podía dejar datos parciales ante errores. | Transacciones y validación antes de confirmar el registro. |
| Alta | Facturación contenía referencias a `InvalidOperation`/`User` que podían fallar y aceptaba relaciones inconsistentes. | Formularios y comprobaciones de importe, estado, cliente y cita; cliente de la cita conservado para facturación histórica; se impide reactivar una factura de una cita cancelada. |
| Alta | Django instalado era 5.2.8, con parches posteriores de seguridad pendientes. | Actualización a Django 5.2.19, manteniendo la rama 5.2; `pip check` sin incompatibilidades. |
| Media | El dashboard mezclaba número de clientes, citas y vacunas bajo indicadores distintos. | Indicadores calculados según su significado y enlaces a los módulos correspondientes. |
| Media | No existía publicación, evaluación ni transferencia de mascotas entre clientes. | App `adopcion`, historial de evaluaciones y transferencia atómica de propietario. |
| Media | El entorno heredado `DEBUG=release` podía desactivar los estáticos locales. | Arranque reproducible con `scripts/start_local.ps1`, variable limitada al proceso. |
| Media | Una ejecución genérica de pruebas podía utilizar la configuración de MySQL. | `manage.py test` selecciona por defecto `veterinaria.test_settings`, que no lee `.env` y fuerza SQLite en memoria; el script de comprobación usa ese módulo explícitamente. |
| Media | Había controles decorativos y etiquetas incoherentes en el login y dashboard. | Capturas iniciales conservadas; revisión y comprobación visual de la interfaz final en curso. |

La actualización de Django se basó en las
[versiones oficiales soportadas](https://www.djangoproject.com/download/) y las
[notas de Django 5.2.19](https://docs.djangoproject.com/en/5.2/releases/5.2.19/).
La versión 5.2.18 también corrigió problemas en formularios con claves primarias
editables, una estructura presente en modelos de este proyecto
([notas oficiales](https://docs.djangoproject.com/en/5.2/releases/5.2.18/)).

## Reglas de adopción

1. Se publica una mascota existente cuyo propietario es un cliente activo.
2. Debe asignarse un empleado con cargo `Encargado de adopciones`.
3. Una mascota solo puede tener una publicación disponible a la vez.
4. El candidato debe ser otro cliente activo.
5. El servidor calcula y guarda la evaluación y su desglose; no acepta un
   porcentaje calculado por el navegador.
6. La confirmación exige la evaluación más reciente de ese cliente para esa
   publicación y un resultado **estrictamente superior a 70**.
7. La confirmación cambia el propietario de la mascota y cierra la publicación
   dentro de una transacción. Conserva publicaciones, evaluaciones, vacunas,
   citas, tratamientos y facturas anteriores.
8. Cancelar una publicación conserva al propietario y permite publicar de nuevo.

### Evaluación v1: 100 puntos

| Criterio | Puntos | Regla |
| --- | ---: | --- |
| Tiempo diario de cuidado | 25 | ≥3 h: 25; ≥2 h: 20; ≥1 h: 10; >0 h: 5; 0 h: 0 |
| Presupuesto sostenible | 25 | Ingresos menos gastos cubren dos veces el presupuesto: 25; cubren el presupuesto: 20; presupuesto cero o no sostenible: 0 |
| Vivienda apta | 10 | Sí: 10; no: 0 |
| Permiso para tener mascotas | 10 | Sí: 10; no: 0 |
| Acceso a atención veterinaria | 10 | Sí: 10; no: 0 |
| Experiencia con mascotas | 5 | Sí: 5; no: 0 |
| Apoyo durante ausencias | 5 | Sí: 5; no: 0 |
| Compromiso permanente | 10 | Sí: 10; no: 0 |

Estas ponderaciones son una regla explícita de esta versión del proyecto, no una
escala veterinaria o socioeconómica validada. Es un modelo aditivo: **es posible
alcanzar 75 puntos y aprobar obteniendo cero en presupuesto**, si se obtiene el
máximo en los demás criterios. No hay vetos independientes del porcentaje.
70 puntos exactos no aprueban; 75 sí. Los importes se conservan como cadenas
decimales exactas en el historial de evaluación.

## Pruebas reproducibles

```powershell
.\scripts\check_project.ps1
```

Comando directo equivalente para la suite:

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=veterinaria.test_settings --verbosity 2
```

El módulo de pruebas reutiliza apps, middleware y plantillas reales, pero anula
la carga de `.env` durante la importación y sustituye la base por SQLite en
memoria. Resultado de la suite integrada: **72 pruebas aprobadas**. Las 29 pruebas
de adopción verifican, entre otros casos:

- 70 frente a 75 puntos; importes negativos/no finitos y elecciones inválidas.
- No aceptar puntuaciones enviadas por el cliente.
- Publicaciones duplicadas y estados incoherentes rechazados también por la DB.
- Evaluaciones de otro cliente, otra publicación o anteriores a una más reciente.
- Propietario cambiado o candidato inactivo después de evaluar.
- Rollback completo al simular un fallo después de modificar al propietario.
- Conservación del historial clínico y de facturas, y protección contra borrados.
- Sesión obligatoria, métodos correctos y protección CSRF activa.

Para una comprobación visual independiente:

```powershell
.\.venv\Scripts\python.exe scripts\qa_server.py
```

Ese servidor utiliza exclusivamente `.qa/e2e.sqlite3` y muestra credenciales
ficticias de QA. No debe usarse como servidor de la aplicación ni publicarse.
El arranque normal del proyecto es:

```powershell
.\scripts\start_local.ps1
```

## Capturas iniciales

1. [Login inicial](auditoria/capturas/00-login-inicial.png): acceso funcional;
   etiquetas en inglés, opciones decorativas y ancho superior al viewport.
2. [Dashboard inicial](auditoria/capturas/01-dashboard-inicial.png): acceso y
   cierre de sesión visibles; notificación fija y métricas por corregir.

Las dos capturas se guardaron y se inspeccionaron en esta auditoría. Corresponden
al entorno aislado de QA y no muestran datos de clientes reales.

## Límites de esta revisión

- La aplicación se prepara para ejecución local. No se ha validado una
  publicación productiva con HTTPS, servidor WSGI, backups y restauración.
- Las pruebas exhaustivas de transacciones y restricciones se ejecutan en SQLite,
  complementadas con una prueba de humo transaccional en MySQL; no son una prueba
  de carga ni una simulación de concurrencia real en el MySQL de Railway.
- El control de acceso es el de una aplicación interna con usuarios Django;
  los registros de empleados no son cuentas de acceso por sí mismos.
- Las comprobaciones visuales no constituyen una certificación completa de
  accesibilidad. La matriz final de recorridos se incorporará tras la integración.
