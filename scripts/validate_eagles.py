"""
Sanity-check the Eagles puzzles by computing the valid-answer pool for every row
and printing a summary. Catches puzzles with empty/tiny answer pools or top-5
results that look broken (e.g. all zeros, suggesting a stat coverage gap).

Run after build_eagles.py finishes:  python3 scripts/validate_eagles.py

Replicates the constraint engine from game.js so the answer pools the validator
prints are exactly what the live game would compute.
"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PLAYERS_PATH = os.path.join(ROOT, 'data', 'eagles', 'players.json')
PUZZLES_PATH = os.path.join(ROOT, 'data', 'eagles', 'puzzles.json')

# Thresholds for flagging suspicious rows
WARN_POOL_SIZE = 10     # fewer than this many answers => probably a constraint mistake
WARN_ZERO_TOP  = True   # warn if every entry in the top 5 has value 0

# ── LOAD ─────────────────────────────────────────────────────────────────────

if not os.path.exists(PLAYERS_PATH):
    print(f"ERROR: {PLAYERS_PATH} not found. Run `python3 scripts/build_eagles.py` first.")
    sys.exit(1)

with open(PLAYERS_PATH) as f:
    PLAYERS = json.load(f)
with open(PUZZLES_PATH) as f:
    PUZZLE_DATA = json.load(f)

ERAS = PUZZLE_DATA.get('eras', {})
POSITION_GROUPS = PUZZLE_DATA.get('position_groups', {})
PUZZLES = PUZZLE_DATA['puzzles']

print(f"Loaded {len(PLAYERS)} players, {len(PUZZLES)} puzzles.\n")

# ── CONSTRAINT ENGINE (mirrors game.js) ──────────────────────────────────────

def year_in_era(year, era_name):
    rng = ERAS.get(era_name)
    return bool(rng) and rng[0] <= year <= rng[1]

def player_meets_player_constraints(player, c):
    if 'position' in c and player.get('position') != c['position']:
        return False
    if 'position_group' in c:
        group = POSITION_GROUPS.get(c['position_group'], [])
        if player.get('position') not in group:
            return False
    if 'draft_round' in c and player.get('draftRound') != c['draft_round']:
        return False
    if 'draft_round_not' in c and player.get('draftRound') == c['draft_round_not']:
        return False
    if 'drafted_by' in c and player.get('draftedBy') != c['drafted_by']:
        return False
    if 'drafted_by_not' in c and player.get('draftedBy') == c['drafted_by_not']:
        return False
    if 'super_bowl' in c:
        wins = (player.get('career') or {}).get('super_bowls', [])
        if c['super_bowl'] not in wins:
            return False
    if 'career_stat_gt' in c:
        for k, v in c['career_stat_gt'].items():
            if (player.get('career') or {}).get(k, 0) <= v:
                return False
    if 'career_stat_lt' in c:
        for k, v in c['career_stat_lt'].items():
            if (player.get('career') or {}).get(k, 0) >= v:
                return False
    return True

def season_meets_constraints(season, c):
    if 'team' in c and season.get('team') != c['team']:
        return False
    if 'year_min' in c and season.get('year', 0) < c['year_min']:
        return False
    if 'year_max' in c and season.get('year', 0) > c['year_max']:
        return False
    if 'era' in c and not year_in_era(season.get('year'), c['era']):
        return False
    if 'era_any' in c and not any(year_in_era(season.get('year'), e) for e in c['era_any']):
        return False
    return True

def get_valid_answers(constraints, stat_key):
    answers = []
    for player in PLAYERS:
        if not player_meets_player_constraints(player, constraints):
            continue
        for season in player.get('seasons', []):
            if not season_meets_constraints(season, constraints):
                continue
            value = season.get(stat_key, 0) or 0
            answers.append((player, season, value))
    answers.sort(key=lambda a: -a[2])
    return answers

# ── REPORT ───────────────────────────────────────────────────────────────────

C_RESET  = "\033[0m"
C_RED    = "\033[91m"
C_YELLOW = "\033[93m"
C_GREEN  = "\033[92m"
C_DIM    = "\033[2m"

def fmt_season(year):
    return f"{year}-{year + 1}"

issues_found = 0

for puzzle in PUZZLES:
    print(f"\n=== Puzzle #{puzzle['id']}: {puzzle['category']} ({puzzle['stat_key']}) ===")
    for i, row in enumerate(puzzle['rows']):
        constraints = row['constraints']
        answers = get_valid_answers(constraints, puzzle['stat_key'])
        top5 = answers[:5]

        # Flag suspicious rows
        flags = []
        if len(answers) == 0:
            flags.append(f"{C_RED}EMPTY POOL{C_RESET}")
            issues_found += 1
        elif len(answers) < WARN_POOL_SIZE:
            flags.append(f"{C_YELLOW}small pool ({len(answers)}){C_RESET}")
            issues_found += 1
        if WARN_ZERO_TOP and top5 and all(a[2] == 0 for a in top5):
            flags.append(f"{C_RED}top-5 all zero{C_RESET}")
            issues_found += 1

        flag_str = (" " + " ".join(flags)) if flags else f" {C_GREEN}OK{C_RESET}"
        print(f"\n  Row {i+1}: {row['qualifier_text']} [{row['qualifier_badge']}]{flag_str}")
        print(f"    {C_DIM}constraints: {json.dumps(constraints, sort_keys=True)}{C_RESET}")
        print(f"    Answers: {len(answers)}")
        for rank, (player, season, value) in enumerate(top5, 1):
            print(f"      {rank}. {player['name']:<24} {fmt_season(season['year'])} ({season['team']:<12}) {value}")

# ── SUMMARY ──────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
if issues_found == 0:
    print(f"{C_GREEN}All puzzle rows passed.{C_RESET}")
else:
    print(f"{C_YELLOW}{issues_found} suspicious row(s) flagged above.{C_RESET}")
    print("Review the constraints — small pools usually indicate either a data gap")
    print("(see CLAUDE.md 'Data coverage') or an over-tight constraint combination.")
