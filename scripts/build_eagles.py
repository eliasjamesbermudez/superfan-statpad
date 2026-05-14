"""
Builds data/eagles/players.json from nfl_data_py.

Output schema follows CLAUDE.md:
- Full career stats for every player who has ever been an Eagle (not just PHI tenure).
- `seasons` is an array of {year, team, ...stats, pro_bowl, all_pro_team, super_bowl}.
- `career` rollup with totals + games_played, seasons_played, pro_bowls, etc.
- super_bowls stored as season-start years (e.g. 2024 for SB LIX).

Stat naming: snake_case with NFL prefixes per CLAUDE.md.
  rec, rec_yards, rec_td
  rush_yards, rush_td
  pass_yards, pass_td, pass_int
  def_sacks, def_int, def_tackles
  games (universal)

Run from repo root:  python3 scripts/build_eagles.py
"""
import nfl_data_py as nfl
import pandas as pd
import json
import os
import re
import sys
from collections import defaultdict

# Make scripts/ importable so we can pull in manual_awards regardless of CWD.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'eagles', 'players.json')

YEARS = list(range(1999, 2025))
# Defensive stats come from play-by-play across the full range, minus 2016-2017
# (gap in PBP defensive coverage — filled by MANUAL_DEF below). PHI-only.
PBP_YEARS = list(range(1999, 2016)) + list(range(2018, 2025))

