from __future__ import annotations
from pathlib import Path
from library import Album, Library, Track, EXTS
import matching
import prompts
import os
import shutil
from tools import _pickle, _unpickle
import tools
from tabulate import tabulate
import re
import progressbar

# God app :')

class App:

    # Constants
    THRESHOLD_CONFIDENT: float = 0.97
    THRESHOLD_PROBABLE: float = 0.85
    THRESHOLD_POSSIBLE: float = 0.65
    FAST_BATCH_SIZE: int = 40
    ALBUM_NAME_LENGTH: int = 60

    PATH_CONFIG: Path = Path('src/config.ini')

    RE_UNKNOWN = r'Y|N|E|Q|S'
    RE_UNMATCHED = r'(N)|(M \d+)|(E \d+)|(Q)|(S)'
    RE_COMPARE = r'K|R|M|X|N'
    
    # Configurables
    PATH_LIB_OLD: Path
    PATH_LIB_NEW: Path
    PATH_LIB_CULL: Path
    PATH_PICKLES: Path

    PATH_PICKLE_LIB_OLD: Path
    PATH_PICKLE_LIB_NEW: Path
    PATH_PICKLE_DECISIONS: Path
    PATH_PICKLE_DECISIONS_BACKUP: Path

    PATH_PICKLE_ESCAPEES: Path

    def load_configuration(self: App) -> None:

        with open(self.PATH_CONFIG, 'r') as f:
            for line in f.readlines():
                k, v = (c.strip() for c in line.split('::'))

                if k == 'BASE_OLD':
                    self.PATH_LIB_OLD = Path(v)
                elif k == 'BASE_NEW':
                    self.PATH_LIB_NEW = Path(v)
                elif k == 'BASE_CULL':
                    self.PATH_LIB_CULL = Path(v)
                elif k == 'BASE_PICKLES':
                    self.PATH_PICKLES = Path(v)

        if not Path.exists(self.PATH_PICKLES):
            Path.mkdir(self.PATH_PICKLES, exist_ok=True, parents=True)

        # libraries
        self.PATH_PICKLE_LIB_OLD = Path(f'{self.PATH_PICKLES}/lib_old.pickle')
        self.PATH_PICKLE_LIB_NEW = Path(f'{self.PATH_PICKLES}/lib_new.pickle')
        self.PATH_PICKLE_DECISIONS = Path(f'{self.PATH_PICKLES}/decisions.pickle')
        self.PATH_PICKLE_DECISIONS_BACKUP = Path(f'{self.PATH_PICKLES}/decisions_backup.pickle')
        self.PATH_PICKLE_ESCAPEES = Path(f'{self.PATH_PICKLES}/escapees.pickle')

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

def find_best_match_strict(a: matching.Matchable, pool: list[matching.Matchable]) -> tuple[matching.Matchable, float]:
    best = None
    best_score = 0.0

    for b in pool:
        score, _, _ = matching.score_similarity(a, b)

        if score >= app.THRESHOLD_PROBABLE:
            best = b
            best_score = score

    return best, best_score

def find_best_match(a: matching.Matchable, pool: list[matching.Matchable], allow_unlikely: bool=True, newer_only: bool=False, dec_ts: int=0) -> tuple[matching.Matchable, float, bool]:
    best = None
    best_score = 0.0
    satisfied = False

    for b in pool:

        if newer_only:
            print(b.ts_seen)
            print(dec_ts)
            print()

        if newer_only and (b.ts_seen <= dec_ts):
            continue

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

def find_best_matches(a: matching.Matchable, pool: list[matching.Matchable], n: int=10) -> tuple[matching.Matchable, float]:
    options = {}

    for b in pool:
        score, _, _ = matching.score_similarity(a, b)
        if score not in options:
            options[score] = []

        options[score].append(b)

    best = sorted(options, reverse=True)
    results = []

    for score in best[:n]:
        for o in options[score]:
            results.append((score, o))
    
    return results

