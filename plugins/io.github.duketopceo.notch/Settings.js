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
  timer: true,        // Timer tab, ear countdown, finish notification
  chargingAlert: true, // ear shows percent and time to full when AC is plugged in
  hiddenTabs: [],     // built-in tab ids the owner hid (home and settings never hide)
  tabUsage: {},       // tab id -> open count, picks which tabs keep a label
  setupDone: false    // first-run optional-module setup completed
}

// ONE registry. Every setting the owner can see is a row here, in exactly one
// of SECTIONS. `feature: true` rows are the on/off switches for a tab or an
// ear activity: they are generated into "Tabs and features" (with a switch for
// each built-in tab, see sections()), so a feature has one switch, never two.
// `hint` is the one-line plain-language explanation drawn under the label.
// `choices` on an int turns the stepper into a segmented control (a saved
// value outside the list is still honoured and shown).
var SECTIONS = [
  { id: "look", title: "Look" },
  { id: "features", title: "Tabs and features" },
  { id: "data", title: "Data sources" },
  { id: "advanced", title: "Advanced" }
]

var FIELDS = [
  { key: "theme", section: "look", label: "Theme", type: "choice", hint: "Swift follows your Omarchy colors; Pxl is a retro 16-bit look.",
    options: [{ value: "swift", label: "Swift" }, { value: "pxl", label: "Pxl (16-bit)" }] },
  { key: "unit", section: "look", label: "Temperature", type: "choice",
    options: [{ value: "F", label: "\u00B0F" }, { value: "C", label: "\u00B0C" }] },
  { key: "clockHours", section: "look", label: "Clock", type: "choice",
    options: [{ value: 12, label: "12 h" }, { value: 24, label: "24 h" }] },
  { key: "reduceMotion", section: "look", label: "Reduce motion", type: "bool", hint: "Quick fades instead of springs and slides." },

  { key: "snapdex", section: "features", feature: true, label: "Screenshots tab", type: "bool", setup: true,
    hint: "Snapdex captions your screenshots; this adds a tab for them." },
  { key: "optAgents", section: "features", feature: true, label: "Agents tab", type: "bool", setup: true,
    hint: "herdr runs your coding agents; this shows their status." },
  { key: "optMessages", section: "features", feature: true, label: "Messages tab", type: "bool", setup: true,
    hint: "Blip relays your iMessages here, read-only; shows unread texts." },
  { key: "aiUsage", section: "features", feature: true, label: "AI usage tab", type: "bool", hint: "Token spend and limits per AI provider." },
  { key: "dayflow", section: "features", feature: true, label: "Dayflow", type: "bool", hint: "Dayflow is a work journal; adds a tab and an ear item." },
  { key: "timer", section: "features", feature: true, label: "Timer tab", type: "bool", hint: "Countdown and pomodoro; time left shows in the ear." },
  { key: "chargingAlert", section: "features", feature: true, label: "Charging alert", type: "bool", hint: "Percent and time to full in the ear when you plug in." },
  { key: "optWordink", section: "features", feature: true, label: "Dictation (WordInk)", type: "bool", setup: true, hint: "Shows recording state from the WordInk dictation app." },
  { key: "optWisp", section: "features", feature: true, label: "Wisp status", type: "bool", setup: true, hint: "A status dot for the Wisp assistant on Home." },
  { key: "optFan", section: "features", feature: true, label: "Fan mode control", type: "bool", setup: true, hint: "Lets System switch fan profiles (needs the fan plugin)." },

  { key: "showWeather", section: "data", label: "Show weather", type: "bool", hint: "Current weather in the ear (Open-Meteo, no key)." },
  { key: "showStocks", section: "data", label: "Show stocks", type: "bool", hint: "Your watchlist quotes in the ear (Yahoo, no key)." },

  { key: "slideSeconds", section: "advanced", label: "Slide seconds", type: "int", min: 2, max: 30, step: 1, suffix: " s", choices: [4, 7, 10, 15],
    hint: "How long each ear item shows before the next." },
  { key: "clockSeconds", section: "advanced", label: "Quote rotation", type: "int", min: 5, max: 120, step: 5, suffix: " s", choices: [12, 24, 40, 60],
    hint: "Time before the ear shows the next stock." },
  { key: "hoverDelay", section: "advanced", label: "Hover delay", type: "int", min: 0, max: 1000, step: 50, suffix: " ms", choices: [0, 150, 300, 500],
    hint: "How long the pointer rests before it opens." },
  { key: "cameraWidth", section: "advanced", label: "Camera width", type: "int", min: 0, max: 400, step: 10, suffix: " px", zero: "auto",
    hint: "Camera cutout width; Auto detects it." },

  { key: "hiddenTabs", label: "Hidden tabs", type: "list", hidden: true },
  { key: "tabUsage", label: "Tab usage", type: "map", hidden: true },
  { key: "setupDone", label: "Setup done", type: "bool", hidden: true }
]

