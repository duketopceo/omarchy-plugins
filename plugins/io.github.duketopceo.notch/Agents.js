// Pure logic for the notch's agent status and AI usage. No QML globals, so
// node can run it (tests/test_notch_agents.py).
//
// herdr-app ls JSON: { spaces: [{ id, name, machine|null, tabs: [{ id, name,
//   terminals: [{ terminal, pane, status, app, sub_agents }] }] }] }
// status: working | blocked | idle | done (null for a plain shell).
// usage report (`ai-usagebar usage --json`): { entries: [{ id, display_name,
//   plan, status, error, sections: [{ type: "metric", label, percent,
//   reset_at, severity }] }] }

var PRIORITY_BLOCKED = 80
var PRIORITY_DONE = 40

var APP_NAMES = {
  "claude-code": "Claude", "claude": "Claude", "codex": "Codex", "devin": "Devin",
  "opencode": "OpenCode", "droid": "Droid", "antigravity": "Antigravity",
  "gemini": "Gemini", "cursor": "Cursor", "pi": "Pi"
}

function appName(app) {
  var key = String(app || "").toLowerCase()
  if (!key) return "Agent"
  if (APP_NAMES[key]) return APP_NAMES[key]
  return key.charAt(0).toUpperCase() + key.slice(1)
}

function normStatus(status) {
  var s = String(status || "").toLowerCase()
  return s === "working" || s === "blocked" || s === "done" ? s : "idle"
}

// Sort weight: needs-you first, then just-done, working, idle.
function statusPriority(status) {
  var s = normStatus(status)
  return s === "blocked" ? PRIORITY_BLOCKED : s === "done" ? PRIORITY_DONE : s === "working" ? 10 : 0
}

function emptySummary(ok) {
  return { ok: !!ok, counts: { working: 0, blocked: 0, done: 0, idle: 0 }, total: 0, groups: [], blockedApps: [], doneApps: [] }
}

function pushAgent(sum, group, tab, t) {
  if (!t || typeof t !== "object" || !t.terminal) return
  if (!t.app && !t.status) return  // plain shell, not an agent
  var st = normStatus(t.status)
  var a = { terminal: String(t.terminal), app: String(t.app || ""), appName: appName(t.app), status: st, tab: String(tab.name || "") }
  group.agents.push(a)
  sum.counts[st]++
  sum.total++
  if (st === "blocked") sum.blockedApps.push(a.appName)
  if (st === "done") sum.doneApps.push(a.appName)
  var subs = Array.isArray(t.sub_agents) ? t.sub_agents : []
  for (var i = 0; i < subs.length; i++) pushAgent(sum, group, tab, subs[i])
}

// Parse `herdr-app ls` output. Groups are per space (machine kept), agents
// sorted by status priority; groups with no agents are dropped.
function parseLs(text) {
  var data
  try { data = JSON.parse(String(text || "")) } catch (e) { return emptySummary(false) }
  if (!data || !Array.isArray(data.spaces)) return emptySummary(false)
  var sum = emptySummary(true)
  for (var i = 0; i < data.spaces.length; i++) {
    var sp = data.spaces[i]
    if (!sp || typeof sp !== "object") continue
    var g = { id: String(sp.id || ""), space: String(sp.name || "Space"), machine: sp.machine ? String(sp.machine) : "", agents: [] }
    var tabs = Array.isArray(sp.tabs) ? sp.tabs : []
    for (var j = 0; j < tabs.length; j++) {
      var tab = tabs[j]
      var terms = tab && Array.isArray(tab.terminals) ? tab.terminals : []
      for (var k = 0; k < terms.length; k++) pushAgent(sum, g, tab, terms[k])
    }
    if (g.agents.length === 0) continue
    g.agents.sort(function(a, b) { return statusPriority(b.status) - statusPriority(a.status) })
    sum.groups.push(g)
  }
  sum.groups.sort(function(a, b) {
    return statusPriority(b.agents[0].status) - statusPriority(a.agents[0].status)
  })
  return sum
}

