// Shortcuts into Omacontrol (io.github.twiking.omacontrol), the third-party
// settings window. ES5, no Qt types; node tests load it with require().
//
// The Island never copies Omacontrol's code: it only runs its own IPC target,
//   qs -p /usr/share/omarchy/shell ipc call omacontrol showPage <page>
// and the page id comes from the fixed list below, never from free text.

var PLUGIN_ID = "io.github.twiking.omacontrol"
var SHELL_ROOT = "/usr/share/omarchy/shell"

// Every page id Omacontrol's showPage accepts, with the label it shows.
var PAGES = [
  { id: "overview", label: "Overview" }, { id: "network", label: "Network" },
  { id: "bluetooth", label: "Bluetooth" }, { id: "audio", label: "Sound" },
  { id: "displays", label: "Displays" }, { id: "power", label: "Power" },
  { id: "idle", label: "Idle & Lock" }, { id: "keyboard", label: "Keyboard" },
  { id: "bindings", label: "Bindings" }, { id: "pointer", label: "Mouse & touchpad" },
  { id: "theme", label: "Appearance" }, { id: "wallpaper", label: "Wallpaper" },
  { id: "bar", label: "Bar" }, { id: "workspaces", label: "Workspaces" },
  { id: "windows", label: "Windows" }, { id: "security", label: "Security" },
  { id: "disk", label: "Storage" }, { id: "processes", label: "Processes" },
  { id: "datetime", label: "Date & time" }, { id: "about", label: "About" },
  { id: "plugins", label: "Plugins" }, { id: "packages", label: "Packages" }
]

// The shortcut row on the Settings page, in order: page id, short label and
// the Glyphs.js glyph name. "overview" is the "All settings" entry.
var SHORTCUTS = [
  { id: "network", label: "Network", glyph: "wifi" },
  { id: "bluetooth", label: "Bluetooth", glyph: "bluetooth" },
  { id: "audio", label: "Sound", glyph: "sound" },
  { id: "displays", label: "Displays", glyph: "display" },
  { id: "power", label: "Power", glyph: "power" },
  { id: "keyboard", label: "Keyboard", glyph: "keyboard" },
  { id: "theme", label: "Appearance", glyph: "theme" },
  { id: "overview", label: "All settings", glyph: "tune" }
]

function _find(id) {
  for (var i = 0; i < PAGES.length; i++) if (PAGES[i].id === id) return PAGES[i]
  return null
}

function label(id) { var p = _find(id); return p ? p.label : "" }

// The argv that opens Omacontrol on a page, or null for an id that is not in
// the list. "" and "open" open it on its own last page.
function command(page) {
  var id = page === null || page === undefined ? "" : String(page)
  var base = ["qs", "-p", SHELL_ROOT, "ipc", "call", "omacontrol"]
  if (id === "" || id === "open") return base.concat(["open"])
  return _find(id) ? base.concat(["showPage", id]) : null
}

// The hint a shortcut shows.
function hint(id) {
  if (id === "overview") return "Open all settings"
  var l = label(id)
  return l === "" ? "" : "Open " + l + " settings"
}

// Omacontrol is usable when its manifest exists and shell.json does not list
// it in disabledPlugins. An unreadable shell.json counts as not disabled.
function available(shellText, manifestExists) {
  if (manifestExists !== true) return false
  var d
  try { d = JSON.parse(String(shellText || "")) } catch (e) { return true }
  var off = d && Array.isArray(d.disabledPlugins) ? d.disabledPlugins : []
  return off.indexOf(PLUGIN_ID) < 0
}

if (typeof module !== "undefined") module.exports = {
  PLUGIN_ID: PLUGIN_ID, PAGES: PAGES, SHORTCUTS: SHORTCUTS, label: label, command: command, hint: hint, available: available
}
