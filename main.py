import signal
import json
import os
import threading
from time import sleep
from mpris_server.adapters import MprisAdapter
from mpris_server.base import PlayState, Track, Position, Rate, Volume
from mpris_server.events import EventAdapter
from mpris_server.server import Server
from mpris_server import MetadataObj

import Xlib
import Xlib.display as display
import Xlib.xobject.drawable as drawable
import Xlib.protocol.event as event

import sqlite3
import subprocess

KEYCODE_NEXT = 171
KEYCODE_PLAYPAUSE = 172
KEYCODE_PREVIOUS = 173
KEYCODE_STOP = 174

DISPLAY = display.Display()
ROOT_WINDOW = DISPLAY.screen().root

SIGINT_RCVD = False


class TrackInfo:
    def __init__(self, rid, ptime, tid, info):
        self.rowid = rid
        self.playtime = ptime
        self.trackid = tid
        self.picurl = info['album']['picUrl'] if 'album' in info else ''
        self.name = info['name'] if 'name' in info else ''
        self.albumname = info['album']['albumName'] if 'album' in info else ''
        self.artists = [artist['name'] for artist in info['artists']] if 'artists' in info else []
        self.raw_info = info

    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, TrackInfo):
            return False

        return self.rowid == __value.rowid and self.playtime == __value.playtime and self.trackid == __value.trackid


TRACKINFO = TrackInfo(-1, -1, -1, {})


def get_netease_windows(window: drawable.Window):
    global WINDOW
    candidates = []

    children = window.query_tree().children
    for c in children:
        candidates += get_netease_windows(c)

    c = window.get_wm_class()
    if c is None:
        return candidates

    wClass1, wClass2 = c
    if wClass1 != "cloudmusic.exe":
        return candidates

    wName = window.get_property(Xlib.Xatom.WM_NAME, 0, 0, 100000000)
    val = wName.value
    if ' - ' not in str(val):
        return candidates

    # print(hex(window.id), wClass1, wClass2)

    candidates.append(window)
    return candidates


def sendkey(keycode):
    active_window_id = ROOT_WINDOW.get_full_property(
        DISPLAY.intern_atom('_NET_ACTIVE_WINDOW'), Xlib.X.AnyPropertyType
    ).value[0]

    NETEASE_WINDOW_CANDIDATES = get_netease_windows(ROOT_WINDOW)

    if not NETEASE_WINDOW_CANDIDATES:
        print('No Netease window found')
        return

    isin = active_window_id in [w.id for w in NETEASE_WINDOW_CANDIDATES]
    window = NETEASE_WINDOW_CANDIDATES[1]
    print('Active window:', hex(active_window_id), 'Netease window:', hex(window.id), 'Is in:', isin, 'Sending key:', keycode)

    kwargs = {'time': 0, 'root': 0, 'same_screen': 0, 'child': 0, 'root_x': 0, 'root_y': 0, 'event_x': 0, 'event_y': 0, 'state': 0}

    def send_single_key_press(keycode):
        ev = event.KeyPress(window=window, type=Xlib.X.KeyPress, detail=keycode, **kwargs)
        window.send_event(ev, propagate=False)
        DISPLAY.flush()

    def send_single_key_release(keycode):
        ev = event.KeyRelease(window=window, type=Xlib.X.KeyRelease, detail=keycode, **kwargs)
        window.send_event(ev, propagate=False)
        DISPLAY.flush()

    if isin:
        send_single_key_release(37)  # Left Ctrl
        send_single_key_release(50)  # Left Shift
        send_single_key_release(38)  # Left A

    send_single_key_press(keycode)
    sleep(0.1)
    send_single_key_release(keycode)

    if isin:
        send_single_key_press(37)  # Left Ctrl
        send_single_key_press(50)  # Left Shift
        send_single_key_press(38)  # Left A


class WineNeteaseAdapter(MprisAdapter):
    paused = False

    # Make sure to implement all methods on MprisAdapter, not just metadata()
    def metadata(self) -> MetadataObj:
        metadata = MetadataObj(
            artists=TRACKINFO.artists,
            title=TRACKINFO.name,
            album=TRACKINFO.albumname,
            length=0,
            art_url=TRACKINFO.picurl,
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
    def on_app_event(self):
        self.on_title()

    # and so on


def gettitle(id):
    return subprocess.Popen(["xprop", "-id", str(id), "WM_NAME"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL).communicate()[0].decode("utf-8").strip().split("=")[1].strip()[1:-1]


def timerevent():
    LATEST_TRACK_QUERY = 'SELECT "_rowid_", * FROM "historyTracks" ORDER BY "playtime" DESC LIMIT 1;'
    DRIVE_C_PATH = os.environ['HOME'] + '/.deepinwine/Spark-CloudMusic/drive_c'
    USERNAME = os.environ['USER']
    WEBDB_PATH = f'{DRIVE_C_PATH}/users/{USERNAME}/Local Settings/Application Data/NetEase/CloudMusic/Library/webdb.dat'

    global TRACKINFO

    conn = sqlite3.connect(WEBDB_PATH)
    c = conn.cursor()

    while True:
        c.execute(LATEST_TRACK_QUERY)
        rid, ptime, tid, info = c.fetchone()
        track = TrackInfo(rid, ptime, tid, json.loads(info))

        if TRACKINFO != track:
            TRACKINFO = track
            event_handler.on_app_event()
        else:
            sleep(1)

        if SIGINT_RCVD:
            break


def sigint_handler(signum, frame):
    global SIGINT_RCVD
    SIGINT_RCVD = True
    print()
    print('SIGINT received, exiting...')
    exit(0)


signal.signal(signal.SIGINT, sigint_handler)

threading.Thread(target=timerevent).start()


adapter = WineNeteaseAdapter()
mpris = Server('Wine Netease', adapter=adapter)
event_handler = WineNeteaseEventHandler(root=mpris.root, player=mpris.player)
mpris.loop()
