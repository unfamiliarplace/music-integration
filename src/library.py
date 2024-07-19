from __future__ import annotations
from pathlib import Path
from fuzzywuzzy import fuzz
from tinytag import TinyTag
from enum import Enum
from tools import get_filepaths, normalize_title
import progressbar

EXTS = ['mp3', 'flac', 'wav', 'm4a']

class MatchState(Enum):
    UNKNOWN = 0
    MATCHED = 1
    PARTIAL = 2
    UNMATCHED = 3

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
        
        filepaths = get_filepaths(self.path_base, exts=EXTS)
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
                if par not in self.albums:
                    a = Album(par)
                    self.albums[par] = a

                a.tracks[key] = t

# class Match:
#     pass

# class TrackMatch:
#     pass

# class AlbumMatch:
#     pass

class Album:
    path: Path
    folder: str
    tracks: dict[str, Track]

    match_state: MatchState

    weight_folder = 5
    weight_n_tracks = 3
    weight_track_alignment = 10

    def __init__(self: Album, path: Path) -> None:
        self.path = path
        self.tracks = {}

class Track:
    path: Path
    match_state: MatchState
    data: dict[str, str]
    album: Album
    weights = {
        'filename': 5,
        'albumname': 6,
        'title': 6,
        'artist': 2,
        'albumartist': 6,
        'track': 2,
        'composer': 1,
        'genre': 1
    }
    weight_duration = 5
    # weight_sum = sum(weights.values()) + weight_duration

    def __init__(self: Track, path: Path, duration: int, data: dict[str, str]) -> None:
        self.path = path
        self.duration = duration
        self.set_default_data()
        self.set_data(data)

    def set_default_data(self: Track) -> None:
        self.data = {}
        for k in self.weights:
            self.data[k] = ''

    def set_data(self: Track, data: dict[str, str]) -> None:
        for (k, v) in data.items():
            self.data[k] = v

    @staticmethod
    def from_path(path: Path, fill_gaps: bool=True) -> Track:
        tags = TinyTag.get(path)
        duration = tags.duration

        data = {
            'albumname': tags.album,
            'title': tags.title,
            'artist': tags.artist,
            'albumartist': tags.albumartist,
            'track': tags.track,
            'composer': tags.composer,
            'genre': tags.genre
        }

        if fill_gaps and (data['albumartist'] is None):
            data['albumartist'] = data['artist']

        data['filename'] = path.stem

        for (k, v) in data.items():
            data[k] = normalize_title(v)


        return Track(path, duration, data)
    
    def get_siblings(self: Track, include_self: bool=True) -> set[Track]:
        siblings = self.album.tracks.copy()
        if not include_self:
            siblings.remove(self)
        return siblings

    def measure_similarity(self: Track, other: Track) -> tuple[float, int]:
        stats = []
        denom = 0

        for key in self.data:
            if None in (self.data[key], other.data[key]):
                continue

            d = self.weights[key]
            n = fuzz.ratio(self.data[key], other.data[key])

            # print(n, self.data[key], other.data[key])

            stats.append((n * d) / 100)
            denom += d
        
        durs = [self.duration, other.duration]
        d = self.weight_duration
        n = (min(durs) / max(durs))
        stats.append((n * d))
        denom += d

        return stats, denom

    def score_similarity(self: Track, other: Track) -> float:        
        stats, denom = self.measure_similarity(other)
        return sum(stats) / denom, stats, denom

    def __str__(self: Track) -> str:
        return self.sig()
    
    def __hash__(self) -> int:
        return hash(self.path)
    