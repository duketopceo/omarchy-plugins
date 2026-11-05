// Pure logic for the notch's Dayflow integration (local customization, not
// upstream). Parses the `dayflow` CLI's JSON (status, today, agents, briefing,
// forecast) into small view models. No Qt types, so tests run it with node.
//
// Privacy: block titles and summaries can name other people, so the collapsed
// notch never shows them. It shows only the category and how long the current
// streak has run (`slotText`); titles appear in the expanded tab only.

var PRIORITY_PAUSED = 20   // below screenshots (30), done agents (40), media (50), blocked agents (80)
var STATUS_MS = 10000      // `dayflow status --json`, cheap
var TODAY_MS = 60000       // `dayflow today --json`, cheap
var AGENTS_MS = 10 * 60 * 1000     // `dayflow agents --no-recaps`, ~30 s of CPU: tab-visible only
var BRIEFING_MS = 30 * 60 * 1000   // `dayflow briefing`, ~90 s of CPU: tab-visible only
var FORECAST_MS = 60 * 60 * 1000
var CURRENT_GRACE_S = 30 * 60      // a block counts as "current" until 30 min after it ends
var GLYPH = "\u{F0CA2}"            // md-record-circle-outline (as the dayflow plugin)
var PAUSED_GLYPH = "\u{F03E6}"     // md-pause-circle-outline

// The dayflow plugin's engine defaults (Tokens.qml engineDefaults).
var CATEGORY_COLORS = {
  coding: "#388bee", communication: "#f27326", browsing: "#8b5cf6",
  writing: "#34d399", meetings: "#f3b13d", design: "#f53d7a",
  media: "#f53d3d", system: "#80808f", idle: "#6b7280",
  personal: "#f85a6a", other: "#9ca3af"
}

function categoryColor(cat) {
  var k = String(cat || "").toLowerCase()
  return Object.prototype.hasOwnProperty.call(CATEGORY_COLORS, k) ? CATEGORY_COLORS[k] : CATEGORY_COLORS.other
}

function categoryLabel(cat) {
  var s = String(cat || "").trim()
  if (s === "") return "Other"
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase()
}

function parseJson(text) {
  if (typeof text !== "string" || text.trim() === "") return null
  try { var d = JSON.parse(text); return d && typeof d === "object" ? d : null } catch (e) { return null }
}

function num(v) { var n = Number(v); return isFinite(n) ? n : 0 }
function str(v) { return v === null || v === undefined ? "" : String(v) }

// "1h 45m" / "45m" / "0m".
function duration(minutes) {
  var m = Math.max(0, Math.round(num(minutes)))
  var h = Math.floor(m / 60)
  return h > 0 ? h + "h" + (m % 60 ? " " + (m % 60) + "m" : "") : m + "m"
}

// ------------------------------------------------------------ status

function parseStatus(text) {
  var d = parseJson(text)
  if (!d || typeof d.capture_state !== "string") return { ok: false, recording: false, paused: false, state: "", activeApp: "", frames: 0, blocksDone: 0, blocksPending: 0, lastFrame: "", storage: "" }
  var paused = d.paused === true || d.capture_state === "paused"
  return {
    ok: true,
    state: d.capture_state,
    paused: paused,
    recording: !paused && d.capture_state === "recording",
    activeApp: str(d.active_app),
    frames: num(d.frames_today),
    blocksDone: num(d.blocks_done),
    blocksPending: num(d.blocks_pending),
    lastFrame: str(d.last_frame),
    storage: str(d.storage_text)
  }
}

function stateText(status) {
  if (!status || !status.ok) return "Dayflow unavailable"
  if (status.paused) return "Paused"
  if (status.recording) return "Recording"
  return categoryLabel(status.state)
}

// Pause when recording, resume when paused.
function toggleArgs(bin, status) {
  return [bin, status && status.paused ? "resume" : "pause"]
}

// ------------------------------------------------------------ today

function emptyToday() {
  return { ok: false, blocks: [], current: null, currentIndex: -1, trackedMin: 0, productiveMin: 0, focusPct: -1, topApps: [], categories: [], streakMin: 0 }
}