def get_unmatched_track_sets() -> tuple[list[matching.MatchDecision], list[Track], list[Track]]:
    decs = _unpickle(app.PATH_PICKLE_DECISIONS, [])
    lib_old, lib_new = get_libraries()
    all_old, all_new = lib_old.tracks.copy(), lib_new.tracks.copy()

    for dec in decs:
        match dec.state:
            case matching.MatchState.MATCHED:
                for key in dec.old.tracks:
                    del all_old[key]

            case matching.MatchState.PARTIAL:
                for key in dec.old.tracks:
                    if key not in dec.omit:
                        del all_old[key]

    return decs, set(all_old.values()), set(all_new.values())

def get_unmatched_album_sets_for_newer() -> tuple[list[matching.MatchDecision], list[Album], list[Album]]:
    decs = _unpickle(app.PATH_PICKLE_DECISIONS, [])
    lib_old, lib_new = get_libraries()
    all_old, all_new = lib_old.albums.copy(), lib_new.albums.copy()

    for dec in decs:
        match dec.state:
            case matching.MatchState.MATCHED:
                try:
                    del all_old[dec.old.path]
                except:
                    pass

                try:
                    del all_new[dec.new.path]
                except:
                    pass

    return decs, set(all_old.values()), set(all_new.values())

def get_unmatched_album_sets() -> tuple[list[matching.MatchDecision], list[Album], list[Album]]:
    decs = _unpickle(app.PATH_PICKLE_DECISIONS, [])
    lib_old, lib_new = get_libraries()
    all_old, all_new = lib_old.albums.copy(), lib_new.albums.copy()

    for dec in decs:
        match dec.state:
            case matching.MatchState.MATCHED:
                try:
                    del all_old[dec.old.path]
                except:
                    pass

            case matching.MatchState.PARTIAL:
                try:
                    del all_old[dec.old.path]
                except:
                    pass

            case matching.MatchState.UNKNOWN:
                try:
                    del all_old[dec.old.path]
                except:
                    pass

            case matching.MatchState.CONFIRMED_UNMATCHED:
                try:
                    del all_old[dec.old.path]
                except:
                    pass

    return decs, set(all_old.values()), set(all_new.values())

def get_unknown_album_sets() -> tuple[list[matching.MatchDecision], list[Album], list[Album]]:
    decs = _unpickle(app.PATH_PICKLE_DECISIONS, [])
    lib_old, lib_new = get_libraries()
    all_old, all_new = lib_old.albums.copy(), lib_new.albums.copy()

    for dec in decs:
        match dec.state:
            case matching.MatchState.MATCHED:
                try:
                    del all_old[dec.old.path]
                except:
                    pass
                
                try:
                    del all_new[dec.new.path]
                except:
                    pass

            case matching.MatchState.PARTIAL:
                try:
                    del all_old[dec.old.path]
                except:
                    pass

                try:
                    del all_new[dec.new.path]
                except:
                    pass

            case matching.MatchState.UNMATCHED:
                try:
                    del all_old[dec.old.path]
                except:
                    pass

            case matching.MatchState.CONFIRMED_UNMATCHED:
                try:
                    del all_old[dec.old.path]
                except:
                    pass

    return decs, set(all_old.values()), set(all_new.values())

def report_progress_unknown(n_dec: int, n_old: int, n_new: int) -> None:
    print()
    print(f'Decisions made:       {n_dec}')
    print(f'Old albums undecided: {n_old}')
    print(f'New albums eligible:  {n_new}')
    print()

def report_progess_unmatched(n_unm: int) -> None:
    print()
    print(f'Old albums unmatched but not confirmed: {n_unm}')
    print()

