import sqlite3
import json
import pathlib
import mutagen
import os
import shutil

class TrackFileMatcher(object):
    def __init__(self, dir):
        self.dir = dir
        self.files = []
        self.files_id3 = {}

        self.load_files()
        self.load_files_id3()

    def load_files(self):
        p = pathlib.Path(self.dir)
        fs = p.glob('*')
        files = [f.name for f in fs]
        files = filter(lambda x: not x.endswith('.ncm'), files)
        self.files = list(files)

    def _get_file_id3(self, file_name):
        info = {}
        f = mutagen.File(os.path.join(self.dir, file_name))
        if f:
            for k in f.keys():
                if k != 'APIC:':
                    info[k] = str(f[k])

        return info

    def load_files_id3(self):
        files_id3 = {}
        for fn in self.files:
            try:
                files_id3[fn] = self._get_file_id3(fn)
            except Exception as e:
                print(e)
                continue

        self.files_id3 = files_id3

    def _filename_match(self, song_name, file_name):
        bits = file_name.split(' - ')
        for b in bits:
            if song_name in b:
                return True

        return False

    def _id3_match(self, song_name, file_name):
        info = self.files_id3.get(file_name, None)
        if info:
            tit2 = info.get('TIT2', '')
            return tit2 == song_name

    def id3_match(self, song_name):
        matchs = []
        for file_name in self.files:
            if self._id3_match(song_name, file_name):
                matchs.append(file_name)

        return matchs

    def fn_match(self, song_name):
        matchs = []
        for file_name in self.files:
            if self._filename_match(song_name, file_name):
                matchs.append(file_name)

        return matchs


    def match(self, song_name):
        # try id3 match
        id3_matchs = self.id3_match(song_name)
        if id3_matchs:
            return id3_matchs

        # try file name match
        fn_matchs = self.fn_match(song_name)
        fn_id3_matchs = []
        if len(fn_matchs) == 1:
            return fn_matchs
        else:
            # try to reduce by id3 match
            for fn in fn_matchs:
                if self._id3_match(song_name, fn):
                    fn_id3_matchs.append(fn)

        if fn_id3_matchs:
            return fn_id3_matchs
        else:
            return fn_matchs
            

class NeteaseMusic(object):
    def __init__(self, fn='/Users/shn7798/sqlite_storage.sqlite3', song_dir='/Users/shn7798/Music/网易云音乐'):
        self.db = sqlite3.connect(fn)
        self.playlists = []
        self.matcher = TrackFileMatcher(song_dir)
        self.song_dir = song_dir

    def load_playlists(self):
        cur = self.db.execute('select pl.playlist from web_playlist pl')

        pls = []
        for row in cur:
            data = json.loads(row[0])
            pl = {
                'id': data['id'],
                'name': data['name'],
                'subscribed_count': data['subscribedCount'],
    #            'creator_name': data['creator']['nickname'],
    #            'creator_userid': data['pcExtData']['userPoint']['userId'],
                'creator_userid': data['creator']['userId'],
            }


            pls.append(pl)

        self.playlists = pls


    def get_tracks(self, pid):
        cur = self.db.execute("select tr.track from web_playlist_track pltr, web_track tr where pltr.pid = '%s' and pltr.tid = tr.tid" % str(pid))
        return [json.loads(r[0]) for r in cur]


    def search_playlist(self, name):
        if not self.playlists:
            self.load_playlists()

        for pl in self.playlists:
            if name in pl['name']:
                return pl

    def search_playlist_files(self, name):
        pl = self.search_playlist(name)
        if not pl:
            return []

        tracks = self.get_tracks(pl['id'])
        print('playlist: %s, songs: %d' % (pl['name'], len(tracks)))

        pl_files = []
        for tr in tracks:
            files = self.matcher.match(tr['name'])
            print('song(%d): %s: %s' % (len(files), tr['name'],  str(files)))
            pl_files.extend(files)

        return list(set(pl_files))

    def export_playlist_files(self, name, out_path):
        if not os.path.exists(out_path):
            os.makedirs(out_path, exist_ok=True)

        files = self.search_playlist_files(name)
        for fn in files:
            print('copy %s' % fn)
            src = os.path.join(self.song_dir, fn)
            dst = os.path.join(out_path, fn)
            if not os.path.exists(dst):
                shutil.copy(src, dst)


