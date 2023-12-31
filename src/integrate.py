from pathlib import Path
from track import Track
from match import Match
import prompts
import pickle
import random

# Constants

THRESHOLD_CANDIDATE = .9
THRESHOLD_CONFIDENT = .98
FAST_BATCH_SIZE = 40

# Configurables

BASE_OLD = ''
BASE_NEW = ''
BASE_PICKLES = ''
EXTS = []

# Config

if __name__ == '__main__':

    with open('src/config.ini', 'r') as f:
        for line in f.readlines():
            k, v = (c.strip() for c in line.split('::'))

            if k == 'BASE_OLD':
                BASE_OLD = Path(v)
            elif k == 'BASE_NEW':
                BASE_NEW = Path(v)
            elif k == 'BASE_PICKLES':
                BASE_PICKLES = Path(v)
            elif k == 'EXTS':
                EXTS = v.split(',')

    if not Path.exists(BASE_PICKLES):
        Path.mkdir(BASE_PICKLES, exist_ok=True, parents=True)

    # libraries
    PATH_PICKLE_LIB_OLD = Path(f'{BASE_PICKLES}/lib_old.pickle')
    PATH_PICKLE_LIB_NEW = Path(f'{BASE_PICKLES}/lib_new.pickle')

    # filenames
    PATH_PICKLE_F_OLD = Path(f'{BASE_PICKLES}/f_old.pickle')
    PATH_PICKLE_F_NEW = Path(f'{BASE_PICKLES}/f_new.pickle')

    # unmatched
    PATH_PICKLE_U_OLD = Path(f'{BASE_PICKLES}/u_old.pickle')
    PATH_PICKLE_U_NEW = Path(f'{BASE_PICKLES}/u_new.pickle')

    # matched
    PATH_PICKLE_M_OLD = Path(f'{BASE_PICKLES}/m_old.pickle')
    PATH_PICKLE_M_NEW = Path(f'{BASE_PICKLES}/m_new.pickle')

    # matches
    PATH_PICKLE_MATCHES = Path(f'{BASE_PICKLES}/matches.pickle')
    PATH_PICKLE_MANUAL = Path(f'{BASE_PICKLES}/manual.pickle')

# Functions

def _pickle(o: object, path: Path) -> None:
    with open(path, 'wb') as f:
        pickle.dump(o, f)

def _unpickle(path: Path, default: object=None) -> object:
    if Path.exists(path):
        with open(path, 'rb') as f:
            return pickle.load(f)
    else:
        return default
    
def get_track_siblings(lib: dict[str, Track], track: Track, include_self: bool=False) -> set[Track]:
    result = set()

    for path in get_filenames(track.path.parent):
        sig = Track.sig_static(path)
        t = lib.get(sig, None)
        if t is not None and sig != track.sig():
            result.add(t)
    
    return result

def get_filenames(path_base: Path) -> set[str]:
    result = set()
    for path in Path.rglob(path_base, '*'):
        if path.suffix.strip('.').lower() in EXTS: # and 'Jackson Square' not in str(path):
            result.add(path)
    return result

def get_filename_sets(path_pickle: Path, path_base: Path) -> tuple[set[str]]:
    """Returns 3 sets: existing, new, deleted."""

    existing: set = _unpickle(path_pickle, set())
    found = get_filenames(path_base)
    return existing, found.difference(existing), existing.difference(found)

def update_library(path_pickle_lib: Path, path_base: Path, path_pickle_filenames: Path) -> tuple[dict[str, Track], set[str]]:
    lib = _unpickle(path_pickle_lib, dict())
    existing, new, deleted = get_filename_sets(path_pickle_filenames, path_base)

    print(f'Forgetting deleted tracks: {len(deleted)}')

    for path in deleted:
        if path in lib:
            del lib[Track.sig_static(path)]

    # Report
    print(f'Memorizing new tracks: {len(new)}')

    if not len(new):
        _pickle(lib, path_pickle_lib)
        _pickle(existing.difference(deleted).union(new), path_pickle_filenames)
        return lib, deleted

    n = 0

    # for path in Path.rglob(BASE_OLD / 'Bebo Norman', '*'):
    for path in new:
            
        t = Track.from_path(path)
        lib[t.sig()] = t

        n += 1
        if not (n % 1_000):
            print(n)

    print()

    _pickle(lib, path_pickle_lib)
    _pickle(existing.difference(deleted).union(new), path_pickle_filenames)
    return lib, deleted

