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
    THRESHOLD_CANDIDATE: float = 0.75
    THRESHOLD_CONFIDENT: float = 0.97
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

# Functions

def manually_vet_matches():
    matches = _unpickle(PATH_PICKLE_MATCHES, dict())
    manual = _unpickle(PATH_PICKLE_MANUAL, set())

    lib_old = _unpickle(PATH_PICKLE_LIB_OLD, dict())
    lib_new = _unpickle(PATH_PICKLE_LIB_NEW, dict())

    considerable = list(filter(lambda m: not m.manually_scored and m.score < THRESHOLD_CONFIDENT, matches.values()))
    considerable = sorted(considerable, key=lambda m: m.sig())

    if not considerable:
        print('None left to manually vet')
        return
    
    print(f'{len(considerable)} to go...')

    i = 0
    proceed = input('Hit Enter to see a match or Q to quit: ')
    while (i < (len(considerable) - 1)) and (proceed.upper().strip() != 'Q'):
        try:
            print()

            m = considerable[i]
            n = 0

            prompt = 'Is this a match?'

            old_short = ' / '.join(m.track_old.path.parts[2:])
            new_short = ' / '.join(m.track_new.path.parts[2:])

            prompt += f'\n{m.score:.2f}\n\n{old_short}\n{new_short}\n\n'
            result = prompts.p_bool(prompt + '\n')

            m.manually_score(result)
            if result:
                manual.add(m.sig())
                n += 1

                old_sibs = get_track_siblings(lib_old, m.track_old)
                new_sibs = get_track_siblings(lib_new, m.track_new)
                further = {}

                for sib in old_sibs:
                    for other in new_sibs:
                        sig = Match.sig_static(sib, other)
                        if sig in matches and matches[sig] in considerable:
                            further[sig] = matches[sig]
                            break
                
                if further:

                    print()
                    print('Then are these also matches?')
                    print()

                    pairs = [
                        (
                        ' / '.join(m2.track_old.path.parts[-2:]),
                        ' / '.join(m2.track_new.path.parts[-2:])
                        )
                        for m2 in further.values()]
                    
                    longest = max(pairs, key=lambda p: len(p[0]))

                    for pair in sorted(pairs):
                        p1, p2 = pair[0].ljust(len(longest[0])), pair[1]
                        print(f'{p1}  =  {p2}')

                    print()
                    result_further = prompts.p_bool('(In this case NO does not manually score)')
                    if result_further:
                        for m2 in further.values():
                            m2.manually_score(True)
                            manual.add(m2.sig())
                            n += 1
                            i += 1

                    print()

                print(f'Confirmed {n} matches manually')
            
        except KeyboardInterrupt:
            break
        
        print()
        proceed = input('Hit Enter to see another match or Q to quit: ')

        i += 1
    
    _pickle(matches, PATH_PICKLE_MATCHES)
    _pickle(manual, PATH_PICKLE_MANUAL)

