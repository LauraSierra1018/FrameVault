import unittest, tempfile, threading, json, urllib.request, urllib.error, time, stat
from pathlib import Path
from web_server import make_server

class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.server=make_server(0,self.base);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.token=self.req('bootstrap')['token']
    def tearDown(self):
        self.server.shutdown();self.server.server_close()
        for p in self.base.rglob('*'):
            if p.is_file():p.chmod(stat.S_IWRITE|stat.S_IREAD)
        self.temp.cleanup()
    def req(self,path,body=None,headers=None):
        h={'X-FrameVault-Token':getattr(self,'token','')}
        if headers:h.update(headers)
        data=None if body is None else json.dumps(body).encode()
        r=urllib.request.Request(self.url+'/api/'+path,data=data,headers=h)
        with urllib.request.urlopen(r) as response:return json.loads(response.read())
    def wait(self):
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            s=self.req('state')
            if not s['busy']:return s
            time.sleep(.02)
        self.fail('Operation timed out')
    def inventory(self):
        demo=self.req('demo',{})
        self.req('inventory',{'paths':demo['paths']})
        return self.wait()
    def test_entire_web_flow_and_missing_copy(self):
        s=self.inventory();self.assertEqual(len(s['session']['files']),8)
        self.req('transfer',{});s=self.wait();self.assertEqual(s['session']['state'],'Protegido')
        sid=s['session']['id'];self.assertTrue((self.base/'historial'/(sid+'.html')).exists())
        self.assertEqual(self.req('history')[0]['id'],sid)
        self.req('load',{'id':sid});self.assertTrue(self.req('state')['historical'])
        p=Path(s['session']['destinations'][1])/s['session']['files'][0]['path'];p.chmod(stat.S_IWRITE);p.unlink()
        self.req('audit',{});s=self.wait();self.assertEqual(s['session']['state'],'En riesgo')
    def test_foreign_origin_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as exc:self.req('demo',{}, {'Origin':'https://example.org'})
        self.assertEqual(exc.exception.code,403)
    def test_missing_token_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as exc:self.req('demo',{}, {'X-FrameVault-Token':''})
        self.assertEqual(exc.exception.code,403)
    def test_foreign_host_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as exc:self.req('bootstrap',headers={'Host':'example.org'})
        self.assertEqual(exc.exception.code,403)
    def test_invalid_paths_reported(self):
        self.req('inventory',{'paths':['Z:/not-found']*3});s=self.wait()
        self.assertTrue(s['error']);self.assertFalse(s['busy']);self.assertIsNone(s['session'])
    def test_folder_browser(self):
        d=self.req('demo',{});from urllib.parse import quote
        rows=self.req('folders?path='+quote(str(Path(d['paths'][0]).parent)))
        self.assertEqual(len(rows['folders']),3)
    def test_overlapping_operation_rejected(self):
        self.server.service.busy=True
        with self.assertRaises(urllib.error.HTTPError):self.req('demo',{})
        self.req('cancel',{});self.assertTrue(self.server.service.cancel.is_set());self.server.service.busy=False
    def test_report_traversal_rejected(self):
        with self.assertRaises(urllib.error.HTTPError):self.req('load',{'id':'../../core'})

    def upload(self, sid, name, data=b'personal file'):
        from urllib.parse import urlencode
        request=urllib.request.Request(self.url+'/api/upload-file?'+urlencode({'id':sid,'name':name}),
            data=data,headers={'X-FrameVault-Token':self.token,'Content-Type':'application/octet-stream'})
        with urllib.request.urlopen(request) as response: return json.loads(response.read())

    def test_personal_upload_and_two_verified_copies(self):
        sid=self.req('upload-start',{})['id']
        payload=b'\x00personal document\xff'
        self.upload(sid,'mi documento.pdf',payload)
        self.upload(sid,'sin extension',b'')
        state=self.req('upload-finish',{'id':sid})
        source=Path(state['paths'][0])
        self.assertEqual((source/'mi documento.pdf').read_bytes(),payload)
        a=self.base/'backup-a';b=self.base/'backup-b';a.mkdir();b.mkdir()
        self.req('inventory',{'paths':[str(source),str(a),str(b)]});self.wait()
        self.req('transfer',{});state=self.wait()
        self.assertEqual(state['session']['state'],'Protegido')
        for destination in state['session']['destinations']:
            self.assertEqual((Path(destination)/'mi documento.pdf').read_bytes(),payload)
        self.assertEqual(len(state['session']['files']),2)

    def test_upload_rejects_paths_duplicates_and_wrong_batch(self):
        sid=self.req('upload-start',{})['id']
        for name in ('../escape','C:\\escape','NUL.txt','bad:name','trailing.'):
            with self.assertRaises(urllib.error.HTTPError):self.upload(sid,name)
        with self.assertRaises(urllib.error.HTTPError):self.upload('wrong','ok.txt')
        self.upload(sid,'ok.txt')
        with self.assertRaises(urllib.error.HTTPError):self.upload(sid,'OK.txt')
        with self.assertRaises(urllib.error.HTTPError):self.req('demo',{})
        self.req('upload-abort',{'id':sid})
        self.assertFalse((self.base/'archivos_subidos'/sid).exists())
        self.assertFalse(self.req('state')['busy'])

    def test_upload_empty_batch_and_partial_stream(self):
        import io
        sid=self.req('upload-start',{})['id']
        with self.assertRaises(urllib.error.HTTPError):self.req('upload-finish',{'id':sid})
        with self.assertRaises(ValueError):self.server.service.receive_file(sid,'short.bin',io.BytesIO(b'x'),10)
        self.assertFalse((self.base/'archivos_subidos'/sid/'short.bin').exists())
        self.req('upload-abort',{'id':sid})

    def test_preview_organization_and_retry_via_api(self):
        d=self.req('demo',{})
        preview=self.req('preview',{'source':d['paths'][0]})
        self.assertEqual(len(preview['files']),8)
        self.assertIsNone(self.req('state')['session'])
        self.req('inventory',{'paths':d['paths'],'organization':{'enabled':True,'project':'Test','camera':'Cam A','card':'01'}})
        self.wait();self.req('transfer',{});s=self.wait()
        self.assertTrue(s['session']['card_safe'])
        f=s['session']['files'][0]
        target=Path(s['session']['destinations'][1])/f['backup_path']
        target.chmod(stat.S_IWRITE);target.unlink()
        self.req('audit',{});s=self.wait();self.assertFalse(s['session']['card_safe'])
        self.req('retry',{});s=self.wait();self.assertTrue(s['session']['card_safe'])
        self.assertTrue(target.exists())

if __name__=='__main__':unittest.main(verbosity=2)
