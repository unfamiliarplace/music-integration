from __future__ import annotations
from pathlib import Path
from tinytag import TinyTag
from matching import Matchable
from datetime import datetime
import tools
import progressbar
from functools import total_ordering

EXTS = ['mp3', 'flac', 'wav', 'm4a']

class Library:
    path_base: Path
    tracks: dict[str, Track]
    albums: dict[str, Album]

    def __init__(self: Library, path_base: Path) -> None:
        self.path_base = path_base
        self.tracks = {}
        self.albums = {}
    
    def scan(self: Library) -> None:
        existing = set(t.path for t in self.tracks.values())
        
        filepaths = tools.get_filepaths(self.path_base, exts=EXTS)
        new = filepaths.difference(existing)
        deleted = existing.difference(filepaths)

        if deleted:
            print(f'Forgetting deleted tracks: {len(deleted)}')

            bar = progressbar.ProgressBar()
            for path in bar(deleted):
                key = str(path)

                # Remove track
                t = self.tracks[key]
                del self.tracks[key]

                # Remove track from album; remove album if it has no more tracks
                a = t.album
                del a.tracks[key]
                if not a.tracks:
                    del self.albums[str(a.path)]

        if new:
            print(f'Memorizing new tracks: {len(new)}')

            bar = progressbar.ProgressBar()
            for path in bar(new):
                key = str(path) 

                t = Track.from_path(path)
                self.tracks[key] = t

                par = path.parent
                a = self.albums.setdefault(par, Album(par))

                a.tracks[key] = t
                a.update_data(t)

@total_ordering
class Album(Matchable):
    path: Path
    tracks: dict[str, Track]
    weights = {
        'folder_name': 6,
        'n_tracks': 2,
        'albumartists': 12,
        'artists': 4
    }

    def __init__(self: Album, path: Path) -> None:
        self.path = path
        self.tracks = {}
        self.dt_seen = datetime.now()
        self.set_default_data()

    def set_default_data(self: Album) -> None:
        self.data = {}
        for k in self.weights:
            self.data[k] = None

        self.data['n_tracks'] = 0        
        self.data['folder_name'] = self.path.name
        self.data['artists'] = set()
        self.data['albumartists'] = set()

    def update_data(self: Album, t: Track) -> None:
        self.data['n_tracks'] += 1
        self.data['artists'].add(t.data['artist'])
        self.data['albumartists'].add(t.data['albumartist'])

    def present(self: Album) -> str:
        artist = sorted(self.data['albumartists'])[0]
        return f'{artist} / {self.path.name}'

    def __str__(self: Album) -> str:
        return self.path.name
    
    def __hash__(self: Album) -> int:
        return hash(self.path)

    def __lt__(self: Album, other: object) -> bool:
        if not isinstance(other, Album):
            raise TypeError('Cannot compare Album and non-Album')
        
        return str(self.path.name) < str(other.path.name)
    
    def __eq__(self: Album, other: object) -> bool:
        if not isinstance(other, Album):
            return False
        
        return str(self.path) == str(other.path)

@total_ordering
class Track(Matchable):
    path: Path
    album: Album
    weights = {
        'filename': 5,
        'albumname': 6,
        'title': 6,
        'artist': 2,
        'albumartist': 6,
        'track': 2,
        'composer': 1,
        'genre': 1,
        'duration': 5
    }

    def __init__(self: Track, path: Path, data: dict[str, str]) -> None:
        self.path = path
        self.album = None # Gets set at album creation
        self.dt_seen = datetime.now()
        self.set_default_data()
        self.set_data(data)

    def set_default_data(self: Track) -> None:
        self.data = {}
        for k in self.weights:
            self.data[k] = None

    def set_data(self: Track, data: dict[str, str]) -> None:
        for (k, v) in data.items():
            self.data[k] = v

    @staticmethod
    def from_path(path: Path, fill_gaps: bool=True) -> Track:
        tags = TinyTag.get(path)

        data = {
            'albumname': tags.album,
            'title': tags.title,
            'artist': tags.artist,
            'albumartist': tags.albumartist,
            'track': tags.track,
            'composer': tags.composer,
            'genre': tags.genre,
            'duration': tags.duration
        }

        if fill_gaps and (data['albumartist'] is None):
            data['albumartist'] = data['artist']

        data['filename'] = path.stem

        for (k, v) in data.items():
            data[k] = tools.normalize_title(v)

        return Track(path, data)
    
    def get_siblings(self: Track, include_self: bool=True) -> set[Track]:
        siblings = set(self.album.tracks.values())
        if not include_self:
            siblings.remove(self)
        return siblings

    def __str__(self: Track) -> str:
        return self.path.name
    
    def __hash__(self: Track) -> int:
        return hash(self.path)

    def __lt__(self: Track, other: object) -> bool:
        if not isinstance(other, Track):
            raise TypeError('Cannot compare Track and non-Track')
        
        return str(self.path.name) < str(other.path.name)
    
    def __eq__(self: Album, other: object) -> bool:
        if not isinstance(other, Track):
            return False
        
        return str(self.path) == str(other.path)
    