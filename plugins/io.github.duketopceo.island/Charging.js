// Pure charging logic for the Island. ES5, no Qt types.
//
// The adapter reads the battery's `status`, `capacity` and `time_to_full_now`
// sysfs files every few seconds and feeds the raw text to parse(). The first
// valid reading is only a baseline (a charger that is already in shows
// nothing). A later reading that is "Charging" when the previous one was not
// starts a brief notice that lasts NOTICE_MS. Callers pass `now` (ms epoch).

var NOTICE_MS = 6000
var PRIORITY = 30

// nf-md icon, plane 15 codepoint, built as a surrogate pair.
function _cp(code) {
  var c = code - 0x10000
  return String.fromCharCode(0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF))
}
var GLYPHS = {
  charging: _cp(0xF0084)   // nf-md-battery_charging
}

function _int(text) {
  var s = String(text === undefined || text === null ? "" : text).replace(/^\s+|\s+$/g, "")
  if (!/^-?\d+$/.test(s)) return null
  return parseInt(s, 10)
}

// Raw sysfs strings -> { status, capacity, timeToFull } or null when the
// capacity is not an integer 0-100.
function parse(raw) {
  var r = raw || {}
  var capacity = _int(r.capacity)
  if (capacity === null || capacity < 0 || capacity > 100) return null
  var ttf = _int(r.timeToFull)
  if (ttf === null || ttf < 0) ttf = 0
  var status = String(r.status === undefined || r.status === null ? "" : r.status)
  return { status: status.replace(/^\s+|\s+$/g, ""), capacity: capacity, timeToFull: ttf }
}

function initial() {
  return { seen: false, status: "", capacity: 0, timeToFull: 0, until: 0 }
}

function step(model, reading, now) {
  if (!reading) return model
  var until = model.until
  if (model.seen && reading.status === "Charging" && model.status !== "Charging")
    until = now + NOTICE_MS
  return {
    seen: true, status: reading.status, capacity: reading.capacity,
    timeToFull: reading.timeToFull, until: until
  }
}

function _duration(seconds) {
  var minutes = Math.round(seconds / 60)
  var h = Math.floor(minutes / 60)
  var m = minutes % 60
  if (h > 0) return h + "h " + m + "m"
  return m + "m"
}

function activity(model, now) {
  if (!model.seen || !(now < model.until))
    return { id: "charging", active: false, priority: PRIORITY, text: "", glyph: "", card: "" }
  var text = model.capacity + "%"
  var card = text
  if (model.timeToFull > 0) card = text + " · " + _duration(model.timeToFull) + " to full"
  return {
    id: "charging", active: true, priority: PRIORITY, text: text,
    glyph: GLYPHS.charging, card: card, until: model.until
  }
}

if (typeof module !== "undefined") {
  module.exports = {
    NOTICE_MS: NOTICE_MS, GLYPHS: GLYPHS,
    parse: parse, initial: initial, step: step, activity: activity
  }
}
