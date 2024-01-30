import subprocess
from time import sleep
import Xlib
from mpris_server.adapters import MprisAdapter
from mpris_server.base import PlayState, Track, Position, Rate, Volume
from mpris_server.events import EventAdapter
from mpris_server.server import Server
from mpris_server import MetadataObj

import Xlib.display as display
from Xlib.xobject.drawable import Window
import Xlib.protocol.event as event
from Xlib.ext.xtest import fake_input

KEYCODE_NEXT = 171
KEYCODE_PLAYPAUSE = 172
KEYCODE_PREVIOUS = 173
KEYCODE_STOP = 174

WINDOW = None
DISPLAY = display.Display()


def sendkey(keycode):
    keyword_args = {'time': 0, 'root': 0, 'same_screen': 0, 'child': 0, 'root_x': 0, 'root_y': 0, 'event_x': 0, 'event_y': 0, 'state': 0}
    ev = event.KeyPress(window=WINDOW, type=Xlib.X.KeyPress, detail=keycode, **keyword_args)
    WINDOW.send_event(ev, propagate=False)
    ev = event.KeyRelease(window=WINDOW, type=Xlib.X.KeyRelease, detail=keycode, **keyword_args)
    WINDOW.send_event(ev, propagate=False)
    print('sendkey: ', keycode, 'to', hex(WINDOW.id))
    DISPLAY.sync()


class WineNeteaseAdapter(MprisAdapter):
    paused = False

    # Make sure to implement all methods on MprisAdapter, not just metadata()
    def metadata(self) -> MetadataObj:
        print("query metadata")

        title = gettitle(WINDOW.id)
        if ' - ' in title:
            artist, title = title.split(' - ', 1)
        else:
            artist = ''

        metadata = MetadataObj(
            artists=[artist],
            title=title,
            album='',
            length=0,
        )

        return metadata

    def get_playstate(self) -> PlayState:
        if self.paused:
            return PlayState.PAUSED
        else:
            return PlayState.PLAYING

    def pause(self):
        self.paused = True
        sendkey(KEYCODE_PLAYPAUSE)
        event_handler.on_playpause()

    def resume(self):
        self.paused = False
        sendkey(KEYCODE_PLAYPAUSE)
        event_handler.on_playback()

    def play(self):
        self.paused = False
        sendkey(KEYCODE_PLAYPAUSE)
        event_handler.on_playback()

    def previous(self):
        sendkey(KEYCODE_PREVIOUS)

    def next(self):
        sendkey(KEYCODE_NEXT)

    def stop(self):
        self.paused = True
        sendkey(KEYCODE_STOP)

    def can_control(self) -> bool:
        return True

    def can_go_next(self) -> bool:
        return True

    def can_go_previous(self) -> bool:
        return True

    def can_pause(self) -> bool:
        return True

    def can_play(self) -> bool:
        return True

    # !! below methods are not implemented !!
    def can_seek(self) -> bool:
        return False

    def get_art_url(self, track: int) -> str:
        print('get_art_url: ', track, 'unimplemented')

    def get_current_position(self) -> Position:
        return 0

    def get_next_track(self) -> Track:
        print('get_next_track unimplemented')

    def get_previous_track(self) -> Track:
        print('get_previous_track unimplemented')

    def get_shuffle(self) -> bool:
        return False

    def get_stream_title(self) -> str:
        pass

    def get_volume(self) -> Volume:
        pass

    def is_mute(self) -> bool:
        return False

    def is_playlist(self) -> bool:
        return True

    def is_repeating(self) -> bool:
        return False

    def open_uri(self, uri: str):
        print('open_uri: ', uri, 'unimplemented')

    def set_maximum_rate(self, val: Rate):
        print('set_maximum_rate: ', val, 'unimplemented')

    def set_minimum_rate(self, val: Rate):
        print('set_minimum_rate: ', val, 'unimplemented')

    def set_mute(self, val: bool):
        print('set_mute: ', val, 'unimplemented')

    def set_rate(self, val: Rate):
        print('set_rate: ', val, 'unimplemented')

    def set_repeating(self, val: bool):
        print('set_repeating: ', val, 'unimplemented')

    def set_shuffle(self, val: bool):
        print('set_shuffle: ', val, 'unimplemented')

    def set_volume(self, val: Volume):
        print('set_volume: ', val, 'unimplemented')

    def seek(self, time: Position, track_id):
        print('seek: ', time, track_id, 'unimplemented')


class WineNeteaseEventHandler(EventAdapter):
    # EventAdapter has good default implementations for its methods.
    # Only override the default methods if it suits your app.

    def on_app_event(self, event: str):
        print(event)
        # trigger DBus updates based on events in your app
        if event == 'pause':
            self.on_playpause()

    # and so on


def gettitle(id):
    return subprocess.Popen(["xprop", "-id", str(id), "WM_NAME"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL).communicate()[0].decode("utf-8").strip().split("=")[1].strip()[1:-1]


larger_wid = 0


def try_this_window(window: Window):
    global WINDOW, larger_wid

    children = window.query_tree().children
    for c in children:
        if not try_this_window(c):
            continue

    c = window.get_wm_class()
    if c is None:
        return False

    wClass1, wClass2 = c
    if wClass1 != "cloudmusic.exe":
        return False

    wName = window.get_property(Xlib.Xatom.WM_NAME, 0, 0, 100000000)
    val = wName.value
    if ' - ' not in str(val):
        return False

    print(hex(window.id), wClass1, wClass2, wName, window.get_geometry())

    if larger_wid < window.id:
        larger_wid = window.id
        WINDOW = window

    return True


try_this_window(DISPLAY.screen().root)


if WINDOW is None:
    print("ERROR: window not found")
    exit(1)

print("OK: ", hex(WINDOW.id), "title: ", gettitle(WINDOW.id))
# sendkey(KEYCODE_PLAYPAUSE)

adapter = WineNeteaseAdapter()
mpris = Server('Wine Netease', adapter=adapter)
event_handler = WineNeteaseEventHandler(root=mpris.root, player=mpris.player)
mpris.loop()
