# Hometeam Statpad

User-facing name: **Hometeam Statpad**.

Daily stats guessing game across multiple sports teams, inspired by [StatPad](https://www.statpadgame.com/). Users pick a team or a city group (e.g., Philadelphia = Eagles + Sixers + Phillies) and play that day's puzzle from the chosen pool.

Currently deployed as an Eagles-only MVP at https://eliasjamesbermudez.github.io/hometeam-statpad/. Repo on GitHub: `eliasjamesbermudez/hometeam-statpad`. Local folder: `~/Desktop/hometeam-statpad`.

Note: the visible UI still says "EAGLES STATPAD" in `index.html` (header and `<title>`). That stays Eagles-branded until multi-team support ships, since there's nothing else to switch to yet.

## Scope

- Sports: NFL, NBA, MLB. NHL is intentionally out.
- Team selector design intent: a user can pick a single team, multiple teams, or a city group that bundles teams. In multi-team mode, daily puzzles draw from the combined pool.
- City groups are first-class. The Philly group (Eagles, Sixers, Phillies) is the canonical example.

## Tech stack

- Vanilla HTML, CSS, JS. No framework, no build step.
- Static hosting on GitHub Pages from `main`. Push to deploy, live in 30 to 60 seconds.
- Python data pipeline produces static JSON files committed to the repo. One build script per team.

## Repo structure

```
index.html
game.js
data/
  manifest.json              (available teams and city groups)
  eagles/
    players.json             (pipeline output, committed)
    puzzles.json             (hand-authored content)
scripts/
  build_eagles.py            (pipeline)
  manual_awards.py           (hand-curated supplements for gaps in nfl_data_py)
  validate_eagles.py         (sanity-checks puzzle answer pools)
  requirements.txt
.venv/                       (gitignored)
```

Planned additions when more teams ship: `data/sixers/`, `data/phillies/`, `scripts/build_sixers.py`, etc. Same shape per team.

Rationale for per-team JSON: each team's data is loadable independently, the manifest tells the UI what's available, and we can add new teams without touching existing files.

## Player record schema

```json
{
  "name": "A.J. Brown",
  "position": "WR",
  "draftYear": 2019,
  "draftRound": 2,
  "draftedBy": "Titans",
  "teams": ["Titans", "Eagles"],
  "seasons": [
    {
      "year": 2019,
      "team": "Titans",
      "rec": 52,
      "rec_yards": 1051,
      "rec_td": 8,
      "pro_bowl": false,
      "all_pro_team": 0,
      "super_bowl": false
    }
  ],
  "career": {
    "rec": 350,
    "rec_yards": 5400,
    "rec_td": 49,
    "games_played": 87,
    "seasons_played": 6,
    "pro_bowls": 3,
    "first_team_all_pros": 1,
    "second_team_all_pros": 0,
    "super_bowls": []
  }
}
```

Notes:
- `teams` is cached and derived from `seasons` by the pipeline (not hand-maintained).
- `career` is pre-computed totals so the runtime doesn't re-aggregate.
- `all_pro_team` is an integer (0 = none, 1 = first team, 2 = second team) since these are mutually exclusive per season.
- `super_bowls` is a list of years won, not a count, so cross-team filtering still works after multi-team rosters merge. Count is just `super_bowls.length`.

## Stat naming conventions

- snake_case throughout.
- NFL: category prefixes (`pass_`, `rush_`, `rec_`, `def_`, `kick_`, `pun_`, `ret_`).
- NBA: flat top-level for traditional stats (`pts`, `reb`, `ast`). Per-game variants get `_pg` suffix. Use `fg3_made`, not `3p_made`, since leading digits break JS dot access.
- MLB: disambiguate shared abbreviations with category prefix. Strikeouts are `bat_so` and `pit_so`. WAR is `bat_war` and `pit_war`. Doubles and triples (`"2b"`, `"3b"`) require bracket access in JS for the same leading-digit reason.

## Brand

- User-facing name: Hometeam Statpad. One word "Hometeam," single-capital "Statpad" (intentionally distinct from the inspiration's "StatPad" camelcase).
- Eagles MVP keeps Eagles colors for now. Per-team or per-city theming is a future decision once multi-team ships.
- Footer credits the original: "Inspired by [StatPad](https://www.statpadgame.com/)". Keep this on every team variant.

## UX details locked in

- Date archive picker is capped to the last 15 days.
- Daily puzzle is date-seeded: `daysSinceEpoch % puzzles.length`.

## Puzzle constraint keys

Constraint keys are snake_case in puzzles.json. The engine in `game.js` reads:

**Player-level (filters the player pool):**
- `position` (string), `position_group` (string, looked up in `position_groups`)
- `draft_round` (int), `draft_round_not` (int)
- `drafted_by` (string, full team name), `drafted_by_not` (string)
- `super_bowl` (int — season year of the SB win, e.g. 2017 = LII)
- `career_stat_gt` / `career_stat_lt` (object: `{ stat_key: threshold }`)

**Season-level (filters individual season-rows):**
- `team` (string — full team name; SAME SEASON rows for Eagles puzzles set `"team": "Eagles"` to keep era-bound rows from leaking non-Eagles seasons)
- `era` (string — looked up in `eras`), `era_any` (list of strings)
- `year_min` (int), `year_max` (int)

## Data coverage (Eagles)

What the pipeline reliably gives us, and what it doesn't. **Author puzzles within these bounds** — if you need data outside them, either add it to `scripts/manual_awards.py` or skip that puzzle idea.

**Reliable (use freely):**
- Offensive stats (`rush_yards`, `rush_td`, `rec`, `rec_yards`, `rec_td`, `pass_yards`, `pass_td`, `pass_int`) — league-wide, 1999-2024, for any player who's ever been on PHI roster. Full career covered, including non-Eagles seasons.
- Defensive stats (`def_sacks`, `def_int`, `def_tackles`) — **PHI tenure only**, full 1999-2024 (PBP-derived plus a hand-curated 2016-2017 supplement). Reliable for any puzzle constrained to `team: "Eagles"`.
- Eagles Super Bowl wins (LII/2017, LVII/2022, LIX/2024) — hand-curated rosters in the pipeline.
- Draft year, round, team — from rosters.

**Has gaps (handle with care):**
- **Pro Bowl / All-Pro** — **NO automated source available** (investigated 2026-05-13: `nfl_data_py`'s PFR endpoints don't expose awards, nflverse-data publishes no awards release, PFR direct pages block our fetch tool). All Pro Bowl and All-Pro entries must come from `scripts/manual_awards.py`. Don't write a "PRO BOWLER" puzzle until that file covers the relevant players + years.
- **Non-Eagles Super Bowl rings** — e.g., Chris Long's SB LI with NE — only present if entered in `manual_awards.py`. Don't write a "WON A SUPER BOWL (anywhere in career)" puzzle without that.
- **Defensive stats outside PHI tenure** — A player's pre/post-Eagles defensive years aren't in the data. ANYTIME IN CAREER defensive-stat puzzles silently exclude those seasons.
- **Mid-season trades** — Offensive stats for a traded player are attributed to their final team of that season (`recent_team`), so a mid-season acquisition's pre-trade stats roll up under the wrong team. Minor for now.

**Not in data at all:**
- Anything pre-1999 (Buddy Ryan, Kotite, Rhodes eras). The era list in `puzzles.json` still names them, but no player records exist. Don't write puzzles referencing those eras.
- Stats not currently captured: rushing attempts, receiving targets, completions/attempts, fumbles, returns, kicking. Pipeline change needed to add any.

**Workflow:** before shipping a new puzzle, run `python3 scripts/validate_eagles.py`. It prints the answer pool size and top 5 for each row — any row with a suspiciously small or zero-valued top-5 probably hits a coverage gap.

## Working notes

- EJ is a PM, not an engineer, and is learning Python while building this. Explain pipeline tooling and ecosystem concepts plainly without jargon. Use analogies to familiar tools when helpful.
- Constraint engine will need to support career-level stat constraints (`career_stat_lt`, `career_stat_gt`), not just season-level. This is what enables StatPad-style "career receptions over X" prompts.

## Current phase

Eagles pipeline is live (`scripts/build_eagles.py` → `data/eagles/players.json`). Next milestones, in order:
1. Backfill `scripts/manual_awards.py` with pre-2018 Pro Bowls / All-Pros / non-Eagles SB rings as new puzzles demand them.
2. Add Sixers via `nba_api` using the same per-team pattern.
3. Build the team picker UI; activate `data/manifest.json`'s `city_groups` once ≥2 teams exist.
