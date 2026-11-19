// The Agents page: bin/island-agents output -> ordered rows, labels, and the
// commands that focus a session's terminal. ES5, no Qt types; node tests load
// it with require(). Approve/deny is not here (needs a hook socket).

var ORDER = { needs: 0, working: 1, done: 2, idle: 3 }
var LABEL = { needs: "needs you", done: "done", working: "working", idle: "idle" }
var NEEDS = { blocked: true, waiting: true, needs_input: true, awaiting_input: true, permission: true }
var APPS = {
  "claude-code": "Claude", claude: "Claude", codex: "Codex", opencode: "OpenCode", gemini: "Gemini",
  grok: "Grok", antigravity: "Antigravity", cursor: "Cursor", devin: "Devin", droid: "Droid"
}

function normStatus(status) {
  var s = String(status || "").toLowerCase()
  if (NEEDS[s] === true) return "needs"
  if (s === "done") return "done"
  if (s === "working" || s === "busy") return "working"
  return "idle"
}

function appName(app) {
  var k = String(app || "").toLowerCase()
  if (APPS[k]) return APPS[k]
  return k ? k.charAt(0).toUpperCase() + k.slice(1) : "Agent"
}

// The app's own key ("claude", "codex", ...): picks an icon; "" when unknown.
function appKey(app) {
  var k = String(app || "").toLowerCase()
  if (k === "claude-code") return "claude"
  return /^[a-z0-9_-]+$/.test(k) ? k : ""
}

// Icon-theme names to try for an app, in order. Claude and Antigravity ship no
// theme icon on this machine; they use Omarchy's agent marks (below), and the
// tile falls back to a lettered circle when neither resolves.
var ICONS = {
  claude: ["claude-code", "claude", "anthropic-claude"], codex: ["codex-desktop", "codex", "openai-codex"],
  opencode: ["ai.opencode", "opencode", "opencode-desktop"], antigravity: ["antigravity", "google-antigravity"],
  gemini: ["gemini"], cursor: ["cursor"], grok: ["grok"], devin: ["devin"]
}
function iconNames(app) { return ICONS[appKey(app)] || [] }

// Omarchy's own agent marks, looked up at run time (nothing is copied into this
// plugin): /usr/share/omarchy/shell/plugins/agents/assets/<id>.svg, plus a
// "-light" twin for light surfaces. An id that has no file simply fails to load
// and the tile keeps its lettered circle.
var ASSET_DIR = "/usr/share/omarchy/shell/plugins/agents/assets/"
var ASSET_ID = { antigravity: "agy" }

// -> file URLs to try in order, for a dark or a light card surface.
function assetCandidates(app, lightSurface) {
  var k = appKey(app)
  if (k === "") return []
  var id = ASSET_ID[k] || k
  var out = []
  if (lightSurface === true) out.push("file://" + ASSET_DIR + id + "-light.svg")
  out.push("file://" + ASSET_DIR + id + ".svg")
  return out
}

// WCAG relative luminance of a colour (r, g, b in 0..1) >= 0.5: a light surface.
function isLight(r, g, b) {
  function ch(v) { v = Number(v); if (!isFinite(v)) return 0; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
  return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b) >= 0.5
}

// The small muted line of a tile: the machine of "Space @ machine", else the
// space or folder name.
function hostOf(where) {
  var w = String(where || "")
  var i = w.lastIndexOf(" @ ")
  return i >= 0 ? w.slice(i + 3) : w
}

// A Hyprland window address: hex, "0x" added when missing; "" when invalid.
function _address(a) {
  var s = String(a || "")
  if (!/^(0x)?[0-9a-fA-F]{1,16}$/.test(s)) return ""
  return s.indexOf("0x") === 0 ? s : "0x" + s
}

// A herdr terminal id passed as one argv element: no leading "-" (it would
// read as an option) and no whitespace; "" when invalid.
function _terminal(t) {
  var s = String(t || "")
  return /^[A-Za-z0-9_.:\/@][A-Za-z0-9_.:\/@-]*$/.test(s) ? s : ""
}

