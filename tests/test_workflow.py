import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack
from scout import app as scout
from scout import media
from scout import search


class MediaTests(unittest.TestCase):
    def test_only_public_source_links_are_accepted(self):
        for url in ('file:///etc/passwd', 'https://localhost/reel/a/', 'https://instagram.com.evil/reel/a/',
                    'https://instagram.com/accounts/login/', 'https://user:pass@youtube.com/watch?v=a', 'https://youtube.com/redirect?q=http://localhost/'):
            with self.assertRaises(ValueError):
                media.link_source(url)
        self.assertEqual(media.link_source('https://www.instagram.com/reel/ABC_12/'), 'reels')
        self.assertEqual(media.link_source('https://youtu.be/abcdefghijk'), 'youtube')

    def test_sampling_is_bounded(self):
        self.assertEqual(media.frame_times('', 500, cap=3), [0, 15, 30])
        self.assertEqual(media.frame_times('[00:00:05] look at the chart\n[00:00:12] goodbye', 60, method='visual'), [5])
        self.assertEqual(media.frame_times('', 60, method='manual', manual=[30, 5, 5]), [5, 30])
        with self.assertRaises(ValueError):
            media.frame_times('', 60, method='manual', manual=[60])
        with self.assertRaises(ValueError):
            media.frame_times('', 60, cap=100)

    def test_reel_captions_avoid_speech_recognition(self):
        def download(argv, timeout=120):
            output = Path(argv[argv.index('-o') + 1])
            output.with_name('media.en.vtt').write_text('WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nA public caption\n')
            self.assertIn('--ignore-config', argv)
            self.assertNotIn('--cookies-from-browser', argv)
            return ''
        with patch('scout.media.metadata', return_value={'subtitles': {'en': []}}), patch('scout.media.command', side_effect=download):
            self.assertEqual(media.reel_transcript({'url': 'https://instagram.com/reel/a/'}, 'yt-dlp', {}), '[00:00:01] A public caption')

    def test_reel_without_captions_reports_local_stt_requirement(self):
        with patch('scout.media.metadata', return_value={}):
            with self.assertRaisesRegex(RuntimeError, 'No public captions'):
                media.reel_transcript({'url': 'https://instagram.com/reel/a/'}, 'yt-dlp', {})


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.base = Path(self.directory.name)
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(scout, 'BASE', self.base))
        self.stack.enter_context(patch.object(scout, 'CACHE', self.base / '.cache'))
        self.stack.enter_context(patch.object(scout, 'STATE_PATH', self.base / 'scout.json'))
        self.stack.enter_context(patch.object(scout.su, 'TRANSCRIPTS_DIR', self.base / 'transcripts'))
        self.stack.enter_context(patch.object(scout.su, 'SUMMARIES_DIR', self.base / 'summaries'))
        self.stack.enter_context(patch.object(scout, 'STATE', {'session': 1, 'videos': {
            name: dict(id=name, title='title '+name, source='channel', date='2026-11-17', status='new', **{'from': 'channel'}) for name in ('a', 'b')}}))
        self.settings = dict(model='haiku', warn_words=10000, language='en')
        self.stack.enter_context(patch.object(scout, 'settings', side_effect=lambda: dict(self.settings)))
        self.stack.enter_context(patch.object(scout, 'ytdlp', return_value='unused'))
        self.stack.enter_context(patch.object(scout.su, 'load_metadata'))
        def transcripts(videos, settings, downloader):
            (self.base / 'transcripts').mkdir(exist_ok=True)
            for v in videos:
                v['transcript'] = '[00:00:01] A transcript about robotics.'
            return videos
        self.stack.enter_context(patch.object(scout.su, 'load_transcripts', side_effect=transcripts))
        self.engine = self.stack.enter_context(patch.dict(scout.ENGINES, claude=lambda p,s: ('{"a":{"thesis":"Robotics is discussed","points":["A point"],"tickers":[],"check":[]}}', {'input_tokens': 45})))
        scout.PREVIEW = {}
        scout.PREPARED = []

    def tearDown(self):
        self.stack.close()
        self.directory.cleanup()

    def test_preview_makes_no_engine_call_then_partial_result_is_retryable(self):
        calls = []
        with patch.dict(scout.ENGINES, claude=lambda p,s: (calls.append(p) or ('{"a":{"thesis":"Robotics"}}', {}))):
            scout.prepare_job(['a', 'b'], 'claude', 'en')
            self.assertEqual(calls, [])
            self.assertEqual(scout.PREVIEW['model_calls'], 1)
            scout.summarize_job(['a', 'b'], 'claude', 'en')
            self.assertEqual(len(calls), 1)
        self.assertEqual(scout.STATE['videos']['a']['status'], 'summarized')
        self.assertEqual(scout.STATE['videos']['b']['status'], 'failed')
        file = scout.STATE['videos']['a']['file']
        self.assertIn('[00:00:01]', (self.base/'transcripts'/f'{file}.txt').read_text())
        self.assertIn('Robotics', (self.base/'summaries'/f'{file}.md').read_text())

    def test_cache_reuse_and_language_invalidation(self):
        scout.prepare_job(['a'], 'claude', 'en')
        scout.summarize_job(['a'], 'claude', 'en')
        scout.prepare_job(['a'], 'claude', 'en')
        self.assertEqual(scout.PREVIEW['model_calls'], 0)
        with patch.dict(scout.ENGINES, claude=lambda *a: self.fail('Cache hit called model')):
            scout.summarize_job(['a'], 'claude', 'en')
        scout.prepare_job(['a'], 'claude', 'Romanian')
        self.assertEqual(scout.PREVIEW['model_calls'], 1)

    def test_word_guard_and_settings_change_block_model(self):
        self.settings['warn_words'] = 1
        with self.assertRaisesRegex(RuntimeError, 'no model called'):
            scout.prepare_job(['a'], 'claude', 'en')
        self.assertFalse(scout.PREVIEW.get('ready'))
        self.settings['warn_words'] = 10000
        scout.prepare_job(['a'], 'claude', 'en')
        self.settings['model'] = 'sonnet'
        with self.assertRaisesRegex(RuntimeError, 'Settings changed'):
            scout.summarize_job(['a'], 'claude', 'en')

    def test_engine_failure_marks_videos_failed(self):
        scout.prepare_job(['a'], 'claude', 'en')
        with patch.dict(scout.ENGINES, claude=lambda *args: (_ for _ in ()).throw(RuntimeError('offline'))):
            with self.assertRaisesRegex(RuntimeError, 'offline'):
                scout.summarize_job(['a'], 'claude', 'en')
        self.assertEqual(scout.STATE['videos']['a']['status'], 'failed')

    def test_missing_ocr_tool_fails_video_without_model_call(self):
        with patch.object(media, 'on_screen', side_effect=RuntimeError('ffmpeg missing')):
            scout.prepare_job(['a'], 'claude', 'en', {'depth': 'ocr'})
        self.assertEqual(scout.STATE['videos']['a']['status'], 'failed')
        self.assertFalse(scout.PREVIEW['ready'])
        self.assertEqual(scout.PREVIEW['model_calls'], 0)

    def test_lowered_word_limit_blocks_previously_prepared_batch(self):
        scout.prepare_job(['a'], 'claude', 'en')
        self.settings['warn_words']=1
        with patch.dict(scout.ENGINES,claude=lambda *args:self.fail('Model called above current word limit')):
            with self.assertRaisesRegex(RuntimeError,'current word limit'):
                scout.summarize_job(['a'],'claude','en')

    def test_search_indexes_transcripts_and_rebuilds_from_files(self):
        directory = self.base / 'transcripts'
        directory.mkdir()
        (directory / 'a.txt').write_text('A nonobvious robotics fact')
        self.assertEqual(search.search(self.base, 'robotics')[0]['path'], 'transcripts/a.txt')
        (self.base / '.cache/search.sqlite3').unlink()
        self.assertEqual(len(search.search(self.base, 'robotics')), 1)
        (directory / 'a.txt').unlink()
        self.assertEqual(search.search(self.base, 'robotics'), [])
        self.assertEqual(search.search(self.base, '" OR *'), [])
