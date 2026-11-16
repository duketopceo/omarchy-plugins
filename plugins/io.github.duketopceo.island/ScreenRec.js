// Pure screen-recording logic for the Island. ES5, no Qt types.
//
// The adapter reads the recorder's pid file, then /proc/<pid>/stat and
// /proc/uptime, and feeds the raw text here. Callers pass `now` (ms epoch).

var PRIORITY = 88

function _cp(code) {
  var c = code - 0x10000
  return String.fromCharCode(0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF))
}
var GLYPH = _cp(0xF044A)   // nf-md-record_rec

// Positive integer pid, or 0 for anything else.
function parsePid(text) {
  var s = String(text === undefined || text === null ? "" : text).trim()
  if (!/^\d+$/.test(s)) return 0
  var n = parseInt(s, 10)
  return n > 0 ? n : 0
}

// Whole seconds the process has run, or -1 when the text cannot be parsed.
function elapsed(statText, uptimeText, hz) {
  var stat = String(statText === undefined || statText === null ? "" : statText)
  var close = stat.lastIndexOf(")")
  if (close < 0) return -1
  // Remainder starts at field 3 (state); starttime is field 22 = index 19.
  var rest = stat.slice(close + 1).trim().split(/\s+/)
  var start = rest.length > 19 && /^\d+$/.test(rest[19]) ? parseInt(rest[19], 10) : NaN
  var up = parseFloat(String(uptimeText === undefined || uptimeText === null ? "" : uptimeText).trim().split(/\s+/)[0])
  if (isNaN(start) || isNaN(up)) return -1
  var rate = hz > 0 ? hz : 100
  return Math.max(0, Math.floor(up - start / rate))
}

function initial() {
  return { recording: false, pid: 0, startedAt: 0 }
}

function _pad(n) { return n < 10 ? "0" + n : String(n) }

function _clock(totalSeconds) {
  var s = Math.max(0, Math.floor(totalSeconds))
  var h = Math.floor(s / 3600)
  var m = Math.floor((s % 3600) / 60)
  var sec = s % 60
  return h > 0 ? h + ":" + _pad(m) + ":" + _pad(sec) : m + ":" + _pad(sec)
}

function activity(model, now) {
  if (!(model.recording && model.startedAt > 0))
    return { id: "screenrec", active: false, priority: PRIORITY, text: "", glyph: "", card: "" }
  var text = _clock((now - model.startedAt) / 1000)
  return { id: "screenrec", active: true, priority: PRIORITY, text: text,
           glyph: GLYPH, card: "Recording " + text, state: "recording" }
}

if (typeof module !== "undefined") module.exports = {
  PRIORITY: PRIORITY, parsePid: parsePid, elapsed: elapsed, initial: initial,
  activity: activity
}
