// Pure logic for the notch's settings: defaults, validation, the field list
// the Settings tab draws, and the shell.json mutator. No Qt types.
//
// Settings live in the plugin's own entry of shell.json's `plugins` array:
//   { "id": "io.github.duketopceo.notch", "clockSeconds": 24, ... }

var DEFAULTS = {
  theme: "swift",     // "swift" (polished) | "pxl" (retro pixel); see Theme.js
  clockSeconds: 24,
  slideSeconds: 7,
  showWeather: true,
  showStocks: true,
  unit: "F",          // "F" | "C"
  clockHours: 12,     // 12 | 24
  cameraWidth: 0,     // 0 = auto, else logical px
  hoverDelay: 150,    // ms before hover expands the panel
  reduceMotion: false, // swap springs and slides for quick fades
  snapdex: false,     // optional: Screenshots tab (snapdex when detected)
  optAgents: true,    // optional: Agents tab (herdr when detected)
  optMessages: true,  // optional: Messages tab (Blip when detected)
  optWordink: true,   // Home Dict / activity when wordink CLI exists
  optWisp: true,      // Home Wisp dot when wisp plugin exists
  optFan: true,       // System fan mode writes when lukedaduke.fan exists
  aiUsage: true,      // AI usage tab + the percent on the Plugins hub AI tile
  dayflow: false,     // local: Dayflow tab, Home tile, idle slot + paused indicator
  setupDone: false    // first-run optional-module setup completed
}

var FIELDS = [
  { key: "theme", label: "Theme", type: "choice",
    options: [{ value: "swift", label: "Swift" }, { value: "pxl", label: "Pxl (16-bit)" }] },
  { key: "clockSeconds", label: "Clock seconds", type: "int", min: 5, max: 120, step: 5, suffix: " s" },
  { key: "slideSeconds", label: "Slide seconds", type: "int", min: 2, max: 30, step: 1, suffix: " s" },
  { key: "showWeather", label: "Show weather", type: "bool" },
  { key: "showStocks", label: "Show stocks", type: "bool" },
  { key: "unit", label: "Temperature", type: "choice",
    options: [{ value: "F", label: "°F" }, { value: "C", label: "°C" }] },
  { key: "clockHours", label: "Clock", type: "choice",
    options: [{ value: 12, label: "12 h" }, { value: 24, label: "24 h" }] },
  { key: "cameraWidth", label: "Camera width", type: "int", min: 0, max: 400, step: 10, suffix: " px", zero: "auto" },
  { key: "hoverDelay", label: "Hover delay", type: "int", min: 0, max: 1000, step: 50, suffix: " ms" },
  { key: "reduceMotion", label: "Reduce motion", type: "bool" },
  { key: "snapdex", label: "Screenshots tab", type: "bool", setup: true },
  { key: "optAgents", label: "Agents tab", type: "bool", setup: true },
  { key: "optMessages", label: "Messages tab", type: "bool", setup: true },
  { key: "optWordink", label: "Dictation (WordInk)", type: "bool", setup: true },
  { key: "optWisp", label: "Wisp status", type: "bool", setup: true },
  { key: "optFan", label: "Fan mode control", type: "bool", setup: true },
  { key: "aiUsage", label: "AI usage tab", type: "bool" },
  { key: "dayflow", label: "Dayflow", type: "bool" },
  { key: "setupDone", label: "Setup done", type: "bool", hidden: true }
]

// Prefs grid: hide setup-only / hidden keys (those live in the Setup strip).
function prefFields() {
  return FIELDS.filter(function (f) { return !f.hidden && !f.setup })
}

function field(key) {
  for (var i = 0; i < FIELDS.length; i++) if (FIELDS[i].key === key) return FIELDS[i]
  return null
}

function clampInt(f, v, fallback) {
  var n = Number(v)
  if (typeof v === "boolean" || v === null || v === "" || !isFinite(n)) return fallback
  return Math.max(f.min, Math.min(f.max, Math.round(n)))
}

function coerce(f, v, fallback) {
  if (f.type === "bool") return typeof v === "boolean" ? v : fallback
  if (f.type === "int") return clampInt(f, v, fallback)
  for (var i = 0; i < f.options.length; i++) if (f.options[i].value === v) return v
  return fallback
}