def report_progess_escapees(n_unm: int, n_c_unmatched: int, n_matched: int) -> None:
    print()
    print(f'Unmatched tracks with alternatives worth considering: {n_unm}')
    print(f'Matches made among those: {n_matched}')
    print(f'Unmatches confirmed among those: {n_c_unmatched}')
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

    opts = list(filter(lambda d: (kw in d.present().lower()) or (kw in str(d.old.path).lower()) or ((d.new is not None) and (kw in str(d.new.path).lower())), decs))
    if not opts:
        print('None found')
        return

    print('\n'.join([f'{e + 1:>2}.  {str(opt)}' for (e, opt) in enumerate(opts)]))
    undos = input('Enter space-separated numbers to delete, or Enter to cancel: ')
    if not undos:
        print('Cancelled')
        return
    else:
        undos = undos.split()
        for i in (int(undo) for undo in undos):
            t = opts[i - 1]
            decs.remove(t)

        print(f'Removed {len(undos)} decisions')

    _pickle(decs, app.PATH_PICKLE_DECISIONS)

def delete_outdated_decs() -> list[matching.MatchDecision]:
    decs = _unpickle(app.PATH_PICKLE_DECISIONS, [])
    _pickle(decs, app.PATH_PICKLE_DECISIONS_BACKUP)

    latest = {}
    for dec in decs:
        p = str(dec.old.path)
        if p not in latest:
            latest[p] = dec
        elif dec.ts_made > latest[p].ts_made:
            latest[p] = dec
    
    news = sorted(latest.values(), key=lambda d: d.ts_made)
    print(f'Eliminated {len(decs) - len(news)} outdated decisions')
    _pickle(news, app.PATH_PICKLE_DECISIONS)

def update_decs_version() -> None:
    decs = _unpickle(app.PATH_PICKLE_DECISIONS, [])
    _pickle(decs, app.PATH_PICKLE_DECISIONS_BACKUP)

    news = []
    for d in decs:
        news.append(matching.MatchDecision.remake(d))

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

        p = 'k = accept these judgements; r = revise manually; m = album is a perfect match; n = album is unmatched; x = leave album undecided: '
        choice = input(p).upper().strip()
        while (choice) and not (m := re.match(app.RE_COMPARE, choice)):
            print('\nUnrecognized decision.')
            choice = input(p).upper().strip()

        choice = m.group(0)
        
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
            return matching.MatchState.PARTIAL, misaligned_tracks
        
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
            
        elif choice == 'N':
            return matching.MatchState.UNMATCHED, []
        
        elif choice == 'X':
            return matching.MatchState.UNKNOWN, []
        
def find_track_escapees() -> None:
    _, unm, new = get_unmatched_track_sets()
    bests = _unpickle(app.PATH_PICKLE_ESCAPEES, {})

    ow = False
    if bests:
        ow = prompts.p_bool('Overwrite existing bests')
        if ow:
            print('Overwriting')
        else:
            print('Not overwriting')

    bar = progressbar.ProgressBar()
    for a in bar(unm):
        if ow or (str(a.path) not in bests):
            best, score = find_best_match_strict(a, new)
            if best is not None:
                bests[str(a.path)] = (best, score)

    print(f'Perhaps {len(bests)} unmatched tracks can be individually matched')
    print(f'Pickling the best options')
    _pickle(bests, app.PATH_PICKLE_ESCAPEES)
        
def do_track_escapees() -> None:
    decs = _unpickle(app.PATH_PICKLE_DECISIONS, [])
    bests = _unpickle(app.PATH_PICKLE_ESCAPEES, {})
    lib_old, lib_new = get_libraries()

    report_progess_escapees(len(bests), 0, 0)

    print('y = match; n = confirm matchless; e = open folders; q = stop for now; s = save; Enter = no decision.\n')

    keys = list(bests)
    n_matched = 0
    n_c_unmatched = 0

    i = 0
    while i < len(keys):
        key = keys[i]
        t = lib_old.tracks[key]
        (best, score) = bests[key]

        p = f'{Track.present(t):<80} {Track.present(best):<80} {score:<.2f} ::: '

        choice = input(p).upper().strip()
        while (choice) and not (m := re.match(app.RE_UNKNOWN, choice)):
            print('\nUnrecognized decision.')
            choice = input(p).upper().strip()
        
        choice = m.group(0)

        if choice == 'Y':
            decs.append(matching.MatchDecision(t, best, matching.MatchState.MATCHED, score, tools.ts_now()))
            del bests[key]

            n_matched += 1
            i += 1

        elif choice == 'E':
            os.startfile(t.path.parent)
            os.startfile(best.path.parent)
            continue
            
        elif choice == 'N':
            decs.append(matching.MatchDecision(t, best, matching.MatchState.CONFIRMED_UNMATCHED, score, tools.ts_now()))
            del bests[key]

            n_c_unmatched += 1
            i += 1

        elif choice == 'S':
            report_progess_escapees(len(bests), n_c_unmatched, n_matched)
            _pickle(decs, app.PATH_PICKLE_DECISIONS)
            _pickle(bests, app.PATH_PICKLE_ESCAPEES)
            continue
        
        elif choice == 'Q':
            break

        i += 1
    
    report_progess_escapees(len(bests), n_c_unmatched, n_matched)
    _pickle(bests, app.PATH_PICKLE_ESCAPEES)
    _pickle(decs, app.PATH_PICKLE_DECISIONS)

