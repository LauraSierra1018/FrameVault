# FrameVault · Prototipo funcional

**Job principal:** Proteger el material audiovisual durante su paso de grabación a postproducción.

FrameVault reduce la incertidumbre con un flujo visible: tarjeta → inventario → dos copias → SHA-256 → pasaporte → reporte. El original se lee y se conserva. Todo el programa funciona localmente y sin conexión.

## Inicio rápido en Windows

1. Abre `Iniciar FrameVault.cmd` con doble clic.
2. Pulsa **Preparar demostración**. Se generan 8 archivos pequeños reales: 4 audios WAV reproducibles, 3 imágenes PPM y una nota. No son videos con extensión falsa.
3. Pulsa **Crear inventario** y revisa la lista.
4. Pulsa **Proteger material**. Al finalizar, el semáforo debe indicar **Protegido** y 8/8 archivos.
5. Selecciona un archivo y abre su pasaporte, o haz doble clic sobre él.
6. Abre el reporte final. Es un HTML local que puedes imprimir como PDF desde el navegador.
7. Pulsa **Volver a verificar** cuando quieras comprobar de nuevo el origen y las copias.

Para usar clips reales: elige una tarjeta/carpeta de origen y dos carpetas de destino existentes. Se incluyen todos los archivos, también notas y archivos auxiliares; no se descartan formatos desconocidos. La selección del origen es manual y su inventario es automático y recursivo. La detección al conectar una tarjeta queda para una versión futura.

**Dependencias:** Python 3.10 o posterior con Tkinter/Tcl-Tk. Probado aquí con Python 3.12.12 y Tk 8.6.17. No necesitas instalar paquetes con pip, una cuenta, claves ni un servidor. Si llevas la carpeta a otro computador, instala Python con Tcl/Tk y agrégalo al PATH. El lanzador prueba primero `python` y luego `py -3`.

Desde una terminal situada en esta carpeta:

```text
python app.py
python -m unittest discover -p test_core.py -v
python test_ui.py
```

## Qué significa el semáforo

- **En riesgo:** no hay comprobación completa, hubo cancelación, falta un archivo o hay una inconsistencia.
- **Copiando:** se están escribiendo archivos temporales en los destinos.
- **Verificando:** se están leyendo bytes y comparando SHA-256.
- **Protegido:** en la última revisión, origen y ambas copias coincidían con la huella guardada y no había nuevos archivos fuera del inventario.

El porcentaje representa archivos comprobados, no porcentaje de bytes transferidos. Una sesión abierta del historial muestra explícitamente que su resultado es anterior hasta volver a verificar. Dos carpetas del mismo disco sirven para demostrar el flujo, pero no protegen contra la falla de ese disco. La aplicación no certifica independencia física de los dispositivos. No borres tu tarjeta basándote únicamente en esta demostración.

## Arquitectura y cómo se construyó

Se eligió Python y Tkinter para tener una ventana de escritorio sin dependencias externas. El motor y la interfaz están separados para probar las operaciones con archivos reales sin depender de clics.

| Archivo/carpeta | Responsabilidad |
|---|---|
| `app.py` | Ventana en español, selección de carpetas, tabla, semáforo, pasaporte e historial |
| `core.py` | Inventario, validaciones, SHA-256, copia, auditoría, persistencia y reporte |
| `demo.py` | Generación de un conjunto nuevo de medios sintéticos por demostración |
| `test_core.py` | Pruebas automatizadas con carpetas temporales y errores simulados |
| `test_ui.py` | Prueba del flujo desde la interfaz, incluido cambio a rojo por archivo faltante |
| `Iniciar FrameVault.cmd` | Lanzador de Windows |
| `historial/` | Un manifiesto JSON y un reporte HTML por sesión |
| `demostraciones/` | Tarjeta y dos destinos de cada demo |

