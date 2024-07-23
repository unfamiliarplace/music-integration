from __future__ import annotations
from pathlib import Path
from library import Album, Library, Track
import matching
import prompts
import random
from tools import _pickle, _unpickle
import tools
from tabulate import tabulate

# God app :')

class App:

    # Constants
    THRESHOLD_CONFIDENT: float = 0.97
    THRESHOLD_PROBABLE: float = 0.80
    THRESHOLD_POSSIBLE: float = 0.65
    FAST_BATCH_SIZE: int = 40
    ALBUM_NAME_LENGTH: int = 60

    PATH_CONFIG: Path = Path('src/config.ini')

    # Configurables
    PATH_LIB_OLD: Path
    PATH_LIB_NEW: Path
    PATH_PICKLES: Path

    PATH_PICKLE_LIB_OLD: Path
    PATH_PICKLE_LIB_NEW: Path
    PATH_PICKLE_DECISIONS: Path

    def load_configuration(self: App) -> None:

        with open(self.PATH_CONFIG, 'r') as f:
            for line in f.readlines():
                k, v = (c.strip() for c in line.split('::'))

                if k == 'BASE_OLD':
                    self.PATH_LIB_OLD = Path(v)
                elif k == 'BASE_NEW':
                    self.PATH_LIB_NEW = Path(v)
                elif k == 'BASE_PICKLES':
                    self.PATH_PICKLES = Path(v)

        if not Path.exists(self.PATH_PICKLES):
            Path.mkdir(self.PATH_PICKLES, exist_ok=True, parents=True)

        # libraries
        self.PATH_PICKLE_LIB_OLD = Path(f'{self.PATH_PICKLES}/lib_old.pickle')
        self.PATH_PICKLE_LIB_NEW = Path(f'{self.PATH_PICKLES}/lib_new.pickle')
        self.PATH_PICKLE_DECISIONS = Path(f'{self.PATH_PICKLES}/decisions.pickle')

#  Functions

def get_libraries() -> tuple[Library]:

    def _get_library(path: Path, path_pickle: Path) -> Library:
        lib = _unpickle(path_pickle, Library(path))
        lib.scan()
        _pickle(lib, path_pickle)
        return lib
    
    print('Scanning old library...')
    old = _get_library(app.PATH_LIB_OLD, app.PATH_PICKLE_LIB_OLD)
    print('Scanning new library...')
    new = _get_library(app.PATH_LIB_NEW, app.PATH_PICKLE_LIB_NEW)

    return old, new

def get_libraries_dev() -> tuple[Library]:
    '''Without pickling'''

    def _get_library(path: Path) -> Library:
        lib = Library(path)
        lib.scan()
        return lib

    print('Scanning old library...')
    old = _get_library(app.PATH_LIB_OLD)
    print('Scanning new library...')
    new = _get_library(app.PATH_LIB_NEW)

    return old, new

def find_best_match(a: matching.Matchable, pool: list[matching.Matchable], allow_unlikely: bool=True) -> tuple[matching.Matchable, float, bool]:
    best = None
    best_score = 0.0
    satisfied = False

    for b in pool:
        score, _, _ = matching.score_similarity(a, b)
        # input(f'{str(b):<70} {score}')

        if score >= app.THRESHOLD_CONFIDENT:
            return b, score, True

        elif (score >= app.THRESHOLD_PROBABLE) or (allow_unlikely and (score >= app.THRESHOLD_POSSIBLE)):
            satisfied = True

        if score > best_score:
            best = b
            best_score = score

    return best, best_score, satisfied

def get_unknown_album_sets() -> tuple[list[matching.MatchDecision], list[Album], list[Album]]:
    decs = _unpickle(app.PATH_PICKLE_DECISIONS, [])
    lib_old, lib_new = get_libraries()
    all_old, all_new = lib_old.albums.copy(), lib_new.albums.copy()

    for dec in decs:
        match dec.state:
            case matching.MatchState.MATCHED:
                del all_old[dec.old.path]
                del all_new[dec.new.path]
            case matching.MatchState.PARTIAL:
                del all_old[dec.old.path]
                del all_new[dec.new.path]
            case matching.MatchState.UNMATCHED:
                del all_old[dec.old.path]

    return decs, set(all_old.values()), set(all_new.values())

