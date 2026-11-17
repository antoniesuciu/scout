"""Optional Ubuntu native window over the same Scout interface. No frontend rewrite."""
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit


def runtime():
    try:
        import gi
    except ImportError:
        # Explicit bridge to Ubuntu's already-installed OS GUI runtime, not a global venv change.
        bindings = Path('/usr/lib/python3/dist-packages')
        if str(bindings) not in sys.path:
            sys.path.append(str(bindings))
        try:
            import gi
        except ImportError:
            raise RuntimeError('Desktop mode needs Ubuntu GTK3/WebKit2 and python3-gi. Browser mode remains ./scout.') from None
    gi.require_version('Gtk','3.0')
    gi.require_version('WebKit2','4.1')
    from gi.repository import Gtk, WebKit2, Gio, GLib, Gdk
    GLib.set_prgname('scout')  # window class / Wayland app id must match scout.desktop to get the dock icon
    if not Gtk.init_check()[0]:
        raise RuntimeError('Desktop display is inaccessible. Run ./scout --desktop from your graphical Ubuntu session, or use ./scout for browser mode.')
    return Gtk,WebKit2,Gio,GLib,Gdk


def is_local_navigation(url, origin):
    destination, local = urlsplit(url), urlsplit(origin)
    return (destination.scheme,destination.netloc)==(local.scheme,local.netloc)


def window_action(window,action,payload,Gtk,Gdk):
    """The native bridge exposes window controls only, never filesystem/shell access."""
    if action=='minimize':
        window.iconify()
    elif action=='maximize':
        window.unmaximize() if window.is_maximized() else window.maximize()
    elif action=='close':
        window.close()
    elif action in ('drag','resize'):
        x,y=payload.get('x'),payload.get('y')
        if type(x) not in (int,float) or type(y) not in (int,float) or not -100000<=x<=100000 or not -100000<=y<=100000:
            return False
        arguments=(1,int(x),int(y),Gtk.get_current_event_time())
        if action=='drag':
            window.begin_move_drag(*arguments)
        else:
            window.begin_resize_drag(Gdk.WindowEdge.SOUTH_EAST,*arguments)
    else:
        return False
    return True


APP_ID='io.scout.Scout'  # must equal the installed .desktop file name for the dock icon


def run(url, *, busy, on_close, bindings=None):
    """One Scout window per user: a second launch hands over to the first via D-Bus and exits."""
    Gtk,WebKit2,Gio,GLib,Gdk = bindings or runtime()
    application=Gtk.Application(application_id=APP_ID)
    opened=[]
    def activate(application):
        if opened:
            opened[0].present()
            return
        opened.append(build(application,url,busy,on_close,Gtk,WebKit2,Gio,GLib,Gdk))
    application.connect('activate',activate)
    application.run(None)


def build(application,url,busy,on_close,Gtk,WebKit2,Gio,GLib,Gdk):
    window = Gtk.Window(title='Scout')
    application.add_window(window)
    window.set_decorated(False)
    window.set_default_size(1280,850)
    window.set_size_request(400,500)
    icon=Path(__file__).resolve().parents[2]/'assets/icons/scout-256.png'
    if icon.is_file():
        window.set_icon_from_file(str(icon))
    manager=WebKit2.UserContentManager()
    manager.register_script_message_handler('scout')
    view=WebKit2.WebView.new_with_user_content_manager(manager)
    def message(manager,result):
        try:
            payload=json.loads(result.get_js_value().to_string())
            if isinstance(payload,dict):
                window_action(window,payload.get('action'),payload,Gtk,Gdk)
        except (ValueError,TypeError):
            pass
    manager.connect('script-message-received::scout',message)
    window.add(view)
    def decide_policy(webview,decision,kind):
        if kind not in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION,WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
            return False
        destination = decision.get_navigation_action().get_request().get_uri()
        if is_local_navigation(destination,url):
            return False
        decision.ignore()
        if urlsplit(destination).scheme in ('http','https'):
            Gio.AppInfo.launch_default_for_uri(destination,None)
        return True
    def download_started(context,download):
        def destination(download,suggested):
            chooser=Gtk.FileChooserNative.new('Save Scout document',window,Gtk.FileChooserAction.SAVE,'Save','Cancel')
            chooser.set_current_name(Path(suggested).name)
            chooser.set_do_overwrite_confirmation(True)
            if chooser.run()==Gtk.ResponseType.ACCEPT:
                download.set_destination(Path(chooser.get_filename()).absolute().as_uri())
            else:
                download.cancel()
            chooser.destroy()
            return True
        download.connect('decide-destination',destination)
    def close(window,event):
        if busy():
            dialog=Gtk.MessageDialog(transient_for=window,modal=True,message_type=Gtk.MessageType.QUESTION,
                                    buttons=Gtk.ButtonsType.YES_NO,text='Stop the active job and close Scout?')
            response=dialog.run();dialog.destroy()
            if response!=Gtk.ResponseType.YES:
                return True
        on_close()
        return False  # the application exits once its only window is gone
    def keypress(widget,event):
        if event.keyval==Gdk.KEY_F5 or (event.state&Gdk.ModifierType.CONTROL_MASK and event.keyval==Gdk.KEY_r):
            view.reload();return True
        if event.state&Gdk.ModifierType.CONTROL_MASK and event.keyval==Gdk.KEY_w:
            window.close();return True
        return False
    window.connect('key-press-event',keypress)
    view.connect('decide-policy',decide_policy)
    view.get_context().connect('download-started',download_started)
    window.connect('delete-event',close)
    view.load_uri(url)
    window.show_all()
    return window
