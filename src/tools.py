
import pickle
from pathlib import Path
from fuzzywuzzy import fuzz

def _pickle(o: object, path: Path) -> None:
    with open(path, 'wb') as f:
        pickle.dump(o, f)

def _unpickle(path: Path, default: object=None) -> object:
    if Path.exists(path):
        with open(path, 'rb') as f:
            return pickle.load(f)
    else:
        return default

def get_filepaths(path_base: Path, exts: list[str]=[]) -> set[Path]:
    result = set()
    for path in Path.rglob(path_base, '*'):
        if (not exts) or (path.suffix.strip('.').lower() in exts):
            result.add(path)
    return result

def normalize_title(s: str) -> str:
    s = str(s)

    if ' [' in s:
        s = s[:s.rfind(' [')] # eliminate [Jackson Browne] and so forth

    s = ''.join(c for c in s if c.isalnum())
    s = s.casefold()

    return s

def compare(a: object, b: object) -> float:
    if isinstance(a, str):
        n = compare_strings(a, b)
    elif isinstance(a, int) or isinstance(a, float):
        n = compare_numbers(a, b)

    return n

def compare_strings(a: str, b: str) -> float:
    return fuzz.ratio(a, b) / 100

def compare_numbers(a: float, b: float) -> float:
    nums = sorted([a, b])    
    return nums[0] / nums[1]