# 2016-2017 defensive supplement (PFR seasonal and PBP both have a gap here).
# PHI players only — full-career coverage outside PHI not attempted in this window.
MANUAL_DEF = [
    # 2016
    {'season': 2016, 'player_name': 'Nigel Bradham',    'position': 'LB', 'g': 16, 'sacks': 2.0, 'interceptions': 1, 'tackles': 102},
    {'season': 2016, 'player_name': 'Jordan Hicks',     'position': 'LB', 'g': 16, 'sacks': 1.0, 'interceptions': 5, 'tackles': 85},
    {'season': 2016, 'player_name': 'Rodney McLeod',    'position': 'S',  'g': 16, 'sacks': 1.0, 'interceptions': 3, 'tackles': 83},
    {'season': 2016, 'player_name': 'Malcolm Jenkins',  'position': 'S',  'g': 16, 'sacks': 1.0, 'interceptions': 3, 'tackles': 72},
    {'season': 2016, 'player_name': 'Jalen Mills',      'position': 'CB', 'g': 16, 'sacks': 0.0, 'interceptions': 0, 'tackles': 61},
    {'season': 2016, 'player_name': 'Brandon Graham',   'position': 'DE', 'g': 16, 'sacks': 5.5, 'interceptions': 0, 'tackles': 59},
    {'season': 2016, 'player_name': 'Nolan Carroll',    'position': 'CB', 'g': 16, 'sacks': 0.0, 'interceptions': 1, 'tackles': 55},
    {'season': 2016, 'player_name': 'Fletcher Cox',     'position': 'DT', 'g': 16, 'sacks': 6.5, 'interceptions': 0, 'tackles': 43},
    {'season': 2016, 'player_name': 'Leodis McKelvin',  'position': 'CB', 'g': 13, 'sacks': 0.0, 'interceptions': 1, 'tackles': 43},
    {'season': 2016, 'player_name': 'Connor Barwin',    'position': 'LB', 'g': 16, 'sacks': 5.0, 'interceptions': 0, 'tackles': 34},
    {'season': 2016, 'player_name': 'Mychal Kendricks', 'position': 'LB', 'g': 15, 'sacks': 0.0, 'interceptions': 0, 'tackles': 32},
    {'season': 2016, 'player_name': 'Beau Allen',       'position': 'DT', 'g': 16, 'sacks': 0.0, 'interceptions': 0, 'tackles': 29},
    {'season': 2016, 'player_name': 'Bennie Logan',     'position': 'DT', 'g': 13, 'sacks': 2.5, 'interceptions': 0, 'tackles': 26},
    {'season': 2016, 'player_name': 'Vinny Curry',      'position': 'DE', 'g': 16, 'sacks': 2.5, 'interceptions': 0, 'tackles': 26},
    {'season': 2016, 'player_name': 'Marcus Smith',     'position': 'LB', 'g': 13, 'sacks': 2.5, 'interceptions': 0, 'tackles': 24},
    {'season': 2016, 'player_name': 'Destiny Vaeao',    'position': 'DT', 'g': 16, 'sacks': 2.5, 'interceptions': 0, 'tackles': 16},
    {'season': 2016, 'player_name': 'Ron Brooks',       'position': 'CB', 'g': 16, 'sacks': 2.0, 'interceptions': 0, 'tackles': 15},
    {'season': 2016, 'player_name': 'Najee Goode',      'position': 'LB', 'g': 16, 'sacks': 0.0, 'interceptions': 0, 'tackles': 11},
    # 2017 (Super Bowl LII season)
    {'season': 2017, 'player_name': 'Nigel Bradham',    'position': 'LB', 'g': 15, 'sacks': 1.0, 'interceptions': 0, 'tackles': 88},
    {'season': 2017, 'player_name': 'Mychal Kendricks', 'position': 'LB', 'g': 15, 'sacks': 2.0, 'interceptions': 0, 'tackles': 77},
    {'season': 2017, 'player_name': 'Malcolm Jenkins',  'position': 'S',  'g': 16, 'sacks': 1.0, 'interceptions': 2, 'tackles': 76},
    {'season': 2017, 'player_name': 'Jalen Mills',      'position': 'CB', 'g': 15, 'sacks': 0.0, 'interceptions': 3, 'tackles': 64},
    {'season': 2017, 'player_name': 'Rodney McLeod',    'position': 'S',  'g': 14, 'sacks': 0.0, 'interceptions': 0, 'tackles': 54},
    {'season': 2017, 'player_name': 'Brandon Graham',   'position': 'DE', 'g': 15, 'sacks': 9.5, 'interceptions': 0, 'tackles': 47},
    {'season': 2017, 'player_name': 'Patrick Robinson', 'position': 'CB', 'g': 16, 'sacks': 1.0, 'interceptions': 4, 'tackles': 47},
    {'season': 2017, 'player_name': 'Tim Jernigan',     'position': 'DT', 'g': 14, 'sacks': 2.5, 'interceptions': 0, 'tackles': 38},
    {'season': 2017, 'player_name': 'Corey Graham',     'position': 'S',  'g': 14, 'sacks': 0.0, 'interceptions': 2, 'tackles': 38},
    {'season': 2017, 'player_name': 'Ronald Darby',     'position': 'CB', 'g':  8, 'sacks': 0.0, 'interceptions': 3, 'tackles': 34},
    {'season': 2017, 'player_name': 'Chris Long',       'position': 'DE', 'g': 16, 'sacks': 3.0, 'interceptions': 0, 'tackles': 34},
    {'season': 2017, 'player_name': 'Jordan Hicks',     'position': 'LB', 'g':  7, 'sacks': 0.0, 'interceptions': 2, 'tackles': 28},
    {'season': 2017, 'player_name': 'Fletcher Cox',     'position': 'DT', 'g': 16, 'sacks': 5.0, 'interceptions': 0, 'tackles': 28},
    {'season': 2017, 'player_name': 'Derek Barnett',    'position': 'DE', 'g': 15, 'sacks': 5.5, 'interceptions': 0, 'tackles': 26},
    {'season': 2017, 'player_name': 'Vinny Curry',      'position': 'DE', 'g': 16, 'sacks': 3.0, 'interceptions': 0, 'tackles': 25},
]

# Super Bowl rosters keyed by player name as it appears in PFR/nflreadr.
# Key = SB roman numeral; value = (season_year, roster_set).
SUPER_BOWL_ROSTERS = {
    "LII": (2017, {
        "Nick Foles","Zach Ertz","Jay Ajayi","Corey Clement","LeGarrette Blount",
        "Alshon Jeffery","Torrey Smith","Nelson Agholor","Mack Hollins","Trey Burton",
        "Brent Celek","Jason Kelce","Lane Johnson","Brandon Brooks","Stefen Wisniewski",
        "Jason Peters","Fletcher Cox","Brandon Graham","Derek Barnett","Tim Jernigan",
        "Vinny Curry","Chris Long","Nigel Bradham","Mychal Kendricks","Jordan Hicks",
        "Corey Graham","Patrick Robinson","Jalen Mills","Ronald Darby","Malcolm Jenkins",
        "Rodney McLeod",
    }),
    "LVII": (2022, {
        "Jalen Hurts","A.J. Brown","DeVonta Smith","Dallas Goedert","Miles Sanders",
        "Boston Scott","Kenneth Gainwell","Jason Kelce","Lane Johnson","Jordan Mailata",
        "Landon Dickerson","Isaac Seumalo","Fletcher Cox","Javon Hargrave",
        "Josh Sweat","Robert Quinn","Brandon Graham","Haason Reddick","T.J. Edwards",
        "Kyzir White","Darius Slay","James Bradberry","Chauncey Gardner-Johnson",
        "Marcus Epps","Reed Blankenship",
    }),
    "LIX": (2024, {
        "Jalen Hurts","A.J. Brown","DeVonta Smith","Dallas Goedert","Saquon Barkley",
        "Kenneth Gainwell","Will Shipley","Lane Johnson","Jordan Mailata",
        "Landon Dickerson","Cam Jurgens","Brandon Graham","Josh Sweat",
        "Jalen Carter","Milton Williams","Nolan Smith","Nakobe Dean","Zack Baun",
        "Darius Slay","Quinyon Mitchell","Reed Blankenship","C.J. Gardner-Johnson",
    }),
}

