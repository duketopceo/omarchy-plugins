// Pure logic for the notch's WordInk dictation view. No Qt types, so tests
// run it with node.
//
// Inputs are NDJSON lines from `wordink logs -f` (live.ndjson) and the JSON
// from `wordink status --json`. Real shapes:
//   {"kind":"state","state":"dictating|listening|transcribing|stopping","device":"..."}
//   {"kind":"dictation","phase":"started|transcribing|pasted|cancelled|discarded"}
//   {"kind":"transcript","phase":"completed"}
//   status: { capture: {state: "idle|recording|transcribing"},
//             listener: {running, status}, model: {installed, error},
//             permissions: {ready} }
// Note the "listening" state means the hotkey listener is armed and idle, not
// that the mic is open; "dictating" is the live recording.

var DONE_MS = 2000
var ERROR_MS = 6000   // an error takes over the notch this long, then yields

var STATES = ["idle", "recording", "transcribing", "error", "not-running"]

// Map one log line to a base state, or null when the line says nothing about
// dictation state (unknown kinds, junk, oversized lines).
function eventToState(line) {
  var ev
  if (typeof line === "string") {
    if (line.length > 4000) return null
    try { ev = JSON.parse(line) } catch (error) { return null }
  } else {
    ev = line
  }
  if (!ev || typeof ev !== "object") return null
  var kind = String(ev.kind || "")
  if (kind === "state") {
    var s = String(ev.state || "")
    if (s === "dictating") return "recording"
    if (s === "transcribing" || s === "stopping") return "transcribing"
    if (s === "listening" || s === "sleeping" || s === "idle") return "idle"
    return null
  }
  if (kind === "dictation") {
    var p = String(ev.phase || "")
    if (p === "started") return "recording"
    if (p === "transcribing") return "transcribing"
    if (p === "pasted" || p === "cancelled" || p === "discarded") return "idle"
    if (p === "failed" || p === "error") return "error"
    return null
  }
  if (kind === "transcript") {
    var tp = String(ev.phase || "")
    if (tp === "failed" || tp === "error") return "error"
    return null
  }
  if (kind === "api_server_stopped") return null  // caller re-polls status
  if (/error|failed/.test(kind) || ev.level === "error") return "error"
  return null
}

// Map a `wordink status --json` object (or its text) to a base state.
function statusToState(status) {
  var d = status
  if (typeof d === "string") {
    try { d = JSON.parse(d) } catch (error) { return null }
  }
  if (!d || typeof d !== "object") return null
  var m = d.model || {}
  var cap = d.capture && typeof d.capture.state === "string" ? d.capture.state : "idle"
  if (m.error) return "error"
  if (d.permissions && d.permissions.microphone && d.permissions.microphone !== "ready") return "error"
  if (cap === "recording") return "recording"
  if (cap === "transcribing") return "transcribing"
  return "idle"
}

// Fresh model: base state plus the timestamps the flashes hang off.
function initial() { return { base: "not-running", doneUntil: 0, errorSince: 0 } }

// Fold a new base state into the model at time `now` (ms). Finishing a
// transcription (transcribing -> idle) starts the 2 s "done" flash; a
// recording that is cancelled or discarded does not.
function step(model, base, now) {
  var prev = model || initial()
  if (base === null || base === undefined || STATES.indexOf(base) < 0) return prev
  var next = { base: base, doneUntil: prev.doneUntil, errorSince: prev.errorSince }
  if (prev.base === "transcribing" && base === "idle") next.doneUntil = now + DONE_MS
  else if (base !== "idle") next.doneUntil = 0
  if (base === "error" && prev.base !== "error") next.errorSince = now
  return next
}

// The state to show at `now`: "done" while the flash lasts, else the base.
function current(model, now) {
  var m = model || initial()
  if (m.base === "idle" && now < m.doneUntil) return "done"
  return m.base
}

// Does this state take over the notch's side text? A mic error only does so
// briefly, so a standing permission problem does not hold the notch forever.
function isActive(model, now) {
  var s = current(model, now)
  if (s === "recording" || s === "transcribing" || s === "done") return true
  if (s === "error") return now - (model.errorSince || 0) < ERROR_MS
  return false
}

// Side text: a mic glyph plus a short label; empty when not active.
function displayText(state) {
  var mic = "\u{F036C}"
  if (state === "recording") return mic + " Listening"
  if (state === "transcribing") return mic + " Transcribing…"
  if (state === "done") return "\u{F012C} Done"
  if (state === "error") return mic + " Mic error"
  return ""
}

// Which view the notch shows: dictation beats media beats the idle cycle.
function chooseView(dictationActive, mediaPlaying, idleView) {
  if (dictationActive) return "dictation"
  if (mediaPlaying) return "media"
  return idleView
}

if (typeof module !== "undefined") {
  module.exports = {
    DONE_MS: DONE_MS,
    ERROR_MS: ERROR_MS,
    eventToState: eventToState,
    statusToState: statusToState,
    initial: initial,
    step: step,
    current: current,
    isActive: isActive,
    displayText: displayText,
    chooseView: chooseView
  }
}