// Resolve a plugin entry (or null) plus optional unsaved overrides into a full
// settings object; anything missing or invalid falls back to its default.
function resolve(entry, overrides) {
  var out = {}
  for (var i = 0; i < FIELDS.length; i++) {
    var f = FIELDS[i]
    var v = DEFAULTS[f.key]
    if (entry && typeof entry === "object" && entry[f.key] !== undefined) v = coerce(f, entry[f.key], v)
    if (overrides && typeof overrides === "object" && overrides[f.key] !== undefined) v = coerce(f, overrides[f.key], v)
    out[f.key] = v
  }
  out.unitName = out.unit === "C" ? "celsius" : "fahrenheit"
  out.timeFormat = out.clockHours === 24 ? "HH:mm" : "h:mm AP"
  return out
}

// Next value for `key` one step in `dir` (+1 / -1). Ints clamp, choices wrap.
function next(settings, key, dir) {
  var f = field(key)
  if (!f) return null
  var cur = settings ? settings[key] : DEFAULTS[key]
  var d = Number(dir) < 0 ? -1 : 1
  if (f.type === "bool") return !cur
  if (f.type === "int") return clampInt(f, Number(cur) + d * f.step, DEFAULTS[key])
  var idx = 0
  for (var i = 0; i < f.options.length; i++) if (f.options[i].value === cur) idx = i
  return f.options[(idx + d + f.options.length) % f.options.length].value
}

// Display text for a value.
function format(f, value) {
  if (!f) return ""
  if (f.type === "bool") return value ? "on" : "off"
  if (f.type === "choice") {
    for (var i = 0; i < f.options.length; i++) if (f.options[i].value === value) return f.options[i].label
    return String(value)
  }
  if (value === 0 && f.zero) return f.zero
  return String(value) + (f.suffix || "")
}

function pluginEntry(config, pluginId) {
  var plugins = config && Array.isArray(config.plugins) ? config.plugins : []
  for (var i = 0; i < plugins.length; i++)
    if (plugins[i] && String(plugins[i].id || "") === pluginId) return plugins[i]
  return null
}

// A function for shell.mutateShellConfig: merges `patch` into the plugin's
// entry, creating it (and the plugins array) when absent.
function settingsMutator(pluginId, patch) {
  return function(config) {
    if (!Array.isArray(config.plugins)) config.plugins = []
    var entry = pluginEntry(config, pluginId)
    if (!entry) { entry = { id: pluginId }; config.plugins.push(entry) }
    for (var k in patch) entry[k] = patch[k]
  }
}

// Geometry of the first-run / new-module setup card, in logical px. The card
// is: padding + a two-line intro + a scrolling list of one row per module +
// (first run only) a footer that holds Done. The footer is never part of the
// scrolling list, so Done stays visible however many modules are offered.
//   offerCount  modules to list (0 shows a one-row "none found" note)
//   firstRun    setup not finished yet (Done is shown)
//   avail       vertical room the card may use
//   minBelow    room kept for the settings below when setup is already done
var SETUP = { pad: 20, intro: 34, row: 28, footer: 40, gap: 6, minBelow: 120 }

function setupLayout(offerCount, firstRun, avail, minBelow) {
  var n = Math.max(1, Math.floor(Number(offerCount) || 0))
  var room = Math.max(0, Number(avail) || 0)
  var footer = firstRun ? SETUP.footer : 0
  var chrome = SETUP.pad + SETUP.intro + footer + SETUP.gap
  var contentH = n * SETUP.row
  var cap = firstRun ? room : Math.max(chrome + SETUP.row, room - (minBelow === undefined ? SETUP.minBelow : minBelow))
  var height = Math.min(chrome + contentH, cap)
  var listH = Math.max(0, height - chrome)
  return { height: height, listH: listH, contentH: contentH, scroll: contentH > listH, footerH: footer }
}

// Arguments for bin/notch-data derived from the settings.
function dataArgs(settings) {
  return ["--max-age", "900", "--unit", settings && settings.unitName ? settings.unitName : "fahrenheit"]
}

if (typeof module !== "undefined") {
  module.exports = { DEFAULTS: DEFAULTS, FIELDS: FIELDS, prefFields: prefFields, field: field, resolve: resolve, next: next, format: format,
    setupLayout: setupLayout, SETUP: SETUP, pluginEntry: pluginEntry, settingsMutator: settingsMutator, dataArgs: dataArgs }
}
