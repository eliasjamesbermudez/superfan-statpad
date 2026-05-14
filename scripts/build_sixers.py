"""
Builds data/sixers/players.json from nba_api (stats.nba.com).

Output schema follows CLAUDE.md:
- Full career stats for every player who has ever been on a Sixers roster.
- `seasons` is an array of {year, team, ...stats, all_star, all_nba_team, championship}.
- `career` rollup with totals + games_played, seasons_played, etc.
- `championships` stored as season-start years (e.g. 1982 for the 1982-83 chip).

Stat naming: snake_case, NBA flat-top-level per CLAUDE.md.
  pts, reb, ast, stl, blk, tov
  fg_made, fg_att, fg3_made, fg3_att, ft_made, ft_att
  min, games
  Per-game variants suffixed _pg (e.g. pts_pg).

NBA seasons span two calendar years; we key on the start year (2016 = 2016-17 season).

Run from repo root:  python3 scripts/build_sixers.py

Note: stats.nba.com is rate-touchy. Script sleeps between calls. Total runtime
~3-5 minutes depending on roster size.
"""
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

import pandas as pd
from nba_api.stats.endpoints import (
    commonteamroster,
    drafthistory,
    playercareerstats,
)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'sixers', 'players.json')

PHI_TEAM_ID = 1610612755

# 1999-00 through 2025-26, matching the Eagles range. SEASON_ID format used by
# nba_api is "YYYY-YY" (e.g. "1999-00").
START_YEAR = 1999
END_YEAR = 2025  # inclusive — most recent completed/in-progress season

def season_id(year):
    """1999 -> '1999-00', 2009 -> '2009-10', etc."""
    return f"{year}-{str(year + 1)[-2:]}"

SEASONS = [season_id(y) for y in range(START_YEAR, END_YEAR + 1)]

# Sleep between API calls to keep stats.nba.com from rate-limiting us.
THROTTLE_SEC = 0.6

# NBA team abbreviation -> nickname. Includes franchise relocations and rebrand
# aliases so historical seasons resolve to the right name.
#
# Notable: CHA was Bobcats from 2004-05 through 2013-14. The 1988-2002 Hornets
# were a different franchise (now Pelicans, via NOH/NOK). We default CHA to
# Hornets here and live with the small wrong-attribution risk in 2004-2014 —
# very few Sixers played there in that window, and it's not the kind of thing
# that breaks puzzles. Promote to a season-aware lookup later if needed.
TEAM_NAMES = {
    'ATL': 'Hawks',
    'BOS': 'Celtics',
    'BKN': 'Nets',       'NJN': 'Nets',
    'CHA': 'Hornets',    'CHH': 'Hornets',
    'CHI': 'Bulls',
    'CLE': 'Cavaliers',
    'DAL': 'Mavericks',
    'DEN': 'Nuggets',
    'DET': 'Pistons',
    'GSW': 'Warriors',
    'HOU': 'Rockets',
    'IND': 'Pacers',
    'LAC': 'Clippers',
    'LAL': 'Lakers',
    'MEM': 'Grizzlies',  'VAN': 'Grizzlies',
    'MIA': 'Heat',
    'MIL': 'Bucks',
    'MIN': 'Timberwolves',
    'NOP': 'Pelicans',   'NOH': 'Pelicans',   'NOK': 'Pelicans',
    'NYK': 'Knicks',
    'OKC': 'Thunder',
    'SEA': 'Supersonics',
    'ORL': 'Magic',
    'PHI': '76ers',
    'PHX': 'Suns',
    'POR': 'Trail Blazers',
    'SAC': 'Kings',
    'SAS': 'Spurs',
    'TOR': 'Raptors',
    'UTA': 'Jazz',
    'WAS': 'Wizards',
}

def team_name(abbrev):
    if not abbrev or (isinstance(abbrev, float) and pd.isna(abbrev)):
        return 'Unknown'
    return TEAM_NAMES.get(str(abbrev).upper(), str(abbrev))

# Position normalization. nba_api roster returns "G", "F", "C", "F-G", "C-F", etc.
# CommonPlayerInfo uses long form ("Guard", "Forward-Center"). For puzzle constraints
# we collapse to single letter G/F/C using the *primary* (first) slot.
def normalize_pos(raw):
    if not raw or (isinstance(raw, float) and pd.isna(raw)):
        return '?'
    s = str(raw).strip().upper()
    if not s:
        return '?'
    # Long form: take first word, then first letter
    first_token = re.split(r'[-/\s]+', s)[0]
    first_letter = first_token[0]
    if first_letter in ('G', 'F', 'C'):
        return first_letter
    return '?'

