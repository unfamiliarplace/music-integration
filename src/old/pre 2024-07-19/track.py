from __future__ import annotations
from pathlib import Path
from fuzzywuzzy import fuzz
from tinytag import TinyTag

class Track:
    path: Path
    data: dict[str, str]
    weights = {
        'filename': 5,
        'album': 6,
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
            'album': tags.album,
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
            data[k] = Track.norm(v)


        return Track(path, duration, data)
    
    @staticmethod
    def norm(s: object) -> str:
        s = str(s)

        if ' [' in s:
            s = s[:s.rfind(' [')] # eliminate [Jackson Browne] and so forth

        s = ''.join(c for c in s if c.isalnum())
        s = s.casefold()

        return s
    
    @staticmethod
    def sig_static(path: Path) -> str:
        """lol... needs a refactoring to remove this crap."""
        return str(path)
    
    def sig(self: Track) -> str:
        return Track.sig_static(self.path)

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
    