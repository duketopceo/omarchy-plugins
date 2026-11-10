// Pure logic for the expanded panel's tabs. No Qt types, so tests run it with
// node.
//
// Contract: each tab is { id, title, short, glyph, source }; `short` is the
// label for the tab strip (<= 7 chars, so seven or more tabs fit). `source` is a QML file
// next to Notch.qml; the panel loads it with a Loader and sets the loaded
// item's `notch` property to the root Notch.qml item. A source that does not
// exist yet (a sibling branch has not landed) shows a quiet "coming soon"
// line instead of an error.

var DEFAULT_TAB = "home"

// Every tab opens at Home's size, so the panel never jumps between tabs.
var PANEL_SIZE = { w: 720, h: 380 }

var TABS = [
  { id: "home", title: "Home", short: "Home", glyph: "\u{F02DC}", source: "HomeTab.qml", size: PANEL_SIZE },
  { id: "media", title: "Media", short: "Media", glyph: "\u{F075A}", source: "MediaTab.qml", size: PANEL_SIZE },
  { id: "agents", title: "Agents", short: "Agents", glyph: "\u{F06A9}", source: "AgentsTab.qml", optional: "optAgents", size: PANEL_SIZE },
  { id: "ai", title: "AI usage", short: "AI", glyph: "\u{F0E7}", source: "AiUsageTab.qml", optional: "aiUsage", size: PANEL_SIZE },
  { id: "messages", title: "Messages", short: "Msgs", glyph: "\u{F0361}", source: "MessagesTab.qml", optional: "optMessages", size: PANEL_SIZE },
  { id: "network", title: "Network", short: "Net", glyph: "\u{F05A9}", source: "NetworkTab.qml", size: PANEL_SIZE },
  { id: "power", title: "Power", short: "Power", glyph: "\u{F140B}", source: "PowerTab.qml", size: PANEL_SIZE },
  { id: "system", title: "System", short: "System", glyph: "\u{F061A}", source: "SystemTab.qml", size: PANEL_SIZE },
  { id: "stocks", title: "Stocks", short: "Stocks", glyph: "\u{F012A}", source: "StocksTab.qml", size: PANEL_SIZE },
  { id: "screenshots", title: "Shots", short: "Shots", glyph: "\u{F0100}", source: "ScreenshotsTab.qml", optional: "snapdex", size: PANEL_SIZE },
  { id: "dayflow", title: "Dayflow", short: "Day", glyph: "\u{F0CA2}", source: "DayflowTab.qml", optional: "dayflow", size: PANEL_SIZE },  // local customization
  { id: "timer", title: "Timer", short: "Timer", glyph: "\u{F13AB}", source: "TimerTab.qml", optional: "timer", size: PANEL_SIZE },
  { id: "clipboard", title: "Clipboard", short: "Clip", glyph: "\u{F014C}", source: "ClipboardTab.qml", optional: "clipboard", needs: "clipboard", size: PANEL_SIZE },
  { id: "plugins", title: "Plugins", short: "Plugins", glyph: "\u{F0431}", source: "PluginsTab.qml", size: PANEL_SIZE },
  { id: "settings", title: "Settings", short: "Prefs", glyph: "\u{F0493}", source: "SettingsTab.qml", size: PANEL_SIZE }
]

// Tabs the owner can never hide: Home is where the panel opens and Settings is
// the way back to every switch.
var PINNED = ["home", "settings"]

// Tabs to show for these resolved settings: an `optional` tab needs the
// setting of that name to be true (personal integrations, off by default).
// Tabs the owner hid (`hiddenTabs`) are dropped too, except the pinned ones.
//
// A tab with `needs: "<probe key>"` also needs that capability from the
// capability probe (`probe`, Caps.parseProbe output): it is hidden when the
// probe says the dependency is missing (Clipboard without cliphist). Without a
// probe argument nothing is filtered.
function visibleTabs(settings, tabs, probe) {
  var list = Array.isArray(tabs) ? tabs : TABS
  var hidden = settings && Array.isArray(settings.hiddenTabs) ? settings.hiddenTabs : []
  return list.filter(function (t) {
    if (t.optional && !(settings && settings[t.optional] === true)) return false
    if (t.needs && probe && probe[t.needs] !== true) return false
    return PINNED.indexOf(t.id) >= 0 || hidden.indexOf(t.id) < 0
  })
}

// Just the ids of the visible tabs. The Plugins tab uses this to decide
// whether an embedded tile can open in place or has to fall back to the
// launcher chain (Tabs.js stays the one source of truth for what is shipped).
function visibleIds(settings, tabs, probe) {
  return visibleTabs(settings, tabs, probe).map(function (t) { return t.id })
}

// Optional per-tab panel size `size: { w, h }` (logical px) lives on the tab
// entry; a tab without one gets the default 460 x 240 (Expand.panelSize).
function sizeFor(id, tabs) {
  var t = byId(id, tabs)
  return t && t.size ? t.size : null
}

// Tallest panel any tab asks for (the layer-shell window is sized to this).
function maxHeight(defaultHeight, tabs) {
  var list = Array.isArray(tabs) ? tabs : TABS
  var h = Number(defaultHeight) > 0 ? Number(defaultHeight) : 240
  for (var i = 0; i < list.length; i++) if (list[i] && list[i].size) h = Math.max(h, Number(list[i].size.h) || 0)
  return h
}

function byId(id, tabs) {
  var list = Array.isArray(tabs) ? tabs : TABS
  for (var i = 0; i < list.length; i++) if (list[i] && list[i].id === id) return list[i]
  return null
}

// The tab to show for a requested id: unknown ids fall back to home.
function select(id, tabs) {
  return byId(id, tabs) || byId(DEFAULT_TAB, tabs) || (Array.isArray(tabs) ? tabs[0] : TABS[0]) || null
}

