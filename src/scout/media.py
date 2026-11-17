"""Public-link media preparation. No cookies, accounts, APIs or model calls."""
import html
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlsplit, parse_qs
from . import pipeline as pipe


def link_source(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or parsed.port:
        raise ValueError('Paste a public YouTube or Instagram Reel link.')
    host = (parsed.hostname or '').lower()
    if host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'):
        if host == 'youtu.be':
            video_id = parsed.path.strip('/')
        elif parsed.path == '/watch':
            video_id = parse_qs(parsed.query).get('v', [''])[0]
        else:
            match = re.fullmatch(r'/(?:shorts|live|embed)/([A-Za-z0-9_-]{11})/?', parsed.path)
            video_id = match[1] if match else ''
        if re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
            return 'youtube'
        raise ValueError('Paste a YouTube video link, not a channel, playlist or redirect.')
    if host in ('instagram.com', 'www.instagram.com') and re.fullmatch(r'/reels?/[A-Za-z0-9_-]+/?', parsed.path):
        return 'reels'
    raise ValueError('Only YouTube and public Instagram Reel links are supported.')


def tool(name):
    """Optional media tools stay inside the project environment."""
    path = pipe.BASE / '.venv/bin' / name
    if not path.is_file():
        raise RuntimeError(f'{name} is missing from .venv/bin; see README')
    return str(path)


def command(argv, timeout=120):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{Path(argv[0]).name} failed; public media may require login (Scout never logs in or retries)')
    return result.stdout


def metadata(url, downloader):
    source = link_source(url)
    raw = json.loads(command([downloader, '--ignore-config', '-J', '--skip-download', '--no-playlist', '--', url]))
    expected = 'Youtube' if source == 'youtube' else 'Instagram'
    if raw.get('extractor_key') != expected:
        raise ValueError('Link resolved to an unsupported source')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', str(raw.get('id', ''))):
        raise ValueError('Invalid media ID')
    raw['platform'] = source
    return raw


def reel_transcript(video, downloader, settings):
    """Try caption tracks first; use an explicitly installed local STT model otherwise."""
    raw = metadata(video['url'], downloader)
    with tempfile.TemporaryDirectory(prefix='scout-reel-') as directory:
        tracks = raw.get('subtitles') or raw.get('automatic_captions') or {}
        if tracks:
            language = next(iter(tracks))
            command([downloader, '--ignore-config', '--skip-download', '--write-subs', '--write-auto-subs',
                     '--sub-langs', language, '--sub-format', 'vtt', '--no-playlist',
                     '-o', str(Path(directory) / 'media.%(ext)s'), '--', video['url']])
            files = list(Path(directory).glob('*.vtt'))
            if files:
                text = pipe.clean_vtt(files[0].read_text())
                if text:
                    return text
        model = settings.get('whisper_model_path')
        if not model or not Path(model).is_dir() or not importlib.util.find_spec('faster_whisper'):
            raise RuntimeError('No public captions. Install optional local STT and configure whisper_model_path; no model is downloaded automatically.')
        ffmpeg = tool('ffmpeg')
        command([downloader, '--ignore-config', '--no-playlist', '--max-filesize', '100M',
                 '-f', 'bestaudio/best', '-o', str(Path(directory) / 'media.%(ext)s'), '--', video['url']])
        files = list(Path(directory).glob('media.*'))
        if not files:
            raise RuntimeError('No public audio downloaded')
        wav = Path(directory) / 'audio.wav'
        command([ffmpeg, '-nostdin', '-i', str(files[0]), '-vn', '-ar', '16000', '-ac', '1', str(wav)])
        from faster_whisper import WhisperModel
        model = WhisperModel(model, device='cpu', compute_type='int8', local_files_only=True)
        segments, _ = model.transcribe(str(wav), vad_filter=True)
        return '\n'.join(f'[{int(s.start)//3600:02}:{int(s.start)//60%60:02}:{int(s.start)%60:02}] {s.text.strip()}' for s in segments)


def frame_times(transcript, duration, method='periodic', interval=15, manual=(), cap=12):
    if not 5 <= interval <= 300 or not 1 <= cap <= 12:
        raise ValueError('Frame interval must be 5–300 seconds; cap 1–12')
    if not duration or duration <= 0:
        raise ValueError('A known duration is required for frames')
    if method == 'manual':
        times = sorted(set(float(t) for t in manual))
        if len(times) > cap or any(not math.isfinite(t) or t < 0 or t >= duration for t in times):
            raise ValueError('Manual timestamps exceed the duration or frame cap')
    elif method == 'visual':
        times = []
        for h, m, s, text in re.findall(r'\[(\d+):(\d+):(\d+)\]([^\n]*)', transcript):
            if re.search(r'\b(look|chart|screen|shown|graph|here|see)\b', text, re.I):
                times.append(int(h)*3600 + int(m)*60 + int(s))
        times = sorted(set(t for t in times if t < duration))[:cap]
    elif method == 'periodic':
        times = list(range(0, min(int(duration) + 1, interval * cap), interval))
        times = [t for t in times if t < duration]
    else:
        raise ValueError('Unknown frame method')
    return times


def on_screen(video, transcript, downloader, options):
    ffmpeg, tesseract = tool('ffmpeg'), tool('tesseract')
    times = frame_times(transcript, video.get('duration'), **options)
    if not times:
        return []
    with tempfile.TemporaryDirectory(prefix='scout-frames-') as directory:
        directory = Path(directory)
        command([downloader, '--ignore-config', '--no-playlist', '--max-filesize', '150M',
                 '-f', 'worst[ext=mp4]/worst', '-o', str(directory/'video.%(ext)s'), '--', video['url']])
        files = list(directory.glob('video.*'))
        if not files:
            raise RuntimeError('No video downloaded for OCR')
        spoken = set(re.findall(r'\w+', transcript.lower()))
        results, seen = [], set()
        for index, seconds in enumerate(times):
            frame = directory / f'frame-{index}.png'
            command([ffmpeg, '-nostdin', '-ss', str(seconds), '-i', str(files[0]), '-frames:v', '1', str(frame)])
            text = command([tesseract, str(frame), 'stdout']).strip()
            words = set(re.findall(r'\w+', text.lower()))
            if text and text not in seen and words - spoken:
                results.append(dict(seconds=seconds, text=text))
                seen.add(text)
        return results