// Rows outside "Tabs and features" (those are generated by sections()).
function prefFields() {
  return FIELDS.filter(function (f) { return !f.hidden && !f.feature })
}

function featureFields() {
  return FIELDS.filter(function (f) { return !f.hidden && f.feature })
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
  if (f.type === "list") {
    if (!Array.isArray(v)) return fallback
    var seen = {}
    return v.filter(function (x) {
      if (typeof x !== "string" || x === "" || seen[x]) return false
      seen[x] = true
      return true
    }).slice(0, 64)
  }
  if (f.type === "map") {
    if (v === null || typeof v !== "object" || Array.isArray(v)) return fallback
    var m = {}
    for (var k in v) { var n = Number(v[k]); if (isFinite(n) && n > 0) m[k] = Math.min(1e6, Math.round(n)) }
    return m
  }
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
    out[f.key] = Array.isArray(v) ? v.slice() : (v !== null && typeof v === "object" ? JSON.parse(JSON.stringify(v)) : v)
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
  if (f.type === "list" || f.type === "map") return null
  if (f.type === "int" && f.choices) {
    var list = choicesFor(f, cur)
    var at = list.indexOf(Number(cur))
    return list[Math.max(0, Math.min(list.length - 1, at + d))]
  }
  if (f.type === "int") return clampInt(f, Number(cur) + d * f.step, DEFAULTS[key])
  var idx = 0
  for (var i = 0; i < f.options.length; i++) if (f.options[i].value === cur) idx = i
  return f.options[(idx + d + f.options.length) % f.options.length].value
}

// Segment values for an int field with `choices`: the list, plus the saved
// value when it is not in it (sorted in), so the control always shows it.
function choicesFor(f, value) {
  if (!f || !Array.isArray(f.choices)) return []
  var list = f.choices.slice()
  var n = Number(value)
  if (isFinite(n) && list.indexOf(n) < 0) { list.push(n); list.sort(function (a, b) { return a - b }) }
  return list
}

// The sections the Settings tab draws, from the one registry. `tabs` is
// Tabs.TABS: each built-in tab (no `optional` switch of its own, not pinned)
// gets a "<Title> tab" switch under "Tabs and features". Row:
//   { key, label, hint, type, kind: "setting" | "tab", tabId? }
// `pinned` lists tab ids that can never be hidden (Home, Settings).
function sections(tabs, pinned) {
  var pin = Array.isArray(pinned) ? pinned : []
  var out = SECTIONS.map(function (sec) {
    var rows = []
    FIELDS.forEach(function (f) {
      if (f.hidden || f.section !== sec.id) return
      rows.push({ key: f.key, label: f.label, hint: f.hint || "", type: f.type, kind: "setting" })
    })
    return { id: sec.id, title: sec.title, rows: rows }
  })
  var feat = out[1].rows
  ;(Array.isArray(tabs) ? tabs : []).forEach(function (t) {
    if (!t || t.optional || pin.indexOf(t.id) >= 0) return
    feat.push({ key: "tab:" + t.id, label: t.title + " tab", hint: "", type: "bool", kind: "tab", tabId: t.id })
  })
  return out
}

// Current value of a row: a setting's own value, or (tab rows) shown-ness.
function rowValue(settings, row) {
  if (!row) return null
  if (row.kind === "tab") return !(settings && Array.isArray(settings.hiddenTabs) && settings.hiddenTabs.indexOf(row.tabId) >= 0)
  return settings ? settings[row.key] : DEFAULTS[row.key]
}

// Patch to persist when `row` is set to `value`.
function rowPatch(settings, row, value) {
  var patch = {}
  if (row.kind === "tab") {
    var hidden = settings && Array.isArray(settings.hiddenTabs) ? settings.hiddenTabs.slice() : []
    var at = hidden.indexOf(row.tabId)
    if (value === false && at < 0) hidden.push(row.tabId)
    if (value === true && at >= 0) hidden.splice(at, 1)
    patch.hiddenTabs = hidden
  } else {
    patch[row.key] = value
  }
  return patch
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
  module.exports = { DEFAULTS: DEFAULTS, FIELDS: FIELDS, SECTIONS: SECTIONS, prefFields: prefFields, featureFields: featureFields, choicesFor: choicesFor, sections: sections, rowValue: rowValue, rowPatch: rowPatch, field: field, resolve: resolve, next: next, format: format,
    setupLayout: setupLayout, SETUP: SETUP, pluginEntry: pluginEntry, settingsMutator: settingsMutator, dataArgs: dataArgs }
}
