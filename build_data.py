"""
Fetches Eagles player stats from nfl-data-py and outputs data.js.
Run: python3 build_data.py
"""
import nfl_data_py as nfl
import pandas as pd
import json
import re
from collections import defaultdict

YEARS = list(range(1999, 2025))
PFR_YEARS = list(range(2018, 2025))   # PFR seasonal defense only available 2018+
PBP_YEARS = list(range(1999, 2016))   # PBP covers 1999-2015; 2016-2017 are hard-coded below

# 2016-2017 defensive stats -- manually sourced from ESPN/PFR (PFR seasonal and PBP both have a gap here)
# Columns: season, player_name, position, g (games), sacks, interceptions, tackles (combined)
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

# Super Bowl rosters keyed by player name as it appears in PFR/nflreadr
SUPER_BOWL_ROSTERS = {
    "LII": {
        "Nick Foles","Zach Ertz","Jay Ajayi","Corey Clement","LeGarrette Blount",
        "Alshon Jeffery","Torrey Smith","Nelson Agholor","Mack Hollins","Trey Burton",
        "Brent Celek","Jason Kelce","Lane Johnson","Brandon Brooks","Stefen Wisniewski",
        "Jason Peters","Fletcher Cox","Brandon Graham","Derek Barnett","Tim Jernigan",
        "Vinny Curry","Chris Long","Nigel Bradham","Mychal Kendricks","Jordan Hicks",
        "Corey Graham","Patrick Robinson","Jalen Mills","Ronald Darby","Malcolm Jenkins",
        "Rodney McLeod",
    },
    "LVII": {
        "Jalen Hurts","A.J. Brown","DeVonta Smith","Dallas Goedert","Miles Sanders",
        "Boston Scott","Kenneth Gainwell","Jason Kelce","Lane Johnson","Jordan Mailata",
        "Landon Dickerson","Isaac Seumalo","Fletcher Cox","Javon Hargrave",
        "Josh Sweat","Robert Quinn","Brandon Graham","Haason Reddick","T.J. Edwards",
        "Kyzir White","Darius Slay","James Bradberry","Chauncey Gardner-Johnson",
        "Marcus Epps","Reed Blankenship",
    },
    "LIX": {
        "Jalen Hurts","A.J. Brown","DeVonta Smith","Dallas Goedert","Saquon Barkley",
        "Kenneth Gainwell","Will Shipley","Lane Johnson","Jordan Mailata",
        "Landon Dickerson","Cam Jurgens","Brandon Graham","Josh Sweat",
        "Jalen Carter","Milton Williams","Nolan Smith","Nakobe Dean","Zack Baun",
        "Darius Slay","Quinyon Mitchell","Reed Blankenship","C.J. Gardner-Johnson",
    },
}

SB_BY_NAME = defaultdict(list)
for label, names in SUPER_BOWL_ROSTERS.items():
    for name in names:
        SB_BY_NAME[name].append(label)

# ── FETCH ROSTERS (team + draft info per player per season) ───────────────────

print("Fetching seasonal rosters (this takes a moment)...")
rosters_raw = nfl.import_seasonal_rosters(YEARS, columns=[
    'season','team','player_id','player_name','position',
    'draft_club','draft_number','entry_year','gsis_it_id'
])
phi_rosters = rosters_raw[rosters_raw['team'] == 'PHI'].copy()
phi_rosters = phi_rosters.drop_duplicates(['player_id','season'])

# Build draft info lookup: player_id -> (draft_round, drafted_by)
# draft_number is overall pick; convert to round (32 picks per round approx)
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

draft_info = {}
for _, r in phi_rosters.drop_duplicates('player_id').iterrows():
    pid = r['player_id']
    draft_info[pid] = {
        'draft_round': pick_to_round(r.get('draft_number')),
        'drafted_by': str(r['draft_club']) if pd.notna(r.get('draft_club')) else 'UDFA',
    }

# ── FETCH SEASONAL OFFENSIVE STATS ───────────────────────────────────────────

print("Fetching seasonal offensive stats (1999-2024)...")
seasonal = nfl.import_seasonal_data(YEARS, s_type='REG')

# Join with PHI rosters to get only Eagles seasons
phi_ids_by_season = phi_rosters.groupby('season')['player_id'].apply(set).to_dict()

