// Pure settings logic for the Island. ES5, no Qt types.
//
// Settings live in the plugin's own entry of shell.json's `plugins` array:
//   { "id": "io.github.duketopceo.island", "openDelay": 140, ... }
// The shell's updateEntryInline(id, settings) REPLACES that whole entry and
// returns false when there is no entry or nothing changed, so a write must
// carry the full object: merge() builds it, changed() says whether to write.

// The booleans switch activity sources, indicators and alerts on or off; a
// stored value that is not a boolean resolves to the default.
var DEFAULTS = {
  openDelay: 140, closeDelay: 450, cameraWidth: 0,
  dictation: true, media: true, webArt: true, charging: true, hud: true,
  screenRecording: true, privacy: true, dnd: true, bluetooth: true, alerts: true,
  calendar: true, weather: true, agents: true, messages: true, dayflow: true, shots: true,
  sansFont: true
}
var RANGES = {
  openDelay: [0, 600],
  closeDelay: [150, 1500],
  cameraWidth: [0, 4000]
}

function clamp(key, value) {
  var r = RANGES[key]
  var n = Number(value)
  if (value === null || value === "" || typeof value === "boolean" || !isFinite(n)) return DEFAULTS[key]
  return Math.round(Math.max(r[0], Math.min(r[1], n)))
}

function _parse(shellJson) {
  if (typeof shellJson === "string") {
    try { shellJson = JSON.parse(shellJson) } catch (e) { return null }
  }
  return shellJson && typeof shellJson === "object" && !Array.isArray(shellJson) ? shellJson : null
}

function _entry(shellJson, id) {
  var root = _parse(shellJson)
  var list = root && Array.isArray(root.plugins) ? root.plugins : []
  for (var i = 0; i < list.length; i++) {
    var e = list[i]
    if (e && typeof e === "object" && e.id === id) return e
  }
  return null
}

function _withDefaults(obj) {
  var out = {}
  for (var k in DEFAULTS) {
    var v = obj && obj[k] !== undefined ? obj[k] : DEFAULTS[k]
    if (typeof DEFAULTS[k] === "boolean") out[k] = typeof v === "boolean" ? v : DEFAULTS[k]
    else out[k] = clamp(k, v)
  }
  return out
}

// -> { entryExists, settings } ; never throws.
function resolve(shellJson, id) {
  var e = _entry(shellJson, id)
  return { entryExists: e !== null, settings: _withDefaults(e) }
}

// Full object for updateEntryInline: current entry (unknown keys kept) with
// defaults filled, the edit applied, known keys clamped, and the id set.
function merge(current, edit, id) {
  var out = { id: id }
  var src = current && typeof current === "object" ? current : {}
  for (var k in src) if (k !== "id") out[k] = src[k]
  var e = edit && typeof edit === "object" ? edit : {}
  for (var k2 in e) if (k2 !== "id") out[k2] = e[k2]
  var known = _withDefaults(out)
  for (var k3 in known) out[k3] = known[k3]
  return out
}

function changed(current, merged) {
  return JSON.stringify(current === undefined ? null : current) !== JSON.stringify(merged)
}

if (typeof module !== "undefined") {
  module.exports = {
    DEFAULTS: DEFAULTS, RANGES: RANGES,
    clamp: clamp, resolve: resolve, merge: merge, changed: changed
  }
}
