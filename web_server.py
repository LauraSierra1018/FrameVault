"""Servidor local de FrameVault. Solo escucha en 127.0.0.1; React se sirve compilado."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse, parse_qs
import json, threading, secrets, mimetypes, re, os, argparse, webbrowser, copy, shutil, uuid
from core import Session, scan
from demo import create_demo

BASE = Path(__file__).resolve().parent
ID = re.compile(r'^[0-9]{8}-[0-9]{6}-[a-f0-9]{8}$')

class Service:
    def __init__(self, base=BASE):
        self.base = Path(base).resolve()
        self.storage = self.base / 'historial'
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.token = secrets.token_urlsafe(32)
        self.session = None
        self.view = None
        self.busy = False
        self.operation = None
        self.error = None
        self.historical = False
        self.upload_id = None
        self.paths = ['', '', '']

    def publish(self, data):
        with self.lock: self.view = copy.deepcopy(data)

    def state(self):
        with self.lock:
            return dict(session=self.view, busy=self.busy, operation=self.operation,
                        error=self.error, paths=self.paths, historical=self.historical)

    def start(self, name, work):
        with self.lock:
            if self.busy: raise ValueError('Ya hay una operación en curso. Espera a que termine.')
            self.busy, self.operation, self.error = True, name, None
            self.cancel.clear()
        def run():
            try: work()
            except Exception as exc:
                with self.lock: self.error = str(exc)
            finally:
                with self.lock:
                    if self.session: self.publish(self.session.data)
                    self.busy = False
                    self.operation = None
        threading.Thread(target=run, daemon=True).start()

    def action(self, name, body):
        with self.lock:
            if name == 'cancel':
                if self.upload_id:
                    return self.upload_action('upload-abort', {'id': self.upload_id})
                self.cancel.set()
                return self.state()
            if self.busy: raise ValueError('Espera a que termine la operación actual.')
            if name == 'demo':
                self.paths = list(map(str, create_demo(self.base/'demostraciones')))
                self.session = self.view = None
                self.error = None
                self.historical = False
            elif name == 'preview':
                return {'files': scan(body['source'])}
            elif name == 'inventory':
                paths = body.get('paths')
                if not isinstance(paths, list) or len(paths) != 3 or not all(isinstance(p,str) and p.strip() for p in paths):
                    raise ValueError('Selecciona el origen y los dos respaldos.')
                self.paths = paths
                self.session = self.view = None
                self.historical = False
                def inventory():
                    self.session = Session.create(*paths,self.storage,emit=self.publish,cancel=self.cancel.is_set, organization=body.get('organization'))
                    self.session.data['source_kind'] = 'upload' if Path(paths[0]).resolve().is_relative_to(self.base / 'archivos_subidos') else 'folder'
                    self.session.save()
                    self.publish(self.session.data)
                self.start('inventory', inventory)
            elif name in ('transfer', 'audit', 'retry'):
                if not self.session: raise ValueError('Primero crea un inventario o abre una sesión.')
                if name == 'transfer' and any(Path(p).exists() for p in self.session.data['destinations']):
                    raise ValueError('Esta sesión ya tiene respaldos. Verifica de nuevo o crea otra sesión.')
                self.historical = False
                self.start(name, {'transfer': self.session.transfer, 'audit': self.session.audit, 'retry': self.session.retry}[name])
            elif name == 'load':
                sid = body.get('id','')
                if not ID.fullmatch(sid): raise ValueError('Identificador no válido.')
                data = json.loads((self.storage/(sid+'.json')).read_text(encoding='utf-8'))
                if data.get('id') != sid or data.get('version') != 1 or not data.get('files'):
                    raise ValueError('El manifiesto no es compatible.')
                for f in data['files']:
                    rel = PurePosixPath(f['path'])
                    if rel.is_absolute() or '..' in rel.parts or '\\' in f['path'] or ':' in f['path']:
                        raise ValueError('El manifiesto contiene una ruta no válida.')
                for f in data['files']:
                    relative = f.get('backup_path', f['path'])
                    rel = PurePosixPath(relative)
                    if rel.is_absolute() or '..' in rel.parts or '\\' in relative or ':' in relative:
                        raise ValueError('Ruta organizada no válida.')
                if len(data.get('destinations',[])) != 2: raise ValueError('Destinos inválidos.')
                self.session = Session(data,self.storage,emit=self.publish,cancel=self.cancel.is_set)
                self.publish(data)
                self.paths = [data['source']]+[str(Path(p).parent) for p in data['destinations']]
                self.error = None
                self.historical = True
            elif name == 'reset':
                self.session = self.view = None
                self.paths = ['', '', '']
                self.error = None
                self.historical = False
            else: raise ValueError('Acción desconocida.')
            return self.state()

    def upload_action(self, name, body):
        with self.lock:
            if name == 'upload-start':
                if self.busy or self.upload_id:
                    raise ValueError('Espera a que termine la operación actual.')
                self.upload_id = uuid.uuid4().hex
                folder = self.base / 'archivos_subidos' / self.upload_id
                folder.mkdir(parents=True)
                self.busy, self.operation = True, 'upload'
                return {'id': self.upload_id}
            if not self.upload_id or body.get('id') != self.upload_id:
                raise ValueError('Carga no válida. Selecciona los archivos de nuevo.')
            folder = self.base / 'archivos_subidos' / self.upload_id
            if name == 'upload-abort':
                shutil.rmtree(folder)
            elif name == 'upload-finish':
                if not any(folder.iterdir()):
                    raise ValueError('Selecciona al menos un archivo.')
                self.paths = [str(folder), '', '']
                self.session = self.view = None
                self.error = None
                self.historical = False
            else:
                raise ValueError('Acción de carga desconocida.')
            self.upload_id = None
            self.busy, self.operation = False, None
            return self.state()

    def receive_file(self, upload_id, filename, stream, length):
        with self.lock:
            if not self.upload_id or upload_id != self.upload_id:
                raise ValueError('Carga no válida.')
            # Portable Windows filenames; never allow paths or device names.
            if (not filename or len(filename) > 240 or
                any(ord(c) < 32 or c in '<>:"/\\|?*' for c in filename) or
                filename.endswith((' ', '.')) or
                filename.split('.')[0].upper() in {'CON','PRN','AUX','NUL',
                    *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}):
                raise ValueError('Nombre de archivo no válido.')
            folder = self.base / 'archivos_subidos' / self.upload_id
            target = folder / filename
            if target.exists():
                raise ValueError('Hay dos archivos con el mismo nombre: ' + filename)
            if length < 0 or length > 10 * 1024**3:
                raise ValueError('El límite por archivo es de 10 GB. Para archivos mayores, usa una carpeta local.')
            if shutil.disk_usage(folder).free < length + 1024**2:
                raise ValueError('No hay espacio suficiente para subir este archivo.')
            try:
                with target.open('xb') as output:
                    remaining = length
                    while remaining:
                        chunk = stream.read(min(1024**2, remaining))
                        if not chunk:
                            raise ValueError('La carga del archivo quedó incompleta.')
                        output.write(chunk)
                        remaining -= len(chunk)
            except Exception:
                target.unlink(missing_ok=True)
                raise
            return {'name': filename, 'size': length}

    def history(self):
        rows=[]
        for p in sorted(self.storage.glob('*.json'), reverse=True):
            if not ID.fullmatch(p.stem): continue
            try:
                d=json.loads(p.read_text(encoding='utf-8'))
                rows.append(dict(id=p.stem,created=d['created'],state=d['state'],count=len(d['files']),source=d['source']))
            except (ValueError, KeyError, OSError): continue
        return rows

    def folders(self,path):
        if not path:
            roots=[f'{c}:\\' for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if Path(f'{c}:\\').is_dir()] if os.name=='nt' else ['/']
            return dict(path='',parent=None,folders=[dict(name=p,path=p) for p in roots],home=str(self.base))
        p=Path(path).resolve()
        if not p.is_dir(): raise ValueError('La carpeta no existe o no está disponible.')
        folders=[]
        for child in p.iterdir():
            try:
                if child.is_dir() and not child.is_symlink() and not (hasattr(child,'is_junction') and child.is_junction()):
                    folders.append(dict(name=child.name,path=str(child)))
            except OSError: continue
        return dict(path=str(p),parent=str(p.parent) if p.parent!=p else '',folders=sorted(folders,key=lambda x:x['name'].lower()),home=str(self.base))

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def respond(self,code,data,kind='application/json; charset=utf-8'):
        raw=json.dumps(data,ensure_ascii=False).encode() if kind.startswith('application/json') else data
        self.send_response(code)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(raw)
    def allowed(self):
        host=self.headers.get('Host','')
        if host != f'127.0.0.1:{self.server.server_port}':
            self.respond(403,{'error':'Host no permitido. Abre la dirección 127.0.0.1.'}); return False
        origin=self.headers.get('Origin')
        if origin and origin != f'http://{host}':
            self.respond(403,{'error':'Origen no permitido.'}); return False
        return True
    def do_GET(self):
        if not self.allowed(): return
        url=urlparse(self.path); query=parse_qs(url.query); service=self.server.service
        try:
            if url.path=='/api/bootstrap': return self.respond(200,dict(token=service.token,**service.state()))
            if url.path.startswith('/api/') and self.headers.get('X-FrameVault-Token')!=service.token:
                return self.respond(403,{'error':'Sesión web no válida. Recarga la página.'})
            if url.path=='/api/state': return self.respond(200,service.state())
            if url.path=='/api/history': return self.respond(200,service.history())
            if url.path=='/api/folders': return self.respond(200,service.folders(query.get('path',[''])[0]))
            if url.path=='/api/report':
                sid=query.get('id',[''])[0]
                if not ID.fullmatch(sid): raise ValueError('Reporte inválido.')
                return self.respond(200,(service.storage/(sid+'.html')).read_bytes(),'text/html; charset=utf-8')
            if url.path.startswith('/api/'):return self.respond(404,{'error':'No encontrado.'})
            dist=(BASE/'frontend'/'dist').resolve()
            target=(dist/('index.html' if url.path=='/' else url.path.lstrip('/'))).resolve()
            if not target.is_relative_to(dist) or not target.is_file(): return self.respond(404,{'error':'Archivo no encontrado.'})
            self.respond(200,target.read_bytes(),mimetypes.guess_type(target)[0] or 'application/octet-stream')
        except (OSError,ValueError) as exc: self.respond(400,{'error':str(exc)})
    def do_POST(self):
        if not self.allowed():return
        service=self.server.service
        if not secrets.compare_digest(self.headers.get('X-FrameVault-Token',''),service.token):
            return self.respond(403,{'error':'Sesión web no válida. Recarga la página.'})
        try:
            route = urlparse(self.path)
            length=int(self.headers.get('Content-Length',0))
            if route.path == '/api/upload-file':
                query = parse_qs(route.query)
                self.connection.settimeout(60)
                return self.respond(200, service.receive_file(query.get('id',[''])[0],
                    query.get('name',[''])[0], self.rfile, length))
            if length<0 or length>16384:raise ValueError('Solicitud demasiado grande.')
            body=json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(body,dict):raise ValueError('Solicitud inválida.')
            name = route.path.removeprefix('/api/')
            if name in ('upload-start', 'upload-finish', 'upload-abort'):
                return self.respond(200, service.upload_action(name, body))
            self.respond(200,service.action(name,body))
        except (OSError,ValueError,KeyError) as exc:self.respond(400,{'error':str(exc)})

def make_server(port=8765,base=BASE):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.service=Service(base)
    return server

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    url=f'http://127.0.0.1:{args.port}'
    try:server=make_server(args.port)
    except OSError:
        print(f'No se pudo abrir el puerto {args.port}. Puede que FrameVault ya esté abierto en {url}.');raise SystemExit(1)
    print(f'FrameVault está disponible en {url}',flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:server.shutdown()
