// Pure logic for the notch's settings: defaults, validation, the field list
// the Settings tab draws, and the shell.json mutator. No Qt types.
//
// Settings live in the plugin's own entry of shell.json's `plugins` array:
//   { "id": "io.github.duketopceo.notch", "clockSeconds": 24, ... }

var DEFAULTS = {
  clockSeconds: 24,
  slideSeconds: 7,
  showWeather: true,
  showStocks: true,
  unit: "F",          // "F" | "C"
  clockHours: 12,     // 12 | 24
  cameraWidth: 0,     // 0 = auto, else logical px
  hoverDelay: 150,    // ms before hover expands the panel
  reduceMotion: false, // swap springs and slides for quick fades
  snapdex: false      // optional personal integration: Screenshots tab + caption flash
}

var FIELDS = [
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
  { key: "snapdex", label: "Screenshots (snapdex)", type: "bool" }
]

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

// Arguments for bin/notch-data derived from the settings.
function dataArgs(settings) {
  return ["--max-age", "900", "--unit", settings && settings.unitName ? settings.unitName : "fahrenheit"]
}

if (typeof module !== "undefined") {
  module.exports = { DEFAULTS: DEFAULTS, FIELDS: FIELDS, field: field, resolve: resolve, next: next, format: format,
    pluginEntry: pluginEntry, settingsMutator: settingsMutator, dataArgs: dataArgs }
}