# Build (player_name, season_year) -> bool lookup
SB_SEASONS_BY_NAME = defaultdict(set)
for sb_label, (season_year, roster) in SUPER_BOWL_ROSTERS.items():
    for name in roster:
        SB_SEASONS_BY_NAME[name].add(season_year)

# Team abbreviation -> nickname. Includes nflreadr/PFR aliases for relocated or
# variably-coded franchises so historical seasons resolve correctly. nflreadr
# is inconsistent across seasons — Baltimore is BAL most years but BLT for
# others, Houston is HOU/HST, Arizona ARI/ARZ, etc.
TEAM_NAMES = {
    'ARI': 'Cardinals','ARZ': 'Cardinals',
    'ATL': 'Falcons',
    'BAL': 'Ravens',   'BLT': 'Ravens',
    'BUF': 'Bills',
    'CAR': 'Panthers',
    'CHI': 'Bears',
    'CIN': 'Bengals',
    'CLE': 'Browns',   'CLV': 'Browns',
    'DAL': 'Cowboys',
    'DEN': 'Broncos',
    'DET': 'Lions',
    'GB':  'Packers',
    'HOU': 'Texans',   'HST': 'Texans',
    'IND': 'Colts',
    'JAX': 'Jaguars',  'JAC': 'Jaguars',
    'KC':  'Chiefs',
    'LV':  'Raiders',  'OAK': 'Raiders',
    'LAC': 'Chargers', 'SD':  'Chargers', 'SDG': 'Chargers',
    'LA':  'Rams',     'LAR': 'Rams',     'STL': 'Rams',
    'MIA': 'Dolphins',
    'MIN': 'Vikings',
    'NE':  'Patriots',
    'NO':  'Saints',
    'NYG': 'Giants',
    'NYJ': 'Jets',
    'PHI': 'Eagles',
    'PIT': 'Steelers',
    'SEA': 'Seahawks',
    'SF':  '49ers',
    'TB':  'Buccaneers',
    'TEN': 'Titans',
    'WAS': 'Commanders',
}

def team_name(abbrev):
    if not abbrev or pd.isna(abbrev):
        return 'Unknown'
    return TEAM_NAMES.get(str(abbrev).upper(), str(abbrev))

_POS_NORM = {
    'OLB': 'LB', 'ILB': 'LB', 'MLB': 'LB', 'LLB': 'LB', 'RLB': 'LB',
    'FS': 'S', 'SS': 'S',
    'LCB': 'CB', 'RCB': 'CB', 'RCB/SS': 'CB',
    'LDT': 'DT', 'RDT': 'DT', 'DL': 'DT', 'NT': 'DT',
    'LDE': 'DE', 'RDE': 'DE',
}

def normalize_pos(pos):
    return _POS_NORM.get(str(pos).upper(), pos)

