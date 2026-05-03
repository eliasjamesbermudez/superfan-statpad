// ── CONSTRAINT ENGINE ─────────────────────────────────────────────────────────

function yearInEra(year, eraName) {
  const range = ERAS[eraName];
  return range && year >= range[0] && year <= range[1];
}

function playerMeetsPlayerConstraints(player, c) {
  if (c.position && player.position !== c.position) return false;

  if (c.position_group) {
    const group = POSITION_GROUPS[c.position_group] || [];
    if (!group.includes(player.position)) return false;
  }

  if (c.draftRound !== undefined && player.draftRound !== c.draftRound) return false;
  if (c.draftRound_not !== undefined && player.draftRound === c.draftRound_not) return false;

  if (c.draftedBy && player.draftedBy !== c.draftedBy) return false;
  if (c.draftedBy_not && player.draftedBy === c.draftedBy_not) return false;

  if (c.superBowl && !player.superBowl.includes(c.superBowl)) return false;

  return true;
}

function yearMeetsYearConstraints(year, c) {
  if (c.era && !yearInEra(year, c.era)) return false;
  if (c.era_any) {
    const ok = c.era_any.some(e => yearInEra(year, e));
    if (!ok) return false;
  }
  if (c.yearMin !== undefined && year < c.yearMin) return false;
  if (c.yearMax !== undefined && year > c.yearMax) return false;
  return true;
}

function statValue(player, year, statKey) {
  const s = player.seasons[year];
  return s ? (s[statKey] ?? 0) : 0;
}

// NFL seasons span two calendar years (Sept-Feb). Display as "YYYY-YYYY".
function formatSeason(year) {
  return `${year}-${year + 1}`;
}

function playerYearRange(player) {
  const years = Object.keys(player.seasons).map(Number).sort((a, b) => a - b);
  if (!years.length) return '';
  const first = years[0];
  const last = years[years.length - 1];
  if (first === last) return formatSeason(first);
  return `${first}-${last + 1}`;
}

function getValidAnswers(rowConstraints, statKey) {
  const answers = [];
  for (const player of PLAYERS) {
    if (!playerMeetsPlayerConstraints(player, rowConstraints)) continue;
    for (const year of Object.keys(player.seasons).map(Number)) {
      if (!yearMeetsYearConstraints(year, rowConstraints)) continue;
      answers.push({ player, year, value: statValue(player, year, statKey) });
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

function getDateKey(date) {
  return `statpad-${dateToISO(date)}`;
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

function loadTodaysPuzzle() {
  initDatePicker();
  loadPuzzleForDate(todayLocal());
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
      <div class="row-qualifier">${row.qualifierText}</div>
      <div class="row-badge">${row.qualifierBadge}</div>
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

function renderResult(i) {
  const state = rowStates[i];
  const row = currentPuzzle.rows[i];
  const allAnswers = getValidAnswers(row.constraints, currentPuzzle.statKey);
  const pct = getPercentile(state.value, allAnswers);
  const label = currentPuzzle.statKey.replace(/_/g, ' ').toUpperCase();
  const top5 = allAnswers.slice(0, 5);

  const leaderboardRows = top5.map((a, rank) => {
    const isUser = a.player.name === state.playerName && a.year === state.year;
    return `
      <div class="lb-row${isUser ? ' lb-row-highlight' : ''}">
        <span class="lb-rank">${rank + 1}.</span>
        <span class="lb-name">${a.player.name}</span>
        <span class="lb-year">${formatSeason(a.year)}</span>
        <span class="lb-val">${a.value}</span>
      </div>`;
  }).join('');

  return `
    <div class="result-block">
      <div class="result-summary">
        <div>
          <div class="result-name">${state.playerName}</div>
          <div class="result-year-label">${formatSeason(state.year)}</div>
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

function populateYears(i, player) {
  const yearSel = document.getElementById(`year-select-${i}`);
  const errorEl = document.getElementById(`error-${i}`);
  const row = currentPuzzle.rows[i];
  const stat = currentPuzzle.statKey;

  const validYears = Object.keys(player.seasons)
    .map(Number)
    .filter(y => yearMeetsYearConstraints(y, row.constraints))
    .sort((a, b) => statValue(player, b, stat) - statValue(player, a, stat));

  yearSel.innerHTML = '<option value="">Year</option>';
  validYears.forEach(y => {
    const opt = document.createElement('option');
    opt.value = y;
    opt.textContent = formatSeason(y);
    yearSel.appendChild(opt);
  });

  if (!validYears.length) {
    errorEl.textContent = `${player.name} has no seasons matching this row's year requirements.`;
  } else {
    errorEl.textContent = '';
  }
}

function submitRow(i) {
  const playerName = document.getElementById(`player-input-${i}`).value.trim();
  const year = parseInt(document.getElementById(`year-select-${i}`).value);
  const errorEl = document.getElementById(`error-${i}`);

  errorEl.textContent = '';

  if (!playerName) { errorEl.textContent = 'Enter a player name.'; return; }
  if (!year) { errorEl.textContent = 'Select a year.'; return; }

  const player = PLAYERS.find(p => p.name.toLowerCase() === playerName.toLowerCase());
  if (!player) { errorEl.textContent = 'Player not found - try the dropdown.'; return; }

  const row = currentPuzzle.rows[i];
  if (!playerMeetsPlayerConstraints(player, row.constraints)) {
    errorEl.textContent = "That player doesn't meet this row's requirements.";
    return;
  }
  if (!yearMeetsYearConstraints(year, row.constraints)) {
    errorEl.textContent = "That year doesn't meet this row's requirements.";
    return;
  }

  const value = statValue(player, year, currentPuzzle.statKey);
  rowStates[i] = { submitted: true, playerName: player.name, year, value };

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
    'Pick one Eagles player per row that meets the row\'s requirements.\n\n' +
    'Submit the player and a year — your score increases by their stat total from that year.\n\n' +
    'Try to maximize your total score across all 5 rows.\n\n' +
    'SAME SEASON: the qualifier must apply to the year you submit.\n' +
    'ANYTIME IN CAREER: the qualifier just has to be true at some point in their career.\n\n' +
    'The percentile shows how your answer ranks against all valid answers.'
  );
}

// ── INIT ──────────────────────────────────────────────────────────────────────

loadTodaysPuzzle();
