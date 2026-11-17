import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import json
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack
import test_http
from scout import app, config

class WorkbenchAPITests(unittest.TestCase):
    request=test_http.HTTPTests.request
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.base=Path(self.directory.name)
        self.settings=self.base/'settings.json';self.settings.write_text('{"channels":[],"language":"en"}')
        self.stack=ExitStack()
        self.stack.enter_context(patch.object(app,'BASE',self.base))
        self.stack.enter_context(patch.object(app,'STATE_PATH',self.base/'scout.json'))  # never touch the real inbox
        self.stack.enter_context(patch.object(app.su,'SETTINGS_PATH',self.settings))
        self.stack.enter_context(patch.object(app,'STATE',{'session':0,'videos':{'a':dict(id='a',date='2026-11-17')}}))
        self.stack.enter_context(patch.object(app.Handler,'engines',dict(claude=True,codex=True,gemini=True)))
        self.stack.enter_context(patch.object(app,'PREVIEW',{}))
        self.stack.enter_context(patch.object(app,'BUSY',[None]))
    def tearDown(self):self.stack.close();self.directory.cleanup()
    def post(self,path,body):return self.request('POST',path,json.dumps(body),{'Content-Type':'application/json'})

    def test_discovery_window_is_validated_and_exposed(self):
        self.assertEqual(self.post('/api/settings',{'mode':'days','max_age_days':14,'max_per_channel':4})[0],200)
        self.assertEqual(json.loads(app.state_json({},'en'))['discovery'],{'mode':'days','max_per_channel':4,'max_age_days':14})
        self.assertEqual(self.post('/api/settings',{'mode':'forever'})[0],400)
        self.assertEqual(self.post('/api/settings',{'max_age_days':0})[0],400)

    def test_settings_save_is_internal_and_persisted(self):
        with patch.object(app.subprocess,'Popen') as opener:
            status,body=self.post('/api/settings',{'ui':{'font':'serif','size':'l'},'engine_models':{'codex':'custom-heavy'}})
            self.assertEqual(status,200,body);opener.assert_not_called()
        result=json.loads(self.request('GET','/api/settings')[1])
        self.assertEqual(result['ui']['font'],'serif');self.assertEqual(result['ui']['size'],'l')
        self.assertEqual(config.load(self.settings)['engine_models']['codex'],'custom-heavy')

    def test_model_is_passed_through_prepare_and_stale_preview_is_rejected(self):
        with patch.object(app,'start',return_value=True) as start:
            status,body=self.post('/api/prepare',dict(ids=['a'],engine='gemini',model='pro',language='en',options={'depth':'text'}))
            self.assertEqual(status,200,body)
            self.assertEqual(start.call_args.args[-1],'pro')
        app.PREVIEW=dict(ready=True,ids=['a'],engine='gemini',model='flash',language='en')
        with patch.object(app,'start') as start:
            status,body=self.post('/api/run',dict(ids=['a'],engine='gemini',model='pro',language='en'))
            self.assertEqual(status,400,body);start.assert_not_called()

    def test_summary_length_reaches_prompt_and_bad_length_is_rejected(self):
        video=[dict(id='a',channel='c',title='t',date='2026-11-17',transcript='x')]
        self.assertIn('2 to 3 key points',app.build_prompt(video,'en','brief'))
        self.assertIn('[hh:mm:ss] timestamp',app.build_prompt(video,'en','deep'))
        self.assertIn('3 to 6 key points, one sentence each',app.build_prompt(video,'en'))
        for length in ('epic',['brief']):
            with patch.object(app,'start') as start:
                status,body=self.post('/api/prepare',dict(ids=['a'],engine='claude',language='en',options={'depth':'text','length':length}))
                self.assertEqual(status,400,body);self.assertIn(b'Invalid input mode',body);start.assert_not_called()

    def test_renaming_a_channel_relabels_its_videos(self):
        follow=lambda name,handle:dict(name=name,url='https://www.youtube.com/@'+handle,channel_id=None,group=None)
        self.assertEqual(self.post('/api/settings',{'channels':[follow('old','a'),follow('other','b')]})[0],200)
        app.STATE['videos']['a']['from']='old'
        with patch.object(app,'save'):
            self.assertEqual(self.post('/api/creator',{'old':'other','new':'old'})[0],400)  # duplicate name
            self.assertEqual(self.post('/api/creator',{'old':'missing','new':'x'})[0],400)
            self.assertEqual(self.post('/api/creator',{'old':'old','new':'   '})[0],400)
            self.assertEqual(self.post('/api/creator',{'old':'old','new':' Nice name '})[0],200)
        self.assertEqual([c['name'] for c in config.load(self.settings)['channels']],['Nice name','other'])
        self.assertEqual(app.STATE['videos']['a']['from'],'Nice name')

    def test_removed_videos_leave_inbox_and_can_be_restored(self):
        self.assertEqual(self.post('/api/hide',{'ids':['a']})[0],200)
        self.assertEqual(json.loads(self.request('GET','/api/state')[1])['videos'],[])
        self.assertIn('a',app.STATE['videos'])  # kept, so a later check does not re-add it
        for bad in ({'ids':['zz']},{'ids':[]},{'ids':['a'],'hidden':'no'}):
            self.assertEqual(self.post('/api/hide',bad)[0],400)
        self.assertEqual(self.post('/api/hide',{'ids':['a'],'hidden':False})[0],200)
        self.assertEqual(len(json.loads(self.request('GET','/api/state')[1])['videos']),1)

    def test_check_can_be_limited_to_chosen_channels(self):
        with patch.object(app,'start',return_value=True) as start:
            self.assertEqual(self.post('/api/session',{'channels':['A']})[0],200)
            self.assertEqual(start.call_args.args[2],{'A'})
            self.assertEqual(self.post('/api/session',{})[0],200)
            self.assertIsNone(start.call_args.args[2])
            for bad in ([],[1],'A'):
                self.assertEqual(self.post('/api/session',{'channels':bad})[0],400)
            self.assertEqual(start.call_count,2)
        settings=dict(channels=[dict(name='A',url='u'),dict(name='B',url='v')])
        with patch.object(app,'settings',return_value=settings),patch.object(app,'ytdlp',return_value='y'),\
             patch.object(app.su,'resolve_channel_ids'),patch.object(app.su,'get_candidates',return_value=[]) as found,\
             patch.object(app,'save'):
            app.new_session({'B'})
            self.assertEqual([c['name'] for c in found.call_args.args[0]['channels']],['B'])

    def test_followed_channels_are_in_state_and_saved_from_app(self):
        channel=dict(name='name',url='https://www.youtube.com/@name',channel_id=None,group=None)
        self.assertEqual(self.post('/api/settings',{'channels':[channel]})[0],200)
        self.assertEqual(json.loads(self.request('GET','/api/state')[1])['channels'],[channel])
        status,body=self.post('/api/settings',{'channels':[{**channel,'url':'https://evil.example/@x'}]})
        self.assertEqual(status,400,body)

    def test_notes_round_trip_library_document_and_download(self):
        key='notes/My note.md';text='# A note\n\n**A real document**'
        self.assertEqual(self.post('/api/document',dict(key=key,text=text))[0],200)
        listed=json.loads(self.request('GET','/api/library')[1]);self.assertEqual(listed[0]['key'],key)
        read=json.loads(self.request('GET','/api/document?key=notes%2FMy%20note.md')[1])
        self.assertEqual(read['text'],text)
        status,content=self.request('GET','/file/notes/My%20note.md')
        self.assertEqual(status,200);self.assertEqual(content.decode(),text)

    def test_large_note_import_and_invalid_paths(self):
        self.assertEqual(self.post('/api/document',dict(key='notes/long.md',text='a'*100000))[0],200)
        self.assertEqual(self.post('/api/document',dict(key='notes/../../settings.json',text='bad'))[0],400)
        self.assertEqual(self.request('GET','/file/notes/%2e%2e/settings.json')[0],404)

    def test_external_origins_cannot_read_or_write_settings(self):
        self.assertEqual(self.request('GET','/api/settings',headers={'Origin':'https://evil.example'})[0],403)

    def test_native_open_only_accepts_library_keys(self):
        self.post('/api/document',dict(key='notes/a.md',text='A'))
        with patch.object(app.subprocess,'Popen') as opener:
            self.assertEqual(self.post('/api/open',dict(key='notes/a.md'))[0],200)
            self.assertEqual(opener.call_args.args[0],['xdg-open',str(self.base/'notes/a.md')])
            self.assertEqual(self.post('/api/open',dict(key='/etc/passwd'))[0],400)
            self.assertEqual(opener.call_count,1)

    def test_new_session_fetches_without_launching_a_summarizer(self):
        with patch.object(app,'start',return_value=True) as start,patch.object(app.engines,'run') as engine:
            self.assertEqual(self.post('/api/session',{})[0],200)
            self.assertEqual(start.call_args.args[1],app.new_session);engine.assert_not_called()
