import os
from shutil import copy2
from pathlib import Path
import unicodedata

DIR_SEP = '/'
DIR_SRC = '4_to_integrate'
DIR_CMP = '1_processed'
DIR_OUT = '77_integrating'

EXT_SEP = '.'
EXTS = ('mp3', 'm4a', 'mp4', 'wav', 'flac', 'aac')

REPORT = 25

def has_good_ext(fname: str) -> bool:
    return any([fname.endswith(x) for x in EXTS])

def normalize(s: str) -> str:

    # Remove extension
    s = s[:s.rfind(EXT_SEP)]

    # Replace unwanted characters
    s = s.replace('-', '').replace('!', '').replace(',', '')
    s = s.replace("'", '').replace('&', 'and').replace('  ', ' ')
    s = s.replace('`', '')

    # Remove accents
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode()

    # Remove [artist] comments
    if '[' in s:
        s = s[:s.find('[')]

    # Strip and lowercase
    s = s.strip().lower()
    
    return s

def path_pieces(p: str) -> list:
    return list(filter(lambda x: x is not '', p.split(DIR_SEP)))

def from_parent(path: str, n: int=1) -> str:
    pieces = path_pieces(path)
    pieces.reverse()
    pieces = pieces[:n]
    pieces.reverse()
    return DIR_SEP.join(pieces)

def prepend_path(path: str, sub: str) -> str:
    return f'{path}{DIR_SEP}{sub}'

def replace_base(path: str, new_base: str) -> str:
    pieces = [new_base] + path_pieces(path)[1:]
    return DIR_SEP.join(pieces)

def get_songs(path: str, songs: dict={}) -> list:

    walk = list(os.walk(path))[0]
    _, dirs, files = walk

    files = filter(has_good_ext, files)
    parent = from_parent(path, 2)
    for f in files:
        f_key = normalize(prepend_path(parent, f))
        songs[f_key] = prepend_path(path, f)
        # songs.setdefault(f_key, []).append(prepend_path(path, f))

    for d in dirs:
        get_songs(prepend_path(path, d), songs)
    
def is_not_in(f: str, d: dict) -> bool:
    return f not in d

def get_unaccounted(old: dict, new: dict) -> iter:
    return filter(lambda s: s not in new, old)

def copy_unaccounted(old: dict, unaccounted: iter):

    n = 0
    total = len(unaccounted)

    print(f'{total} songs to copy')
        
    for k in unaccounted:
        orig = old[k]
        dest = replace_base(orig, DIR_OUT)

        path = Path(dest[:dest.rfind(DIR_SEP)])
        path.mkdir(parents=True, exist_ok=True)
        
        copy2(orig, dest)
        n += 1

        if not n % REPORT:
            print(f'Copied {n} of {total}...')

    print(f'Copied {n}. Done!')
    

def run():
    old, new = {}, {}
    get_songs(DIR_SRC, old)
    get_songs(DIR_CMP, new)

    unaccounted = list(get_unaccounted(old, new))
#   print(len(unaccounted))
    copy_unaccounted(old, unaccounted)
    
##    for key in old:
##        if key not in new:
##            print(key)
    

    
##    for k, v in new.items():
##        if len(v) > 1:
##            vs = '\n'.join(v)
##            print(f'k: {k}\nv:\n{vs}\n')
    

if __name__ == '__main__':
    run()
