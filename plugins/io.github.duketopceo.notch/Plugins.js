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
  var pv = typeof m.preview === "string" ? m.preview : ""
  if (pv !== "") {
    if (IMAGE_RE.test(pv)) {
      image = pv.charAt(0) === "/" ? pv : String(home) + "/.config/omarchy/plugins/" + id + "/" + pv.replace(/^\.\//, "")
    } else if (pv.length <= 4) {
      glyph = pv
    }
  }
  return { id: id, name: name, glyph: glyph, image: image }
}

// `qs ipc` fallback for opening a plugin's panel when the injected shell has
// no in-process toggle.
function ipcCommand(id) {
  return ["qs", "-p", "/usr/share/omarchy/shell", "ipc", "call", "shell", "toggle", String(id), "{}"]
}

if (typeof module !== "undefined") {
  module.exports = { GENERIC_GLYPH: GENERIC_GLYPH, trayIds: trayIds, manifestPath: manifestPath, slotInfo: slotInfo, ipcCommand: ipcCommand }
}
