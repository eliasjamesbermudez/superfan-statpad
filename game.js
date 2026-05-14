// ── DATA (loaded async at init) ──────────────────────────────────────────────

let MANIFEST = null;
let PLAYERS = [];
let PUZZLES = [];
let ERAS = {};
let POSITION_GROUPS = {};
let ACTIVE_TEAM = null; // e.g. { id: "eagles", name: "Philadelphia Eagles", short_name: "Eagles" }

// ── CONSTRAINT ENGINE ─────────────────────────────────────────────────────────

function yearInEra(year, eraName) {
  const range = ERAS[eraName];
  return range && year >= range[0] && year <= range[1];
}

// Player-level constraints: filters the player pool. These never depend on a
// specific season.
function playerMeetsPlayerConstraints(player, c) {
  if (c.position && player.position !== c.position) return false;

  if (c.position_group) {
    const group = POSITION_GROUPS[c.position_group] || [];
    if (!group.includes(player.position)) return false;
  }

  if (c.draft_round !== undefined && player.draftRound !== c.draft_round) return false;
  if (c.draft_round_not !== undefined && player.draftRound === c.draft_round_not) return false;

  if (c.drafted_by && player.draftedBy !== c.drafted_by) return false;
  if (c.drafted_by_not && player.draftedBy === c.drafted_by_not) return false;

  if (c.super_bowl !== undefined) {
    const wins = (player.career && player.career.super_bowls) || [];
    if (!wins.includes(c.super_bowl)) return false;
  }

  // Career-level stat thresholds (e.g. career_stat_gt: { rec: 500 })
  if (c.career_stat_gt) {
    for (const [k, v] of Object.entries(c.career_stat_gt)) {
      if (((player.career || {})[k] || 0) <= v) return false;
    }
  }
  if (c.career_stat_lt) {
    for (const [k, v] of Object.entries(c.career_stat_lt)) {
      if (((player.career || {})[k] || 0) >= v) return false;
    }
  }

  return true;
}

// Season-level constraints: filters individual season-rows.
function seasonMeetsConstraints(season, c) {
  if (c.team && season.team !== c.team) return false;
  if (c.year_min !== undefined && season.year < c.year_min) return false;
  if (c.year_max !== undefined && season.year > c.year_max) return false;
  if (c.era && !yearInEra(season.year, c.era)) return false;
  if (c.era_any && !c.era_any.some(e => yearInEra(season.year, e))) return false;
  return true;
}

// Returns a short explanation of why a season failed the row constraints, or
// null if it passes. Used to give the user a clear "your pick didn't qualify
// because..." message instead of a generic 0-point result.
function getSeasonFailReason(season, c, player) {
  const seasonStr = formatSeason(season.year);
  if (c.team && season.team !== c.team) {
    return `${player.name} wasn't on the ${c.team} in ${seasonStr}.`;
  }
  if (c.era && !yearInEra(season.year, c.era)) {
    return `${seasonStr} wasn't in the ${c.era} era.`;
  }
  if (c.era_any && !c.era_any.some(e => yearInEra(season.year, e))) {
    return `${seasonStr} wasn't in the ${c.era_any.join(' or ')} era.`;
  }
  if (c.year_min !== undefined && season.year < c.year_min) {
    return `${seasonStr} is too early — must be ${c.year_min} or later.`;
  }
  if (c.year_max !== undefined && season.year > c.year_max) {
    return `${seasonStr} is too late — must be ${c.year_max} or earlier.`;
  }
  return null;
}

function statValue(season, statKey) {
  return (season && season[statKey]) ? season[statKey] : 0;
}

// NFL seasons span two calendar years (Sept-Feb). Display as "YYYY-YYYY".
function formatSeason(year) {
  return `${year}-${year + 1}`;
}

function playerYearRange(player) {
  if (!player.seasons || !player.seasons.length) return '';
  const years = player.seasons.map(s => s.year).sort((a, b) => a - b);
  const first = years[0];
  const last = years[years.length - 1];
  if (first === last) return formatSeason(first);
  return `${first}-${last + 1}`;
}

// Returns [{ player, season, value }, ...] sorted by value desc.
function getValidAnswers(rowConstraints, statKey) {
  const answers = [];
  for (const player of PLAYERS) {
    if (!playerMeetsPlayerConstraints(player, rowConstraints)) continue;
    for (const season of player.seasons) {
      if (!seasonMeetsConstraints(season, rowConstraints)) continue;
      answers.push({ player, season, value: statValue(season, statKey) });
    }
  }
  return answers.sort((a, b) => b.value - a.value);
}