def check_unknown_all() -> None:
    check_unknown()

def check_unknown_newer() -> None:
    print('This functionality does not work yet because timestamps were not saved properly')
    return
    check_unknown(newer_only=True)

def check_unmatched() -> None:
    decs, unm, new = get_unmatched_album_sets()
    report_progess_unmatched(len(unm))

    print('n = confirm no match; m # = matched after all; e # = open folders; q = stop for now; s = save\n')

    unm = list(unm)
    n_decided = 0

    i = 0
    while i < len(unm):
        a = unm[i]
        print(a.present())

        best = find_best_matches(a, new)
        
        for (n, pair) in enumerate(best):
            score, option = pair
            print(f'\t{n + 1:>2}.   {score:<.2f} : {option.present()}')
        print()
        
        p = 'Decision: '
        choice = input(p).upper().strip()
        while not (m := re.match(app.RE_UNMATCHED, choice)):
            print('\nUnrecognized decision.')
            choice = input(p).upper().strip()

        choice = m.group(0)

        if choice.startswith('M'):
            n = int(choice.split()[1])
            b = best[n - 1][1]

            state, unmatched_tracks = compare_albums(a, b)
            decs.append(matching.MatchDecision(a, b, state, score, tools.ts_now(), omit=unmatched_tracks[:]))
            print(f'Marked as matched with {b.present()}')
            print()

            n_decided += 1
            i += 1

        elif choice.startswith('E'):
            os.startfile(a.path)
            n = int(choice.split()[1])
            if n != 0:
                b = best[n - 1][1]
                os.startfile(b.path)
            
        elif choice == 'N':
            decs.append(matching.MatchDecision(a, None, matching.MatchState.CONFIRMED_UNMATCHED, score, tools.ts_now()))
            print(f'Marked as confirmed unmatched')
            print()

            n_decided += 1
            i += 1

        elif choice == 'S':
            report_progess_unmatched(len(unm) - n_decided)
            _pickle(decs, app.PATH_PICKLE_DECISIONS)
        
        elif choice == 'Q':
            break
    
    report_progess_unmatched(len(unm) - n_decided)
    _pickle(decs, app.PATH_PICKLE_DECISIONS)