def match_library(lib_old: dict[str, Track], lib_new: dict[str, Track], forget_old: set[str], forget_new: set[str]) -> tuple[int, dict[str, Match], set[str], set[str]]:

    # Utility
    def _add_match(_m: Match, _old: Track, _new: Track) -> None:
        matches[_m.sig()] = _m
        matched_old.add(_old.sig())
        matched_new.add(_new.sig())
        eligible_new.remove(_new.sig())

    # Dict of 2 sigs to a Match
    matches = _unpickle(PATH_PICKLE_MATCHES, dict())

    # Filter down to eligible
    all_old = set(lib_old.keys())
    all_new = set(lib_new.keys())

    # Sets of tracks CHECKED without a match
    unmatched_old = _unpickle(PATH_PICKLE_U_OLD, set())
    unmatched_new = _unpickle(PATH_PICKLE_U_NEW, set())

    # Sets of tracks matched
    matched_old = _unpickle(PATH_PICKLE_M_OLD, set())
    matched_new = _unpickle(PATH_PICKLE_M_NEW, set())

    # Forget deleted ones
    # TODO So hilariously inefficient... but cumbersome to do it otherwise,
    # and at this scale it hardly matters...
    m_old_to_new = {k.split(' + ')[0]: k for k in matches}
    m_new_to_old = {k.split(' + ')[1]: k for k in matches}

    for path in forget_old:
        sig = Track.sig_static(path)
        if sig in m_old_to_new:
            del matches[m_old_to_new[sig]]
            matched_old.discard(sig)
            unmatched_old.discard(sig)

    for path in forget_new:
        sig = Track.sig_static(path)
        if sig in m_new_to_old:
            del matches[m_new_to_old[sig]]
            matched_new.discard(sig)
            unmatched_new.discard(sig)
        
    # Sets of tracks UNCHECKED and known not to be yet matched
    eligible_old = all_old.difference(matched_old).difference(unmatched_old)
    eligible_new = all_new.difference(matched_new) # .difference(unmatched_new)

    # print('mm', len(matches))
    # print()
    # print('ao', len(all_old))
    # print('an', len(all_new))
    # print()
    # print('uo', len(unmatched_old))
    # print('un', len(unmatched_new))
    # print()
    # print('mo', len(matched_old))
    # print('mn', len(matched_new))
    # print()
    # print('eo', len(eligible_old))
    # print('en', len(eligible_new))

    try:

        n = 0

        for old_key in eligible_old:
            old = lib_old[old_key]
            found = False
            best = None

            for new_key in eligible_new:
                new = lib_new[new_key]
                m = Match(old, new)

                if m.score > THRESHOLD_CONFIDENT:
                    _add_match(m, old, new)
                    found = True
                    break

                elif m.score > THRESHOLD_CANDIDATE:
                    if (best is None) or (m.score > best.score):
                        best = m

            if not found:
                if best is not None:
                    _add_match(best, old, new)
                else:
                    unmatched_old.add(old.sig())

            n += 1
            if not (n % 100):
                print(n)

            # # TODO
            # if n == 1_000:
            #     break

        unmatched_new = all_new.difference(matched_new)

    except KeyboardInterrupt:
        print('Interrupted')

    except Exception as e:
        print(e)
    
    finally:
        _pickle(matches, PATH_PICKLE_MATCHES)
        _pickle(unmatched_old, PATH_PICKLE_U_OLD)
        _pickle(unmatched_new, PATH_PICKLE_U_NEW)
        _pickle(matched_old, PATH_PICKLE_M_OLD)
        _pickle(matched_new, PATH_PICKLE_M_NEW)

        return n, matches, unmatched_old, unmatched_new

def load_libraries() -> tuple[dict[str, Track], set[str]]:
    """Return the old library and the new one, plus a set of filenames to forget."""

    print('Loading old library...')
    lib_old, forget_old = update_library(PATH_PICKLE_LIB_OLD, BASE_OLD, PATH_PICKLE_F_OLD)
    print('Loaded old library')
    print()

    print('Loading new library...')
    lib_new, forget_new = update_library(PATH_PICKLE_LIB_NEW, BASE_NEW, PATH_PICKLE_F_NEW)
    print('Loaded new library')
    print()

    return lib_old, lib_new, forget_old, forget_new

def update_matches():
    lib_old, lib_new, forget_old, forget_new = load_libraries()

    print('Matching libraries...')
    n, matches, unmatched_old, unmatched_new = match_library(lib_old, lib_new, forget_old, forget_new)
    print('Matched libraries')
    print()

    print('Matches: ')

    # for m in matches:
    #     print(matches[m])

    print(f'Tested this time: {n}')
    print(f'Unmatched old: {len(unmatched_old)}')
    print(f'Unmatched new: {len(unmatched_new)}')
    print(f'Matches: {len(matches)}')

