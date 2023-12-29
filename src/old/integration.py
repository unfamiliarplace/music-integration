import os
from shutil import copy2
from pathlib import Path
import unicodedata

DIR_SEP = '/'
DIR_BASE = f'D:{DIR_SEP}Music'
DIR_NEW = f'{DIR_BASE}{DIR_SEP}1_processed'
DIR_OLD = f'{DIR_BASE}{DIR_SEP}88_old_music'
DIR_OUT = f'{DIR_BASE}{DIR_SEP}77_integrating'

EXT_SEP = '.'
EXTS = ('mp3', 'm4a', 'mp4', 'wav', 'flac', 'aac')

REPORT = 25

class Song:
    def __init__(self, path: str):     
        self.path = path
        
        pieces = path_pieces(path)
        
        self.name = pieces[-1][:pieces[-1].rfind(EXT_SEP)]
        self.album = pieces[-2]
        self.artist = pieces[1]  

        self.name = normalize(self.name)
        self.album = normalize(self.album)
        self.artist = normalize(self.artist)

    def __repr__(self) -> str:
        return f'{self.artist}: {self.name}'

    def __eq__(self, other) -> bool:
        return (self.name == other.name) and (self.artist == other.artist)
            
        
def has_good_ext(fname: str) -> bool:
    return any([fname.endswith(x) for x in EXTS])

def normalize(s: str) -> str:

    # Remove extension
    s = s[:s.rfind(EXT_SEP)] if EXT_SEP in s else s

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

def prepend_path(path: str, sub: str) -> str:
    return f'{path}{DIR_SEP}{sub}'

def replace_base(path: str, old_base: str, new_base: str) -> str:
    return path.replace(old_base, new_base)

def get_songs(path: str, songs: list=[]) -> list:

    walk = list(os.walk(path))[0]
    _, dirs, files = walk

    for f in filter(has_good_ext, files):
        songs.append(Song(prepend_path(path, f)))

    for d in dirs:
        get_songs(prepend_path(path, d), songs)

def get_artist_song_sets(path: str, songs: dict={}) -> dict:

    walk = list(os.walk(path))[0]
    _, dirs, files = walk

    for f in filter(has_good_ext, files):
        song = Song(prepend_path(path, f))
        key = f'{song.artist}/{song.name}'
        songs.setdefault(key, []).append(song)

    for d in dirs:
        get_artist_song_sets(prepend_path(path, d), songs)

def get_unaccounted(old: list, new: list) -> iter:
    return filter(lambda s: s not in new, old)

def copy_unaccounted(unaccounted: iter):

    n, total = 0, len(unaccounted)
    
    print(f'{total} songs to copy')
        
    for song in unaccounted:
        orig = song.path
        dest = replace_base(orig, DIR_OLD, DIR_OUT)

        path = Path(dest[:dest.rfind(DIR_SEP)])
        path.mkdir(parents=True, exist_ok=True)
        
        copy2(orig, dest)
        n += 1

        if not n % REPORT:
            print(f'Copied {n} of {total}...')

    print(f'Copied {n}. Done!')
    

def run():
    
    old, new = [], []
    get_songs(DIR_OLD, old)
    get_songs(DIR_NEW, new)

    print(f'n old: {len(old)}')
    print(f'n new: {len(new)}')

    unaccounted = list(get_unaccounted(old, new))
    
    print(f'n uac: {len(unaccounted)}')
    copy_unaccounted(unaccounted)
    
    

if __name__ == '__main__':
    x = run()