function getPercentile(value, allAnswers) {
  if (allAnswers.length === 0) return 0;
  const below = allAnswers.filter(a => a.value < value).length;
  return Math.round((below / allAnswers.length) * 100);
}

// ── GAME STATE ────────────────────────────────────────────────────────────────

let currentPuzzle = null;
let rowStates = [];
let totalScore = 0;
let totalGuesses = 0;

let currentDate = todayLocal();

function todayLocal() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function dateToISO(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function getPuzzleIndexForDate(date) {
  const daysSinceEpoch = Math.floor(date.getTime() / 86400000);
  return daysSinceEpoch % PUZZLES.length;
}

const SCHEMA_VERSION = 5; // bump when row-state shape changes; invalidates old saves
function getDateKey(date) {
  return `statpad-${ACTIVE_TEAM.id}-v${SCHEMA_VERSION}-${dateToISO(date)}`;
}

function saveProgress() {
  const payload = { rowStates, totalScore, totalGuesses };
  try {
    localStorage.setItem(getDateKey(currentDate), JSON.stringify(payload));
  } catch (e) {}
}

function loadProgress() {
  try {
    const raw = localStorage.getItem(getDateKey(currentDate));
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

function loadPuzzleForDate(date) {
  currentDate = date;
  const index = getPuzzleIndexForDate(date);
  currentPuzzle = PUZZLES[index];

  const saved = loadProgress();
  if (saved && saved.rowStates && saved.rowStates.length === currentPuzzle.rows.length) {
    rowStates = saved.rowStates;
    totalScore = saved.totalScore || 0;
    totalGuesses = saved.totalGuesses || 0;
  } else {
    rowStates = currentPuzzle.rows.map(() => ({ submitted: false }));
    totalScore = 0;
    totalGuesses = 0;
  }

  updateScoreboard();
  renderBoard();
}

function minSelectableDate() {
  const today = todayLocal();
  return new Date(today.getFullYear(), today.getMonth(), today.getDate() - 14);
}

function onDateChange(value) {
  if (!value) return;
  const [y, m, d] = value.split('-').map(Number);
  const picked = new Date(y, m - 1, d);
  const today = todayLocal();
  const minDate = minSelectableDate();
  if (picked.getTime() > today.getTime() || picked.getTime() < minDate.getTime()) {
    document.getElementById('date-picker').value = dateToISO(today);
    return;
  }
  loadPuzzleForDate(picked);
}

function initDatePicker() {
  const picker = document.getElementById('date-picker');
  const today = todayLocal();
  picker.value = dateToISO(today);
  picker.max = dateToISO(today);
  picker.min = dateToISO(minSelectableDate());
}

function updateScoreboard() {
  document.getElementById('display-category').textContent = currentPuzzle.category;
  document.getElementById('display-score').textContent = totalScore.toLocaleString();
  document.getElementById('display-guesses').textContent = totalGuesses;
}

// ── RENDER ────────────────────────────────────────────────────────────────────

function renderBoard() {
  const board = document.getElementById('board');
  board.innerHTML = '';
  currentPuzzle.rows.forEach((row, i) => renderRow(i));
  renderCompletionBanner();
}

function renderCompletionBanner() {
  const banner = document.getElementById('completion-banner');
  const allDone = rowStates.length > 0 && rowStates.every(s => s.submitted);
  if (!allDone) {
    banner.style.display = 'none';
    banner.innerHTML = '';
    return;
  }

  banner.style.display = 'block';
  banner.innerHTML = `
    <div class="banner-title">PUZZLE COMPLETE</div>
    <div class="banner-score">${totalScore.toLocaleString()}</div>
    <div class="banner-label">FINAL SCORE</div>
    <div class="banner-msg">Pick another date to keep playing.</div>
  `;
}

function renderRow(i) {
  const board = document.getElementById('board');
  const state = rowStates[i];
  const row = currentPuzzle.rows[i];

  const el = document.createElement('div');
  el.className = 'row' + (state.submitted ? ' completed' : '');
  el.id = `row-${i}`;

  el.innerHTML = `
    <div class="row-meta">
      <div class="row-qualifier">${row.qualifier_text}</div>
      <div class="row-badge">${row.qualifier_badge}</div>
    </div>
    <div class="row-action" id="row-action-${i}">
      ${state.submitted ? renderResult(i) : renderInputArea(i)}
    </div>
  `;

  board.appendChild(el);
}

function renderInputArea(i) {
  return `
    <button class="add-btn" id="add-btn-${i}" onclick="openInput(${i})">
      <span style="font-size:18px">+</span> add player
    </button>
    <div class="input-form" id="form-${i}">
      <div class="input-row">
        <div class="input-wrap">
          <input
            class="player-input"
            id="player-input-${i}"
            type="text"
            placeholder="Player name..."
            oninput="handleAutocomplete(${i})"
            autocomplete="off"
          />
          <div class="suggestions" id="suggestions-${i}" style="display:none"></div>
        </div>
        <select class="year-select" id="year-select-${i}">
          <option value="">Year</option>
        </select>
        <button class="go-btn" onclick="submitRow(${i})">GO</button>
      </div>
      <div class="error-msg" id="error-${i}"></div>
    </div>
  `;
}

// Year-only label for inputs: keeps the user guessing. The team is intentionally
// hidden in the picker so we don't telegraph which years pass the row's
// constraints. The team is revealed in renderResult after submission.
function yearOnlyLabel(season) {
  return formatSeason(season.year);
}

// Year-with-team label used in the result/leaderboard after submission — that's
// where it becomes useful information rather than a hint.
function seasonLabel(season) {
  return `${formatSeason(season.year)} (${season.team})`;
}

function renderResult(i) {
  const state = rowStates[i];
  const row = currentPuzzle.rows[i];
  const allAnswers = getValidAnswers(row.constraints, currentPuzzle.stat_key);
  const pct = getPercentile(state.value, allAnswers);
  const label = currentPuzzle.stat_key.replace(/_/g, ' ').toUpperCase();
  const top5 = allAnswers.slice(0, 5);

  const leaderboardRows = top5.map((a, rank) => {
    const isUser = a.player.name === state.playerName
                && a.season.year === state.year
                && a.season.team === state.team;
    return `
      <div class="lb-row${isUser ? ' lb-row-highlight' : ''}">
        <span class="lb-rank">${rank + 1}.</span>
        <span class="lb-name">${a.player.name}</span>
        <span class="lb-year">${seasonLabel(a.season)}</span>
        <span class="lb-val">${a.value}</span>
      </div>`;
  }).join('');

  return `
    <div class="result-block">
      <div class="result-summary">
        <div>
          <div class="result-name">${state.playerName}</div>
          <div class="result-year-label">${formatSeason(state.year)} (${state.team})</div>
          <div class="result-pct">${pct}th percentile</div>
        </div>
        <div class="result-stat-block">
          <div class="result-stat">${state.value}</div>
          <div class="result-stat-label">${label}</div>
        </div>
      </div>
      <div class="leaderboard">
        <div class="lb-header">TOP ANSWERS</div>
        ${leaderboardRows}
      </div>
    </div>
  `;
}

// ── INPUT INTERACTION ─────────────────────────────────────────────────────────

function openInput(i) {
  document.getElementById(`add-btn-${i}`).style.display = 'none';
  document.getElementById(`form-${i}`).classList.add('open');
  document.getElementById(`player-input-${i}`).focus();
}

function handleAutocomplete(i) {
  const input = document.getElementById(`player-input-${i}`);
  const list = document.getElementById(`suggestions-${i}`);
  const query = input.value.toLowerCase().trim();

  if (query.length < 2) { list.style.display = 'none'; return; }

  const matches = PLAYERS.filter(p => p.name.toLowerCase().includes(query)).slice(0, 8);
  if (!matches.length) { list.style.display = 'none'; return; }

  list.innerHTML = '';
  list.style.display = 'block';
  matches.forEach(player => {
    const item = document.createElement('div');
    item.className = 'suggestion-item';
    item.innerHTML = `<span class="suggestion-name"></span><span class="suggestion-years"></span>`;
    item.querySelector('.suggestion-name').textContent = player.name;
    item.querySelector('.suggestion-years').textContent = playerYearRange(player);
    item.onmousedown = (e) => {
      e.preventDefault();
      input.value = player.name;
      list.style.display = 'none';
      populateYears(i, player);
    };
    list.appendChild(item);
  });
}

// Encodes a season as "year|team" so it round-trips through the <option value>.
function encodeSeason(season) {
  return `${season.year}|${season.team}`;
}

function decodeSeasonValue(value) {
  const [yearStr, team] = value.split('|');
  return { year: parseInt(yearStr, 10), team };
}

function populateYears(i, player) {
  const yearSel = document.getElementById(`year-select-${i}`);
  const errorEl = document.getElementById(`error-${i}`);

  // Show every year of the player's career, chronologically. We intentionally
  // don't filter to "valid for this row" or sort by stat — that would
  // telegraph the right answer. Wrong years are allowed; they just score 0.
  const seasons = [...player.seasons].sort((a, b) => a.year - b.year);

  yearSel.innerHTML = '<option value="">Year</option>';
  seasons.forEach(s => {
    const opt = document.createElement('option');
    opt.value = encodeSeason(s);
    opt.textContent = yearOnlyLabel(s);
    yearSel.appendChild(opt);
  });

  if (!seasons.length) {
    errorEl.textContent = `${player.name} has no recorded seasons.`;
  } else {
    errorEl.textContent = '';
  }
}

function submitRow(i) {
  const playerName = document.getElementById(`player-input-${i}`).value.trim();
  const yearSelValue = document.getElementById(`year-select-${i}`).value;
  const errorEl = document.getElementById(`error-${i}`);

  errorEl.textContent = '';

  if (!playerName) { errorEl.textContent = 'Enter a player name.'; return; }
  if (!yearSelValue) { errorEl.textContent = 'Select a year.'; return; }

  const player = PLAYERS.find(p => p.name.toLowerCase() === playerName.toLowerCase());
  if (!player) { errorEl.textContent = 'Player not found - try the dropdown.'; return; }

  // Player-level constraints are non-negotiable: wrong position or wrong draft
  // is an invalid pick, not a guess. Surface as an error.
  const row = currentPuzzle.rows[i];
  if (!playerMeetsPlayerConstraints(player, row.constraints)) {
    errorEl.textContent = "That player doesn't meet this row's requirements.";
    return;
  }

  const { year, team } = decodeSeasonValue(yearSelValue);
  const season = player.seasons.find(s => s.year === year && s.team === team);
  if (!season) {
    errorEl.textContent = "Couldn't find that season - try again.";
    return;
  }

  // Season-level constraints (era, team, year range) block submission and let
  // the user pick again. The failure reason — "X wasn't on the Eagles in
  // 2020-2021" — surfaces in the error spot so they know why it's invalid.
  // A "poor guess" is a player+season that DO pass constraints but the stat
  // value happens to be 0; that's accepted (and scores 0).
  const failReason = getSeasonFailReason(season, row.constraints, player);
  if (failReason !== null) {
    errorEl.textContent = failReason;
    return;
  }

  const value = statValue(season, currentPuzzle.stat_key);
  rowStates[i] = { submitted: true, playerName: player.name, year, team, value };

  totalScore += value;
  totalGuesses++;
  updateScoreboard();

  document.getElementById(`row-${i}`).classList.add('completed');
  document.getElementById(`row-action-${i}`).innerHTML = renderResult(i);

  saveProgress();
  renderCompletionBanner();
}

// ── HELP ──────────────────────────────────────────────────────────────────────

function showHelp() {
  alert(
    'HOW TO PLAY\n\n' +
    `Pick one ${ACTIVE_TEAM.short_name} player per row that meets the row's requirements.\n\n` +
    'Submit the player and a season - your score increases by their stat total from that season.\n\n' +
    'Try to maximize your total score across all 5 rows.\n\n' +
    'SAME SEASON: the qualifier must apply to the season you submit.\n' +
    'ANYTIME IN CAREER: the qualifier just has to be true at some point in their career.\n\n' +
    'The percentile shows how your answer ranks against all valid answers.'
  );
}

// ── INIT ──────────────────────────────────────────────────────────────────────

async function init() {
  try {
    MANIFEST = await fetch('data/manifest.json').then(r => r.json());
    const teamId = MANIFEST.default_team;
    ACTIVE_TEAM = MANIFEST.teams.find(t => t.id === teamId);

    const [playersJson, puzzlesJson] = await Promise.all([
      fetch(`data/${teamId}/players.json`).then(r => r.json()),
      fetch(`data/${teamId}/puzzles.json`).then(r => r.json()),
    ]);

    PLAYERS = playersJson;
    PUZZLES = puzzlesJson.puzzles;
    ERAS = puzzlesJson.eras || {};
    POSITION_GROUPS = puzzlesJson.position_groups || {};

    initDatePicker();
    loadPuzzleForDate(todayLocal());
  } catch (err) {
    console.error('Failed to load game data:', err);
    document.getElementById('board').innerHTML =
      `<div style="padding:20px;color:#ff6b6b">Failed to load game data. Check the console.</div>`;
  }
}

init();
