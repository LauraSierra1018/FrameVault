# FrameVault Web · React + Python

## Abrir

Doble clic en **Iniciar FrameVault Web.cmd**. Se abre http://127.0.0.1:8765 en el navegador. Conserva el proceso del servidor abierto mientras trabajas. Para detenerlo, presiona Ctrl+C en su consola cuando no haya una operación en curso.

La versión web convive con `app.py`, la interfaz anterior. Utiliza una sola interfaz para operar cada sesión. No requiere internet durante el uso: React, estilos e iconos se incluyen en `frontend/dist/`. Python 3.10+ es la única dependencia para ejecutar la versión compilada. Node y npm solo se necesitan para modificar/recompilar el frontend.

## Prueba rápida

1. Pulsa **Probar con una demo**. Se generan medios pequeños en una carpeta nueva.
2. Pulsa **Crear inventario**.
3. Pulsa **Proteger material** y espera hasta el estado protegido.
4. Abre el pasaporte usando el nombre del archivo o su flecha.
5. Pulsa **Reporte** para descargar un HTML imprimible.
6. En **Historial de sesiones**, abre una sesión y pulsa **Verificar de nuevo**.

Las tres tarjetas abren un explorador de carpetas locales. Se puede navegar por unidades o escribir una ruta y pulsar Ir. «Usar esta carpeta» confirma la selección. No hay carga de archivos al servidor remoto: las operaciones suceden en el mismo computador. Si cambias las carpetas, debes crear otro inventario.

Si abriste un historial de antes de mover FrameVault, sus rutas apuntan a la ubicación anterior. Crea una demo nueva o un inventario nuevo con las rutas actuales; no se reescribe silenciosamente la evidencia histórica.

## Estructura añadida

- `web_server.py`: servidor HTTP de Python, API local, operaciones en segundo plano, instantáneas de progreso, navegación de carpetas y reportes.
- `frontend/src/main.jsx`: componentes React, selección de carpetas, inventario, estados, búsqueda/filtros, pasaporte, historial y guía.
- `frontend/src/style.css`: diseño adaptable, barra lateral, tarjetas, tabla y diálogos accesibles por teclado.
- `frontend/dist/`: versión compilada y autocontenida que sirve Python.
- `frontend/package.json` y `package-lock.json`: dependencias y versiones resueltas.
- `test_web.py`: pruebas del flujo HTTP y restricciones de acceso.

`core.py` y `demo.py` continúan realizando las operaciones originales. La interfaz antigua y su documentación se conservan.

## Arquitectura

Navegador (React) → API en 127.0.0.1 → motor Python → carpetas locales.

El servidor escucha exclusivamente en loopback. Valida Host y Origin, y exige un token de sesión en las llamadas de lectura de datos y de modificación. El frontend consulta snapshots de estado cada 650 ms; las transferencias se ejecutan en un hilo separado. Solo se permite una operación de archivos a la vez, incluso con varias pestañas. No se sirve el árbol completo del proyecto: únicamente los recursos compilados y los reportes de sesiones con identificadores válidos.

Los diálogos tienen foco inicial, cierre con Escape y ciclo de foco. Los estados se expresan con texto y color. El progreso indica archivos verificados, no bytes transferidos. El historial muestra que el resultado es anterior hasta una reauditoría. La tabla permite buscar y filtrar por estado.

## Desarrollo y pruebas

Desde la carpeta FrameVault:

```text
python web_server.py --no-browser
python -m unittest test_core test_web -v
cd frontend
npm ci
npm run build
```

Después de compilar, recarga el navegador; Python sirve los archivos nuevos. El entorno de desarrollo no requiere un segundo servidor Vite: se usa la compilación para mantener un único origen local. Si necesitas otro puerto: `python web_server.py --port 8766`.

## Límites

El servidor es de desarrollo local, no un servicio para publicar en internet. El explorador puede leer nombres de carpetas accesibles al usuario de Windows. No hay cuentas multiusuario, monitorización continua ni protección frente a otro proceso local malicioso. Las limitaciones del motor sobre hash, solo lectura, evidencia local y discos independientes siguen aplicando (ver LEEME.md).