Los destinos reciben `FrameVault-fecha-identificador/`, conservando la estructura relativa del origen. Así, dos tomas con igual nombre en subcarpetas diferentes no colisionan. El identificador evita mezclar sesiones. Los metadatos son ruta, extensión, tamaño y fecha de modificación del sistema de archivos; no se extraen aún codec, cámara, timecode o GPS.

La interfaz utiliza un hilo de trabajo y una cola: las copias y los hashes no bloquean la ventana. Solo el hilo principal actualiza los controles. Durante una operación se deshabilitan los botones que cambiarían la sesión. Cancelar se comprueba entre bloques de 1 MiB y conserva los archivos ya terminados.

Antes de copiar se crea y guarda el inventario, se rechazan carpetas iguales o anidadas, se comprueba espacio disponible y se rechazan enlaces simbólicos/junctions del árbol de origen. Cada archivo obtiene un SHA-256; se copia a un temporal exclusivo, se vacía el búfer y se compara el hash del temporal. Solo entonces se renombra y se aplica solo lectura. Se repite para el segundo destino y se revisa otra vez el origen. La auditoría final vuelve a leer las tres ubicaciones.

El manifiesto JSON se actualiza mediante archivo temporal y reemplazo para reducir la posibilidad de guardar JSON incompleto. El pasaporte registra eventos con fecha UTC, usuario local, hash y rutas. El reporte HTML incluye estado, inconsistencias y pasaportes. No hay una base de datos ni tráfico de red.

## Decisiones de seguridad y alcance

- No hay botón de borrar originales ni sobrescritura de respaldos previos.
- Un fallo de una copia nunca basta para declarar la sesión protegida. Se conserva lo completado y se reporta el fallo.
- Los archivos faltantes se detectan contra el inventario. Los nuevos archivos en origen también impiden marcar la sesión completa.
- Un hash distinto detecta alteración de bytes; no demuestra que un video pueda decodificarse ni que el original estuviera sano antes de ingresar.
- Solo lectura es una protección accidental reversible, no WORM, bloqueo contra borrado ni defensa frente a usuarios maliciosos.
- El historial es local y editable, no una cadena de custodia forense firmada.
- Las comprobaciones de rutas reducen errores ordinarios; este MVP no está endurecido frente a cambios maliciosos de rutas concurrentes. Usa carpetas controladas y manifiestos propios.
- Si el proceso se termina abruptamente puede quedar un temporal `.partial`. No se considera una copia verificada. Abre la sesión y verifica; crea un inventario nuevo para repetir la transferencia. No hay reanudación ni reparación automática.
- El historial se conserva junto a la aplicación; perder esa carpeta implica perder la evidencia local. Los respaldos de los medios permanecen en los destinos.

## Relación con el proyecto y la clase

La misión es reducir al máximo pérdida, corrupción y desorganización. La emoción buscada es certeza y control: textos comprensibles, estado visible, evidencia por archivo y una tarea que otra persona puede completar sin entender hashes.

El contexto recuperado menciona estos objetivos del radar: plataforma 10, experiencia 9, soluciones 8, cliente 7, proceso 6, comunicación 5, ecosistema 4, gestión 2 y captura de valor 1. Son prioridades del proyecto, no puntuaciones ya alcanzadas por este prototipo. No se inventan los tres ejes restantes: sus nombres y valores no aparecen completos en el contexto disponible.

| Dimensión | Reflejo en el MVP |
|---|---|
| Plataforma | Un solo flujo de inventario, copia, verificación, historial y reporte |
| Experiencia | Semáforo con texto, acciones numeradas y demo guiada |
| Soluciones | Dos copias, detección de cambios y conservación de subcarpetas |
| Cliente | Guion de prueba con otra persona y preguntas de comprensión |
| Proceso | Inventario antes de copiar; protección después de verificar |
| Comunicación | Estado visible y reporte que explica la evidencia |
| Ecosistema | Archivos ordinarios legibles por herramientas de postproducción; integraciones futuras |
| Gestión | Separación entre motor, interfaz, pruebas y documentación |
| Captura de valor | Sin monetización inicial; validar utilidad y confianza primero |