# Tag each seasonal row with whether that player was on PHI that year
def was_on_phi(row):
    return row['player_id'] in phi_ids_by_season.get(row['season'], set())

seasonal['on_phi'] = seasonal.apply(was_on_phi, axis=1)
phi_seasonal = seasonal[seasonal['on_phi']].copy()

# Bring in player name and position from rosters
roster_lookup = phi_rosters[['player_id','season','player_name','position']].set_index(['player_id','season'])
phi_seasonal = phi_seasonal.join(roster_lookup, on=['player_id','season'])

# ── FETCH DEFENSIVE SACKS (2018+) ─────────────────────────────────────────────

print("Fetching defensive stats (2018-2024 via PFR)...")
def_pfr = nfl.import_seasonal_pfr('def', PFR_YEARS)
def_pfr_phi = def_pfr[def_pfr['tm'] == 'PHI'][['season','player','pfr_id','pos','g','sk','int','comb']].copy()

name_to_pid = {}
for _, r in phi_rosters.iterrows():
    name_to_pid[r['player_name']] = r['player_id']

def_pfr_phi['player_id'] = def_pfr_phi['player'].map(name_to_pid)

print("Fetching play-by-play defensive stats (1999-2015)...")
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

pid_to_name = dict(zip(phi_rosters['player_id'], phi_rosters['player_name']))
pid_to_pos  = dict(zip(phi_rosters['player_id'], phi_rosters['position']))

# Aggregate sacks
sack_agg = defaultdict(lambda: defaultdict(float))
for _, row in pbp_phi[pbp_phi['sack'] == 1].iterrows():
    s = int(row['season'])
    pid, h1, h2 = row['sack_player_id'], row['half_sack_1_player_id'], row['half_sack_2_player_id']
    if pd.notna(pid):   sack_agg[s][pid] += 1.0
    else:
        if pd.notna(h1): sack_agg[s][h1] += 0.5
        if pd.notna(h2): sack_agg[s][h2] += 0.5

# Aggregate interceptions
int_agg = defaultdict(lambda: defaultdict(int))
for _, row in pbp_phi[pbp_phi['interception'] == 1].iterrows():
    s = int(row['season'])
    pid = row['interception_player_id']
    if pd.notna(pid): int_agg[s][pid] += 1

# Aggregate tackles (solo = 1 pt, assist = 0.5 pt -> combined)
tackle_agg = defaultdict(lambda: defaultdict(float))
solo_cols   = ['solo_tackle_1_player_id','solo_tackle_2_player_id']
assist_cols = ['assist_tackle_1_player_id','assist_tackle_2_player_id',
               'assist_tackle_3_player_id','assist_tackle_4_player_id']
for _, row in pbp_phi.iterrows():
    s = int(row['season'])
    for col in solo_cols:
        if pd.notna(row.get(col)): tackle_agg[s][row[col]] += 1.0
    for col in assist_cols:
        if pd.notna(row.get(col)): tackle_agg[s][row[col]] += 0.5

# Aggregate games played per player per season from PBP
games_agg = defaultdict(lambda: defaultdict(set))
all_tackle_pids = set()
for _, row in pbp_phi.iterrows():
    s = int(row['season'])
    gid = row['game_id']
    for col in solo_cols + assist_cols + ['sack_player_id','interception_player_id']:
        pid = row.get(col)
        if pd.notna(pid):
            games_agg[s][pid].add(gid)
            all_tackle_pids.add(pid)

# Collect all unique player/season combos from PBP
all_pbp_pids = set()
for d in [sack_agg, int_agg, tackle_agg]:
    for season_dict in d.values():
        all_pbp_pids.update(season_dict.keys())

pbp_rows = []
for pid in all_pbp_pids:
    for season in set(list(sack_agg.keys()) + list(int_agg.keys()) + list(tackle_agg.keys())):
        sk  = sack_agg[season].get(pid, 0)
        ints = int_agg[season].get(pid, 0)
        tkl = tackle_agg[season].get(pid, 0)
        g   = len(games_agg[season].get(pid, set()))
        if sk > 0 or ints > 0 or tkl > 0:
            pbp_rows.append({
                'season': season,
                'player': pid_to_name.get(pid, pid),
                'pfr_id': None,
                'pos': pid_to_pos.get(pid, '?'),
                'g': g,
                'sk': sk,
                'int': ints,
                'comb': round(tkl),
                'player_id': pid,
            })
