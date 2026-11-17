from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from scout import library,search

class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.base=Path(self.directory.name)
    def tearDown(self):self.directory.cleanup()

    def test_note_creation_edit_and_listing_without_inbox_state(self):
        library.write(self.base,'notes/My note.md','# Hello\n\nA robotics note')
        documents=library.listing(self.base)
        self.assertEqual(documents[0]['key'],'notes/My note.md')
        self.assertTrue(library.read(self.base,documents[0]['key'])['markdown'])
        library.write(self.base,'notes/My note.md','# Revised')
        self.assertEqual(library.read(self.base,documents[0]['key'])['text'],'# Revised')

    def test_library_rejects_traversal_and_symlinks_and_export_overwrites(self):
        for key in ('../settings.json','notes/../../secret.md','notes/.hidden.md','notes/a.exe','unknown/a.md'):
            with self.assertRaises(ValueError):library.write(self.base,key,'bad')
        (self.base/'notes').mkdir()
        (self.base/'outside.md').write_text('private')
        (self.base/'notes/link.md').symlink_to(self.base/'outside.md')
        with self.assertRaises(ValueError):library.read(self.base,'notes/link.md')
        self.assertEqual(library.listing(self.base),[])
        with self.assertRaisesRegex(ValueError,'Only personal notes'):
            library.write(self.base,'summaries/export.md','overwrite')

    def test_search_includes_markdown_and_plain_notes(self):
        library.write(self.base,'notes/first.md','Robotics notes')
        library.write(self.base,'notes/second.txt','Robotics details')
        self.assertEqual({item['path'] for item in search.search(self.base,'robotics')},
                         {'notes/first.md','notes/second.txt'})
        self.assertEqual(len(search.search(self.base,'robotics')),2)