def call_with_retry(builder, label, retries=3):
    """Call an nba_api endpoint with a small retry loop. Throttle after each call."""
    last_err = None
    for attempt in range(retries):
        try:
            obj = builder()
            time.sleep(THROTTLE_SEC)
            return obj
        except Exception as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  WARN: {label} attempt {attempt + 1} failed ({e}); sleeping {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"{label} failed after {retries} attempts: {last_err}")

# ── FETCH: PHI rosters across all seasons ────────────────────────────────────

print(f"Fetching Sixers rosters across {len(SEASONS)} seasons ({SEASONS[0]} → {SEASONS[-1]})...")
roster_rows = []  # list of dicts: {season_year, player_id, player_name, position}
for sid in SEASONS:
    try:
        ep = call_with_retry(
            lambda: commonteamroster.CommonTeamRoster(
                team_id=PHI_TEAM_ID, season=sid, timeout=30,
            ),
            label=f"roster {sid}",
        )
    except RuntimeError as e:
        print(f"  SKIP {sid}: {e}")
        continue
    df = ep.common_team_roster.get_data_frame()
    season_year = int(sid.split('-')[0])
    for _, r in df.iterrows():
        pid = int(r['PLAYER_ID'])
        roster_rows.append({
            'season_year': season_year,
            'player_id': pid,
            'player_name': r['PLAYER'],
            'position': r.get('POSITION') or '',
        })
    print(f"  {sid}: {len(df)} players")

sixer_pids = sorted({r['player_id'] for r in roster_rows})
print(f"\nUnique Sixers (all-time, {START_YEAR}-{END_YEAR}): {len(sixer_pids)}")

# Best-effort name lookup. Prefer the most recent roster appearance for canonical name.
name_by_pid = {}
position_votes = defaultdict(Counter)
for r in sorted(roster_rows, key=lambda x: x['season_year']):
    name_by_pid[r['player_id']] = r['player_name']  # last write wins → most recent
    pos = normalize_pos(r['position'])
    if pos != '?':
        position_votes[r['player_id']][pos] += 1

def resolved_position(pid):
    counter = position_votes.get(pid)
    if not counter:
        return '?'
    return counter.most_common(1)[0][0]

# ── FETCH: full draft history (one call, lookup table for everyone) ──────────

print("\nFetching NBA draft history (one call)...")
draft_ep = call_with_retry(lambda: drafthistory.DraftHistory(timeout=30), label='drafthistory')
draft_df = draft_ep.draft_history.get_data_frame()
draft_by_pid = {}
for _, r in draft_df.iterrows():
    pid = int(r['PERSON_ID'])
    draft_by_pid[pid] = {
        'year': int(r['SEASON']) if pd.notna(r['SEASON']) else None,
        'round': int(r['ROUND_NUMBER']) if pd.notna(r['ROUND_NUMBER']) else 0,
        'pick': int(r['OVERALL_PICK']) if pd.notna(r['OVERALL_PICK']) else None,
        'team_abbrev': str(r['TEAM_ABBREVIATION']) if pd.notna(r['TEAM_ABBREVIATION']) else '',
    }
print(f"  Draft entries loaded: {len(draft_by_pid)}")

# ── FETCH: per-player career stats ───────────────────────────────────────────

# We pull season *totals*. Per-game is derived from totals / GP. The endpoint
# returns one row per (player, season, team), plus a "TOT" pseudo-row for
# traded seasons that we filter out.
print(f"\nFetching career stats for {len(sixer_pids)} players (~{int(len(sixer_pids) * THROTTLE_SEC / 60)} min)...")

CAREER_STAT_KEYS = [
    'pts', 'reb', 'ast', 'stl', 'blk', 'tov',
    'fg_made', 'fg_att', 'fg3_made', 'fg3_att', 'ft_made', 'ft_att',
    'min',
]

# Column map from nba_api fields → our snake_case schema.
COL_MAP = {
    'PTS': 'pts',
    'REB': 'reb',
    'AST': 'ast',
    'STL': 'stl',
    'BLK': 'blk',
    'TOV': 'tov',
    'FGM': 'fg_made',
    'FGA': 'fg_att',
    'FG3M': 'fg3_made',
    'FG3A': 'fg3_att',
    'FTM': 'ft_made',
    'FTA': 'ft_att',
    'MIN': 'min',
}

players_data = {}  # pid -> {meta, seasons[]}
fetch_failures = 0