Las carpetas del proyecto están dentro de OneDrive por decisión de ubicación del usuario. FrameVault no envía archivos a la nube; la sincronización propia de OneDrive es independiente de la aplicación.

## Validación de esta versión

- 15 pruebas del motor Python: aprobadas.
- 8 pruebas de API HTTP: aprobadas, incluida doble copia real y detección de faltante.
- 4 pruebas React en DOM simulado: aprobadas (selección requerida, demo/inventario, protección/pasaporte, invalidación al cambiar carpetas y búsqueda).
- Compilación de producción: correcta. Recursos JS/CSS servidos por HTTP con tipo de contenido correcto.
- No se pudo completar la inspección visual automatizada del navegador: el navegador integrado no adjuntó su ventana y el control de Zen no quedó autorizado. Las pruebas React no equivalen a una revisión visual en el navegador ni a una prueba con usuario externo.

Para ejecutar las pruebas de interfaz: `cd frontend`, `npm ci`, `npx vitest run`. Las pruebas usan un motor simulado; las 8 pruebas HTTP realizan operaciones reales en carpetas temporales.


## Subir archivos propios

1. Pulsa **Subir archivos** y selecciona uno o varios archivos de cualquier tipo.
2. Espera a que termine la carga. La copia de origen queda en `archivos_subidos` dentro de FrameVault.
3. Selecciona las carpetas de **Respaldo principal** y **Respaldo secundario**; preferiblemente en discos distintos.
4. Pulsa **Crear inventario**, revisa la lista y pulsa **Proteger material**.

La carga admite hasta 10 GB por archivo y muestra el archivo actual y el número de archivos. Para archivos mayores o carpetas completas, usa el selector de carpeta de origen. Los nombres repetidos en una misma carga se rechazan sin sobrescribir. Si falla una carga, se descarta ese lote para poder repetirlo. Los archivos subidos se conservan para las verificaciones posteriores; no borres su carpeta mientras necesites auditar la sesión.

Esta función funciona en el equipo local. No requiere cuentas ni publica el servidor en internet. Subir archivos no los marca como protegidos: eso sucede después de copiar y verificar los dos respaldos.


## Inventario, organización y recuperación

- Seleccionar un origen muestra automáticamente nombres, cantidad y tamaño antes de copiar. **Crear inventario** fija además la huella SHA-256 de cada archivo y detecta contenido duplicado; los duplicados se señalan y se conservan.
- Activa **Organizar automáticamente los respaldos** para usar Proyecto / Jornada / Cámara / Tarjeta / Extensión / ruta original. La jornada vacía usa la fecha de modificación de cada archivo; cámara y tarjeta pueden indicarse manualmente. No se extraen metadatos de cámara embebidos. La ruta de origen permanece intacta.
- Los estados se distinguen por texto y color: rojo En riesgo, amarillo Copiando, azul Verificando y verde Protegido. El contador muestra archivos protegidos y porcentaje.
- **Reintentar copia** verifica y conserva las copias correctas; vuelve a crear las faltantes o dañadas. Una copia dañada se conserva con sufijo `.invalid-...` antes de colocar la nueva. Si el original cambió, crea un inventario nuevo; el reintento no cambia la huella esperada.
- El pasaporte incluye origen, ingreso, ruta organizada, SHA-256, ubicación y última verificación de A/B, errores e historial. Es un registro local editable, no una cadena de custodia firmada.
- **Material protegido. La tarjeta puede liberarse** aparece solo tras una verificación completa del origen y ambas copias, sin archivos nuevos o faltantes. Es el resultado de la comprobación indicada, no una vigilancia continua. Al abrir el historial se requiere verificar de nuevo. Si subiste archivos individuales, se confirma únicamente ese conjunto y se pide inventariar la tarjeta completa antes de liberarla.
