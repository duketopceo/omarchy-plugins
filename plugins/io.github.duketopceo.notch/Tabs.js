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
  { id: "plugins", title: "Plugins", short: "Plugins", glyph: "\u{F0431}", source: "PluginsTab.qml", size: PANEL_SIZE },
  { id: "settings", title: "Settings", short: "Prefs", glyph: "\u{F0493}", source: "SettingsTab.qml", size: PANEL_SIZE }
]

// Tabs the owner can never hide: Home is where the panel opens and Settings is
// the way back to every switch.
var PINNED = ["home", "settings"]

// Tabs to show for these resolved settings: an `optional` tab needs the
// setting of that name to be true (personal integrations, off by default).
function visibleTabs(settings, tabs) {
  var list = Array.isArray(tabs) ? tabs : TABS
  return list.filter(function (t) { return !t.optional || !!(settings && settings[t.optional] === true) })
}

// Just the ids of the visible tabs. The Plugins tab uses this to decide
// whether an embedded tile can open in place or has to fall back to the
// launcher chain (Tabs.js stays the one source of truth for what is shipped).
function visibleIds(settings, tabs) {
  return visibleTabs(settings, tabs).map(function (t) { return t.id })
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

if (typeof module !== "undefined") {
  module.exports = { PINNED: PINNED, sizeFor: sizeFor, maxHeight: maxHeight, visibleTabs: visibleTabs, visibleIds: visibleIds, DEFAULT_TAB: DEFAULT_TAB, TABS: TABS, byId: byId, select: select, resolve: resolve, failed: failed, comingSoonText: comingSoonText }
}
