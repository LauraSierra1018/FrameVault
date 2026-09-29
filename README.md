# FrameVault

Aplicación local para inventariar archivos, crear dos copias de respaldo y verificar su integridad con SHA-256.

## Funciones

- Carga de archivos propios y selección de carpetas o tarjetas.
- Inventario previo con nombres, cantidad y tamaño.
- Estados por archivo y por sesión, con porcentaje protegido.
- Detección de faltantes, contenido duplicado y copias dañadas.
- Reintentos que conservan las copias correctas y guardan aparte las dañadas.
- Organización opcional por proyecto, jornada, cámara, tarjeta y extensión.
- Pasaporte de cada archivo, historial y reportes HTML.
- Aviso para reutilizar la tarjeta tras verificar el inventario y ambas copias.

## Ejecutar

Requiere Python 3.10 o posterior. En Windows, abre **Iniciar FrameVault Web.cmd**. También puedes ejecutar:

```sh
python web_server.py
```

Abre http://127.0.0.1:8765. La interfaz compilada está incluida; no se necesita Node.js para usar la aplicación.

## Desarrollo

```sh
cd frontend
npm ci
npm run build
```

## Pruebas

```sh
python -m unittest test_core test_web -v
cd frontend
npx vitest run
```

## Alcance

FrameVault funciona en un solo computador y no está preparado para exponerse directamente a internet. Usa dos discos físicos diferentes para los respaldos. La verificación es puntual y debe repetirse cuando cambien los archivos o se reconecten los discos. El historial es local y editable, sin firma digital.

La organización automática usa la fecha de modificación cuando no se indica jornada; la cámara se indica manualmente. Subir archivos individuales solo verifica ese conjunto, no la totalidad de una tarjeta.

Los archivos subidos, respaldos, demos generadas y sesiones locales quedan excluidos del repositorio. Las demos se pueden generar desde la aplicación.

Consulta [WEB_LEEME.md](WEB_LEEME.md) para instrucciones detalladas. `LEEME.md` y `PRUEBAS.md` conservan documentación de versiones anteriores.
