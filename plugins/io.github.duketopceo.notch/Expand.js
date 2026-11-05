// Pure logic for the notch island's hover-expand panel: the hover timing
// state machine, panel sizing, month-grid math and small text helpers.
// No Qt types here, so tests can run it with node.

var HOVER_DELAY_MS = 150   // hover this long before expanding
var LEAVE_DELAY_MS = 300   // leave this long before collapsing
var PANEL_WIDTH = 460      // logical px
var PANEL_HEIGHT = 240

// States: "collapsed" -> "arming" (pointer in, waiting) -> "open"
//         "open" -> "leaving" (pointer out, waiting) -> "collapsed"
// Events: "enter", "leave", "timer" (the pending timer fired).
// step() returns the next state plus the timer to (re)start: `timer` is a
// delay in ms, or 0 when any pending timer must be stopped.
function step(state, event, hoverDelay) {
  // A 0 timer means "stop", so the shortest delay is 1 ms.
  var hover = hoverDelay === null || hoverDelay === undefined || isNaN(Number(hoverDelay)) ? HOVER_DELAY_MS : Math.max(1, Number(hoverDelay))
  switch (state) {
    case "arming":
      if (event === "leave") return { state: "collapsed", timer: 0 }
      if (event === "timer") return { state: "open", timer: 0 }
      return { state: "arming", timer: 0 }
    case "open":
      if (event === "leave") return { state: "leaving", timer: LEAVE_DELAY_MS }
      return { state: "open", timer: 0 }
    case "leaving":
      if (event === "enter") return { state: "open", timer: 0 }
      if (event === "timer") return { state: "collapsed", timer: 0 }
      return { state: "leaving", timer: LEAVE_DELAY_MS }
    default:
      if (event === "enter") return { state: "arming", timer: hover }
      return { state: "collapsed", timer: 0 }
  }
}

// True while the island should be drawn at panel size.
function isExpanded(state) {
  return state === "open" || state === "leaving"
}

// Expanded panel size in logical px. `size` is a tab's optional `{ w, h }` from
// Tabs.js (the per-tab size hook); without it the default PANEL_WIDTH x
// PANEL_HEIGHT. Never wider than the screen minus a margin.
function panelSize(screenWidth, size) {
  var avail = Number(screenWidth) > 0 ? Math.floor(Number(screenWidth)) - 16 : PANEL_WIDTH
  var w = size && Number(size.w) > 0 ? Number(size.w) : PANEL_WIDTH
  var h = size && Number(size.h) > 0 ? Number(size.h) : PANEL_HEIGHT
  return { width: Math.max(0, Math.min(w, avail)), height: h }
}

function daysInMonth(year, month) {
  return new Date(Date.UTC(year, month + 1, 0)).getUTCDate()
}

// Month grid for `month` (0-11). Rows of 7 cells, 0 for padding days.
// firstDay is the weekday a row starts on (0 = Sunday, 1 = Monday).
function monthGrid(year, month, firstDay) {
  var start = Number(firstDay) === 1 ? 1 : 0
  var lead = (new Date(Date.UTC(year, month, 1)).getUTCDay() - start + 7) % 7
  var total = daysInMonth(year, month)
  var cells = []
  for (var i = 0; i < lead; i++) cells.push(0)
  for (var d = 1; d <= total; d++) cells.push(d)
  while (cells.length % 7 !== 0) cells.push(0)
  var rows = []
  for (var r = 0; r < cells.length; r += 7) rows.push(cells.slice(r, r + 7))
  return rows
}

var WEEKDAYS = ["S", "M", "T", "W", "T", "F", "S"]
function weekdayLabels(firstDay) {
  var start = Number(firstDay) === 1 ? 1 : 0
  var out = []
  for (var i = 0; i < 7; i++) out.push(WEEKDAYS[(i + start) % 7])
  return out
}

var CONDITIONS = {
  "clear": "Clear", "night": "Clear", "partly": "Partly cloudy",
  "night-cloudy": "Partly cloudy", "cloudy": "Cloudy", "fog": "Fog",
  "rain": "Rain", "snow": "Snow", "storm": "Thunderstorm"
}

// "Provo  46°F  Clear" from Model.parseWeather output, or "" without data.
// Condition label for a weather kind ("Cloudy" when unknown).
function conditionText(kind) { return CONDITIONS[kind] || "Cloudy" }

function weatherLine(weather) {
  if (!weather) return ""
  var parts = []
  if (weather.place) parts.push(weather.place)
  parts.push(weather.temperature + weather.unit)
  parts.push(CONDITIONS[weather.kind] || "Cloudy")
  return parts.join("  ")
}

// One short line from the cache's `quotes` (another unit writes them), or ""
// when absent. Accepts strings or { symbol, price, changePercent|change }.
function quotesLine(quotes, max) {
  var limit = Number(max) > 0 ? Number(max) : 3
  if (quotes && Array.isArray(quotes.items)) quotes = quotes.items  // watchlist cache shape
  if (!Array.isArray(quotes)) return ""
  var out = []
  for (var i = 0; i < quotes.length && out.length < limit; i++) {
    var q = quotes[i]
    if (typeof q === "string" && q) { out.push(q); continue }
    if (!q || typeof q.symbol !== "string") continue
    var text = q.symbol
    if (typeof q.price === "number") text += " " + q.price.toFixed(2)
    var ch = typeof q.changePercent === "number" ? q.changePercent : q.change
    if (typeof ch === "number") text += " " + (ch >= 0 ? "+" : "") + ch.toFixed(1) + "%"
    out.push(text)
  }
  return out.join("   ")
}

// Wisp state file: a dot is lit when the file holds a JSON object.
function parseWisp(text) {
  try {
    var d = JSON.parse(String(text || ""))
    return d && typeof d === "object" && !Array.isArray(d) ? { status: String(d.status || "") } : null
  } catch (error) {
    return null
  }
}

// probe_nordvpn.py status output: "connected" | "disconnected" | "connecting"
// | "unavailable" (CLI missing, logged out, or unparsable).
function parseNord(text) {
  try {
    var d = JSON.parse(String(text || ""))
    if (!d || d.cli === false || d.logged_in === false || !d.status) return "unavailable"
    return String(d.status.state || "unavailable")
  } catch (error) {
    return "unavailable"
  }
}

if (typeof module !== "undefined") {
  module.exports = {
    HOVER_DELAY_MS: HOVER_DELAY_MS, LEAVE_DELAY_MS: LEAVE_DELAY_MS,
    PANEL_WIDTH: PANEL_WIDTH, PANEL_HEIGHT: PANEL_HEIGHT,
    step: step, isExpanded: isExpanded, panelSize: panelSize, PANEL_HEIGHT: PANEL_HEIGHT, PANEL_WIDTH: PANEL_WIDTH,
    daysInMonth: daysInMonth, monthGrid: monthGrid, weekdayLabels: weekdayLabels,
    weatherLine: weatherLine, conditionText: conditionText, quotesLine: quotesLine, parseWisp: parseWisp, parseNord: parseNord
  }
}