function isActive(sum) { return !!sum && sum.ok && (sum.counts.blocked > 0 || sum.counts.done > 0) }

function priority(sum) {
  if (!sum || !sum.ok) return 0
  return sum.counts.blocked > 0 ? PRIORITY_BLOCKED : sum.counts.done > 0 ? PRIORITY_DONE : 0
}

// "2 need you" / "Codex needs you" / "Claude done" / "3 done" / "3 working" / "".
function activityText(sum) {
  if (!sum || !sum.ok) return ""
  var c = sum.counts
  if (c.blocked > 0) return c.blocked === 1 ? sum.blockedApps[0] + " needs you" : c.blocked + " need you"
  if (c.done > 0) return c.done === 1 ? sum.doneApps[0] + " done" : c.done + " done"
  if (c.working > 0) return c.working + " working"
  return ""
}

function glyph(sum) {
  if (!sum || !sum.ok) return ""
  return sum.counts.blocked > 0 ? "!" : sum.counts.done > 0 ? "✓" : sum.counts.working > 0 ? "●" : ""
}

// Tiny idle-notch badge: working count, "" when nothing is running.
function badgeText(sum) {
  return sum && sum.ok && sum.counts.working > 0 ? "● " + sum.counts.working : ""
}

function statusColorKey(status) {
  var s = normStatus(status)
  return s === "blocked" ? "warn" : s === "done" ? "good" : s === "working" ? "accent" : "dim"
}

// ---------------------------------------------------------------- usage

function clampPct(v) {
  var n = Number(v)
  return isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : null
}

// Parse `<report> usage --json` into providers with metric rows only.
function parseUsage(text) {
  var data
  try { data = JSON.parse(String(text || "")) } catch (e) { return { ok: false, providers: [] } }
  if (!data || !Array.isArray(data.entries)) return { ok: false, providers: [] }
  var out = []
  for (var i = 0; i < data.entries.length; i++) {
    var e = data.entries[i]
    if (!e || typeof e !== "object" || !e.id) continue
    var error = e.error ? String(e.error) : ""
    if (error || e.status === "error") continue  // a failing provider has nothing to draw
    var rows = []
    var secs = Array.isArray(e.sections) ? e.sections : []
    for (var j = 0; j < secs.length; j++) {
      var s = secs[j]
      if (!s || s.type !== "metric") continue
      var pct = clampPct(s.percent)
      if (pct === null) continue
      rows.push({
        label: String(s.label || ""), percent: pct, resetAt: s.reset_at ? String(s.reset_at) : "",
        severity: ["low", "mid", "high", "critical"].indexOf(s.severity) >= 0 ? s.severity : (pct >= 90 ? "critical" : pct >= 75 ? "high" : pct >= 50 ? "mid" : "low")
      })
    }
    if (rows.length === 0) continue
    out.push({ id: String(e.id), name: String(e.display_name || e.name || e.id), plan: e.plan ? String(e.plan) : "", rows: rows })
  }
  return { ok: true, providers: out }
}

// Time until an ISO reset: "3h 26m", "3d 5h", "12m", "now"; "" when unknown.
function resetIn(resetAt, nowMs) {
  var t = Date.parse(resetAt)
  if (!isFinite(t)) return ""
  var mins = Math.floor((t - nowMs) / 60000)
  if (mins <= 0) return "now"
  var d = Math.floor(mins / 1440), h = Math.floor((mins % 1440) / 60), m = mins % 60
  if (d > 0) return d + "d " + h + "h"
  if (h > 0) return h + "h " + m + "m"
  return m + "m"
}

if (typeof module !== "undefined") {
  module.exports = {
    PRIORITY_BLOCKED: PRIORITY_BLOCKED, PRIORITY_DONE: PRIORITY_DONE,
    appName: appName, normStatus: normStatus, statusPriority: statusPriority, parseLs: parseLs,
    isActive: isActive, priority: priority, activityText: activityText, glyph: glyph,
    badgeText: badgeText, statusColorKey: statusColorKey, parseUsage: parseUsage, resetIn: resetIn
  }
}
