// Pure logic for the Island's dictation activity (WordInk recording state).
// ES5, no Qt types: DictationSource.qml feeds it WordInk's status JSON and
// NDJSON log events and renders what activity() returns; node tests load it
// with require().
//
// State is one of "idle" | "recording" | "transcribing" | "off". "off" is set
// by the adapter when the CLI exits 127 (not installed) or 3 (not running).
//
// model: { state, recordingSince }   recordingSince is the ms epoch when the
// current recording began, or 0.

var MAX_LINE = 4000
var PRIORITY = 90

// Nerd Font Material Design glyphs (plane 15).
var GLYPHS = {
  mic: cp(0xF036C),         // nf-md-microphone
  hourglass: cp(0xF051F)    // nf-md-timer_sand
}

function cp(n) {
  n -= 0x10000
  return String.fromCharCode(0xD800 + (n >> 10), 0xDC00 + (n & 0x3FF))
}

// WordInk voice state names -> activity state. "listening" is WordInk's ready
// state (it returns there after every dictation), so only "dictating" records.
function mapVoice(s) {
  if (s === "dictating") return "recording"
  if (s === "transcribing" || s === "stopping") return "transcribing"
  return "idle"
}

// `wordink status --json` text -> state, "" when unparseable.
function fromStatus(text) {
  var d
  try { d = JSON.parse(text) } catch (e) { return "" }
  if (!d || typeof d !== "object") return ""
  var cap = d.capture && typeof d.capture.state === "string" ? d.capture.state : "idle"
  return cap === "recording" ? "recording" : cap === "transcribing" ? "transcribing" : "idle"
}

// One `wordink logs -f` NDJSON line -> state, "" for anything that is not a state event.
function fromEvent(line) {
  if (typeof line !== "string" || line.length > MAX_LINE) return ""
  var ev
  try { ev = JSON.parse(line) } catch (e) { return "" }
  if (!ev || ev.kind !== "state") return ""
  return mapVoice(ev.state)
}

function initial() {
  return { state: "idle", recordingSince: 0 }
}

// Returns the same object when nothing changes.
function step(model, state, now) {
  var since = state === "recording" ? (model.state === "recording" ? model.recordingSince : now) : 0
  if (model.state === state && model.recordingSince === since) return model
  return { state: state, recordingSince: since }
}

function elapsed(ms) {
  var s = Math.max(0, Math.floor(ms / 1000))
  var sec = s % 60
  return Math.floor(s / 60) + ":" + (sec < 10 ? "0" : "") + sec
}

function activity(model, now) {
  if (model.state === "recording") {
    var t = elapsed(now - model.recordingSince)
    return { id: "dictation", active: true, priority: PRIORITY, text: t, glyph: GLYPHS.mic,
             card: "Recording " + t, state: "recording" }
  }
  if (model.state === "transcribing") {
    return { id: "dictation", active: true, priority: PRIORITY, text: "…", glyph: GLYPHS.hourglass,
             card: "Transcribing", state: "transcribing" }
  }
  return { id: "dictation", active: false, priority: PRIORITY, text: "", glyph: "", card: "", state: model.state }
}

if (typeof module !== "undefined") module.exports = {
  fromStatus: fromStatus, fromEvent: fromEvent, initial: initial, step: step, activity: activity
}