def report_progress(n_dec: int, n_old: int, n_new: int) -> None:
    print()
    print(f'Decisions made:       {n_dec}')
    print(f'Old albums undecided: {n_old}')
    print(f'New albums eligible:  {n_new}')
    print()

def print_decisions() -> None:
    decs = _unpickle(app.PATH_PICKLE_DECISIONS, [])
    for dec in decs:
        print(dec)

def undo_decision() -> None:
    decs = _unpickle(app.PATH_PICKLE_DECISIONS, [])
    kw = prompts.p_str('Enter a keyword to search for', allow_blank=True).lower().strip()
    if not kw:
        print('Cancelled')
        return        

    opts = list(filter(lambda d: kw in d.present().lower(), decs))
    if not opts:
        print('None found')
        return

    opt = prompts.p_choice('Choose one to delete, or Enter to cancel', [str(d) for d in opts], allow_blank=True)
    if not opt:
        print('Cancelled')
        return
    else:
        print('Removed')
        decs.remove(opts[opt - 1])

    _pickle(decs, app.PATH_PICKLE_DECISIONS)

def fix_decs() -> None:
    decs = _unpickle(app.PATH_PICKLE_DECISIONS, [])
    news = []
    for d in decs:
        d2 = matching.MatchDecision(d.old, d.new, d.state, d.score, ts=d.ts_made, omit=[])
        news.append(d2)
    _pickle(news, app.PATH_PICKLE_DECISIONS)

def format_track_comparison_row(a: Track, b: Track, score: float) -> list[str]:
    cols = []
    cols.append(a.path.stem)
    cols.append(b.path.stem if b is not None else '')
    cols.append(f'{score:<.2f}')
    return cols

def compare_albums(a: Album, b: Album) -> tuple[matching.MatchState, list[Track]]:
    """Returns a MatchState and Tracks from a that are not matches in b."""
    aligned_tracks = []
    aligned_rows = []
    misaligned_tracks = []
    misaligned_rows = []

    ours = list(a.tracks.values())
    pool = list(b.tracks.values())

    for track in ours:
        best, score, satisfied = find_best_match(track, pool, allow_unlikely=False)

        if not satisfied:
            misaligned_tracks.append(track)
            misaligned_rows.append(format_track_comparison_row(track, best, score))
        else:
            aligned_tracks.append(track)
            aligned_rows.append(format_track_comparison_row(track, best, score))
            pool.remove(best)

    # aligned_rows.sort(key=lambda row: row[2], reverse=True)
    # misaligned_rows.sort(key=lambda row: row[2], reverse=True)

    if not misaligned_rows:
        return matching.MatchState.MATCHED, []

    else:
        print()
        print('Pretty sure about these:')
        print(tabulate(aligned_rows))
        print('Not sure about these:')
        print(tabulate(misaligned_rows))

        p = 'k = accept these judgements; r = revise manually; m = album is a perfect match; x = leave album undecided: '
        choice = input(p).upper().strip()
        while choice not in {'K', 'R', 'M', 'X'}:
            print('Command not recognized')
            choice = input(p).upper().strip()
        
        if choice == 'M':
            aligned_tracks.extend(misaligned_tracks)
            aligned_rows.extend(misaligned_rows)
            misaligned_tracks = []
            misaligned_rows = []

            print('Result after changes:')
            print('Pretty sure about these:')
            print(tabulate(aligned_rows))
            print('Not sure about these:')
            print(tabulate(misaligned_rows))

            return matching.MatchState.MATCHED, []
        
        elif choice == 'K':
            return matching.MatchState.PARTIAL, [m[0] for m in misaligned_rows]
        
        elif choice == 'R':

            revise_a = prompts.p_bool('Revise the ones I think are aligned')
            if revise_a:
                ts_to_remove = []
                rs_to_remove = []

                print('\n'.join([f'{e + 1:>2}.  {row[0]:<80} = {row[1]}' for (e, row) in enumerate(aligned_rows)]))
                flips = input('Enter space-separated numbers to switch to non-matches: ')
                for i in (int(flip) for flip in flips.split()):
                    t = aligned_tracks[i - 1]
                    r = aligned_rows[i - 1]

                    ts_to_remove.append(t)
                    rs_to_remove.append(r)
                    misaligned_tracks.append(t)
                    misaligned_rows.append(r)
                
                for t in ts_to_remove:                    
                    aligned_tracks.remove(t)
                for r in rs_to_remove:
                    aligned_rows.remove(r)

            revise_m = prompts.p_bool('Revise the ones I think are misaligned')
            if revise_m:
                ts_to_remove = []
                rs_to_remove = []

                print('\n'.join([f'{e + 1:>2}.  {row[0]:<80} x {row[1]}' for (e, row) in enumerate(misaligned_rows)]))
                flips = input('Enter space-separated numbers to switch to matches: ')
                for i in (int(flip) for flip in flips.split()):
                    t = misaligned_tracks[i - 1]                    
                    r = misaligned_rows[i - 1]

                    ts_to_remove.append(t)
                    rs_to_remove.append(r)
                    aligned_tracks.append(t)
                    aligned_rows.append(r)
                
                for t in ts_to_remove:      
                    misaligned_tracks.remove(t)
                for r in rs_to_remove:
                    misaligned_rows.remove(r)

            print('Result after changes:')
            print('Pretty sure about these:')
            print(tabulate(aligned_rows))
            print('Not sure about these:')
            print(tabulate(misaligned_rows))
            
            if misaligned_tracks:
                return matching.MatchState.PARTIAL, misaligned_tracks
            else:
                return matching.MatchState.MATCHED, []
        
        elif choice == 'X':
            return matching.MatchState.UNKNOWN, []

