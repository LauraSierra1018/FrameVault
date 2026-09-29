"""Motor offline: inventario, transferencia, auditoría y reportes."""
from pathlib import Path
import hashlib, json, os, shutil, stat, uuid, getpass, html, re
from datetime import datetime, timezone

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def linked(p):
    return p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction())

def digest(p, cancel=lambda: False):
    h = hashlib.sha256()
    with p.open('rb') as f:
        while chunk := f.read(1024 * 1024):
            if cancel(): raise InterruptedError('Operación cancelada')
            h.update(chunk)
    return h.hexdigest()

def scan(root):
    root = Path(root).resolve()
    result = []
    def walk(folder):
        for p in sorted(folder.iterdir()):
            if linked(p): raise ValueError(f'Enlace no admitido: {p}')
            if p.is_dir(): walk(p)
            elif p.is_file():
                s = p.stat()
                result.append(dict(path=p.relative_to(root).as_posix(), size=s.st_size,
                    modified_ns=s.st_mtime_ns, format=p.suffix.lower() or 'sin extensión',
                    state='En riesgo', sha256=None, copies={}, history=[]))
    walk(root)
    return result

def validate(source, a, b, storage):
    paths = [Path(p).resolve() for p in (source, a, b, storage)]
    if not all(p.is_dir() for p in paths[:3]):
        raise ValueError('Selecciona tres carpetas existentes.')
    for i, p in enumerate(paths):
        for q in paths[i+1:]:
            if p == q or p in q.parents or q in p.parents:
                raise ValueError('Origen, destinos e historial deben ser carpetas independientes, sin contenerse.')
    return paths

