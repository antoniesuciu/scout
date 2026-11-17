"""A disposable FTS5 index. Saved transcript and Markdown files remain authoritative."""
from pathlib import Path
import re
import sqlite3


def search(base, query, limit=50):
    base = Path(base)
    directory = base / '.cache'
    directory.mkdir(exist_ok=True)
    with sqlite3.connect(directory / 'search.sqlite3', timeout=10) as db:
        db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS documents USING fts5(path UNINDEXED, content)')
        db.execute('CREATE TABLE IF NOT EXISTS versions (path TEXT PRIMARY KEY, stamp INTEGER)')
        known = dict(db.execute('SELECT path, stamp FROM versions'))
        present = {}
        for folder, extension in (('summaries', '*.md'), ('transcripts', '*.txt'), ('notes', '*.md'), ('notes', '*.txt')):
            if (base/folder).is_symlink():
                continue
            for path in (base / folder).glob(extension):
                if path.is_symlink():
                    continue
                relative = str(path.relative_to(base))
                stamp = path.stat().st_mtime_ns
                present[relative] = stamp
                if known.get(relative) != stamp:
                    db.execute('DELETE FROM documents WHERE path = ?', (relative,))
                    db.execute('INSERT INTO documents(path, content) VALUES (?, ?)',
                               (relative, path.read_text(encoding='utf-8')))
                    db.execute('INSERT OR REPLACE INTO versions VALUES (?, ?)', (relative, stamp))
        for missing in known.keys() - present.keys():
            db.execute('DELETE FROM documents WHERE path = ?', (missing,))
            db.execute('DELETE FROM versions WHERE path = ?', (missing,))
        words = re.findall(r'\w+', query[:500])
        if not words:
            return []
        expression = ' AND '.join('"' + word + '"' for word in words)
        return [dict(path=row[0], snippet=row[1]) for row in db.execute(
            "SELECT path, snippet(documents, 1, '', '', '…', 20) FROM documents WHERE documents MATCH ? ORDER BY rank LIMIT ?",
            (expression, min(limit, 100)))]
