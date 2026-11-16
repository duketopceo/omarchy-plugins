// Pure privacy-indicator logic for the Island. ES5, no Qt types.
//
// micInUse() decides from PipeWire node records whether an application is
// capturing the microphone. Passive effect/virtual nodes and monitor streams
// do not count. parseCamera() reads one JSON line from bin/island-camera.

function _true(v) {
  return v === true || String(v) === "true"
}

function _counts(r) {
  if (!r || r.isStream !== true || r.isSink === true) return false
  var p = r.props || {}
  if (String(p["media.class"]).indexOf("Stream/Input/Audio") !== 0) return false
  if (_true(p["node.passive"]) || _true(p["stream.monitor"])) return false
  if (String(p["media.category"]) === "Monitor") return false
  if (_true(p["stream.capture.sink"])) return false
  return true
}

function _counted(records) {
  var out = []
  if (!Array.isArray(records)) return out
  for (var i = 0; i < records.length; i++) if (_counts(records[i])) out.push(records[i])
  return out
}

function micInUse(records) {
  return _counted(records).length > 0
}

// Tint a dot from the theme colour: fixed hue per kind, readable s and l.
function dotColor(kind, base) {
  var b = base || {}
  var s = typeof b.s === "number" ? b.s : 0
  var l = typeof b.l === "number" ? b.l : 0.5
  return {
    h: (kind === "camera" ? 130 : 30) / 360,
    s: Math.max(s, 0.55),
    l: Math.min(0.65, Math.max(0.45, l))
  }
}

function parseCamera(line) {
  var none = { inUse: false, apps: [] }
  var o
  try { o = JSON.parse(line) } catch (e) { return none }
  if (!o || typeof o !== "object" || Array.isArray(o)) return none
  var apps = []
  if (Array.isArray(o.apps)) {
    for (var i = 0; i < o.apps.length; i++) apps.push(String(o.apps[i]))
  }
  return { inUse: o.inUse === true, apps: apps }
}

if (typeof module !== "undefined") {
  module.exports = { micInUse: micInUse, dotColor: dotColor, parseCamera: parseCamera }
}
