import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
import urllib.request
import urllib.error


class MusicTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        previous = os.environ.get('MPLAYER_DATA')
        os.environ['MPLAYER_DATA'] = cls.temp.name
        spec = importlib.util.spec_from_file_location('mplayer_test', Path(__file__).parents[1] / 'app.py')
        cls.app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.app)
        if previous is None: os.environ.pop('MPLAYER_DATA')
        else: os.environ['MPLAYER_DATA'] = previous
        cls.server = cls.app.ThreadingHTTPServer(('127.0.0.1',0),cls.app.Handler)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.base = 'http://127.0.0.1:'+str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp.cleanup()

    def request(self, path, data=None, headers=None):
        raw = json.dumps(data).encode() if data is not None else None
        return urllib.request.urlopen(urllib.request.Request(self.base+path, data=raw, headers=headers or {}))

    def test_time_and_url_validation(self):
        self.assertEqual(self.app.seconds('1:02:03'),3723)
        for value in ('-1','1:99','abc','1:2:3:4'):
            with self.assertRaises(ValueError): self.app.seconds(value)
        for url in ('http://127.0.0.1','https://youtube.com.evil.test/watch?v=1','file:///etc/passwd'):
            with self.assertRaises(ValueError): self.app.youtube_url(url)

    def test_static_and_traversal(self):
        with self.request('/') as r: self.assertIn(b'Mplayer',r.read())
        with self.assertRaises(urllib.error.HTTPError) as error: self.request('/../app.py')
        self.assertEqual(error.exception.code,404)

    def test_cross_origin_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/api/like',{'id':'x','liked':True},{'Origin':'https://other.test'})
        self.assertEqual(error.exception.code,403)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
    def test_upload_stream_split_and_metadata(self):
        source = Path(self.temp.name)/'tone.wav'
        self.app.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=3',str(source)])
        req = urllib.request.Request(self.base+'/api/upload?name=test.wav',data=source.read_bytes(),headers={'Content-Type':'application/octet-stream'})
        with urllib.request.urlopen(req) as response: tid = json.load(response)['id']
        with self.request('/api/library') as response: data = json.load(response)
        self.assertEqual(len(data['tracks']),1)
        track = data['tracks'][0]
        self.assertAlmostEqual(track['duration'],3,delta=.15)
        with self.request('/media/'+tid,headers={'Range':'bytes=0-31'}) as response:
            self.assertEqual(response.status,206)
            self.assertEqual(len(response.read()),32)
        with self.request('/media/'+tid,headers={'Range':'bytes=-10'}) as response:
            self.assertEqual(len(response.read()),10)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/media/'+tid,headers={'Range':'bytes=999999999-'})
        self.assertEqual(error.exception.code,416)
        for chapters in ('00:02 A\n00:01 B','00:05 Outside','invalid'):
            with self.assertRaises(urllib.error.HTTPError): self.request('/api/split',{'id':tid,'chapters':chapters})
        with self.request('/api/split',{'id':tid,'chapters':'00:00 첫 곡\n00:01.5 두 번째 곡'}) as response:
            ids = json.load(response)['ids']
        self.assertEqual(len(ids),2)
        for new_id in ids:
            duration,tags = self.app.metadata(self.app.MEDIA/(new_id+'.mp3'))
            self.assertAlmostEqual(duration,1.5,delta=.15)
            self.assertIn(tags['title'],('첫 곡','두 번째 곡'))
        with self.request('/api/like',{'id':tid,'liked':True}) as response: self.assertTrue(json.load(response)['ok'])
        with self.request('/api/edit',{'id':tid,'title':'수정한 제목','artist':'가수','album':'앨범'}) as response: self.assertTrue(json.load(response)['ok'])
        with self.request('/api/library') as response: updated = next(t for t in json.load(response)['tracks'] if t['id']==tid)
        self.assertEqual(updated['liked'],1)
        self.assertEqual(updated['title'],'수정한 제목')


if __name__ == '__main__': unittest.main()
