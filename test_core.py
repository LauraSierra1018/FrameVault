import unittest, tempfile, stat, json
from pathlib import Path
from unittest.mock import patch
from core import Session, digest

class ProtectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name).resolve()
        self.src,self.a,self.b,self.store=[self.root/x for x in ('src','a','b','history')]
        for p in (self.src,self.a,self.b):p.mkdir()
        (self.src/'nested').mkdir(); (self.src/'nested'/'clip.mov').write_bytes(b'video-test'*1000)
        (self.src/'audio.wav').write_bytes(b'audio-test'*800)
    def tearDown(self):
        for p in self.root.rglob('*'):
            if p.is_file():p.chmod(stat.S_IWRITE|stat.S_IREAD)
        self.tmp.cleanup()
    def session(self,**kw):return Session.create(self.src,self.a,self.b,self.store,**kw)
    def test_real_double_copy(self):
        s=self.session(); s.transfer(); self.assertEqual(s.data['state'],'Protegido')
        for f in s.data['files']:
            for root in s.data['destinations']:self.assertEqual(digest(Path(root)/f['path']),digest(self.src/f['path']))
        self.assertTrue(s.report().exists()); self.assertTrue(all(f['history'] for f in s.data['files']))
    def test_missing_backup(self):
        s=self.session();s.transfer();p=Path(s.data['destinations'][1])/'audio.wav';p.chmod(stat.S_IWRITE);p.unlink();s.audit()
        self.assertEqual(s.data['state'],'En riesgo')
    def test_corrupt_backup(self):
        s=self.session();s.transfer();p=Path(s.data['destinations'][0])/'audio.wav';p.chmod(stat.S_IWRITE);p.write_bytes(b'changed');s.audit()
        self.assertEqual(s.data['state'],'En riesgo')
    def test_changed_source_before_copy(self):
        s=self.session();(self.src/'audio.wav').write_bytes(b'changed');s.transfer();self.assertEqual(s.data['state'],'En riesgo')
    def test_new_source_file(self):
        s=self.session();s.transfer();(self.src/'new.txt').write_text('new');s.audit();self.assertEqual(s.data['state'],'En riesgo')
        self.assertTrue(s.data['issues'])
    def test_missing_source(self):
        s=self.session();s.transfer();(self.src/'audio.wav').unlink();s.audit();self.assertEqual(s.data['state'],'En riesgo')
    def test_same_destinations(self):
        with self.assertRaises(ValueError):Session.create(self.src,self.a,self.a,self.store)
    def test_nested_destinations(self):
        child=self.a/'child';child.mkdir()
        with self.assertRaises(ValueError):Session.create(self.src,self.a,child,self.store)
    def test_origin_destination_overlap(self):
        with self.assertRaises(ValueError):Session.create(self.src,self.src/'nested',self.b,self.store)
    def test_empty_source(self):
        empty=self.root/'empty';empty.mkdir()
        with self.assertRaises(ValueError):Session.create(empty,self.a,self.b,self.store)
    def test_cancel(self):
        s=self.session();s.cancel=lambda:True;s.transfer();self.assertEqual(s.data['state'],'En riesgo')
        self.assertFalse(list(self.a.rglob('*.partial')))
    def test_existing_not_overwritten(self):
        s=self.session();s.transfer();p=Path(s.data['destinations'][0])/'audio.wav';before=p.read_bytes();s.transfer()
        self.assertEqual(before,p.read_bytes());self.assertEqual(s.data['state'],'En riesgo')
    def test_disk_full(self):
        import shutil
        with patch('core.shutil.disk_usage',return_value=shutil._ntuple_diskusage(100,100,0)):
            with self.assertRaises(ValueError):self.session()
    def test_write_failure(self):
        s=self.session()
        with patch('core.os.fsync',side_effect=OSError('Disco desconectado')):s.transfer()
        self.assertEqual(s.data['state'],'En riesgo');self.assertFalse(list(self.a.rglob('*.partial')))
    def test_persistence(self):
        s=self.session();s.transfer();d=json.loads((self.store/(s.data['id']+'.json')).read_text(encoding='utf-8'))
        resumed=Session(d,self.store);resumed.audit();self.assertEqual(resumed.data['state'],'Protegido')

    def test_inventory_hashes_duplicates_and_no_copy(self):
        (self.src/'duplicate.wav').write_bytes((self.src/'audio.wav').read_bytes())
        s=self.session()
        self.assertTrue(all(f['sha256'] and f['ingested'] for f in s.data['files']))
        self.assertEqual(len(s.data['warnings']),1)
        self.assertFalse(any(Path(p).exists() for p in s.data['destinations']))
        self.assertFalse(s.data['card_safe'])
        s.transfer();self.assertTrue(s.data['card_safe'])

    def test_retry_repairs_only_bad_copies_and_keeps_evidence(self):
        s=self.session();s.transfer()
        good=Path(s.data['destinations'][0])/'audio.wav'
        unchanged=good.stat().st_mtime_ns
        bad=Path(s.data['destinations'][1])/'audio.wav'
        bad.chmod(stat.S_IWRITE);bad.write_bytes(b'corrupt')
        s.audit();self.assertFalse(s.data['card_safe'])
        self.assertTrue(s.data['files'][0]['errors'])
        s.retry();self.assertTrue(s.data['card_safe'])
        self.assertEqual(good.stat().st_mtime_ns,unchanged)
        self.assertEqual(bad.read_bytes(),good.read_bytes())
        evidence=list(bad.parent.glob('audio.wav.invalid-*'))
        self.assertEqual(evidence[0].read_bytes(),b'corrupt')

    def test_retry_after_interruption_and_missing_copy(self):
        s=self.session();s.cancel=lambda:True;s.transfer()
        self.assertFalse(s.data['card_safe'])
        s.cancel=lambda:False;s.retry();self.assertTrue(s.data['card_safe'])
        p=Path(s.data['destinations'][0])/'audio.wav';p.chmod(stat.S_IWRITE);p.unlink()
        s.audit();self.assertFalse(s.data['card_safe'])
        s.retry();self.assertTrue(s.data['card_safe'])

    def test_organized_paths_preserve_original_and_reload(self):
        s=self.session(organization={'enabled':True,'project':'Película','day':'Día 01','camera':'Cam A','card':'T01'})
        for f in s.data['files']:
            self.assertTrue(f['backup_path'].startswith('Película/Día 01/Cam A/T01/'))
            self.assertTrue((self.src/f['path']).is_file())
        s.transfer();self.assertTrue(s.data['card_safe'])
        for f in s.data['files']:
            for root in s.data['destinations']:
                self.assertEqual(digest(Path(root)/f['backup_path']),f['sha256'])
        resumed=Session(json.loads((self.store/(s.data['id']+'.json')).read_text(encoding='utf-8')),self.store)
        resumed.audit();self.assertTrue(resumed.data['card_safe'])

    def test_reject_organization_traversal(self):
        with self.assertRaises(ValueError):self.session(organization={'enabled':True,'project':'../escape'})

    def test_new_or_missing_source_blocks_card_release(self):
        s=self.session();s.transfer();self.assertTrue(s.data['card_safe'])
        (self.src/'new.txt').write_text('new');s.audit();self.assertFalse(s.data['card_safe'])
        s.retry();self.assertFalse(s.data['card_safe'])
        (self.src/'audio.wav').unlink();s.audit();self.assertFalse(s.data['card_safe'])

    def test_cancel_audit_clears_previous_safe_result(self):
        s=self.session();s.transfer();self.assertTrue(s.data['card_safe'])
        s.cancel=lambda:True;s.audit();self.assertFalse(s.data['card_safe'])
        self.assertEqual(s.data['state'],'En riesgo')

    def test_cancel_inventory_does_not_save_incomplete_manifest(self):
        with self.assertRaises(InterruptedError):self.session(cancel=lambda:True)
        self.assertFalse(list(self.store.glob('*.json')))

if __name__=='__main__':unittest.main(verbosity=2)
