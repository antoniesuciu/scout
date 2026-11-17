import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import unittest
from scout.desktop import is_local_navigation

class NativeNavigationTests(unittest.TestCase):
    def test_only_this_app_origin_stays_in_embedded_window(self):
        origin='http://127.0.0.1:8765'
        self.assertTrue(is_local_navigation(origin+'/api/library',origin))
        for target in ('https://youtube.com/watch?v=abc','file:///etc/passwd','javascript:evil()',
                       'http://127.0.0.1:8766','http://127.0.0.1:8765.evil.example'):
            self.assertFalse(is_local_navigation(target,origin),target)

class NativeWindowControlTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import MagicMock
        self.window=MagicMock();self.gtk=MagicMock();self.gdk=MagicMock()
        self.gtk.get_current_event_time.return_value=123
    def test_native_buttons_dispatch_without_arbitrary_commands(self):
        from scout.desktop import window_action
        for action,method in [('minimize','iconify'),('close','close')]:
            self.assertTrue(window_action(self.window,action,{},self.gtk,self.gdk))
            getattr(self.window,method).assert_called_once()
        self.assertFalse(window_action(self.window,'shell',{'command':'anything'},self.gtk,self.gdk))
    def test_maximize_toggles_and_drag_resize_validate_coordinates(self):
        from scout.desktop import window_action
        self.window.is_maximized.return_value=False
        window_action(self.window,'maximize',{},self.gtk,self.gdk);self.window.maximize.assert_called_once()
        self.window.is_maximized.return_value=True
        window_action(self.window,'maximize',{},self.gtk,self.gdk);self.window.unmaximize.assert_called_once()
        window_action(self.window,'drag',dict(x=20,y=30),self.gtk,self.gdk)
        self.window.begin_move_drag.assert_called_once_with(1,20,30,123)
        window_action(self.window,'resize',dict(x=20,y=30),self.gtk,self.gdk)
        self.window.begin_resize_drag.assert_called_once()
        self.assertFalse(window_action(self.window,'drag',dict(x='bad',y=30),self.gtk,self.gdk))
