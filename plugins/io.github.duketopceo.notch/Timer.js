// Pure logic for the notch timer and pomodoro (R4). No Qt types, so tests run
// it with node. The model is plain data; every function returns a new model
// (or the same object when nothing changed) and takes `now` in ms, so the QML
// owner only has to call tick() once a second.
//
// States: idle | running | paused | ready (pomodoro: next phase loaded,
// waiting for Start). A finish never stays in "running", which is what makes
// the notification fire exactly once.

var PRESETS = [5, 10, 15, 25, 45]            // minutes
var POMODORO = { focus: 25, rest: 5, longRest: 15, every: 4 }   // minutes, long rest after every Nth focus
var DONE_MS = 8000                           // how long the ear shows "done"
var DONE_PRIORITY = 85                       // above media/charging, below dictation (90)

var GLYPH_RUN = "⏱"                     // stopwatch
var GLYPH_PAUSE = "⏸"

function initial() {
  return { state: "idle", mode: "timer", phase: "timer", totalMs: 0, remainingMs: 0, endsAt: 0, cycle: 0, doneUntil: 0, doneText: "" }
}

function minutesToMs(m) { return Math.max(1, Math.round(Number(m) || 0)) * 60000 }

function phaseMs(mode, phase) {
  if (mode !== "pomodoro") return 0
  return minutesToMs(phase === "focus" ? POMODORO.focus : phase === "long" ? POMODORO.longRest : POMODORO.rest)
}

// Start a plain countdown of `minutes`, or a pomodoro (focus first).
function start(model, mode, minutes, now) {
  var pomo = mode === "pomodoro"
  var ms = pomo ? phaseMs("pomodoro", "focus") : minutesToMs(minutes)
  var base = initial()
  return { state: "running", mode: pomo ? "pomodoro" : "timer", phase: pomo ? "focus" : "timer", totalMs: ms, remainingMs: ms,
           endsAt: now + ms, cycle: 0, doneUntil: model && model.doneUntil > now ? model.doneUntil : base.doneUntil, doneText: model ? model.doneText : "" }
}

function remaining(model, now) {
  if (!model) return 0
  if (model.state === "running") return Math.max(0, model.endsAt - now)
  if (model.state === "paused" || model.state === "ready") return model.remainingMs
  return 0
}

function copy(model, patch) {
  var out = {}
  for (var k in model) out[k] = model[k]
  for (var p in patch) out[p] = patch[p]
  return out
}

function pause(model, now) {
  if (!model || model.state !== "running") return model
  return copy(model, { state: "paused", remainingMs: Math.max(0, model.endsAt - now), endsAt: 0 })
}

// Resume a paused timer, or Start the loaded next pomodoro phase.
function resume(model, now) {
  if (!model || (model.state !== "paused" && model.state !== "ready")) return model
  var left = model.remainingMs > 0 ? model.remainingMs : model.totalMs
  return copy(model, { state: "running", endsAt: now + left, remainingMs: left })
}

function cancel(model) {
  var out = initial()
  if (model) { out.doneUntil = model.doneUntil; out.doneText = model.doneText }
  return out
}

function finishText(model) {
  if (model.mode !== "pomodoro") return "Timer done"
  return model.phase === "focus" ? "Focus done" : "Break over"
}

// What a finished pomodoro phase leads to: focus -> rest (long every Nth).
function nextPhase(model) {
  if (model.phase === "focus") {
    var done = model.cycle + 1
    return { phase: done % POMODORO.every === 0 ? "long" : "rest", cycle: done }
  }
  return { phase: "focus", cycle: model.cycle }
}

// Advance to `now`. Returns { model, notify }: `notify` is { title, body }
// exactly once, on the tick that crosses the end, else null.
function tick(model, now) {
  if (!model || model.state !== "running" || model.endsAt > now) return { model: model, notify: null }
  var text = finishText(model)
  var patch = { doneUntil: now + DONE_MS, doneText: text }
  if (model.mode === "pomodoro") {
    var nx = nextPhase(model)
    var ms = phaseMs("pomodoro", nx.phase)
    patch.state = "ready"; patch.phase = nx.phase; patch.cycle = nx.cycle; patch.totalMs = ms; patch.remainingMs = ms; patch.endsAt = 0
    return { model: copy(model, patch), notify: { title: text, body: "Next: " + phaseLabel(nx.phase) + " " + fmt(ms) } }
  }
  patch.state = "idle"; patch.remainingMs = 0; patch.endsAt = 0
  return { model: copy(model, patch), notify: { title: text, body: fmt(model.totalMs) + " elapsed" } }
}

function phaseLabel(phase) { return phase === "focus" ? "Focus" : phase === "long" ? "Long break" : phase === "rest" ? "Break" : "Timer" }

// 754000 -> "12:34"; an hour or more -> "1:02:03". Rounds up so 0:00 means done.
function fmt(ms) {
  var s = Math.max(0, Math.ceil((Number(ms) || 0) / 1000))
  var h = Math.floor(s / 3600)
  var m = Math.floor((s % 3600) / 60)
  var r = s % 60
  var two = function (n) { return (n < 10 ? "0" : "") + n }
  return h > 0 ? h + ":" + two(m) + ":" + two(r) : m + ":" + two(r)
}

// 0..1 elapsed of the current phase (for a progress bar).
function progress(model, now) {
  if (!model || !(model.totalMs > 0) || model.state === "idle") return 0
  return Math.max(0, Math.min(1, 1 - remaining(model, now) / model.totalMs))
}

// The ear line while the timer is running or paused: "⏱ 12:34", pomodoro
// "Focus 12:34", paused "⏸ 12:34".
function slotText(model, now) {
  if (!model || (model.state !== "running" && model.state !== "paused")) return ""
  var t = fmt(remaining(model, now))
  var lead = model.state === "paused" ? GLYPH_PAUSE : (model.mode === "pomodoro" ? phaseLabel(model.phase) : GLYPH_RUN)
  return lead + " " + t
}

// Running or paused timers take a turn in the ear's ONE rotating idle slot
// next to weather, stocks, Dayflow and Messages; they never replace them.
function idleViews(views, model) {
  var list = Array.isArray(views) ? views.slice() : []
  if (model && (model.state === "running" || model.state === "paused")) list.push("timer")
  return list
}

// The "done" flash: an ordinary activity, active for DONE_MS after a finish.
function doneActive(model, clock) { return !!model && model.doneText !== "" && model.doneUntil > clock }

// argv for the single finish notification.
function notifyArgs(note) {
  return ["notify-send", "-a", "Notch", String(note.title), String(note.body || "")]
}

if (typeof module !== "undefined") {
  module.exports = {
    PRESETS: PRESETS, POMODORO: POMODORO, DONE_MS: DONE_MS, DONE_PRIORITY: DONE_PRIORITY,
    initial: initial, start: start, remaining: remaining, pause: pause, resume: resume, cancel: cancel, tick: tick,
    fmt: fmt, progress: progress, slotText: slotText, idleViews: idleViews, doneActive: doneActive, notifyArgs: notifyArgs, phaseLabel: phaseLabel
  }
}