def_pbp_phi = pd.DataFrame(pbp_rows) if pbp_rows else pd.DataFrame(
    columns=['season','player','pfr_id','pos','g','sk','int','comb','player_id'])

# Manual supplement for 2016-2017
manual_rows = []
for entry in MANUAL_DEF:
    pid = name_to_pid.get(entry['player_name'])
    manual_rows.append({
        'season': entry['season'],
        'player': entry['player_name'],
        'pfr_id': None,
        'pos': entry['position'],
        'g': entry['g'],
        'sk': entry['sacks'],
        'int': entry['interceptions'],
        'comb': entry['tackles'],
        'player_id': pid,
    })
def_manual = pd.DataFrame(manual_rows)

# Align columns before concat
for df in [def_pfr_phi, def_pbp_phi, def_manual]:
    for col in ['g','sk','int','comb']:
        if col not in df.columns:
            df[col] = None

def_phi = pd.concat([def_pfr_phi, def_pbp_phi, def_manual], ignore_index=True)

# ── BUILD PLAYER RECORDS ──────────────────────────────────────────────────────

def slugify(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')

_POS_NORM = {
    'OLB': 'LB', 'ILB': 'LB', 'MLB': 'LB', 'LLB': 'LB', 'RLB': 'LB',
    'FS': 'S', 'SS': 'S',
    'LCB': 'CB', 'RCB': 'CB', 'RCB/SS': 'CB',
    'LDT': 'DT', 'RDT': 'DT', 'DL': 'DT', 'NT': 'DT',
    'LDE': 'DE', 'RDE': 'DE',
}

def normalize_pos(pos):
    return _POS_NORM.get(str(pos).upper(), pos)

players = {}

# Offensive players from seasonal data
for _, row in phi_seasonal.iterrows():
    pid = row['player_id']
    name = row.get('player_name','')
    if not name or pd.isna(name):
        continue

    if pid not in players:
        di = draft_info.get(pid, {'draft_round': 0, 'drafted_by': 'UDFA'})
        players[pid] = {
            "id": slugify(name),
            "name": name,
            "position": normalize_pos(str(row.get('position','?')) if pd.notna(row.get('position')) else '?'),
            "draftRound": di['draft_round'],
            "draftedBy": di['drafted_by'],
            "superBowl": SB_BY_NAME.get(name, []),
            "seasons": {}
        }

    season = int(row['season'])
    stats = {}

    rush_yds = row.get('rushing_yards', 0) or 0
    rec_yds = row.get('receiving_yards', 0) or 0
    pass_yds = row.get('passing_yards', 0) or 0

    if rush_yds > 0:
        stats['rushing_yards'] = int(rush_yds)
        stats['rushing_tds'] = int(row.get('rushing_tds', 0) or 0)
    if rec_yds > 0:
        stats['receiving_yards'] = int(rec_yds)
        stats['receiving_tds'] = int(row.get('receiving_tds', 0) or 0)
        stats['receptions'] = int(row.get('receptions', 0) or 0)
    if pass_yds > 0:
        stats['passing_yards'] = int(pass_yds)
        stats['passing_tds'] = int(row.get('passing_tds', 0) or 0)
        stats['interceptions'] = int(row.get('interceptions', 0) or 0)

    stats['games'] = int(row.get('games', 0) or 0)

    if len(stats) > 1:  # more than just games
        players[pid]['seasons'][season] = stats

# Defensive players (sacks, interceptions, tackles, games)
for _, row in def_phi.iterrows():
    pid = row.get('player_id')
    name = row['player']

    if pd.isna(pid) or not isinstance(name, str) or len(name) < 3:
        continue

    pfr_fallback = row.get('pfr_id')
    if pd.isna(pid):
        pid = f"pfr_{pfr_fallback}" if pd.notna(pfr_fallback) else None
    if not pid:
        continue

    if pid not in players:
        di = draft_info.get(pid, {'draft_round': 0, 'drafted_by': 'UDFA'})
        players[pid] = {
            "id": slugify(name),
            "name": name,
            "position": normalize_pos(str(row.get('pos', '?'))),
            "draftRound": di['draft_round'],
            "draftedBy": di['drafted_by'],
            "superBowl": SB_BY_NAME.get(name, []),
            "seasons": {}
        }

    season = int(row['season'])
    if season not in players[pid]['seasons']:
        players[pid]['seasons'][season] = {}

    sk   = row.get('sk',   0) or 0
    ints = row.get('int',  0) or 0
    tkl  = row.get('comb', 0) or 0
    g    = row.get('g',    0) or 0

    if sk   > 0: players[pid]['seasons'][season]['sacks']        = round(float(sk), 1)
    if ints > 0: players[pid]['seasons'][season]['interceptions'] = int(ints)
    if tkl  > 0: players[pid]['seasons'][season]['tackles']      = int(tkl)
    if g    > 0: players[pid]['seasons'][season]['games']        = int(g)

# ── CLEAN UP ──────────────────────────────────────────────────────────────────

player_list = [
    p for p in players.values()
    if p['seasons'] and p['name'] and not p['name'].replace('.','').replace('-','').isdigit() and len(p['name']) > 2
]
player_list.sort(key=lambda p: p['name'])
print(f"\nTotal players: {len(player_list)}")
print(f"Sample: {[p['name'] for p in player_list[:15]]}")

# ── WRITE DATA.JS ─────────────────────────────────────────────────────────────

def seasons_to_js(seasons):
    lines = ["{"]
    for year in sorted(seasons.keys()):
        stats = seasons[year]
        stats_str = ", ".join(f"{k}: {v}" for k, v in stats.items())
        lines.append(f"      {year}: {{ {stats_str} }},")
    lines.append("    }")
    return "\n".join(lines)

def player_to_js(p):
    sb = json.dumps(p['superBowl'])
    seasons_js = seasons_to_js(p['seasons'])
    return (
        f'  {{\n'
        f'    id: "{p["id"]}", name: "{p["name"]}", position: "{p["position"]}",\n'
        f'    draftRound: {p["draftRound"]}, draftedBy: "{p["draftedBy"]}",\n'
        f'    superBowl: {sb},\n'
        f'    seasons: {seasons_js}\n'
        f'  }}'
    )

players_js = ",\n".join(player_to_js(p) for p in player_list)

output = f"""// Auto-generated by build_data.py
// Source: nfl-data-py / nflreadr  |  Offensive: 1999-2024  |  Defensive sacks: 2018-2024

const ERAS = {{
  "Buddy Ryan":    [1986, 1990],
  "Rich Kotite":   [1991, 1994],
  "Ray Rhodes":    [1995, 1998],
  "Andy Reid":     [1999, 2012],
  "Chip Kelly":    [2013, 2015],
  "Doug Pederson": [2016, 2020],
  "Nick Sirianni": [2021, 2024],
}};

const POSITION_GROUPS = {{
  skill:        ["QB", "RB", "WR", "TE"],
  pass_catcher: ["WR", "TE", "RB"],
  offense:      ["QB", "RB", "WR", "TE", "OT", "G", "C"],
  defense:      ["DE", "DT", "LB", "CB", "S", "DB"],
}};

const PLAYERS = [
{players_js}
];

const PUZZLES = [
  {{
    id: 1,
    category: "RUSHING YDS",
    statKey: "rushing_yards",
    rows: [
      {{ qualifierText: "ANDY REID ERA (1999-2012)", qualifierBadge: "SAME SEASON",
        constraints: {{ era: "Andy Reid", position_group: "skill" }} }},
      {{ qualifierText: "CHIP KELLY OR PEDERSON ERA (2013-2020)", qualifierBadge: "SAME SEASON",
        constraints: {{ era_any: ["Chip Kelly", "Doug Pederson"], position_group: "skill" }} }},
      {{ qualifierText: "SIRIANNI ERA (2021-PRESENT)", qualifierBadge: "SAME SEASON",
        constraints: {{ era: "Nick Sirianni", position_group: "skill" }} }},
      {{ qualifierText: "NOT DRAFTED BY EAGLES", qualifierBadge: "ANYTIME IN CAREER",
        constraints: {{ draftedBy_not: "PHI", position_group: "skill" }} }},
      {{ qualifierText: "NOT A 1ST ROUND PICK", qualifierBadge: "ANYTIME IN CAREER",
        constraints: {{ draftRound_not: 1, position_group: "skill" }} }},
    ]
  }},
  {{
    id: 2,
    category: "RECEIVING YDS",
    statKey: "receiving_yards",
    rows: [
      {{ qualifierText: "ANDY REID ERA (1999-2012)", qualifierBadge: "SAME SEASON",
        constraints: {{ era: "Andy Reid", position_group: "pass_catcher" }} }},
      {{ qualifierText: "SIRIANNI ERA - WR ONLY", qualifierBadge: "SAME SEASON",
        constraints: {{ era: "Nick Sirianni", position: "WR" }} }},
      {{ qualifierText: "TIGHT END", qualifierBadge: "SAME SEASON",
        constraints: {{ position: "TE" }} }},
      {{ qualifierText: "SUPER BOWL LII ROSTER", qualifierBadge: "ANYTIME IN CAREER",
        constraints: {{ superBowl: "LII", position_group: "pass_catcher" }} }},
      {{ qualifierText: "NOT DRAFTED BY EAGLES", qualifierBadge: "ANYTIME IN CAREER",
        constraints: {{ draftedBy_not: "PHI", position_group: "pass_catcher" }} }},
    ]
  }},
  {{
    id: 3,
    category: "SACKS",
    statKey: "sacks",
    rows: [
      {{ qualifierText: "ANDY REID ERA (1999-2012)", qualifierBadge: "SAME SEASON",
        constraints: {{ era: "Andy Reid", position_group: "defense" }} }},
      {{ qualifierText: "SIRIANNI ERA (2021-PRESENT)", qualifierBadge: "SAME SEASON",
        constraints: {{ era: "Nick Sirianni", position_group: "defense" }} }},
      {{ qualifierText: "1ST ROUND PICK", qualifierBadge: "ANYTIME IN CAREER",
        constraints: {{ draftRound: 1, position_group: "defense" }} }},
      {{ qualifierText: "NOT DRAFTED BY EAGLES", qualifierBadge: "ANYTIME IN CAREER",
        constraints: {{ draftedBy_not: "PHI", position_group: "defense" }} }},
      {{ qualifierText: "NOT A 1ST ROUND PICK", qualifierBadge: "ANYTIME IN CAREER",
        constraints: {{ draftRound_not: 1, position_group: "defense" }} }},
    ]
  }},
  {{
    id: 4,
    category: "INTERCEPTIONS",
    statKey: "interceptions",
    rows: [
      {{ qualifierText: "ANDY REID ERA (1999-2012)", qualifierBadge: "SAME SEASON",
        constraints: {{ era: "Andy Reid", position_group: "defense" }} }},
      {{ qualifierText: "PEDERSON OR SIRIANNI ERA (2016-PRESENT)", qualifierBadge: "SAME SEASON",
        constraints: {{ era_any: ["Doug Pederson", "Nick Sirianni"], position_group: "defense" }} }},
      {{ qualifierText: "CORNERBACK", qualifierBadge: "SAME SEASON",
        constraints: {{ position: "CB" }} }},
      {{ qualifierText: "NOT DRAFTED BY EAGLES", qualifierBadge: "ANYTIME IN CAREER",
        constraints: {{ draftedBy_not: "PHI", position_group: "defense" }} }},
      {{ qualifierText: "NOT A 1ST ROUND PICK", qualifierBadge: "ANYTIME IN CAREER",
        constraints: {{ draftRound_not: 1, position_group: "defense" }} }},
    ]
  }},
  {{
    id: 5,
    category: "TACKLES",
    statKey: "tackles",
    rows: [
      {{ qualifierText: "ANDY REID ERA (1999-2012)", qualifierBadge: "SAME SEASON",
        constraints: {{ era: "Andy Reid", position_group: "defense" }} }},
      {{ qualifierText: "SIRIANNI ERA (2021-PRESENT)", qualifierBadge: "SAME SEASON",
        constraints: {{ era: "Nick Sirianni", position_group: "defense" }} }},
      {{ qualifierText: "LINEBACKER", qualifierBadge: "SAME SEASON",
        constraints: {{ position: "LB" }} }},
      {{ qualifierText: "NOT DRAFTED BY EAGLES", qualifierBadge: "ANYTIME IN CAREER",
        constraints: {{ draftedBy_not: "PHI", position_group: "defense" }} }},
      {{ qualifierText: "NOT A 1ST ROUND PICK", qualifierBadge: "ANYTIME IN CAREER",
        constraints: {{ draftRound_not: 1, position_group: "defense" }} }},
    ]
  }},
];
"""

with open('/Users/ejbermudez/Desktop/eagles-statpad/data.js', 'w') as f:
    f.write(output)

print("\ndata.js written successfully.")