def worst_matches():
    matches = _unpickle(PATH_PICKLE_MATCHES, dict())

    from_worst = sorted(matches, key=lambda key: matches[key].score)

    i = 0
    proceed = input('Hit Enter to see a match or Q to quit: ')
    while proceed.upper().strip() != 'Q':
        m = matches[from_worst[i]]
        input(f'{m.score:.2f} - {m}')
        i += 1

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


def clean_matches():
    e1, n1, d1 = get_filename_sets(PATH_PICKLE_F_OLD, BASE_OLD)
    e2, n2, d2 = get_filename_sets(PATH_PICKLE_F_NEW, BASE_NEW)

    lib_1 = _unpickle(PATH_PICKLE_LIB_OLD, dict())
    lib_2 = _unpickle(PATH_PICKLE_LIB_NEW, dict())

    matches = _unpickle(PATH_PICKLE_MATCHES, dict())
    matched_old = _unpickle(PATH_PICKLE_M_OLD, set())
    matched_new = _unpickle(PATH_PICKLE_M_NEW, set())
    unmatched_old = _unpickle(PATH_PICKLE_U_OLD, set())
    unmatched_new = _unpickle(PATH_PICKLE_U_OLD, set())

    for path in d1:
        if path in lib_1:
            del lib_1[Track.sig_static(path)]

    for path in d2:
        if path in lib_2:
            del lib_2[Track.sig_static(path)]

    m_old_to_new = {k.split(' + ')[0]: k for k in matches}
    m_new_to_old = {k.split(' + ')[1]: k for k in matches}

    for path in d1:
        sig = Track.sig_static(path)

        if sig in m_old_to_new:
            del matches[m_old_to_new[sig]]
            matched_old.discard(sig)
            unmatched_old.discard(sig)

    for path in d2:  
        sig = Track.sig_static(path)      

        if sig in m_new_to_old:
            del matches[m_new_to_old[sig]]
            matched_new.discard(sig)
            unmatched_new.discard(sig)

    _pickle(e1.difference(d1).union(n1), PATH_PICKLE_F_OLD)
    _pickle(e2.difference(d2).union(n2), PATH_PICKLE_F_NEW)
    _pickle(lib_1, PATH_PICKLE_LIB_OLD)
    _pickle(lib_2, PATH_PICKLE_LIB_NEW)
    _pickle(matches, PATH_PICKLE_MATCHES)
    _pickle(matched_old, PATH_PICKLE_M_OLD)
    _pickle(matched_new, PATH_PICKLE_M_NEW)
    _pickle(unmatched_old, PATH_PICKLE_U_OLD)
    _pickle(unmatched_new, PATH_PICKLE_U_NEW)

def update_match_version() -> None:
    matches = _unpickle(PATH_PICKLE_MATCHES, dict())
    new = {}

    for m in matches.values():
        m2 = Match(m.track_old, m.track_new)
        new[m2.sig()] = m2

    _pickle(new, PATH_PICKLE_MATCHES)

def manually_remove_match() -> None:
    matches = _unpickle(PATH_PICKLE_MATCHES, dict())
    matched_old = _unpickle(PATH_PICKLE_M_OLD, set())
    matched_new = _unpickle(PATH_PICKLE_M_NEW, set())
    unmatched_old = _unpickle(PATH_PICKLE_U_OLD, set())
    unmatched_new = _unpickle(PATH_PICKLE_U_OLD, set())

    key = prompts.p_str('Enter a keyword').lower()

    to_remove = set()

    for (sig, m) in matches.items():
        if key in sig.lower():
            print()
            choice = prompts.p_bool(f'Remove {sig}')
            if choice:
                to_remove.add(sig)
                old_t_sig = m.track_old.sig()
                new_t_sig = m.track_new.sig()

                matched_old.discard(old_t_sig)
                unmatched_old.add(old_t_sig)
                matched_new.discard(new_t_sig)
                unmatched_new.add(new_t_sig)

                print('Removed')
            
            else:
                print('Kept')

    for sig in to_remove:
        del matches[sig]

    _pickle(matches, PATH_PICKLE_MATCHES)
    _pickle(matched_old, PATH_PICKLE_M_OLD)
    _pickle(matched_new, PATH_PICKLE_M_NEW)
    _pickle(unmatched_old, PATH_PICKLE_U_OLD)
    _pickle(unmatched_new, PATH_PICKLE_U_NEW)


def run():
    choices = [
        update_matches,
        manually_vet_matches,
        manually_vet_matches_fast,
        clean_matches,
        worst_matches,
        update_match_version,
        manually_remove_match
    ]

    program = prompts.p_choice('Choose program', choices, allow_blank=True)
    if program is not None:
        choices[program - 1]()

if __name__ == '__main__':
    prompts.p_repeat_till_quit(run, c_phrase='run a program')