def check_unknown(newer_only: bool=False) -> None:
    
    if newer_only:
        decs, old, new = get_unmatched_album_sets_for_newer()
    else:
        decs, old, new = get_unknown_album_sets()

    report_progress_unknown(len(decs), len(old), len(new))

    print('y = match; n = matchless; e = open folders; q = stop for now; s = save; Enter = no decision.\n')
 
    old = list(old)
    n_matched = 0

    i = 0    
    while i < len(old):
        a = old[i]

        if newer_only:
            newest_ts = 0
            for dec in decs:
                if dec.old == a:
                    if dec.ts_made > newest_ts:
                        newest_ts = dec.ts_made

            if newest_ts == 0:
                b = None
            else:
                b, score, _ = find_best_match(a, new, newer_only=True, dec_ts=newest_ts)
        else:
            b, score, _ = find_best_match(a, new)

        if b is None:
            i += 1
            continue

        if score >= app.THRESHOLD_CONFIDENT:
            p_word = 'CONFIDENT!!'
        elif score >= app.THRESHOLD_PROBABLE:
            p_word = 'LIKELY!!!!!'
        else:
            p_word = 'A STRETCH!!'

        p = f'{a.present():<80} {b.present():<80} {p_word} {score:<.2f} ::: '

        choice = input(p).upper().strip()
        while (choice) and not (m := re.match(app.RE_UNKNOWN, choice)):
            print('\nUnrecognized decision.')
            choice = input(p).upper().strip()
        
        choice = m.group(0)

        if choice == 'Y':
            state, unmatched_tracks = compare_albums(a, b)

            decs.append(matching.MatchDecision(a, b, state, score, tools.ts_now(), omit=unmatched_tracks[:]))
            new.remove(b)

            n_matched += 1
            i += 1

        elif choice == 'E':
            os.startfile(a.path)
            os.startfile(b.path)
            continue
            
        elif choice == 'N':
            decs.append(matching.MatchDecision(a, b, matching.MatchState.UNMATCHED, score, tools.ts_now()))
            i += 1

        elif choice == 'S':
            report_progress_unknown(len(decs), len(old) - n_matched, len(new))
            _pickle(decs, app.PATH_PICKLE_DECISIONS)
            continue
        
        elif choice == 'Q':
            break

    report_progress_unknown(len(decs), len(old) - n_matched, len(new))
    _pickle(decs, app.PATH_PICKLE_DECISIONS)

def rebase_path(path: Path) -> Path:
    parts = list(path.parts)
    for part in app.PATH_LIB_OLD.parts:
        parts.remove(part)
    path = app.PATH_LIB_CULL / Path(*parts)
    return path

def get_unmatched_paths() -> set[Path]:
    decs = _unpickle(app.PATH_PICKLE_DECISIONS, [])
    paths = set()

    for dec in decs: 
        if dec.state is matching.MatchState.PARTIAL:
            for (key, t) in dec.old.tracks.items():
                if key not in dec.omit:
                    paths.add(t.path)

        elif dec.state is matching.MatchState.CONFIRMED_UNMATCHED:
            if isinstance(dec.old, Album):
                for t in dec.old.tracks.values():
                    paths.add(t.path)

            elif isinstance(dec.old, Track):
                paths.add(dec.old.path)

    return paths

def sync_cull() -> None:
    are = tools.get_filepaths(app.PATH_LIB_CULL, EXTS)
    should_be = get_unmatched_paths()

    source_target = {p: rebase_path(p) for p in should_be}
    target_source = {v: k for (k, v) in source_target.items()}

    targets = set(target_source)

    to_remove = are.difference(targets)
    if not to_remove:
        print('No files to remove from the cull')
    else:
        print(f'Removing {len(to_remove)} files that should not be in the cull...')
        bar = progressbar.ProgressBar()
        for found in bar(to_remove):
            # print(f'Would be removing {found}')
            os.remove(found)

    to_copy = targets.difference(are)
    if not to_copy:
        print('No files to add to the cull')
    else:
        print(f'Adding {len(to_copy)} files that should be in the cull...')
        bar = progressbar.ProgressBar()
        for target in bar(to_copy):
            source = target_source[target]
            # print(f'Would be copying {source} to {target}')
            if not Path.exists(target.parent):
                Path.mkdir(target.parent, parents=True, exist_ok=True)
            shutil.copy2(source, target.parent)

def quit():
    exit() # LOL. (Why? So it can be a function object with a __name__)

def run():
    choices = [
        quit,
        check_unknown_all,
        check_unknown_newer,
        check_unmatched,
        find_track_escapees,
        do_track_escapees,
        print_decisions,
        undo_decision,
        update_decs_version,
        delete_outdated_decs,
        sync_cull
    ]

    program = prompts.p_choice('Choose program', [c.__name__ for c in choices], allow_blank=True)
    if program is not None:
        choices[program - 1]()

if __name__ == '__main__':
    app = App()
    app.load_configuration()
    prompts.p_repeat_till_quit(run, c_phrase='run a program')