def do_matches() -> None:
    decs, old, new = get_unknown_album_sets()
    old = list(old)
    report_progress(len(decs), len(old), len(new))

    print('y = match; n = matchless; q = stop for now; s = save; Enter = no decision.\n')

    n_matched = 0
    i = 0
    while i < len(old):
        a = old[i]
        b, score, _ = find_best_match(a, new)

        if score >= app.THRESHOLD_CONFIDENT:
            p_word = 'CONFIDENT!!'
        elif score >= app.THRESHOLD_PROBABLE:
            p_word = 'LIKELY!!!!!'
        else:
            p_word = 'A STRETCH!!'

        # TODO
        if (a is None) or (b is None):
            i += 1
            continue

        p = f'{a.present():<80} {b.present():<80} {p_word} {score:<.2f} ::: '

        choice = input(p).upper().strip()
        while choice not in {'Y', '', 'N', 'Q', 'S'}:
            print('\nUnrecognized decision.')
            choice = input(p).upper().strip()

        if choice == 'Y':

            state, unmatched_tracks = compare_albums(a, b)
            match state:
                case matching.MatchState.MATCHED:
                    decs.append(matching.MatchDecision(a, b, matching.MatchState.MATCHED, score, tools.ts_now()))
                    new.remove(b)
                    n_matched += 1

                case matching.MatchState.PARTIAL:
                    decs.append(matching.MatchDecision(a, b, matching.MatchState.PARTIAL, score, tools.ts_now(), omit=unmatched_tracks[:]))
                    new.remove(b)
                    n_matched += 1
            
        elif choice == 'N':
            decs.append(matching.MatchDecision(a, b, matching.MatchState.UNMATCHED, score, tools.ts_now()))

        elif choice == 'S':
            report_progress(len(decs), len(old) - n_matched, len(new))
            _pickle(decs, app.PATH_PICKLE_DECISIONS)
            i -= 1
        
        elif choice == 'Q':
            break

        i += 1

    report_progress(len(decs), len(old) - n_matched, len(new))
    _pickle(decs, app.PATH_PICKLE_DECISIONS)

def retry_unmatched() -> None:
    print('Not implemented yet')

def quit():
    exit() # LOL. (Why? So it can be a function object with a __name__)

def run():
    choices = [
        quit,
        do_matches,
        print_decisions,
        undo_decision,
        # fix_decs
        # update_matches,
        # manually_vet_matches,
        # manually_vet_matches_fast,
        # clean_matches,
        # worst_matches,
        # update_match_version,
        # manually_remove_match
    ]

    program = prompts.p_choice('Choose program', [c.__name__ for c in choices], allow_blank=True)
    if program is not None:
        choices[program - 1]()

if __name__ == '__main__':
    app = App()
    app.load_configuration()
    prompts.p_repeat_till_quit(run, c_phrase='run a program')
