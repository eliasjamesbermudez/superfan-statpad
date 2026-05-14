"""
Hand-curated supplements for awards data the automated pipeline can't reach.

Why this file exists:
  - PFR awards (Pro Bowl / All-Pro) via nfl_data_py's import_seasonal_pfr only
    covers QB/skill positions, 2018-2024. Everything else — OL, defense, special
    teams, anything pre-2018 — is invisible to the automated pipeline.
  - Super Bowl wins outside Philadelphia (e.g. Chris Long with NE in SB LI before
    joining PHI for LII) aren't in the PHI Super Bowl rosters hardcoded in
    build_eagles.py.

When to add entries here:
  Before authoring a puzzle row that uses pro_bowl, all_pro_team, or "won a
  Super Bowl" ANYTIME IN CAREER, check whether the relevant data is already
  reachable. If not, add it here, regenerate players.json, and re-run
  validate_eagles.py.

Entry format (tuples):
  (player_name, season_year, team_abbrev)
  - player_name must match the spelling in players.json exactly (PFR/nflreadr's
    canonical form — e.g. "A.J. Brown", not "AJ Brown").
  - season_year is the NFL season year. SB LI (won Feb 2017) was the 2016 season -> 2016.
  - team_abbrev uses NFL abbreviations (PHI, NE, TEN, etc. — see TEAM_NAMES in
    build_eagles.py for the canonical list).

Merge behavior:
  - build_eagles.py looks up the player by name. If they've never been on PHI,
    the entry is silently skipped (they wouldn't be in players.json anyway).
  - If a season-row for (year, team) already exists, the award flag is set on
    that row. Otherwise an empty row is created with just the flag (no stats).
  - The pipeline prints a skip-count summary so unmatched names surface.

Sources for verification:
  - https://www.pro-football-reference.com/players/{first_letter}/{slug}.htm
  - Wikipedia player pages have a clear awards section.
"""

# Eagles players who won Super Bowls *before or after* their PHI tenure with another team.
# Eagles wins (LII/2017, LVII/2022, LIX/2024) are hardcoded inside build_eagles.py —
# do NOT duplicate them here.
EXTRA_SUPER_BOWLS = [
    # (player_name, season_year, team_abbrev)
    ("LeGarrette Blount", 2016, "NE"),   # SB LI with NE before signing with PHI in 2017
    ("Chris Long",        2016, "NE"),   # SB LI with NE before signing with PHI in 2017
]

# Pro Bowl selections not covered by the automated PFR fetch.
# Specifically: every season pre-2018, plus all defensive/OL/special-teams Pro Bowls
# in 2018-2024 (PFR pass/rec/rush endpoints only cover QB and skill positions).
#
# Empty until a puzzle needs it — add entries before authoring Pro Bowl puzzles.
PRO_BOWLS = [
    # (player_name, season_year, team_abbrev)
    # Example: ("Donovan McNabb", 2000, "PHI"),
]

# 1st-Team All-Pro selections not covered by the automated PFR fetch.
ALL_PROS_FIRST_TEAM = [
    # (player_name, season_year, team_abbrev)
]

# 2nd-Team All-Pro selections not covered by the automated PFR fetch.
ALL_PROS_SECOND_TEAM = [
    # (player_name, season_year, team_abbrev)
]