SCAMPER: se adapta el concepto de pasaporte/caja negra y se reordena el proceso para inventariar antes de transferir. La implementación cubre el alcance solicitado y el contexto textual recuperable; no atribuye contenidos no revisados a los adjuntos de clase.

### Tres ODS presentes

- **ODS 8 — Trabajo decente y crecimiento económico:** menos repetición manual de copias y comprobaciones. Medir tiempo por sesión y errores evitados en pruebas; aún no hay evidencia de impacto real.
- **ODS 9 — Industria, innovación e infraestructura:** un flujo local accesible y verificable para producción audiovisual, con dos respaldos y trazabilidad. Medir proporción de sesiones verificadas y recuperación ante incidencias.
- **ODS 12 — Producción y consumo responsables:** conservar activos para evitar repetir trabajo perdido; organizar sin generar nuevas copias durante la reauditoría. La doble copia consume almacenamiento y la verificación consume energía: no se afirma una reducción ambiental medida.

## Referencias de patentes

Inspiración conceptual a partir de las publicaciones discutidas; el prototipo no implementa todas sus reivindicaciones ni constituye un análisis de libertad de operación. Fuentes consultadas el 23 de septiembre de 2026.

| Publicación | Idea y adaptación concreta |
|---|---|
| [US20190230396A1](https://patents.google.com/patent/US20190230396A1/en) | Ingesta de medios y metadatos: inventario automático tras seleccionar origen. La publicación trata distribución a plataformas; aquí se adapta la idea general. |
| [US7818537B2](https://patents.google.com/patent/US7818537B2/en) | Validación de transferencia mediante hashes: SHA-256 y comparación de archivos. |
| [US20240111906A1](https://patents.google.com/patent/US20240111906A1/en) | Integridad de extremo a extremo: comparación origen/destinos y fallo explícito. Reintento automático pendiente. |
| [US11455380B2](https://patents.google.com/patent/US11455380B2/en) | Trazabilidad de contenido digital: historial por archivo; sin equivalencia forense. |
| [US20140181999A1](https://patents.google.com/patent/US20140181999A1/en) | Objetos condicionalmente inmutables: motivación para proteger copias verificadas. El atributo de solo lectura del MVP tiene un alcance mucho menor. |
| [US12260347B2](https://patents.google.com/patent/US12260347B2/) | Predicción de fallas de almacenamiento: evolución futura, no función presente. |

## Prueba con una persona (10–15 minutos)

1. Sin explicarle los botones, pídele preparar una demostración y protegerla.
2. Pregunta: ¿qué significa el verde?, ¿dónde quedaron los archivos?, ¿cómo sabe que se verificaron?
3. Pídele abrir el pasaporte y el reporte.
4. En una copia de DEMOSTRACIÓN, elimina un archivo desde el explorador (Windows puede pedir quitar solo lectura). Pulsa Volver a verificar: debe quedar En riesgo.
5. Prepara otra demo y altera el contenido de una copia, quitando antes solo lectura. Revisa de nuevo: debe registrar SHA-256 inconsistente.
6. Cierra y vuelve a abrir la aplicación; abre el JSON desde Abrir historial y revisa de nuevo.
7. Anota tiempo, pasos donde pidió ayuda, errores y confianza antes/después de 1 a 5. Pregunta si entendió la diferencia entre dos carpetas y dos discos.

No se ha realizado todavía una prueba con un participante externo.

## Evolución futura

Empaquetado en ejecutable firmado; reanudar/reintentar transferencias; progreso por bytes y velocidad; detección de tarjetas; identificación fiable de discos físicos; validación audiovisual y metadatos con ffprobe; búsqueda de duplicados; reglas por proyecto/jornada/cámara; historial firmado y respaldo de manifiestos; políticas de retención inmutables; monitorización SMART y predicción de fallas; integraciones de postproducción. El MVP no incluye nube, pagos ni monitorización continua.
