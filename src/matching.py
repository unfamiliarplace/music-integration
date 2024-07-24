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
    CONFIRMED_UNMATCHED = 4

class Matchable:
    data: dict[str, object]
    weights: dict[str, int]
    ts_seen: int

    def set_default_data(self: Matchable) -> None:
        raise NotImplementedError

class MatchDecision:
    old: Matchable
    new: Matchable
    state: MatchState
    score: float
    ts_made: int
    omit: list[Matchable]

    def __init__(self: MatchDecision, old: Matchable, new: Matchable, state: MatchState, score: float, ts: int=0, omit: dict[str, Matchable]=[]) -> None:
        self.old, self.new = old, new
        self.state, self.score = state, score
        self.ts_made = ts
        self.omit = omit

    @staticmethod
    def remake(d: MatchDecision) -> MatchDecision:
        omit = d.omit
        omit2 = omit
        if omit and not isinstance(omit, dict):
            omit2 = {}

            for v in omit:
                if isinstance(v, str):
                    for t in d.old.tracks.values():
                        if t.path.stem == v:
                            break
                else:
                    t = v
                    
            omit2[str(t.path)] = t
        return MatchDecision(d.old, d.new, d.state, d.score, d.ts_made, omit2)

    def present(self: MatchDecision) -> str:
        # So hackish

        try:
            second_part = ''
            if self.new is not None:
                second_part = f' vs {self.new.present():<80}'
            return f'{self.old.present():<80}{second_part}'
        except:
            second_part = ''
            if self.new is not None:
                second_part = f' vs {str(self.new):<80}'
            return f'{str(self.old):<80}{second_part}'

    def __str__(self: MatchDecision) -> str:

        if self.state is MatchState.UNMATCHED:
            return f'{self.old.present():<80} x has no match (unconfirmed)'

        if self.state is MatchState.CONFIRMED_UNMATCHED:
            return f'{self.old.present():<80} X has no match (confirmed)'
        
        elif self.state is MatchState.MATCHED:
            return f'{self.old.present():<80} = {self.new.present():<80}'
        
        elif self.state is MatchState.PARTIAL:
            return f'{self.old.present():<80} ~ {self.new.present():<80}'
        
        else:
            return f'{self.old.present():<80} ? unknown match'

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