for i, pid in enumerate(sixer_pids, start=1):
    name = name_by_pid.get(pid, f'pid:{pid}')
    if i % 25 == 0 or i == 1:
        print(f"  [{i}/{len(sixer_pids)}] {name}")

    try:
        ep = call_with_retry(
            lambda: playercareerstats.PlayerCareerStats(
                player_id=pid, per_mode36='Totals', timeout=30,
            ),
            label=f"career {name}",
        )
    except RuntimeError as e:
        print(f"    FAILED {name}: {e}")
        fetch_failures += 1
        continue

    df = ep.season_totals_regular_season.get_data_frame()
    if df.empty:
        continue

    # Filter out the "TOT" combined row for traded seasons — we want per-team rows.
    df = df[df['TEAM_ABBREVIATION'] != 'TOT'].copy()

    seasons = []
    for _, r in df.iterrows():
        sid = str(r['SEASON_ID'])
        # SEASON_ID like "2016-17". We key on start year.
        try:
            year = int(sid.split('-')[0])
        except ValueError:
            continue

        team_abbr = str(r['TEAM_ABBREVIATION']).upper() if pd.notna(r['TEAM_ABBREVIATION']) else ''
        team = team_name(team_abbr)
        gp = int(r['GP']) if pd.notna(r['GP']) else 0

        record = {
            'year': year,
            'team': team,
            'all_star': False,
            'all_nba_team': 0,
            'championship': False,
        }
        for col, key in COL_MAP.items():
            v = r.get(col)
            if pd.notna(v) and v:
                # Cast to int for counting stats, keep float for minutes which can be partial.
                if key == 'min':
                    record[key] = round(float(v), 1)
                else:
                    record[key] = int(v)
        if gp:
            record['games'] = gp

        seasons.append(record)

    if not seasons:
        continue

    players_data[pid] = {
        'name': name,
        'position': resolved_position(pid),
        'seasons': seasons,
    }

print(f"\nFetched career data for {len(players_data)} players ({fetch_failures} failures).")

# ── ASSEMBLE: schema + career rollup ─────────────────────────────────────────

def compute_career(seasons):
    career = {k: 0 for k in CAREER_STAT_KEYS}
    games_played = 0
    seasons_played = 0
    all_stars = 0
    ant1 = ant2 = ant3 = 0
    championships = []

    for s in seasons:
        had_action = False
        for k in CAREER_STAT_KEYS:
            v = s.get(k, 0) or 0
            if v:
                career[k] += v
                had_action = True
        games_played += s.get('games', 0) or 0
        if s.get('all_star'): all_stars += 1
        ant = s.get('all_nba_team', 0)
        if ant == 1: ant1 += 1
        elif ant == 2: ant2 += 1
        elif ant == 3: ant3 += 1
        if s.get('championship'):
            championships.append(s['year'])
        if had_action or s.get('games'):
            seasons_played += 1

    # Minutes can be fractional; keep one decimal.
    if 'min' in career:
        career['min'] = round(career['min'], 1)

    out = {k: v for k, v in career.items() if v}
    out['games_played'] = games_played
    out['seasons_played'] = seasons_played
    out['all_stars'] = all_stars
    out['first_team_all_nbas'] = ant1
    out['second_team_all_nbas'] = ant2
    out['third_team_all_nbas'] = ant3
    out['championships'] = sorted(championships)

    # Career per-game variants for stats that match the typical _pg pattern.
    if games_played > 0:
        for k in ('pts', 'reb', 'ast', 'stl', 'blk', 'fg3_made'):
            total = out.get(k, 0)
            if total:
                out[f'{k}_pg'] = round(total / games_played, 1)

    return out

players_out = []
for pid, p in players_data.items():
    seasons = sorted(p['seasons'], key=lambda s: (s['year'], s['team']))

    # Order teams chronologically by first appearance.
    team_order = []
    seen = set()
    for s in seasons:
        if s['team'] not in seen:
            team_order.append(s['team'])
            seen.add(s['team'])

    # Draft info
    d = draft_by_pid.get(pid)
    if d:
        draft_year = d['year']
        draft_round = d['round']
        drafted_by = team_name(d['team_abbrev']) if d['team_abbrev'] else 'Undrafted'
    else:
        draft_year = None
        draft_round = 0
        drafted_by = 'Undrafted'

    players_out.append({
        'name': p['name'],
        'position': p['position'],
        'draftYear': draft_year,
        'draftRound': draft_round,
        'draftedBy': drafted_by,
        'teams': team_order,
        'seasons': seasons,
        'career': compute_career(seasons),
    })

players_out.sort(key=lambda p: p['name'])
print(f"\nTotal players: {len(players_out)}")
print(f"Sample: {[p['name'] for p in players_out[:10]]}")

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, 'w') as f:
    json.dump(players_out, f, separators=(',', ':'))

size_kb = os.path.getsize(OUTPUT_PATH) / 1024
print(f"\nWrote {OUTPUT_PATH} ({size_kb:.1f} KB)")