class Session:
    def __init__(self, data, storage, emit=lambda d: None, cancel=lambda: False):
        self.data, self.storage, self.emit, self.cancel = data, Path(storage), emit, cancel

    @classmethod
    def create(cls, source, a, b, storage, organization=None, **kwargs):
        source, a, b, storage = validate(source, a, b, storage)
        files = scan(source)
        if not files: raise ValueError('La carpeta de origen está vacía.')
        organization = organization or {}
        if not isinstance(organization, dict): raise ValueError('Organización inválida.')
        def component(value, default):
            value = str(value or default).strip()
            if (value in ('.', '..') or len(value) > 60 or value.endswith(('.', ' ')) or
                re.search(r'[<>:"/\\|?*\x00-\x1f]', value) or
                value.split('.')[0].upper() in {'CON','PRN','AUX','NUL', *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}):
                raise ValueError('Nombre no válido en la organización: ' + value)
            return value
        seen = {}
        warnings = []
        entered = now()
        for f in files:
            f['ingested'] = entered
            f['original'] = str(source / f['path'])
            before = (source / f['path']).stat()
            if (before.st_size, before.st_mtime_ns) != (f['size'], f['modified_ns']):
                raise ValueError('El origen cambió durante el inventario: ' + f['path'])
            f['sha256'] = digest(source / f['path'], kwargs.get('cancel', lambda: False))
            after = (source / f['path']).stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError('El origen cambió durante el inventario: ' + f['path'])
            f['errors'] = []
            f['duplicate_of'] = seen.get(f['sha256'])
            if f['duplicate_of']:
                warnings.append('Contenido duplicado: ' + f['path'] + ' = ' + f['duplicate_of'])
            else: seen[f['sha256']] = f['path']
            f['backup_path'] = f['path']
            if organization.get('enabled'):
                day = datetime.fromtimestamp(f['modified_ns'] / 1e9).strftime('%Y-%m-%d')
                parts = [component(organization.get('project'), 'Proyecto'),
                         component(organization.get('day'), day),
                         component(organization.get('camera'), 'Sin camara'),
                         component(organization.get('card'), source.name),
                         component(f['format'].lstrip('.'), 'sin extension'), f['path']]
                f['backup_path'] = '/'.join(parts)
        total = sum(f['size'] for f in files)
        for dest in (a, b):
            required = total * (2 if a.stat().st_dev == b.stat().st_dev else 1)
            if shutil.disk_usage(dest).free < required + 1024*1024:
                raise ValueError('Espacio insuficiente para los respaldos.')
        sid = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8]
        data = dict(version=1, id=sid, created=now(), operator=getpass.getuser(), source=str(source),
            destinations=[str(a / ('FrameVault-' + sid)), str(b / ('FrameVault-' + sid))],
            files=files, state='En riesgo', issues=[], warnings=warnings, organization=organization, card_safe=False,
            notice='Dos carpetas no garantizan dos discos físicos. Usa discos independientes para material real.')
        obj = cls(data, storage, **kwargs)
        obj.save()
        return obj

    def event(self, f, message):
        f['history'].append(dict(time=now(), operator=self.data['operator'], event=message))

    def save(self):
        self.storage.mkdir(parents=True, exist_ok=True)
        path = self.storage / (self.data['id'] + '.json')
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, path)

    def update(self, state):
        self.data['state'] = state
        if state != 'Protegido': self.data['card_safe'] = False
        self.save()
        self.emit(self.data)

    def target(self, root, f):
        relative = f.get('backup_path', f['path'])
        from pathlib import PurePosixPath
        rel = PurePosixPath(relative)
        if rel.is_absolute() or '..' in rel.parts or '\\' in relative or ':' in relative:
            raise ValueError('Ruta de respaldo no válida.')
        p = Path(root) / relative
        if p.resolve() != p or linked(p): raise ValueError('Enlace en destino')
        return p

    def retry(self):
        self.transfer(retry=True)

    def transfer(self, retry=False):
        self.data['issues'] = []
        self.update('Copiando')
        try:
            # Never recreate an unplugged destination root on the system disk.
            for dest in self.data['destinations']:
                if not Path(dest).parent.is_dir(): raise ValueError('Conecta el disco de respaldo: ' + dest)
                if Path(dest).resolve() != Path(dest): raise ValueError('Enlace en destino')
                Path(dest).mkdir(exist_ok=retry)
            for f in self.data['files']:
                if self.cancel(): raise InterruptedError('Operación cancelada; puedes reintentar la copia.')
                src = Path(self.data['source']) / f['path']
                f['errors'] = []
                f['state'] = 'Copiando'
                self.update('Copiando')
                try:
                    if linked(src) or src.resolve() != src: raise ValueError('El origen cambió a un enlace')
                    before = src.stat()
                    if (before.st_size, before.st_mtime_ns) != (f['size'], f['modified_ns']):
                        raise ValueError('El origen cambió después del inventario. Crea un inventario nuevo.')
                    actual_source = digest(src, self.cancel)
                    if f['sha256'] and actual_source != f['sha256']:
                        raise ValueError('El origen no coincide con el inventario. Crea un inventario nuevo.')
                    f['sha256'] = actual_source
                    for label, root in zip(('A', 'B'), self.data['destinations']):
                        temp = None
                        try:
                            target = self.target(root, f)
                            target.parent.mkdir(parents=True, exist_ok=True)
                            if retry and target.is_file() and digest(target, self.cancel) == f['sha256']:
                                f['copies'][label] = dict(path=str(target), sha256=f['sha256'], verified=now(), valid=True)
                                self.event(f, 'Reintento: copia ' + label + ' válida conservada')
                                continue
                            # Unique temporary names also work for source names ending in .partial.
                            temp = target.with_name('.fv-' + uuid.uuid4().hex + '.partial')
                            f['state'] = 'Copiando'
                            self.update('Copiando')
                            with src.open('rb') as inp, temp.open('xb') as out:
                                while chunk := inp.read(1024*1024):
                                    if self.cancel(): raise InterruptedError('Operación cancelada; puedes reintentar la copia.')
                                    out.write(chunk)
                                out.flush()
                                os.fsync(out.fileno())
                            f['state'] = 'Verificando'
                            self.update('Verificando')
                            actual = digest(temp, self.cancel)
                            if actual != f['sha256']: raise ValueError('Hash diferente en copia ' + label)
                            if target.exists():
                                if not retry: raise ValueError('Destino existente: no se sobrescribe')
                                quarantine = target.with_name(target.name + '.invalid-' + uuid.uuid4().hex[:8])
                                target.rename(quarantine)
                                self.event(f, 'Copia anterior conservada en ' + str(quarantine))
                            temp.rename(target)
                            target.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
                            f['copies'][label] = dict(path=str(target), sha256=actual, verified=now(), valid=True)
                            self.event(f, f'Copia {label} verificada SHA-256; atributo de solo lectura aplicado')
                        except InterruptedError: raise
                        except (OSError, ValueError) as exc:
                            f['copies'].setdefault(label, {})['valid'] = False
                            f['errors'].append('Copia ' + label + ': ' + str(exc))
                            self.event(f, f['errors'][-1])
                        finally:
                            if temp is not None and temp.exists(): temp.unlink()
                    f['state'] = 'En riesgo'
                except InterruptedError: raise
                except (OSError, ValueError) as exc:
                    f['state'] = 'En riesgo'
                    f['errors'].append(str(exc))
                    self.event(f, str(exc))
                self.save()
            self.audit()
        except (OSError, ValueError, InterruptedError) as exc:
            self.data['issues'].append(str(exc))
            for f in self.data['files']:
                if f['state'] in ('Copiando', 'Verificando'): f['state'] = 'En riesgo'
            self.update('En riesgo')
        finally: self.report()

    def audit(self):
        self.data['issues'] = []
        for f in self.data['files']:
            f['state'] = 'Verificando'
            for c in f['copies'].values(): c['valid'] = False
        self.update('Verificando')
        try:
            current = {f['path'] for f in scan(self.data['source'])}
            expected = {f['path'] for f in self.data['files']}
            for p in sorted(current - expected): self.data['issues'].append('Nuevo archivo fuera del inventario: ' + p)
            for p in sorted(expected - current): self.data['issues'].append('Falta en origen: ' + p)
            for f in self.data['files']:
                errors = []
                for label, root in [('Origen', self.data['source'])] + list(zip(('A', 'B'), self.data['destinations'])):
                    try:
                        p = Path(root) / f['path'] if label == 'Origen' else self.target(root, f)
                        if p.resolve() != p or linked(p): raise ValueError('Enlace no admitido')
                        before = p.stat()
                        actual = digest(p, self.cancel)
                        after = p.stat()
                        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                            raise ValueError('El archivo cambió durante la verificación')
                        if not f['sha256'] or actual != f['sha256']: raise ValueError('SHA-256 inconsistente')
                        if label != 'Origen':
                            f['copies'][label] = dict(path=str(p), sha256=actual, verified=now(), valid=True)
                    except InterruptedError: raise
                    except (OSError, ValueError) as exc:
                        errors.append(f'{label}: {exc}')
                        if label != 'Origen': f['copies'].setdefault(label, {})['valid'] = False
                f['errors'] = errors
                f['state'] = 'En riesgo' if errors else 'Protegido'
                self.event(f, 'Revisión: ' + ('; '.join(errors) if errors else 'Origen y ambas copias coinciden'))
                self.save()
                self.emit(self.data)
            # Detect additions/removals and changed metadata during this audit as well.
            final = scan(self.data['source'])
            if {f['path'] for f in final} != current:
                self.data['issues'].append('El contenido del origen cambió durante la verificación. Verifica de nuevo.')
            snapshot = {f['path']: f for f in final}
            for f in self.data['files']:
                other = snapshot.get(f['path'])
                if other and (other['size'],other['modified_ns']) != (f['size'],f['modified_ns']):
                    f['state'] = 'En riesgo'
                    f['errors'].append('El origen cambió desde el inventario. Crea un inventario nuevo.')
            self.data['checked'] = now()
            safe = bool(self.data['files']) and not self.data['issues'] and all(f['state'] == 'Protegido' for f in self.data['files'])
            self.data['card_safe'] = safe
            self.update('Protegido' if safe else 'En riesgo')
        except (OSError, ValueError, InterruptedError) as exc:
            self.data['issues'].append(str(exc))
            for f in self.data['files']:
                if f['state'] == 'Verificando': f['state'] = 'En riesgo'
            self.update('En riesgo')
        self.report()

    def report(self):
        self.save()
        d = self.data
        esc = lambda x: html.escape(str(x))
        rows = ''.join(f'<tr><td>{esc(f["path"])}</td><td>{f["size"]}</td><td>{esc(f["state"])}</td><td>{esc(f["sha256"])}</td></tr>' for f in d['files'])
        details = ''.join('<h3>'+esc(f['path'])+'</h3><pre>'+esc(json.dumps(f, ensure_ascii=False, indent=2))+'</pre>' for f in d['files'])
        content = f'''<!doctype html><html lang="es"><meta charset="utf-8"><title>FrameVault · Reporte</title>
        <style>body{{font:16px Segoe UI,sans-serif;max-width:1100px;margin:40px auto;color:#17243a}}table{{border-collapse:collapse;width:100%}}td,th{{padding:12px;border-bottom:1px solid #ddd;text-align:left}}td:last-child{{word-break:break-all}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef3f8;padding:20px}}</style>
        <h1>FrameVault · {esc(d['state'])}</h1><p>Sesión {esc(d['id'])} · Operador: {esc(d['operator'])}</p>
        <p>Última revisión: {esc(d.get('checked','Sin revisión completa'))}</p><p>{esc(d['notice'])}</p>
        <p>Origen: {esc(d['source'])}<br>A: {esc(d['destinations'][0])}<br>B: {esc(d['destinations'][1])}</p>
        <p>{esc('; '.join(d['issues']))}</p><table><tr><th>Archivo</th><th>Bytes</th><th>Estado</th><th>SHA-256</th></tr>{rows}</table>
        <p>{esc(('Archivos subidos protegidos; no verifica la tarjeta completa.' if d.get('source_kind') == 'upload' else 'Material protegido. La tarjeta puede liberarse.') if d.get('card_safe') else 'No reutilizar la tarjeta todavía.')}</p><p>Resultado puntual: {esc(d.get('checked', 'Pendiente'))}</p><p>{esc('; '.join(d.get('warnings', [])))}</p><h2>Pasaportes e historial</h2>{details}<p>Verificación puntual de bytes; no certifica reproducción audiovisual ni seguridad futura. Historial local editable, sin firma digital.</p></html>'''
        path = self.storage / (d['id'] + '.html')
        path.write_text(content, encoding='utf-8')
        return path
