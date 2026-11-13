// Pure logic for the notch's Screenshots tab and "new caption" activity. No
// Qt types, so tests run it with node. Snapdex does the real work; this only
// reads its output and builds its command lines.
//
//   <Pictures>/Screenshots/index.md   "- [name.png](name.png) — caption" per line
//   snapdex-ctl panel                 {ok, pending, indexed, auto:{enabled,...},
//                                      last_run, items:[{name,caption,ts,path}]}
//   snapdex-ctl process | auto on|off the plugin's own controls

var PYTHON = "/usr/bin/python3"
var CTL_REL = "/.config/omarchy/plugins/io.github.duketopceo.snapdex/bin/snapdex-ctl"
var INDEX_REL = "/Pictures/Screenshots/index.md"
var INBOX_REL = "/Pictures/Screenshots"
var LIBRARY_REL = "/Pictures/Screenshots/Library"
var FLASH_MS = 4000
var PRIORITY = 30
var THUMBS = 8
var MAX_CHARS = 36

function isObject(v) { return v !== null && typeof v === "object" && !Array.isArray(v) }

function ctlArgs(home, args) { return [PYTHON, String(home) + CTL_REL].concat(args) }
function indexPath(home) { return String(home) + INDEX_REL }
function libraryIndexPath(home) { return String(home) + LIBRARY_REL + "/index.md" }
function autoArgs(on) { return ["auto", on ? "on" : "off"] }

var LINE = /^-\s*\[([^\]]+)\]\(([^)]+)\)\s*[—-]+\s*(.*)$/

// index.md text -> [{name, caption, ts}] in file order. ts is the file name's
// "YYYY-MM-DD_HH-MM-SS" prefix, "" when absent.
function parseIndex(text) {
  var rows = []
  String(text || "").split("\n").forEach(function (line) {
    var m = LINE.exec(line.trim())
    if (!m) return
    var ts = /^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})/.exec(m[1])
    rows.push({ name: m[1], caption: m[3].trim(), ts: ts ? ts[1] : "" })
  })
  return rows
}

function nameSet(rows) {
  var set = {}
  rows.forEach(function (r) { set[r.name] = true })
  return set
}

function newer(a, b) { return (a.ts + a.name) > (b.ts + b.name) }

// Flash text for a caption: trimmed, capped.
function flashText(caption) {
  var c = String(caption || "").replace(/\s+/g, " ").trim()
  if (!c) return ""
  return c.length > MAX_CHARS ? c.slice(0, MAX_CHARS - 1) + "…" : c
}

function initial() { return { names: null, text: "", flashUntil: 0 } }

// Fold a fresh parse of index.md into the model. The first parse only sets the
// baseline (no flash for screenshots that were already captioned). Afterwards
// any rows not seen before flash for FLASH_MS: the newest caption, or a count
// when a batch lands.
function step(model, rows, now) {
  var names = nameSet(rows)
  if (!model || model.names === null) return { names: names, text: "", flashUntil: 0 }
  var fresh = rows.filter(function (r) { return !model.names[r.name] })
  if (fresh.length === 0) return { names: names, text: model.text, flashUntil: model.flashUntil }
  var top = fresh.reduce(function (a, b) { return newer(a, b) ? a : b })
  var text = fresh.length > 3 ? fresh.length + " screenshots captioned" : flashText(top.caption)
  if (!text) return { names: names, text: model.text, flashUntil: model.flashUntil }
  return { names: names, text: text, flashUntil: now + FLASH_MS }
}

function isActive(model, clock) { return !!model && model.text !== "" && model.flashUntil > clock }

// snapdex-ctl output -> what the tab shows, or { ok:false } on junk.
function parsePanel(text) {
  var d
  try { d = JSON.parse(String(text || "")) } catch (e) { return { ok: false, pending: 0, indexed: 0, autoOn: false, autoKnown: false, dst: "", inbox: "", library: "", items: [], error: "" } }
  if (!isObject(d)) return { ok: false, pending: 0, indexed: 0, autoOn: false, autoKnown: false, dst: "", inbox: "", library: "", items: [], error: "" }
  var items = (Array.isArray(d.items) ? d.items : []).filter(function (i) { return isObject(i) && i.name && i.path })
    .map(function (i) { return { name: String(i.name), caption: String(i.caption || ""), ts: String(i.ts || ""), path: String(i.path) } })
  items.sort(function (a, b) { return newer(a, b) ? -1 : newer(b, a) ? 1 : 0 })
  var pending = Number(d.pending)
  return {
    ok: d.ok !== false && isFinite(pending),
    pending: isFinite(pending) ? Math.max(0, Math.floor(pending)) : 0,
    indexed: Number(d.indexed) > 0 ? Math.floor(Number(d.indexed)) : 0,
    autoOn: isObject(d.auto) && d.auto.enabled === true,
    autoKnown: isObject(d.auto),
    dst: typeof d.dst === "string" ? d.dst : "",
    inbox: typeof d.inbox === "string" ? d.inbox : "",
    library: typeof d.library === "string" ? d.library : "",
    items: items.slice(0, THUMBS),
    error: typeof d.error === "string" ? d.error : ""
  }
}

// "<home>/Pictures/Screenshots" -> "~/Pictures/Screenshots"
function shortPath(path, home) {
  var p = String(path || ""), h = String(home || "")
  return h && (p === h || p.indexOf(h + "/") === 0) ? "~" + p.slice(h.length) : p
}

// Where things are: `library` (processed shots, opened by "Open folder") and
// `inbox` (unprocessed). Taken from snapdex-ctl's `library`/`inbox` fields;
// when absent: library = ~/Pictures/Screenshots/Library if it exists, else
// ~/Pictures/Screenshots (or snapdex's `dst`); inbox = ~/Pictures/Screenshots.
function folders(snap, home, libraryExists) {
  var h = String(home || "")
  var inbox = snap && snap.inbox ? snap.inbox : (snap && snap.dst ? snap.dst : h + INBOX_REL)
  var library = snap && snap.library ? snap.library : (libraryExists ? h + LIBRARY_REL : (snap && snap.dst ? snap.dst : h + INBOX_REL))
  return { library: library, inbox: inbox, separate: library !== inbox }
}

function pendingText(n) {
  return n === 0 ? "All captioned" : n + " unprocessed"
}

// The directory "Open library" reveals: the processed-shots folder when the
// library index exists, else "" so the caller opens nothing rather than a
// destination that is not there (KTD4).
function libraryDir(home, libraryExists) {
  return libraryExists === true ? String(home) + LIBRARY_REL : ""
}

if (typeof module !== "undefined") {
  module.exports = {
    PYTHON: PYTHON, FLASH_MS: FLASH_MS, PRIORITY: PRIORITY, THUMBS: THUMBS,
    ctlArgs: ctlArgs, indexPath: indexPath, libraryIndexPath: libraryIndexPath, folders: folders, autoArgs: autoArgs, parseIndex: parseIndex,
    flashText: flashText, initial: initial, step: step, isActive: isActive,
    parsePanel: parsePanel, shortPath: shortPath, pendingText: pendingText, libraryDir: libraryDir
  }
}
