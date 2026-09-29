"""Genera medios válidos pequeños; nunca modifica una demo anterior."""
from pathlib import Path
import wave, math, struct, uuid

def create_demo(base):
    root = Path(base) / ('demo-' + uuid.uuid4().hex[:8])
    source, a, b = [root / name for name in ('Tarjeta_CAM_A', 'Respaldo_A', 'Respaldo_B')]
    for p in (source, a, b): p.mkdir(parents=True)
    for i in range(1, 5):
        with wave.open(str(source / f'AUDIO_{i:03}.wav'), 'wb') as w:
            w.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
            w.writeframes(b''.join(struct.pack('<h', int(4000*math.sin(2*math.pi*(220+i*110)*n/8000))) for n in range(8000)))
    images = source / 'Fotogramas'
    images.mkdir()
    for i in range(1, 4):
        (images / f'FRAME_{i:03}.ppm').write_bytes(b'P6\n64 64\n255\n' + bytes((40*i, 100, 180))*4096)
    (source / 'Notas.txt').write_text('FrameVault: medios sintéticos válidos para demostración offline.\n', encoding='utf-8')
    return source, a, b
