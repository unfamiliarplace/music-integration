from __future__ import annotations
from track import Track
from typing import Self

class Match:
    track_old: Track
    track_new: Track
    measured: bool
    stats: list[float]
    denom: int
    score: float

    def __init__(self: Match, track_old: Track, track_new: Track) -> None:
        self.track_old = track_old
        self.track_new = track_new

        self.measured = False
        self.stats = []
        self.denom = 0
        self.score = 0.0

        # Not sure which is stupider here, optimizing or not optimizing
        self.measure()

    def measure(self: Match) -> None:

        # No condition because I prefer allowing to remeasure if necessary
        self.stats, self.denom = self.track_old.measure_similarity(self.track_new)
        self.score = sum(self.stats) / self.denom
        self.measured = True
    
    def sig(self: Match) -> str:
        return f'{self.track_old.sig()} + {self.track_new.sig()}'

    def __repr__(self: Match) -> str:
        return f'{self.track_old.sig():<110} {self.score:<.2f}   {self.track_new.sig()}'
    