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
  module.exports = { openChain: openChain, stepOk: stepOk, GLYPHS: GLYPHS, FALLBACKS: FALLBACKS, GENERIC_GLYPH: GENERIC_GLYPH, trayIds: trayIds, manifestPath: manifestPath, slotInfo: slotInfo, ipcCommand: ipcCommand }
}
