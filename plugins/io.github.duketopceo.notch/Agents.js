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

// Only an agent that needs you is urgent enough for the collapsed notch; "done"
// and "working" stay in the expanded panel and Home.
function isActive(sum) { return !!sum && sum.ok && sum.counts.blocked > 0 }

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

// The provider whose busiest metric is highest: { name, percent } or null.
function topUsage(usage) {
  if (!usage || !usage.ok || !Array.isArray(usage.providers)) return null
  var best = null
  usage.providers.forEach(function (p) {
    p.rows.forEach(function (r) {
      if (best === null || r.percent > best.percent) best = { name: p.name, percent: r.percent }
    })
  })
  return best
}

// Window class -> short app name: "com.mitchellh.ghostty" -> "Ghostty".
function prettyApp(cls) {
  var c = String(cls || "").trim()
  if (!c) return ""
  var last = c.split(".").pop().replace(/[-_]/g, " ")
  return last.charAt(0).toUpperCase() + last.slice(1)
}


// ---------------------------------------------------------------- tab model

var STATUS_LABEL = { blocked: "needs you", done: "done", working: "working", idle: "idle" }
var STATUS_ORDER = ["blocked", "done", "working", "idle"]

function statusLabel(status) { return STATUS_LABEL[normStatus(status)] }

// "2 working · 1 needs you": blocked first, zero counts dropped, "" when empty.
function countsText(counts) {
  if (!counts) return ""
  var parts = []
  for (var i = 0; i < STATUS_ORDER.length; i++) {
    var k = STATUS_ORDER[i], n = counts[k] || 0
    if (n > 0) parts.push(n + " " + STATUS_LABEL[k])
  }
  return parts.join(" · ")
}

function countsOf(agents) {
  var c = { working: 0, blocked: 0, done: 0, idle: 0 }
  for (var i = 0; i < agents.length; i++) c[normStatus(agents[i].status)]++
  return c
}

// Header totals: "6 agents" / "1 agent" / "No agents".
function totalsText(sum) {
  if (!sum || !sum.ok || sum.total === 0) return "No agents"
  return sum.total + (sum.total === 1 ? " agent" : " agents")
}

// Stable key for a group (machine + space), used for the collapsed set.
function groupKey(g) { return (g.machine ? g.machine + "/" : "") + g.space }

// Groups with each group's own counts, text and key. Groups holding a blocked
// agent come first, then done, working, idle; ties keep herdr's order.
function groupModel(sum) {
  if (!sum || !sum.ok) return []
  var out = []
  for (var i = 0; i < sum.groups.length; i++) {
    var g = sum.groups[i]
    var c = countsOf(g.agents)
    out.push({ key: groupKey(g), space: g.space, machine: g.machine, agents: g.agents, counts: c, countsText: countsText(c), blocked: c.blocked > 0, idx: i })
  }
  out.sort(function (a, b) {
    return statusPriority(b.agents[0].status) - statusPriority(a.agents[0].status) || a.idx - b.idx
  })
  return out
}

// Collapsed-set handling. `collapsed` is an array of group keys (what is
// stored under the `agents.collapsed` setting). A group with a blocked agent
// is always shown expanded.
function normCollapsed(v) {
  if (!Array.isArray(v)) return []
  return v.filter(function (x) { return typeof x === "string" && x })
}
function isCollapsed(collapsed, group) {
  return !group.blocked && normCollapsed(collapsed).indexOf(group.key) >= 0
}
function toggleCollapsed(collapsed, group) {
  var list = normCollapsed(collapsed)
  var i = list.indexOf(group.key)
  if (i >= 0) list.splice(i, 1)
  else list.push(group.key)
  return list
}
// The stored value lives in this plugin's shell.json entry (Settings.resolve
// drops keys it does not know, so read the raw entry).
function readCollapsed(shellConfig, pluginId) {
  var list = shellConfig && Array.isArray(shellConfig.plugins) ? shellConfig.plugins : []
  for (var i = 0; i < list.length; i++) if (list[i] && list[i].id === pluginId) return normCollapsed(list[i]["agents.collapsed"])
  return []
}

// ---------------------------------------------------------------- icons

