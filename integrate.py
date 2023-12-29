from pathlib import Path
from track import Track
from match import Match
import pickle

BASE_OLD = Path('D:/88_old_music')
BASE_NEW = Path('D:/1_processed')

EXTS = ['mp3', 'flac', 'wav', 'm4a']

# libraries
PATH_PICKLE_LIB_OLD = Path('pickles/lib_old.pickle')
PATH_PICKLE_LIB_NEW = Path('pickles/lib_new.pickle')

# filenames
PATH_PICKLE_F_OLD = Path('pickles/f_old.pickle')
PATH_PICKLE_F_NEW = Path('pickles/f_new.pickle')

# unmatched
PATH_PICKLE_U_OLD = Path('pickles/u_old.pickle')
PATH_PICKLE_U_NEW = Path('pickles/u_new.pickle')

# matched
PATH_PICKLE_M_OLD = Path('pickles/m_old.pickle')
PATH_PICKLE_M_NEW = Path('pickles/m_new.pickle')

# matches
PATH_PICKLE_MATCHES = Path('pickles/matches.pickle')

THRESHOLD_CANDIDATE = .9
THRESHOLD_CONFIDENT = .98

def _pickle(o: object, path: Path) -> None:
    with open(path, 'wb') as f:
        pickle.dump(o, f)

def _unpickle(path: Path, default: object=None) -> object:
    if Path.exists(path):
        with open(path, 'rb') as f:
            return pickle.load(f)
    else:
        return default

def get_filenames(path_pickle: Path, path_base: Path) -> tuple[set[str]]:
    """Returns 3 sets: existing, new, deleted."""

    existing: set = _unpickle(path_pickle, set())
    found = set()

    for path in Path.rglob(path_base, '*'):
        if path.suffix.strip('.').lower() in EXTS: # and 'Jackson Square' not in str(path):
            found.add(path)

    return existing, found.difference(existing), existing.difference(found)

def update_library(path_pickle_lib: Path, path_base: Path, path_pickle_filenames: Path) -> tuple[dict[str, Track], set[str]]:
    lib = _unpickle(path_pickle_lib, dict())
    existing, new, deleted = get_filenames(path_pickle_filenames, path_base)

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

def run():
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

def clean_matches():
    e1, n1, d1 = get_filenames(PATH_PICKLE_F_OLD, BASE_OLD)
    e2, n2, d2 = get_filenames(PATH_PICKLE_F_NEW, BASE_NEW)

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
    
if __name__ == '__main__':
    # worst_matches()
    # clean_matches()
    run()
