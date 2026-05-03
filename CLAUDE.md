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

Current:
```
index.html
game.js
data.js                      (Eagles puzzles inline; will move to data/eagles/puzzles.json)
.gitignore
```

Planned:
```
index.html
game.js
data/
  manifest.json              (available teams and city groups)
  eagles/
    players.json
    puzzles.json
  sixers/
    players.json
    puzzles.json
  phillies/
    players.json
    puzzles.json
scripts/
  build_eagles.py
  build_sixers.py
  build_phillies.py
  requirements.txt
.venv/                       (gitignored)
```

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

## Working notes

- EJ is a PM, not an engineer, and is learning Python while building this. Explain pipeline tooling and ecosystem concepts plainly without jargon. Use analogies to familiar tools when helpful.
- Constraint engine will need to support career-level stat constraints (`career_stat_lt`, `career_stat_gt`), not just season-level. This is what enables StatPad-style "career receptions over X" prompts.

## Current phase

Building the Python data pipeline for Eagles via `nfl_data_py`. Once the schema is validated end-to-end on Eagles, the same pattern extends to Sixers (`nba_api`) and Phillies (`pybaseball`).
