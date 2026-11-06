// Pure logic for the Plugins tab: which bar plugins to show as slots, what to
// call them, and how to open their panels. No Qt types.

var GENERIC_GLYPH = "\u{F0431}"
var IMAGE_RE = /\.(png|jpe?g|svg|webp)$/i

// Section ids from bar.layout.tray, in order, deduplicated. Entries are
// { id } objects (or bare strings); anything else is skipped.
function trayIds(config) {
  var layout = config && config.bar && config.bar.layout ? config.bar.layout : null
  var tray = layout && Array.isArray(layout.tray) ? layout.tray : []
  var seen = {}
  var ids = []
  for (var i = 0; i < tray.length; i++) {
    var e = tray[i]
    var id = typeof e === "string" ? e : (e && typeof e === "object" ? e.id : "")
    if (typeof id !== "string" || id === "" || seen[id]) continue
    seen[id] = true
    ids.push(id)
  }
  return ids
}

function manifestPath(home, id) {
  return String(home) + "/.config/omarchy/plugins/" + id + "/manifest.json"
}

// Name and icon for one slot from its manifest text (or "" when unreadable).
// `preview` may be an image path (absolute, or relative to the plugin dir) or
// a short glyph; otherwise a generic glyph. Falls back to the id's last
// segment for the name.
function slotInfo(id, manifestText, home) {
  var m = null
  try { m = JSON.parse(manifestText) } catch (e) { m = null }
  if (!m || typeof m !== "object") m = {}
  var bar = m.barWidget && typeof m.barWidget === "object" ? m.barWidget : {}
  var name = String(bar.displayName || m.name || "")
  if (name === "") {
    var parts = String(id).split(".")
    name = parts[parts.length - 1] || String(id)
  }
  var image = ""
  var glyph = GENERIC_GLYPH
  var pv = typeof m.icon === "string" ? m.icon : (typeof m.preview === "string" && !/^preview\.png$/i.test(m.preview) ? m.preview : "")
  if (GLYPHS[id]) glyph = GLYPHS[id]
  if (pv !== "") {
    if (IMAGE_RE.test(pv)) {
      image = pv.charAt(0) === "/" ? pv : String(home) + "/.config/omarchy/plugins/" + id + "/" + pv.replace(/^\.\//, "")
    } else if (pv.length <= 4) {
      glyph = pv
    }
  }
  // A plugin's own icon.png, when it ships one, beats the glyph (the slot falls
  // back to the glyph while the image is not there).
  if (image === "") image = String(home) + "/.config/omarchy/plugins/" + id + "/icon.png"
  return { id: id, name: name, glyph: glyph, image: image }
}

// `qs ipc` fallback for opening a plugin's panel when the injected shell has
// no in-process toggle.
function ipcCommand(id) {
  return ["qs", "-p", "/usr/share/omarchy/shell", "ipc", "call", "shell", "toggle", String(id), "{}"]
}

// ---- opening a plugin's panel
// A tray-section plugin only has a panel the shell can summon while its bar
// widget is live; with the built-in tray off the bar nothing answers. So the
// open is a chain, first success wins:
//   1. shell summon <id>        stdout "ok" when a live widget opened
//   2. qs ipc call <id> toggle  the plugin's own IpcHandler target, exit 0
//   3. a plugin-specific fallback (open its web page / a terminal view)
var QS = ["/usr/bin/qs", "-p", "/usr/share/omarchy/shell", "ipc", "call"]
var FALLBACKS = {
  "robzolkos.github": ["/usr/bin/xdg-open", "https://github.com/notifications"],
  "io.github.duketopceo.dayflow": ["/usr/bin/xdg-terminal-exec", "/bin/sh", "-c", "$HOME/.local/bin/dayflow today | less -R"],
  "io.github.duketopceo.omaseal": ["/usr/bin/xdg-terminal-exec", "/bin/sh", "-c", "$HOME/.local/bin/omaseal ls | less -R"]
}

function openChain(id, extraFallback) {
  var steps = [
    { kind: "summon", cmd: QS.concat(["shell", "summon", String(id), "{}"]) },
    { kind: "ipc", cmd: QS.concat([String(id), "toggle"]) }
  ]
  var fb = FALLBACKS[id] || extraFallback
  if (fb) steps.push({ kind: "run", cmd: fb })
  return steps
}

// Did this step open the panel? `summon` prints "ok"; `ipc` must exit 0 without
// "not found"; a fallback just has to exit 0.
function stepOk(step, code, text) {
  if (!step) return false
  if (step.kind === "summon") return String(text || "").trim() === "ok"
  if (step.kind === "ipc") return code === 0 && !/not found/i.test(String(text || ""))  // qs prints "Target not found." and exits 0
  return code === 0
}

// ---- the hub (Plugins tab)
// The tab is the first place every plugin is reachable (plan R1-R6): the bar's
// tray plugins plus the right-side set the user confirmed, nested in three
// sections, one large tile each.
//
// Nothing here is pinned to one machine's bar: the tray list comes from the
// live config, and the right-side ids are a documented set that is filtered
// against what is actually installed as soon as the caller knows.

var SECTIONS = [
  { id: "tray", title: "Tray" },
  { id: "system", title: "System" },
  { id: "agent", title: "Agent" }
]

// Right-side plugins the user confirmed for the hub (R5). Full ids; the
// matcher also accepts the short name, so "power" finds "lukedaduke.power".
// This is the hub's list, not the bar's: `bin/notch-slim-bar` leaves seven
// widgets on the bar right side (update, blip, bluetooth, network, AI usage,
// audio, power) and the hub still lists what the notch absorbed.
var RIGHT_IDS = [
  "nixfred.blip", "omarchy.network", "omarchy.auth", "omarchy.bluetooth",
  "omarchy.tray", "lukedaduke.power", "lukedaduke.lidguard",
  "io.github.ncr.omaphones", "io.github.duketopceo.wisp", "lukedaduke.agents",
  "ssupt.audio-control", "akitaonrails.ai-usagebar"
]

// Section keys, matched against the id's last segment. "tray" also covers the
// tray hosts themselves (io.github.tyrichards.tray, omarchy.tray).
var SYSTEM_KEYS = ["blip", "network", "auth", "bluetooth", "tray", "power", "lidguard", "omaphones", "wisp", "audio-control", "audio", "ai-usagebar"]
var AGENT_KEYS = ["agents", "herdr", "neo"]

// Plugin ids whose UI already lives inside the notch as a tab. A tile opens
// that tab in place instead of the launcher chain; when the tab is not
// shipped or not visible (an optional tab that is off) the tile degrades to
// the chain and says what it needs (R10).
var EMBED = {
  "lukedaduke.power": { tab: "power" },
  "omarchy.network": { tab: "network" },
  "lukedaduke.agents": { tab: "agents" },
  "nixfred.blip": { tab: "messages" },
  "akitaonrails.ai-usagebar": { tab: "ai", requires: "AI usage" },
  "io.github.duketopceo.dayflow": { tab: "dayflow", requires: "Dayflow" },
  "io.github.duketopceo.snapdex": { tab: "screenshots", requires: "Screenshots" }
}

// R6: the end-of-hub row that opens Preferences.
var CONFIGURE = { id: "settings", label: "Configure", title: "All plugins" }

// Tile box. The old grid was 3 columns of 224 x 94 px in a 720 px panel; a hub
// tile keeps 2 columns and is 3.5x that cell's area, so names and previews are
// readable instead of icon-only. The panel scrolls (NotchScroll) for the rest.
var BASE_CELL = { w: 224, h: 94 }
var GROWTH = 3.5
var HUB_GAP = 10
var TILE_H = 132

function tileColumns(width) {
  var w = Number(width)
  if (!(w > 0)) return 3
  if (w >= 1000) return 4
  if (w >= 650) return 3
  return 2
}

function tileWidth(width, gap) {
  var g = Number(gap) >= 0 ? Number(gap) : HUB_GAP
  var w = Number(width)
  if (!(w > 0)) return BASE_CELL.w
  var n = tileColumns(w)
  return Math.max(120, Math.floor((w - (n - 1) * g) / n))
}

function tileArea(width, gap) {
  return tileWidth(width, gap) * TILE_H
}

// Does this id answer to one of these short keys? "omarchy.network" matches
// "network"; an exact full id also matches.
function matches(id, keys) {
  var s = String(id || "")
  var last = s.split(".").pop()
  for (var i = 0; i < keys.length; i++) if (s === keys[i] || last === keys[i]) return true
  return false
}

// Which hub section a plugin belongs to: agent, then system, else tray.
function sectionOf(id) {
  if (matches(id, AGENT_KEYS)) return "agent"
  if (matches(id, SYSTEM_KEYS)) return "system"
  return "tray"
}

// Ids in the hub: tray order first, then the confirmed right side, de-duped.
// `installed` is the shell's installed-plugin list when known; with it, ids
// that are not installed (stale bar entries, absent right-side plugins) are
// dropped so the hub never shows a tile that cannot do anything. No list means
// "unknown" and nothing is filtered.
function hubIds(config, installed, rightIds) {
  var right = Array.isArray(rightIds) ? rightIds : RIGHT_IDS
  var candidates = trayIds(config).concat(right)
  var known = Array.isArray(installed) && installed.length ? installed : null
  var seen = {}
  var ids = []
  for (var i = 0; i < candidates.length; i++) {
    var id = String(candidates[i])
    if (id === "" || seen[id]) continue
    seen[id] = true
    if (known && known.indexOf(id) < 0) continue
    ids.push(id)
  }
  return ids
}

// Grouped hub for the bar: [{ id, title, tiles: [id] }], empty sections
// dropped, section order fixed (Tray, System, Agent).
function hub(config, installed, rightIds) {
  var ids = hubIds(config, installed, rightIds)
  var out = []
  for (var s = 0; s < SECTIONS.length; s++) {
    var tiles = []
    for (var i = 0; i < ids.length; i++) if (sectionOf(ids[i]) === SECTIONS[s].id) tiles.push(ids[i])
    if (tiles.length) out.push({ id: SECTIONS[s].id, title: SECTIONS[s].title, tiles: tiles })
  }
  return out
}

// What a tile click does. `tabs` is the list of tab ids the panel can actually
// show (Tabs.visibleIds); a null list means "assume available".
//   { kind: "tab", id }    open that notch tab in place
//   { kind: "chain", id, requires }   launch through Plugins.openChain
function action(id, tabs) {
  var e = EMBED[id]
  if (!e) return { kind: "chain", id: String(id), requires: "" }
  if (Array.isArray(tabs) && tabs.indexOf(e.tab) < 0) return { kind: "chain", id: String(id), requires: e.requires || "" }
  return { kind: "tab", id: e.tab, requires: "" }
}

function configure() {
  return { kind: "tab", id: CONFIGURE.id, requires: "" }
}

// Busiest AI usage window: { percent, severity } or null. Same numbers the
// bar widget draws; `usage` is Notch.usage (Agents.parseUsage output).
function topPercent(usage) {
  if (!usage || !usage.ok || !Array.isArray(usage.providers)) return null
  var best = null
  for (var i = 0; i < usage.providers.length; i++) {
    var rows = usage.providers[i] && usage.providers[i].rows
    if (!Array.isArray(rows)) continue
    for (var j = 0; j < rows.length; j++) {
      if (!(rows[j].percent >= 0)) continue
      if (best === null || rows[j].percent > best.percent)
        best = { percent: Math.round(rows[j].percent), severity: String(rows[j].severity || "low") }
    }
  }
  return best
}

// A one-line live detail for a tile: the AI usage percent next to the icon in
// the bar, and Blip's unread count (or its bridge state), each read from the
// notch's shared state. "" when the plugin has nothing to say.
// `ctx` = { usage (Notch.usage), messages (MessagesActivity) }.
function detail(id, ctx) {
  var c = ctx || {}
  var s = String(id || "")
  if (s === "akitaonrails.ai-usagebar") {
    var top = topPercent(c.usage)
    return top ? { text: top.percent + "%", tone: top.severity } : { text: "", tone: "" }
  }
  if (s === "nixfred.blip") {
    var m = c.messages
    if (!m) return { text: "", tone: "" }
    var unread = Number(m.unread) || 0
    if (unread > 0) return { text: unread + " unread", tone: "info" }
    if (m.running === true && !m.online) return { text: "Mac offline", tone: "warn" }
    if (m.running === false) return { text: "Blip off", tone: "dim" }
    return { text: "", tone: "" }
  }
  return { text: "", tone: "" }
}

// Status line for a tile (R3): a pill when the UI lives in the notch, a dot
// for on/off-the-bar plugins. `ctx` = { failed, tabs, tray, right, usage, messages }.
// `detail` carries a live number where one exists (AI %, Blip unread) so the
// hub shows the same figure as the bar.
function status(id, ctx) {
  var c = ctx || {}
  var live = detail(id, c)
  if (c.failed === id) return { kind: "pill", on: false, text: "No panel", detail: live.text, tone: live.tone }
  if (action(id, c.tabs).kind === "tab") return { kind: "pill", on: true, text: "In notch", detail: live.text, tone: live.tone }
  var onBar = (Array.isArray(c.tray) && c.tray.indexOf(id) >= 0) || (Array.isArray(c.right) && c.right.indexOf(id) >= 0)
  return onBar
    ? { kind: "dot", on: true, text: "On the bar", detail: live.text, tone: live.tone }
    : { kind: "dot", on: false, text: "Launcher", detail: live.text, tone: live.tone }
}

function launchHint(id, tabs) {
  var a = action(id, tabs)
  return a.kind === "chain" && a.requires ? "Requires " + a.requires : ""
}

// Per-plugin bar glyph (Nerd Font). preview.png files are screenshots of the
// panel, not icons, so they are never used as the slot icon.
var GLYPHS = {
  "io.github.duketopceo.dayflow": "\u{F0954}", "robzolkos.github": "\u{F02A4}",
  "io.github.duketopceo.omaseal": "\u{F0306}", "io.github.duketopceo.bumblebee": "\u{F0FA1}",
  "lukedaduke.fan": "\u{F0210}", "io.github.duketopceo.numbat": "\u{F03E9}",
  "io.github.duketopceo.pplx": "\u{F0349}", 
  "lukedaduke.lidguard": "\u{F0322}", "io.github.duketopceo.wisp": "\u{F0E7}"
}

if (typeof module !== "undefined") {
  module.exports = {
    openChain: openChain, stepOk: stepOk, GLYPHS: GLYPHS, FALLBACKS: FALLBACKS, GENERIC_GLYPH: GENERIC_GLYPH,
    trayIds: trayIds, manifestPath: manifestPath, slotInfo: slotInfo, ipcCommand: ipcCommand,
    SECTIONS: SECTIONS, RIGHT_IDS: RIGHT_IDS, SYSTEM_KEYS: SYSTEM_KEYS, AGENT_KEYS: AGENT_KEYS,
    EMBED: EMBED, CONFIGURE: CONFIGURE, BASE_CELL: BASE_CELL, GROWTH: GROWTH, HUB_GAP: HUB_GAP, TILE_H: TILE_H,
    tileColumns: tileColumns,
    matches: matches, sectionOf: sectionOf, hubIds: hubIds, hub: hub, action: action, configure: configure,
    status: status, launchHint: launchHint, tileWidth: tileWidth, tileArea: tileArea,
    topPercent: topPercent, detail: detail
  }
}
