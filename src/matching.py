from __future__ import annotations
from enum import Enum
from numbers import Number
from typing import Iterable
from fuzzywuzzy import fuzz

class MatchState(Enum):
    UNKNOWN = 0
    MATCHED = 1
    PARTIAL = 2
    UNMATCHED = 3

class Matchable:
    data: dict[str, object]
    weights: dict[str, int]

    def set_default_data(self: Matchable) -> None:
        raise NotImplementedError

class MatchDecision:
    old: Matchable
    new: Matchable
    state: MatchState
    score: float

    def __init__(self: MatchDecision, old: Matchable, new: Matchable, state: MatchState, score: float) -> None:
        self.old, self.new = old, new
        self.state, self.score = state, score

    def __str__(self: MatchDecision) -> str:

        if self.state is MatchState.UNMATCHED:
            return f'{self.old.present():<80} x has no match'
        
        elif self.state is MatchState.MATCHED:
            return f'{self.old.present():<80} = {self.new.present():<80}'
        
        else:
            return f'{self.old.present():<80} ? unknown or partial match'

def measure_similarity(m1: Matchable, m2: Matchable) -> tuple[tuple[float], int]:
    stats = []
    denom = 0

    for key in m1.data:
        a, b = m1.data[key], m2.data[key]
        if None in (a, b):
            continue
        
        n = compare(a, b)
        d = m1.weights[key]
        stats.append(n * d)
        denom += d

    return stats, denom

def score_similarity(m1: Matchable, m2: Matchable) -> tuple[float, tuple[float], int]:       
    stats, denom = measure_similarity(m1, m2)
    return sum(stats) / denom, stats, denom

def compare(a: object, b: object) -> float:
    if isinstance(a, str):
        n = compare_strings(a, b)
    elif isinstance(a, Number):
        n = compare_numbers(a, b)
    elif isinstance(a, Iterable):
        n = compare_iterables(a, b)
    else:
        raise TypeError(f'trying to compare {a}, type {type(a)}')

    return n

def compare_strings(a: str, b: str) -> float:
    return fuzz.ratio(a, b) / 100

def compare_numbers(a: Number, b: Number) -> float:
    nums = sorted([a, b])    
    return nums[0] / nums[1]

def compare_iterables(a: Iterable, b: Iterable) -> float:
    if 0 in {len(a), len(b)}:
        return 0.0
    
    score = 0.0

    for a_sub in a:
        score += max(compare(a_sub, b_sub) for b_sub in b)
    for b_sub in b:
        score += max(compare(b_sub, a_sub) for a_sub in a)

    return score / (len(a) + len(b))

# class Match:
#     track_old: Track
#     track_new: Track
#     measured: bool
#     stats: list[float]
#     denom: int
#     score: float
#     manually_scored: bool

#     def __init__(self: Match, track_old: Track, track_new: Track) -> None:
#         self.track_old = track_old
#         self.track_new = track_new

#         self.measured = False
#         self.stats = []
#         self.denom = 0
#         self.score = 0.0

#         self.manually_scored = False

#         # Not sure which is stupider here, optimizing or not optimizing
#         self.measure()

#     def measure(self: Match) -> None:

#         # No condition because I prefer allowing to remeasure if necessary
#         self.stats, self.denom = self.track_old.measure_similarity(self.track_new)
#         self.score = sum(self.stats) / self.denom
#         self.measured = True

#     def manually_score(self: Match, score: bool) -> None:
#         self.manually_scored = True
#         self.score = float(100 * score)

#     @staticmethod
#     def sig_static(track_old: Track, track_new: Track) -> str:
#         return f'{track_old.sig()} + {track_new.sig()}'
    
#     def sig(self: Match) -> str:
#         return Match.sig_static(self.track_old, self.track_new)

#     def __repr__(self: Match) -> str:
#         return f'{self.track_old.sig():<110} {self.score:<.2f}   {self.track_new.sig()}'
    