def manually_vet_matches_fast():
    matches = _unpickle(PATH_PICKLE_MATCHES, dict())
    manual = _unpickle(PATH_PICKLE_MANUAL, set())

    lib_old = _unpickle(PATH_PICKLE_LIB_OLD, dict())
    lib_new = _unpickle(PATH_PICKLE_LIB_NEW, dict())

    considerable = list(filter(lambda m: not m.manually_scored and m.score < THRESHOLD_CONFIDENT, matches.values()))

    if not considerable:
        print('None left to manually vet')
        return

    print(f'{len(considerable)} to go...')

    i = 0
    proceed = input('Hit Enter to see a batch of matches or Q to quit: ')
    while considerable and (proceed.upper().strip() != 'Q'):

        try:
            ms = set()
            for _ in range(FAST_BATCH_SIZE):
                ms.add(considerable.pop(random.randrange(len(considerable))))
                if not considerable:
                    break

            n = 0

            print()
            print('Are these all matches?')
            print()

            prompt_pairs = []
            
            for m in ms:
                prompt_pairs.append(
                    (
                    ' / '.join(m.track_old.path.parts[2:]),
                    ' / '.join(m.track_new.path.parts[2:])
                    )
                )

            longest = max(prompt_pairs, key=lambda p: len(p[0]))

            printed = 0
            for pair in prompt_pairs:
                p1, p2 = pair[0].ljust(len(longest[0])), pair[1]
                print(f'{p1}  =  {p2}')

                printed += 1
                if not (printed % 5):
                    print()

            print()
            result = prompts.p_bool('MATCHES (In this case NO does not manually score)')

            if result:

                further = {}
                prompt_pairs = []

                for m in ms:
                    first_sib = True

                    m.manually_score(result)
                    manual.add(m.sig())
                    n += 1

                    old_sibs = get_track_siblings(lib_old, m.track_old)
                    new_sibs = get_track_siblings(lib_new, m.track_new)

                    for sib in old_sibs:
                        for other in new_sibs:
                            sig = Match.sig_static(sib, other)
                            m2 = matches[sig]
                            
                            if sig in matches and m2 in considerable:                                
                                further[sig] = m2
                                
                                if first_sib:
                                    prompt_pairs.append(
                                                    (
                                        ' / '.join(m2.track_old.path.parts[-2:]),
                                        ' / '.join(m2.track_new.path.parts[-2:])
                                        )
                                    )
                                    first_sib = False

                                break
                
                if further:

                    print()
                    print('First sibling of each? (N = change nothing)')
                    print()
                    
                    longest = max(prompt_pairs, key=lambda p: len(p[0]))

                    printed = 0
                    for pair in prompt_pairs:
                        p1, p2 = pair[0].ljust(len(longest[0])), pair[1]
                        print(f'{p1}  =  {p2}')

                        printed += 1
                        if not (printed % 5):
                            print()

                    print()
                    result_further = prompts.p_bool('SIBLINGS (In this case NO does not manually score)')
                    if result_further:
                        for m2 in further.values():
                            m2.manually_score(True)

                            m2_sig = m2.sig()

                            if m2_sig not in manual:
                                manual.add(m2_sig)
                                n += 1                            

                    print()

                print(f'Confirmed {n} matches manually')
            
        except KeyboardInterrupt:
            break
        
        print()
        proceed = input('Hit Enter to see another batch or Q to quit: ')
    
    _pickle(matches, PATH_PICKLE_MATCHES)
    _pickle(manual, PATH_PICKLE_MANUAL)

# New functions

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

def find_best_match(a: matching.Matchable, pool: list[matching.Matchable]) -> tuple[matching.Matchable, float, bool]:
    best = None
    best_score = 0.0
    satisfied = False

    for b in pool:
        score, _, _ = matching.score_similarity(a, b)
        # input(f'{str(b):<70} {score}')

        if score > app.THRESHOLD_CONFIDENT:
            return b, score, True

        elif score > app.THRESHOLD_CANDIDATE:
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
    cols.append(b.path.stem)
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
        best, score, satisfied = find_best_match(track, pool)
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
            return matching.MatchState.MATCHED, []
        
        elif choice == 'K':
            return matching.MatchState.PARTIAL, [m[0] for m in misaligned_rows]
        
        elif choice == 'R':

            revise_a = prompts.p_bool('Revise the ones I think are aligned')
            if revise_a:
                print('\n'.join([f'{e + 1:>2}.  {row[0]:<80} = {row[1]}' for (e, row) in enumerate(aligned_rows)]))
                flips = input('Enter space-separated numbers to switch to non-matches: ')
                for i in (int(flip) for flip in flips.split()):
                    misaligned_tracks.append(aligned_tracks[i - 1])

            revise_m = prompts.p_bool('Revise the ones I think are misaligned')
            if revise_m:
                print('\n'.join([f'{e + 1:>2}.  {row[0]:<80} x {row[1]}' for (e, row) in enumerate(misaligned_rows)]))
                flips = input('Enter space-separated numbers to switch to matches: ')
                for i in (int(flip) for flip in flips.split()):
                    misaligned_tracks.remove(misaligned_tracks[i - 1])
            
            if misaligned_tracks:
                return matching.MatchState.PARTIAL, misaligned_tracks
            else:
                return matching.MatchState.MATCHED, []
        
        elif choice == 'X':
            return matching.MatchState.UNKNOWN, []

def do_matches() -> None:
    decs, old, new = get_unknown_album_sets()
    report_progress(len(decs), len(old), len(new))

    print('y = match; n = matchless; q = stop for now; Enter = no decision.\n')

    n_matched = 0
    for a in old:
        b, score, satisfied = find_best_match(a, new)

        if satisfied:
            p_word = 'LIKELY!!!!!'
        else:
            p_word = 'IMPROBABLE!'

        p = f'{a.present():<80} {b.present():<80} {p_word} {score:<.2f} ::: '

        choice = input(p).upper().strip()
        while choice not in {'Y', '', 'N', 'Q'}:
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
        
        elif choice == 'Q':
            break

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