// Blocks oldest first, with the current block (the newest one that ended no
// more than CURRENT_GRACE_S ago), focus share and top apps.
function parseToday(text, nowSec) {
  var d = parseJson(text)
  if (!d || !Array.isArray(d.blocks)) return emptyToday()
  var now = num(nowSec) || Math.floor(Date.now() / 1000)
  var blocks = []
  for (var i = 0; i < d.blocks.length; i++) {
    var b = d.blocks[i]
    if (!b || typeof b !== "object") continue
    var s = num(b.start_ts), e = num(b.end_ts)
    if (!(s > 0) || !(e > s)) continue
    blocks.push({
      start: s, end: e,
      startLabel: str(b.start), endLabel: str(b.end),
      title: str(b.title), category: str(b.category).toLowerCase() || "other",
      app: str(b.app_name || b.app), productive: b.productive === true
    })
  }
  blocks.sort(function (a, b) { return a.start - b.start })
  var tracked = 0, productive = 0, apps = {}, cats = {}
  for (var j = 0; j < blocks.length; j++) {
    var m = (blocks[j].end - blocks[j].start) / 60
    tracked += m
    if (blocks[j].productive) productive += m
    if (blocks[j].app) apps[blocks[j].app] = (apps[blocks[j].app] || 0) + m
    cats[blocks[j].category] = (cats[blocks[j].category] || 0) + m
  }
  var last = blocks.length - 1
  var curIdx = last >= 0 && blocks[last].end >= now - CURRENT_GRACE_S && blocks[last].start <= now + 60 ? last : -1
  var streak = 0
  if (curIdx >= 0) {
    var k = curIdx
    var cat = blocks[curIdx].category
    var edge = blocks[curIdx].end
    while (k >= 0 && blocks[k].category === cat && edge - blocks[k].end <= 60) {
      streak += (blocks[k].end - blocks[k].start) / 60
      edge = blocks[k].start
      k--
    }
  }
  return {
    ok: true,
    blocks: blocks,
    current: curIdx >= 0 ? blocks[curIdx] : null,
    currentIndex: curIdx,
    trackedMin: Math.round(tracked),
    productiveMin: Math.round(productive),
    focusPct: tracked > 0 ? Math.round(100 * productive / tracked) : -1,
    topApps: rank(apps, 5),
    categories: rank(cats, 10),
    streakMin: Math.round(streak)
  }
}

function rank(map, limit) {
  var out = []
  for (var k in map) out.push({ name: k, minutes: Math.round(map[k]) })
  out.sort(function (a, b) { return b.minutes - a.minutes || (a.name < b.name ? -1 : 1) })
  return out.slice(0, limit)
}

// Timeline strip segments as 0..1 fractions of a window that runs from the
// hour before the first block (or 8 AM, whichever is earlier) to the hour
// after max(now, last end). `dayStartSec` is local midnight.
function strip(today, nowSec, dayStartSec) {
  var blocks = today && Array.isArray(today.blocks) ? today.blocks : []
  var now = num(nowSec)
  var day0 = num(dayStartSec)
  var from = day0 + 8 * 3600
  var to = Math.max(now, from + 3600)
  for (var i = 0; i < blocks.length; i++) { from = Math.min(from, blocks[i].start); to = Math.max(to, blocks[i].end) }
  from = day0 + Math.floor((from - day0) / 3600) * 3600
  to = day0 + Math.ceil((to - day0) / 3600) * 3600
  var span = Math.max(3600, to - from)
  var segs = []
  for (var j = 0; j < blocks.length; j++) {
    segs.push({
      x: (blocks[j].start - from) / span,
      w: (blocks[j].end - blocks[j].start) / span,
      color: categoryColor(blocks[j].category),
      current: j === (today ? today.currentIndex : -1)
    })
  }
  return { from: from, to: to, now: Math.max(0, Math.min(1, (now - from) / span)), segments: segs }
}

// ------------------------------------------------------------ collapsed notch

// Idle-slot text while recording: category and streak only, never a title.
function slotText(status, today) {
  if (!status || !status.ok || !status.recording || !today || !today.current) return ""
  return "● " + categoryLabel(today.current.category) + (today.streakMin > 0 ? " · " + duration(today.streakMin) : "")
}

