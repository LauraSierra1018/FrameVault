# Resultados de pruebas locales

Fecha: 23 de septiembre de 2026.
Entorno: Windows, Python 3.12.12, Tcl/Tk 8.6.17.

## Motor: 15/15 pruebas aprobadas

- Doble copia real con SHA-256 idéntico en ambas ubicaciones.
- Detección de respaldo faltante.
- Detección de respaldo alterado.
- Detección de origen cambiado después del inventario.
- Detección de archivo nuevo en origen.
- Detección de archivo eliminado del origen.
- Rechazo de destinos iguales.
- Rechazo de destinos anidados.
- Rechazo de superposición entre origen y destino.
- Rechazo de origen vacío.
- Cancelación sin declarar protección ni conservar temporales activos.
- Conservación de copia existente sin sobrescribir.
- Espacio insuficiente simulado.
- Error de escritura/desconexión simulado, sin falso verde.
- Carga de manifiesto persistido y reauditoría correcta.

## Interfaz: flujo aprobado

Se abrió una ventana Tk real y se ejecutaron sus acciones programáticamente: preparar demo, crear inventario con 8 archivos, copiar, verificar, comprobar verde y 100%, abrir pasaporte, borrar una copia de demostración, verificar y comprobar rojo. Se comprobó que el hilo de trabajo concluyera y la ventana procesara eventos. No equivale a una prueba de usabilidad con participante externo.

## Límites de la validación

Se usaron carpetas locales del mismo equipo. No se ensayaron discos externos reales, extracción física de USB, corte de energía, archivos de cientos de GB ni ataques concurrentes. Las fallas de espacio y escritura se inyectaron de manera controlada. Los audios e imágenes de la demo son válidos; no se ha implementado un validador de reproducción de video.

Para repetir: ejecutar los comandos documentados en LEEME.md. Las pruebas de motor utilizan carpetas temporales. La prueba de interfaz crea una demo independiente y conserva su historial de fallo intencional.
