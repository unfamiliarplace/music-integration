
import datetime
import pickle
from pathlib import Path

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

def ts_now() -> int:
    return int(datetime.datetime.timestamp(datetime.datetime.now()) * 1_000)
