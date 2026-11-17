"""File library independent of inbox state. Names identify documents, never arbitrary paths."""
from datetime import datetime
from pathlib import Path
import re

FOLDERS = {'summaries': ('.md',), 'transcripts': ('.txt',), 'notes': ('.md','.txt')}


def document_path(base, key, must_exist=True):
    parts = key.split('/') if isinstance(key,str) else []
    if len(parts) != 2 or parts[0] not in FOLDERS or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,180}', parts[1]):
        raise ValueError('Invalid document name.')
    folder = Path(base) / parts[0]
    path = folder / parts[1]
    if folder.is_symlink() or path.is_symlink() or path.suffix.lower() not in FOLDERS[parts[0]]:
        raise ValueError('Unsupported document.')
    if must_exist and not path.is_file():
        raise ValueError('Document not found.')
    return path


def listing(base):
    result = []
    for folder, extensions in FOLDERS.items():
        directory = Path(base) / folder
        if directory.is_symlink():
            continue
        for path in directory.glob('*'):
            if not path.is_file() or path.is_symlink() or path.suffix.lower() not in extensions:
                continue
            key = f'{folder}/{path.name}'
            try:
                document_path(base,key)
            except ValueError:
                continue
            info = path.stat()
            result.append(dict(key=key, name=path.name, kind=folder, bytes=info.st_size,
                               modified=datetime.fromtimestamp(info.st_mtime).isoformat(timespec='seconds')))
    return sorted(result, key=lambda item: item['modified'], reverse=True)


def read(base, key):
    path = document_path(base,key)
    if path.stat().st_size > 2_000_000:
        raise ValueError('Document exceeds the 2 MB reader limit; open it externally.')
    return dict(key=key, text=path.read_text(encoding='utf-8'), markdown=path.suffix.lower()=='.md')


def write(base, key, text):
    path = document_path(base,key,must_exist=False)
    if not isinstance(text,str) or len(text.encode('utf-8')) > 2_000_000:
        raise ValueError('Notes must be text under 2 MB.')
    if key.split('/')[0] != 'notes':
        raise ValueError('Only personal notes are editable; exported summaries/transcripts are preserved.')
    path.parent.mkdir(exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(text,encoding='utf-8')
    temporary.replace(path)
    return read(base,key)
