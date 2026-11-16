// Pure countdown timer logic for the Island. ES5, no Qt types.
//
// The model keeps an END TIME while running and the remaining time while
// paused, so a stalled UI thread never makes the countdown drift: everything
// shown is derived from `now`. Every function takes `now` (ms epoch) and
// returns a new model; an invalid transition returns the input object itself.
//
//   idle -> running (start) -> paused (pause) -> running (resume)
//   running/paused + add -> same state, more time
//   running -> done (tick, now >= endsAt) -> idle (tick, flash expired)
//   running/paused -> idle (cancel)

var MAX_MS = 24 * 3600 * 1000
var DONE_FLASH_MS = 8000
var PRIORITY = 70

// Nerd Font Material Design icons (plane 15).
var GLYPHS = {
  timer: "󱎫",      // nf-md-timer         U+F13AB
  paused: "󱫞",     // nf-md-timer_pause   U+F1ADE
  done: "󰄬"        // nf-md-check         U+F012C
}

function initial() {
  return { state: "idle", endsAt: 0, remainingMs: 0, totalMs: 0, doneUntil: 0 }
}

// "90s", "5m", "1h30m", "2m30s", "10" (minutes) -> ms, or 0 when rejected.
function parse(spec) {
  if (typeof spec !== "string") return 0
  var s = spec.trim().toLowerCase()
  var ms = 0
  var m = /^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/.exec(s)
  if (s !== "" && m) {
    ms = (Number(m[1] || 0) * 3600 + Number(m[2] || 0) * 60 + Number(m[3] || 0)) * 1000
  } else if (/^\d+$/.test(s)) {
    ms = Number(s) * 60000
  }
  if (!(ms > 0) || ms > MAX_MS) return 0
  return ms
}

function _copy(model, changes) {
  var out = {
    state: model.state, endsAt: model.endsAt, remainingMs: model.remainingMs,
    totalMs: model.totalMs, doneUntil: model.doneUntil
  }
  for (var k in changes) out[k] = changes[k]
  return out
}

function start(model, ms, now) {
  if (model.state !== "idle" || !(ms > 0)) return model
  return { state: "running", endsAt: now + ms, remainingMs: 0, totalMs: ms, doneUntil: 0 }
}

function pause(model, now) {
  if (model.state !== "running") return model
  return _copy(model, { state: "paused", remainingMs: Math.max(0, model.endsAt - now), endsAt: 0 })
}

function resume(model, now) {
  if (model.state !== "paused") return model
  return _copy(model, { state: "running", endsAt: now + model.remainingMs, remainingMs: 0 })
}

function add(model, ms, now) {
  if (model.state === "running") {
    return _copy(model, { endsAt: model.endsAt + ms, totalMs: model.totalMs + ms })
  }
  if (model.state === "paused") {
    return _copy(model, { remainingMs: model.remainingMs + ms, totalMs: model.totalMs + ms })
  }
  return model
}

function cancel(model) {
  if (model.state !== "running" && model.state !== "paused") return model
  return initial()
}

function tick(model, now) {
  if (model.state === "running" && now >= model.endsAt) {
    return _copy(model, { state: "done", endsAt: 0, remainingMs: 0, doneUntil: now + DONE_FLASH_MS })
  }
  if (model.state === "done" && now >= model.doneUntil) return initial()
  return model
}

function remaining(model, now) {
  if (model.state === "running") return Math.max(0, model.endsAt - now)
  if (model.state === "paused") return Math.max(0, model.remainingMs)
  return 0
}

function _pad(n) { return n < 10 ? "0" + n : String(n) }

// m:ss under an hour, h:mm:ss above; rounds up to the whole second.
function fmt(ms) {
  var total = Math.ceil(Math.max(0, ms) / 1000)
  var h = Math.floor(total / 3600)
  var m = Math.floor((total % 3600) / 60)
  var s = total % 60
  if (h > 0) return h + ":" + _pad(m) + ":" + _pad(s)
  return m + ":" + _pad(s)
}

function activity(model, now) {
  var base = { id: "timer", priority: PRIORITY, paused: false, state: model.state }
  if (model.state === "running" || model.state === "paused") {
    var t = fmt(remaining(model, now))
    var paused = model.state === "paused"
    base.active = true
    base.text = t
    base.glyph = paused ? GLYPHS.paused : GLYPHS.timer
    base.card = (paused ? "Paused " : "Timer ") + t
    base.paused = paused
    return base
  }
  if (model.state === "done" && now < model.doneUntil) {
    base.active = true
    base.text = "Done"
    base.glyph = GLYPHS.done
    base.card = "Timer done"
    base.until = model.doneUntil
    return base
  }
  base.active = false
  base.text = ""
  base.glyph = ""
  base.card = ""
  base.state = model.state === "done" ? "idle" : model.state
  return base
}

// Milliseconds until the displayed text next changes; 0 means no tick needed.
function nextTickMs(model, now) {
  if (model.state === "running") {
    var r = model.endsAt - now
    if (r <= 0) return 1
    return r - (Math.ceil(r / 1000) - 1) * 1000
  }
  if (model.state === "done") return Math.max(1, model.doneUntil - now)
  return 0
}

if (typeof module !== "undefined") {
  module.exports = {
    GLYPHS: GLYPHS, initial: initial, parse: parse, start: start, pause: pause,
    resume: resume, add: add, cancel: cancel, tick: tick, remaining: remaining,
    fmt: fmt, activity: activity, nextTickMs: nextTickMs
  }
}