// herdr's own program icons (~/.config/herdr-app/icons/<file>) by app id. Only
// the ones that render on a dark island: codex/cursor are white-on-white and
// opencode is currentColor (black), so those use a monogram.
var ICON_FILES = {
  "claude-code": "claude.svg", "claude": "claude.svg", "antigravity": "antigravity.svg"
}
var MONO_COLORS = {
  "claude-code": "#d97757", "claude": "#d97757", "devin": "#4f9dff", "codex": "#10a37f", "opencode": "#8a8f98",
  "cursor": "#9aa0a6", "antigravity": "#7c6cf0", "droid": "#f2762e", "gemini": "#4285f4", "pi": "#c678dd"
}

// { file, monogram, color } for an app id. `file` is "" when herdr has no icon.
function iconFor(app) {
  var key = String(app || "").toLowerCase()
  var name = appName(key)
  return {
    file: ICON_FILES[key] || "",
    monogram: name.charAt(0).toUpperCase(),
    color: MONO_COLORS[key] || "#8a8f98"
  }
}

// ---------------------------------------------------------------- usage rows

var PROVIDER_COLORS = { anthropic: "#d97757", claude: "#d97757", openai: "#10a37f", codex: "#10a37f", cursor: "#9aa0a6", gemini: "#4285f4", google: "#4285f4" }
var PROVIDER_ICONS = { anthropic: "claude.svg", claude: "claude.svg" }

function severityKey(sev) { return sev === "critical" ? "critical" : sev === "high" || sev === "mid" ? "warn" : "ok" }

// "3h", "2d", "12m", "now"; coarser than resetIn, for a narrow column.
function resetShort(resetAt, nowMs) {
  var t = Date.parse(resetAt)
  if (!isFinite(t)) return ""
  var mins = Math.floor((t - nowMs) / 60000)
  if (mins <= 0) return "now"
  if (mins >= 1440) return Math.floor(mins / 1440) + "d"
  if (mins >= 60) return Math.floor(mins / 60) + "h"
  return mins + "m"
}

// One row per provider (its busiest metric), busiest provider first.
// Returns { rows, hidden } where rows holds the first `limit` (all when
// `expanded`) and hidden is how many the "+N more" expander would reveal.
function usageRows(usage, nowMs, expanded, limit) {
  if (!usage || !usage.ok || !Array.isArray(usage.providers)) return { rows: [], hidden: 0, total: 0 }
  var max = limit > 0 ? limit : 3
  var all = []
  for (var i = 0; i < usage.providers.length; i++) {
    var p = usage.providers[i], best = null
    for (var j = 0; j < p.rows.length; j++) if (best === null || p.rows[j].percent > best.percent) best = p.rows[j]
    if (!best) continue
    var id = String(p.id).toLowerCase()
    var rs = best.resetAt ? resetShort(best.resetAt, nowMs) : ""
    all.push({
      id: p.id, name: p.name, initial: String(p.name || "?").charAt(0).toUpperCase(),
      color: PROVIDER_COLORS[id] || "#8a8f98", icon: PROVIDER_ICONS[id] || "",
      label: best.label, percent: best.percent, severity: severityKey(best.severity),
      resetText: rs ? (rs === "now" ? "resets now" : "resets in " + rs) : "", idx: i
    })
  }
  all.sort(function (a, b) { return b.percent - a.percent || a.idx - b.idx })
  var shown = expanded ? all : all.slice(0, max)
  return { rows: shown, hidden: all.length - shown.length, total: all.length }
}

if (typeof module !== "undefined") {
  module.exports = {
    PRIORITY_BLOCKED: PRIORITY_BLOCKED, PRIORITY_DONE: PRIORITY_DONE,
    appName: appName, normStatus: normStatus, statusPriority: statusPriority, parseLs: parseLs,
    isActive: isActive, priority: priority, activityText: activityText, glyph: glyph,
    badgeText: badgeText, topUsage: topUsage, prettyApp: prettyApp, statusColorKey: statusColorKey, parseUsage: parseUsage, resetIn: resetIn,
    statusLabel: statusLabel, countsText: countsText, totalsText: totalsText, groupKey: groupKey, groupModel: groupModel,
    normCollapsed: normCollapsed, isCollapsed: isCollapsed, toggleCollapsed: toggleCollapsed, readCollapsed: readCollapsed,
    iconFor: iconFor, resetShort: resetShort, usageRows: usageRows
  }
}