function comingSoonText(tab) {
  return (tab && tab.title ? tab.title : "This tab") + " is coming soon"
}

// What the panel should show for `tab`. `exists` maps a tab id to true/false
// once the source file has been probed; absent means still probing.
//   { state: "ready", source }   load it
//   { state: "loading", source: "" }   probe not back yet, show nothing
//   { state: "missing", source: "", message }   quiet placeholder
function resolve(tab, exists) {
  if (!tab || !tab.source) return { state: "missing", source: "", message: comingSoonText(tab) }
  var known = exists && Object.prototype.hasOwnProperty.call(exists, tab.id) ? exists[tab.id] : undefined
  if (known === true) return { state: "ready", source: tab.source, message: "" }
  if (known === false) return { state: "missing", source: "", message: comingSoonText(tab) }
  return { state: "loading", source: "", message: "" }
}

// A Loader that failed after the probe said the file exists (syntax error in
// the tab) is also shown as the quiet placeholder rather than an error.
function failed(tab) {
  return { state: "missing", source: "", message: comingSoonText(tab) }
}

// ---------------------------------------------------------------- strip diet

// How many of the most-used tabs keep their text label besides the selected one.
var LABELED_USED = 2
var USAGE_CAP = 500

// Count one more open of `id`. Counts halve once any passes USAGE_CAP so old
// habits fade. Returns a new map.
function bumpUsage(usage, id) {
  var out = {}
  var u = usage && typeof usage === "object" ? usage : {}
  for (var k in u) out[k] = Number(u[k]) || 0
  out[id] = (out[id] || 0) + 1
  if (out[id] > USAGE_CAP) for (var j in out) out[j] = Math.floor(out[j] / 2)
  return out
}

// The `n` most-opened tab ids among `tabs` (never `exceptId`), busiest first;
// ties keep tab order and a tab never opened is never listed.
function topUsed(tabs, usage, n, exceptId) {
  var list = Array.isArray(tabs) ? tabs : TABS
  var u = usage && typeof usage === "object" ? usage : {}
  var ranked = []
  for (var i = 0; i < list.length; i++) {
    var c = Number(u[list[i].id]) || 0
    if (list[i].id !== exceptId && c > 0) ranked.push({ id: list[i].id, c: c, i: i })
  }
  ranked.sort(function (a, b) { return b.c - a.c || a.i - b.i })
  return ranked.slice(0, Math.max(0, n)).map(function (r) { return r.id })
}

// Tab ids that keep a text label: the selected one first, then the most used.
function labelIds(tabs, selectedId, usage, n) {
  return [selectedId].concat(topUsed(tabs, usage, n === undefined ? LABELED_USED : n, selectedId))
}

// Next/previous visible tab id for keyboard cycling (wraps). `dir` +1 / -1.
function cycle(tabs, currentId, dir) {
  var list = Array.isArray(tabs) ? tabs : []
  if (list.length === 0) return null
  var at = 0
  for (var i = 0; i < list.length; i++) if (list[i].id === currentId) at = i
  var d = Number(dir) < 0 ? -1 : 1
  return list[(at + d + list.length) % list.length].id
}

// Chip geometry for the strip. `labelW` maps a tab id to its measured label
// width in px. Everything labeled and equal when that fits; otherwise the
// labelled ids (selected first, then most used) get text-sized chips and the
// rest share what remains as glyph-only chips. When even that does not fit,
// labels drop from the least-used end, never the selected one.
//   returns { equal, widths: [px per id], xs: [x per id], labeled: {id: true} }
function stripLayout(ids, labelled, labelW, total, gap, glyphW, padX) {
  var n = ids.length
  var need = function (id) { return glyphW + 4 + (Number(labelW[id]) || 0) + padX }
  var gaps = Math.max(0, n - 1) * gap
  var longest = 0
  var all = {}
  for (var i = 0; i < n; i++) { longest = Math.max(longest, need(ids[i])); all[ids[i]] = true }
  var equalW = n > 0 ? Math.floor((total - gaps) / n) : 0
  var out = { equal: false, widths: [], xs: [], labeled: {} }
  if (n > 0 && equalW >= longest) {
    out.equal = true
    out.labeled = all
    for (var a = 0; a < n; a++) out.widths.push(equalW)
  } else {
    var want = labelled.filter(function (id) { return ids.indexOf(id) >= 0 })
    var minOther = glyphW + 10
    var otherW = 0
    for (;;) {
      var sum = 0
      for (var b = 0; b < want.length; b++) sum += need(want[b])
      var others = n - want.length
      otherW = others > 0 ? Math.floor((total - gaps - sum) / others) : 0
      if (others === 0 || otherW >= minOther || want.length <= 1) break
      want.pop()
    }
    for (var w = 0; w < want.length; w++) out.labeled[want[w]] = true
    for (var c = 0; c < n; c++) out.widths.push(out.labeled[ids[c]] ? need(ids[c]) : Math.max(1, otherW))
  }
  var x = 0
  for (var d = 0; d < n; d++) { out.xs.push(x); x += out.widths[d] + gap }
  return out
}

if (typeof module !== "undefined") {
  module.exports = { PINNED: PINNED, LABELED_USED: LABELED_USED, bumpUsage: bumpUsage, topUsed: topUsed, labelIds: labelIds, cycle: cycle, stripLayout: stripLayout, sizeFor: sizeFor, maxHeight: maxHeight, visibleTabs: visibleTabs, visibleIds: visibleIds, DEFAULT_TAB: DEFAULT_TAB, TABS: TABS, byId: byId, select: select, resolve: resolve, failed: failed, comingSoonText: comingSoonText }
}