// The collapsed-notch activity: only a paused capture, so it gets noticed.
function activity(enabled, status) {
  var on = enabled === true && !!status && status.ok && status.paused
  return { id: "dayflow", active: on, priority: PRIORITY_PAUSED, text: on ? "Dayflow paused" : "", glyph: PAUSED_GLYPH }
}

// Idle-cycle views with Dayflow's slot appended when it has something to say.
function idleViews(views, enabled, status, today) {
  var list = Array.isArray(views) ? views.slice() : []
  if (enabled === true && slotText(status, today) !== "") list.push("dayflow")
  return list
}

// ------------------------------------------------------------ agents, briefing, forecast

function prettySource(src) {
  var s = str(src).toLowerCase()
  var names = { claude: "Claude", codex: "Codex", opencode: "OpenCode", devin: "Devin", cursor: "Cursor", manual: "Manual" }
  return names[s] || categoryLabel(s)
}

function parseAgents(text, limit) {
  var d = parseJson(text)
  if (!d || !Array.isArray(d.sessions)) return { ok: false, count: 0, bySource: [], latest: [] }
  var counts = {}
  var list = []
  for (var i = 0; i < d.sessions.length; i++) {
    var s = d.sessions[i]
    if (!s || typeof s !== "object") continue
    var src = prettySource(s.source)
    counts[src] = (counts[src] || 0) + 1
    list.push({ source: src, title: str(s.title).replace(/\s+/g, " ").trim(), project: str(s.project), end: num(s.end) })
  }
  list.sort(function (a, b) { return b.end - a.end })
  var by = []
  for (var k in counts) by.push({ source: k, count: counts[k] })
  by.sort(function (a, b) { return b.count - a.count || (a.source < b.source ? -1 : 1) })
  return { ok: true, count: list.length, bySource: by, latest: list.slice(0, limit > 0 ? limit : 3) }
}

function parseBriefing(text, limit) {
  var d = parseJson(text)
  if (!d || !Array.isArray(d.workstreams)) return { ok: false, workstreams: [] }
  var out = []
  for (var i = 0; i < d.workstreams.length; i++) {
    var w = d.workstreams[i]
    if (!w || typeof w !== "object") continue
    var threads = Array.isArray(w.threads) ? w.threads.length : 0
    out.push({ name: str(w.name || w.id), summary: str(w.summary).replace(/\s+/g, " ").trim(), threads: threads })
  }
  out.sort(function (a, b) { return b.threads - a.threads })
  return { ok: true, workstreams: out.slice(0, limit > 0 ? limit : 3) }
}

// "Fri forecast: 74% coding · 7% communication".
function parseForecast(text) {
  var d = parseJson(text)
  if (!d || !Array.isArray(d.items)) return { ok: false, line: "" }
  var items = d.items.filter(function (x) { return x && num(x.pct) >= 1 }).slice(0, 2)
  if (items.length === 0) return { ok: true, line: "" }
  var day = str(d.weekday).slice(0, 3)
  return {
    ok: true,
    line: (day ? day + " forecast: " : "Forecast: ") + items.map(function (x) { return Math.round(num(x.pct)) + "% " + str(x.category).toLowerCase() }).join(" · ")
  }
}

// Is a throttled fetch due? `last` 0 = never fetched.
function due(last, now, every) {
  return !(num(last) > 0) || num(now) - num(last) >= num(every)
}

if (typeof module !== "undefined") {
  module.exports = {
    PRIORITY_PAUSED: PRIORITY_PAUSED, STATUS_MS: STATUS_MS, TODAY_MS: TODAY_MS, AGENTS_MS: AGENTS_MS,
    BRIEFING_MS: BRIEFING_MS, FORECAST_MS: FORECAST_MS, CATEGORY_COLORS: CATEGORY_COLORS, GLYPH: GLYPH,
    categoryColor: categoryColor, categoryLabel: categoryLabel, duration: duration,
    parseStatus: parseStatus, stateText: stateText, toggleArgs: toggleArgs,
    emptyToday: emptyToday, parseToday: parseToday, strip: strip,
    slotText: slotText, activity: activity, idleViews: idleViews,
    prettySource: prettySource, parseAgents: parseAgents, parseBriefing: parseBriefing, parseForecast: parseForecast, due: due
  }
}