def slugify(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')

def pick_to_round(pick):
    if pd.isna(pick) or pick == 0:
        return 0
    pick = int(pick)
    if pick <= 32:   return 1
    if pick <= 64:   return 2
    if pick <= 96:   return 3
    if pick <= 128:  return 4
    if pick <= 160:  return 5
    if pick <= 224:  return 6
    return 7

def find_col(df, candidates):
    """Return the first column name from candidates that exists in df, or None."""
    for c in candidates:
        if c in df.columns:
            return c
    return None

# ── FETCH: identify PHI players (anyone who has ever been on PHI roster) ─────

print("Fetching all-team seasonal rosters (this takes a moment)...")
all_rosters = nfl.import_seasonal_rosters(YEARS, columns=[
    'season', 'team', 'player_id', 'player_name', 'position',
    'draft_club', 'draft_number', 'entry_year',
])
all_rosters = all_rosters.drop_duplicates(['player_id', 'season', 'team'])

phi_rosters = all_rosters[all_rosters['team'] == 'PHI']
phi_player_ids = set(phi_rosters['player_id'].dropna().unique())
print(f"  PHI players (all-time, {YEARS[0]}-{YEARS[-1]}): {len(phi_player_ids)}")

# Full-career rosters for those players — gives us team-per-season everywhere
career_rosters = all_rosters[all_rosters['player_id'].isin(phi_player_ids)].copy()

# Canonical player metadata: take the most recent roster row per player_id for
# name/draft info; resolve position via _resolve_position (see below).
career_rosters_sorted = career_rosters.sort_values('season')
player_meta = career_rosters_sorted.drop_duplicates('player_id', keep='last')[
    ['player_id', 'player_name', 'draft_club', 'draft_number', 'entry_year']
].set_index('player_id')

# Position resolution: nflreadr's roster position tags are inconsistent in two
# ways. (1) One-off mislabels at career end (Jordan Matthews briefly tagged TE
# in a single roster row). (2) Generic catch-all tags (DB, DT, T) used in some
# seasons even though the player has a specific tag (CB, DE, OT) in others.
#
# Strategy: normalize each roster row, take the mode across all rows, then if
# the mode is a generic catch-all and a more specific version also appears in
# the player's history, prefer the specific. Handles both issues at once.
_GENERIC_TO_SPECIFIC = {
    'DB': ['CB', 'S'],   # DB used generically for cornerbacks and safeties
    'DT': ['DE'],        # DL normalizes to DT but the player may be a DE
    'T':  ['OT'],
}

def _resolve_position(group):
    raw = group['position'].dropna().tolist()
    if not raw:
        return '?'
    normalized = [normalize_pos(p) for p in raw]
    counts = pd.Series(normalized).value_counts()
    top = counts.index[0]
    if top in _GENERIC_TO_SPECIFIC:
        for specific in _GENERIC_TO_SPECIFIC[top]:
            if specific in counts.index:
                return specific
    return top

position_by_pid = career_rosters.groupby('player_id').apply(_resolve_position)
player_meta['position'] = position_by_pid

# Map (player_id, season) -> team_abbrev. For mid-season trades a player may have
# multiple rows; collapse to the team listed in seasonal_data (recent_team).
season_team_lookup = {}
for _, r in career_rosters.iterrows():
    season_team_lookup.setdefault((r['player_id'], int(r['season'])), str(r['team']))

# ── FETCH: league-wide offensive stats (full career for PHI players) ─────────

print("Fetching league-wide seasonal offensive stats (1999-2024)...")
seasonal = nfl.import_seasonal_data(YEARS, s_type='REG')
seasonal = seasonal[seasonal['player_id'].isin(phi_player_ids)].copy()
print(f"  PHI-player offensive season-rows: {len(seasonal)}")

# import_seasonal_data uses 'recent_team' for the team in a season (last team if traded)
team_col_seasonal = find_col(seasonal, ['recent_team', 'team'])

# ── FETCH: PFR seasonal offensive (for Pro Bowl / All-Pro awards) ────────────

# Name->player_id lookup from career rosters (best-effort).
# Used by PBP and manual_awards for name->id matching.
name_to_pid = {}
for _, r in career_rosters.iterrows():
    name_to_pid.setdefault(r['player_name'], r['player_id'])

# ── FETCH: PBP defensive (1999-2015 + 2018-2024), PHI-only ───────────────────
# 2016-2017 are filled by MANUAL_DEF since PBP has gaps in those years.

print(f"Fetching play-by-play defensive stats ({len(PBP_YEARS)} seasons, PHI only)...")
PBP_COLS = [
    'season','game_id','defteam',
    'sack','sack_player_id','half_sack_1_player_id','half_sack_2_player_id',
    'interception','interception_player_id',
    'solo_tackle_1_player_id','solo_tackle_2_player_id',
    'assist_tackle_1_player_id','assist_tackle_2_player_id',
    'assist_tackle_3_player_id','assist_tackle_4_player_id',
]
pbp_raw = nfl.import_pbp_data(PBP_YEARS, columns=PBP_COLS)
pbp_phi = pbp_raw[pbp_raw['defteam'] == 'PHI']

sack_agg   = defaultdict(lambda: defaultdict(float))
int_agg    = defaultdict(lambda: defaultdict(int))
tackle_agg = defaultdict(lambda: defaultdict(float))
games_agg  = defaultdict(lambda: defaultdict(set))

solo_cols   = ['solo_tackle_1_player_id','solo_tackle_2_player_id']
assist_cols = ['assist_tackle_1_player_id','assist_tackle_2_player_id',
               'assist_tackle_3_player_id','assist_tackle_4_player_id']

for _, row in pbp_phi[pbp_phi['sack'] == 1].iterrows():
    s = int(row['season'])
    pid, h1, h2 = row['sack_player_id'], row['half_sack_1_player_id'], row['half_sack_2_player_id']
    if pd.notna(pid):   sack_agg[s][pid] += 1.0
    else:
        if pd.notna(h1): sack_agg[s][h1] += 0.5
        if pd.notna(h2): sack_agg[s][h2] += 0.5

for _, row in pbp_phi[pbp_phi['interception'] == 1].iterrows():
    s = int(row['season'])
    pid = row['interception_player_id']
    if pd.notna(pid): int_agg[s][pid] += 1

for _, row in pbp_phi.iterrows():
    s = int(row['season']); gid = row['game_id']
    for col in solo_cols:
        if pd.notna(row.get(col)): tackle_agg[s][row[col]] += 1.0
    for col in assist_cols:
        if pd.notna(row.get(col)): tackle_agg[s][row[col]] += 0.5
    for col in solo_cols + assist_cols + ['sack_player_id','interception_player_id']:
        pid = row.get(col)
        if pd.notna(pid): games_agg[s][pid].add(gid)

# Build a list of (pid, season, team='PHI', sacks, ints, tackles, g) rows
pbp_rows = []
seasons_seen = set(sack_agg.keys()) | set(int_agg.keys()) | set(tackle_agg.keys())
all_pbp_pids = set()
for d in (sack_agg, int_agg, tackle_agg):
    for season_dict in d.values():
        all_pbp_pids.update(season_dict.keys())

for pid in all_pbp_pids:
    if pid not in phi_player_ids:
        continue
    for season in seasons_seen:
        sk   = sack_agg[season].get(pid, 0)
        ints = int_agg[season].get(pid, 0)
        tkl  = tackle_agg[season].get(pid, 0)
        g    = len(games_agg[season].get(pid, set()))
        if sk > 0 or ints > 0 or tkl > 0:
            pbp_rows.append({'player_id': pid, 'season': season, 'team': 'PHI',
                             'sacks': sk, 'int': ints, 'tackles': tkl, 'games': g})

# ── BUILD: per-player records ────────────────────────────────────────────────

# We accumulate: per (player_id, season, team) a dict of stats. Then collapse
# into seasons[].
records = defaultdict(lambda: defaultdict(dict))  # records[pid][(year, team_abbrev)] = {stat: val, ...}

def add_stat(pid, year, team_abbrev, key, value):
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == 0:
        return
    records[pid][(int(year), str(team_abbrev))][key] = value

def set_games(pid, year, team_abbrev, g):
    if g is None or pd.isna(g):
        return
    g = int(g)
    if g <= 0:
        return
    cur = records[pid][(int(year), str(team_abbrev))].get('games', 0)
    if g > cur:
        records[pid][(int(year), str(team_abbrev))]['games'] = g

# 1) Offensive stats from import_seasonal_data
for _, row in seasonal.iterrows():
    pid = row['player_id']
    season = int(row['season'])
    team_ab = str(row.get(team_col_seasonal) or season_team_lookup.get((pid, season), '')).upper()
    if not team_ab:
        continue

    add_stat(pid, season, team_ab, 'rush_yards', int(row.get('rushing_yards') or 0))
    add_stat(pid, season, team_ab, 'rush_td',    int(row.get('rushing_tds') or 0))

    add_stat(pid, season, team_ab, 'rec',        int(row.get('receptions') or 0))
    add_stat(pid, season, team_ab, 'rec_yards',  int(row.get('receiving_yards') or 0))
    add_stat(pid, season, team_ab, 'rec_td',     int(row.get('receiving_tds') or 0))

    add_stat(pid, season, team_ab, 'pass_yards', int(row.get('passing_yards') or 0))
    add_stat(pid, season, team_ab, 'pass_td',    int(row.get('passing_tds') or 0))
    add_stat(pid, season, team_ab, 'pass_int',   int(row.get('interceptions') or 0))

    set_games(pid, season, team_ab, row.get('games'))

# 2) PBP defensive (1999-2015 + 2018-2024, PHI tenure only)
for r in pbp_rows:
    pid, season, team_ab = r['player_id'], r['season'], r['team']
    add_stat(pid, season, team_ab, 'def_sacks',   round(float(r['sacks']), 1))
    add_stat(pid, season, team_ab, 'def_int',     int(r['int']))
    add_stat(pid, season, team_ab, 'def_tackles', int(round(r['tackles'])))
    set_games(pid, season, team_ab, r['games'])

# 3) Manual 2016-2017 defensive (PHI only)
for entry in MANUAL_DEF:
    pid = name_to_pid.get(entry['player_name'])
    if not pid or pid not in phi_player_ids:
        continue
    season = entry['season']
    team_ab = 'PHI'
    add_stat(pid, season, team_ab, 'def_sacks',   round(float(entry['sacks']), 1))
    add_stat(pid, season, team_ab, 'def_int',     int(entry['interceptions']))
    add_stat(pid, season, team_ab, 'def_tackles', int(entry['tackles']))
    set_games(pid, season, team_ab, entry['g'])

# 4) Super Bowl flags (Eagles wins, hardcoded above)
for pid in list(records.keys()):
    meta = player_meta.loc[pid] if pid in player_meta.index else None
    if meta is None:
        continue
    name = meta['player_name']
    if name not in SB_SEASONS_BY_NAME:
        continue
    for sb_year in SB_SEASONS_BY_NAME[name]:
        # mark super_bowl true for that season on whichever team the player was on
        team_for_year = season_team_lookup.get((pid, sb_year))
        if not team_for_year:
            continue
        # only flag if a record exists; if no stats for that season (rare), create empty
        key = (sb_year, team_for_year)
        if key not in records[pid]:
            records[pid][key] = {}
        records[pid][key]['super_bowl'] = True

# 5) Manual awards merge — hand-curated supplements from manual_awards.py.
# Covers awards data the automated pipeline can't reach: pre-2018 Pro Bowls,
# all defensive/OL Pro Bowls, non-Eagles Super Bowl rings, etc.
try:
    import manual_awards
    EXTRA_SBS    = getattr(manual_awards, 'EXTRA_SUPER_BOWLS', [])
    MAN_PB       = getattr(manual_awards, 'PRO_BOWLS', [])
    MAN_AP1      = getattr(manual_awards, 'ALL_PROS_FIRST_TEAM', [])
    MAN_AP2      = getattr(manual_awards, 'ALL_PROS_SECOND_TEAM', [])
except ImportError:
    print("  WARN: scripts/manual_awards.py not importable. Skipping manual awards merge.")
    EXTRA_SBS = MAN_PB = MAN_AP1 = MAN_AP2 = []

def _apply_manual(entries, mutate_fn, label):
    """Look up each (name, year, team_abbrev) entry and apply mutate_fn to the season-row.
    Returns the number of entries skipped because the player isn't in our PHI universe."""
    skipped = 0
    matched = 0
    for entry in entries:
        try:
            name, year, team_ab = entry
        except (ValueError, TypeError):
            print(f"  WARN: malformed {label} entry: {entry!r}")
            skipped += 1
            continue
        pid = name_to_pid.get(name)
        if not pid or pid not in phi_player_ids:
            skipped += 1
            continue
        key = (int(year), str(team_ab).upper())
        if key not in records[pid]:
            records[pid][key] = {}
        mutate_fn(records[pid][key])
        matched += 1
    return matched, skipped

m_sb,  s_sb  = _apply_manual(EXTRA_SBS, lambda r: r.update(super_bowl=True),  'EXTRA_SUPER_BOWLS')
m_pb,  s_pb  = _apply_manual(MAN_PB,    lambda r: r.update(pro_bowl=True),    'PRO_BOWLS')
m_a1,  s_a1  = _apply_manual(MAN_AP1,   lambda r: r.update(all_pro_team=1),   'ALL_PROS_FIRST_TEAM')
m_a2,  s_a2  = _apply_manual(MAN_AP2,   lambda r: r.update(all_pro_team=2),   'ALL_PROS_SECOND_TEAM')
print(f"Manual awards merged: "
      f"SB {m_sb} matched / {s_sb} skipped, "
      f"PB {m_pb} / {s_pb}, "
      f"AP1 {m_a1} / {s_a1}, "
      f"AP2 {m_a2} / {s_a2}")
if s_sb or s_pb or s_a1 or s_a2:
    print("  (Skipped entries are typically player names not on the PHI roster set.)")

# ── ASSEMBLE: convert to schema, compute career rollup ───────────────────────

CAREER_SUM_KEYS = [
    'rec', 'rec_yards', 'rec_td',
    'rush_yards', 'rush_td',
    'pass_yards', 'pass_td', 'pass_int',
    'def_sacks', 'def_int', 'def_tackles',
]

def compute_career(seasons):
    career = {k: 0 for k in CAREER_SUM_KEYS}
    games_played = 0
    pro_bowls = 0
    ap1 = 0
    ap2 = 0
    super_bowls = []
    seasons_played = 0
    for s in seasons:
        had_action = False
        for k in CAREER_SUM_KEYS:
            v = s.get(k, 0) or 0
            if v:
                career[k] += v
                had_action = True
        games_played += s.get('games', 0) or 0
        if s.get('pro_bowl'): pro_bowls += 1
        if s.get('all_pro_team') == 1: ap1 += 1
        if s.get('all_pro_team') == 2: ap2 += 1
        if s.get('super_bowl'):
            super_bowls.append(s['year'])
        if had_action or s.get('games'):
            seasons_played += 1

    # Round floats (def_sacks) cleanly
    if 'def_sacks' in career:
        career['def_sacks'] = round(career['def_sacks'], 1)

    # Drop zero-keys to keep output tight
    out = {k: v for k, v in career.items() if v}
    out['games_played'] = games_played
    out['seasons_played'] = seasons_played
    out['pro_bowls'] = pro_bowls
    out['first_team_all_pros'] = ap1
    out['second_team_all_pros'] = ap2
    out['super_bowls'] = sorted(super_bowls)
    return out

players_out = []
for pid, season_dict in records.items():
    if pid not in player_meta.index:
        continue
    meta = player_meta.loc[pid]
    name = meta['player_name']
    if not isinstance(name, str) or len(name) < 3 or name.replace('.','').replace('-','').isdigit():
        continue

    seasons = []
    teams_set = set()
    for (year, team_ab), stats in sorted(season_dict.items()):
        team = team_name(team_ab)
        teams_set.add(team)
        record = {
            'year': year,
            'team': team,
            'pro_bowl': bool(stats.get('pro_bowl', False)),
            'all_pro_team': int(stats.get('all_pro_team', 0)),
            'super_bowl': bool(stats.get('super_bowl', False)),
        }
        # Stat keys (only include nonzero)
        for k in CAREER_SUM_KEYS:
            if k in stats and stats[k]:
                record[k] = stats[k]
        if 'games' in stats and stats['games']:
            record['games'] = stats['games']
        seasons.append(record)

    if not seasons:
        continue

    draft_round = pick_to_round(meta.get('draft_number'))
    drafted_by  = team_name(meta.get('draft_club')) if pd.notna(meta.get('draft_club')) else 'Undrafted'
    draft_year  = int(meta['entry_year']) if pd.notna(meta.get('entry_year')) else None

    # Order teams chronologically by first season with team
    team_order = []
    seen = set()
    for s in seasons:
        if s['team'] not in seen:
            team_order.append(s['team'])
            seen.add(s['team'])

    player = {
        'name': name,
        'position': normalize_pos(str(meta['position']) if pd.notna(meta.get('position')) else '?'),
        'draftYear': draft_year,
        'draftRound': draft_round,
        'draftedBy': drafted_by,
        'teams': team_order,
        'seasons': seasons,
        'career': compute_career(seasons),
    }
    players_out.append(player)

players_out.sort(key=lambda p: p['name'])
print(f"\nTotal players: {len(players_out)}")
print(f"Sample: {[p['name'] for p in players_out[:10]]}")

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, 'w') as f:
    json.dump(players_out, f, separators=(',', ':'))

size_kb = os.path.getsize(OUTPUT_PATH) / 1024
print(f"\nWrote {OUTPUT_PATH} ({size_kb:.1f} KB)")
