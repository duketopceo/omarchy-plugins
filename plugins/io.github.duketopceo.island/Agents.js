// The Agents page: bin/island-agents output -> ordered rows, labels, and the
// commands that focus a session's terminal. ES5, no Qt types; node tests load
// it with require(). Approve/deny is not here (needs a hook socket).

var ORDER = { needs: 0, done: 1, working: 2, idle: 3 }
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

// A Hyprland window address: hex, "0x" added when missing; "" when invalid.
function _address(a) {
  var s = String(a || "")
  if (!/^(0x)?[0-9a-fA-F]{1,16}$/.test(s)) return ""
  return s.indexOf("0x") === 0 ? s : "0x" + s
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
    var terminal = x.source === "herdr" ? String(x.terminal || "") : ""
    out.push({
      key: String(x.id), source: String(x.source || ""), app: appName(x.app), title: String(x.name || ""),
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

// argv lists, run in order: herdr's own terminal focus, then the window focus
// through Hyprland (the form Omarchy's dock uses). Each is passed as argv, never
// through a shell.
function focusCommands(row) {
  var out = []
  if (!row) return out
  if (row.source === "herdr" && row.terminal) out.push(["herdr-app", "do", "agent.focus", "--terminal", String(row.terminal)])
  var address = _address(row.address)
  if (address) out.push(["hyprctl", "dispatch", 'hl.dsp.focus({ window = "address:' + address + '" })'])
  return out
}

if (typeof module !== "undefined") module.exports = {
  normStatus: normStatus, appName: appName, rows: rows, countsText: countsText, focusCommands: focusCommands
}