// -> [{ key, source, app, title, where, status, statusLabel, terminal, address, focusable }]
function rows(data) {
  var list = data && Array.isArray(data.sessions) ? data.sessions : []
  var out = []
  for (var i = 0; i < list.length; i++) {
    var x = list[i]
    if (!x || typeof x !== "object" || !x.id) continue
    var st = normStatus(x.status)
    var address = _address(x.address)
    var terminal = x.source === "herdr" ? _terminal(x.terminal) : ""
    out.push({
      key: String(x.id), source: String(x.source || ""), app: appName(x.app), appKey: appKey(x.app), host: hostOf(x.where), title: String(x.name || ""),
      where: String(x.where || ""), status: st, statusLabel: LABEL[st], terminal: terminal,
      address: address, focusable: address !== "" || terminal !== "", idx: i
    })
  }
  out.sort(function (a, b) {
    return ORDER[a.status] - ORDER[b.status] || (a.title < b.title ? -1 : a.title > b.title ? 1 : a.idx - b.idx)
  })
  return out
}

// "1 needs you · 2 working": needs-you first, zero counts dropped.
function countsText(list) {
  var c = { needs: 0, done: 0, working: 0, idle: 0 }
  for (var i = 0; i < (list || []).length; i++) c[list[i].status]++
  var parts = []
  var keys = ["needs", "done", "working"]
  for (var k = 0; k < keys.length; k++) if (c[keys[k]] > 0) parts.push(c[keys[k]] + " " + LABEL[keys[k]])
  return parts.join(" · ")
}

// What the grid draws: the rows in order, capped at `cap` tiles. When there
// are more rows than tiles, the last tile is a "+N" tile for the rest (idle
// when they all are, else "more"). -> { tiles: [row], more: { n, label } | null }
function tiles(list, cap) {
  var rows = list || []
  var max = Math.max(1, cap | 0)
  if (rows.length <= max) return { tiles: rows.slice(), more: null }
  var keep = rows.slice(0, max - 1)
  var rest = rows.slice(max - 1)
  var allIdle = true
  for (var i = 0; i < rest.length; i++) if (rest[i].status !== "idle") allIdle = false
  return { tiles: keep, more: { n: rest.length, label: "+" + rest.length + (allIdle ? " idle" : " more") } }
}

// The header pills: [{ status, n, label }] for needs, working and done only,
// zero counts dropped ("1 needs you", "2 working", "1 done").
function pills(list) {
  var c = { needs: 0, working: 0, done: 0 }
  for (var i = 0; i < (list || []).length; i++) if (c[list[i].status] !== undefined) c[list[i].status]++
  var out = []
  var keys = ["needs", "working", "done"]
  for (var k = 0; k < keys.length; k++) if (c[keys[k]] > 0) out.push({ status: keys[k], n: c[keys[k]], label: c[keys[k]] + " " + LABEL[keys[k]] })
  return out
}

// A tile's one-letter fallback badge.
function initial(app) { return appName(app).charAt(0).toUpperCase() }

// argv lists, run in order: herdr's own terminal focus, then the window focus
// through Hyprland (the form Omarchy's dock uses). Each is passed as argv, never
// through a shell.
function focusCommands(row) {
  var out = []
  if (!row) return out
  var terminal = row.source === "herdr" ? _terminal(row.terminal) : ""
  if (terminal) out.push(["herdr-app", "do", "agent.focus", "--terminal", terminal])
  var address = _address(row.address)
  if (address) out.push(["hyprctl", "dispatch", 'hl.dsp.focus({ window = "address:' + address + '" })'])
  return out
}

if (typeof module !== "undefined") module.exports = {
  normStatus: normStatus, appName: appName, appKey: appKey, iconNames: iconNames, assetCandidates: assetCandidates, isLight: isLight, hostOf: hostOf, rows: rows,
  countsText: countsText, tiles: tiles, pills: pills, initial: initial, focusCommands: focusCommands
}
