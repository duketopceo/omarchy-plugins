// Pure hover state machine for the Island's open/close rules.
// ES5, no Qt types: QML feeds it events and runs the timer it returns; node
// tests load it with require().
//
// States: "closed" | "arming" | "open" | "leaving". Flags modify transitions
// (see the plan's High-Level Technical Design).
//
// step(model, event, settings) -> { model, timer }
//   timer > 0   start (or restart) the single pending timer with this delay in ms
//   timer === 0 stop the pending timer
//   timer === -1 leave the pending timer exactly as it is (no-op events)
// model.timerKind says what the pending timer is for: "open", "close",
// "summon" or "" (none). The shortest real delay is 1 ms.
//
// Events are strings or objects { type, hovered }. `timer` events should carry
// the current hover snapshot as `hovered`; without it the last enter/leave is used.

var DEFAULTS = { openDelay: 140, closeDelay: 450, summonTimeout: 5000 }
var KEEP = -1

function num(v, def, lo, hi) {
  var n = Number(v)
  if (v === null || v === undefined || v === "" || isNaN(n)) n = def
  return Math.round(Math.min(hi, Math.max(lo, n)))
}

function clampSettings(s) {
  s = s || {}
  return {
    openDelay: num(s.openDelay, DEFAULTS.openDelay, 0, 600),
    closeDelay: num(s.closeDelay, DEFAULTS.closeDelay, 150, 1500),
    summonTimeout: DEFAULTS.summonTimeout
  }
}

function initial() {
  return {
    state: "closed", pinned: false, focused: false, held: false, summoned: false,
    enteredSinceSummon: false, rearmLock: false, pointerInside: false,
    fullscreen: false, timerKind: ""
  }
}

function copy(m) {
  var o = {}
  for (var k in m) o[k] = m[k]
  return o
}

// A card-visible state: the card is open or about to close.
function cardShown(m) {
  return m.state === "open" || m.state === "leaving"
}

// Close commits: drop every transient flag. rearmLock only when the pointer is
// still inside, so it cannot reopen until the pointer leaves and returns.
function closed(m) {
  m.state = "closed"
  m.pinned = false
  m.focused = false
  m.held = false
  m.summoned = false
  m.enteredSinceSummon = false
  m.rearmLock = m.pointerInside
  m.timerKind = ""
  return { model: m, timer: 0 }
}

function stopTimer(m) {
  m.timerKind = ""
  return { model: m, timer: 0 }
}

function startTimer(m, kind, ms) {
  m.timerKind = kind
  return { model: m, timer: Math.max(1, ms) }
}

function step(model, event, settings) {
  var cfg = clampSettings(settings)
  var type = event && typeof event === "object" ? event.type : event
  var hovered = event && typeof event === "object" && event.hovered !== undefined ? !!event.hovered : undefined
  var m = copy(model)
  var summonPending = m.summoned && !m.enteredSinceSummon

  switch (type) {
    case "enter":
      if (m.fullscreen) return { model: model, timer: KEEP }
      m.pointerInside = true
      if (m.rearmLock) return { model: m, timer: KEEP }
      if (m.state === "closed") {
        if (cfg.openDelay <= 0) { m.state = "open"; return stopTimer(m) }
        m.state = "arming"
        return startTimer(m, "open", cfg.openDelay)
      }
      if (m.state === "leaving") { m.state = "open"; return stopTimer(m) }
      if (m.state === "open" && m.summoned) {
        // First visit ends the summon grace period.
        m.summoned = false
        m.enteredSinceSummon = true
        return stopTimer(m)
      }
      return { model: m, timer: KEEP }

    case "leave":
      m.pointerInside = false
      m.rearmLock = false
      if (m.state === "arming") { m.state = "closed"; return stopTimer(m) }
      if (m.state === "open" && !m.pinned && !m.held && !summonPending) {
        m.state = "leaving"
        return startTimer(m, "close", cfg.closeDelay)
      }
      return { model: m, timer: KEEP }

    case "timer":
      if (hovered !== undefined) m.pointerInside = hovered
      if (m.timerKind === "open" && m.state === "arming") {
        if (m.pointerInside) { m.state = "open"; return stopTimer(m) }
        m.state = "closed"
        return stopTimer(m)
      }
      if (m.timerKind === "close" && m.state === "leaving") {
        if (m.pointerInside) { m.state = "open"; return stopTimer(m) }
        return closed(m)
      }
      if (m.timerKind === "summon" && m.state === "open") {
        if (m.held || m.pinned || !summonPending) return stopTimer(m)
        return closed(m)
      }
      return stopTimer(m)

    case "click":
      if (m.fullscreen) return { model: model, timer: KEEP }
      m.pointerInside = true
      m.rearmLock = false
      if (m.state === "closed" || m.state === "arming" || m.state === "leaving") {
        m.state = "open"
        return stopTimer(m)
      }
      return { model: m, timer: KEEP }

    case "cardClick":
      if (!cardShown(m)) return { model: model, timer: KEEP }
      m.focused = true
      if (m.state === "leaving") { m.state = "open"; return stopTimer(m) }
      return { model: m, timer: KEEP }

    case "pin":
      if (!cardShown(m)) return { model: model, timer: KEEP }
      m.pinned = true
      m.focused = true
      m.state = "open"
      return m.timerKind === "close" ? stopTimer(m) : { model: m, timer: KEEP }

    case "unpin":
      if (!m.pinned) return { model: model, timer: KEEP }
      return closed(m)

    case "escape":
      if (!cardShown(m)) return { model: model, timer: KEEP }
      return closed(m)

    case "ipcClose":
      if (m.state === "closed") return { model: model, timer: KEEP }
      return closed(m)

    case "holdStart":
      if (!cardShown(m)) return { model: model, timer: KEEP }
      m.held = true
      if (m.state === "leaving") { m.state = "open"; return stopTimer(m) }
      return { model: m, timer: KEEP }

    case "holdEnd":
      if (!m.held) return { model: model, timer: KEEP }
      m.held = false
      if (m.state !== "open" || m.pinned) return { model: m, timer: KEEP }
      if (summonPending) return startTimer(m, "summon", cfg.summonTimeout)
      if (!m.pointerInside) {
        m.state = "leaving"
        return startTimer(m, "close", cfg.closeDelay)
      }
      return { model: m, timer: KEEP }

    case "summon":
      if (m.fullscreen) return { model: model, timer: KEEP }
      m.state = "open"
      m.summoned = true
      m.enteredSinceSummon = false
      m.focused = true
      m.rearmLock = false
      return startTimer(m, "summon", cfg.summonTimeout)

    case "focus":
      if (!cardShown(m)) return { model: model, timer: KEEP }
      m.focused = true
      return { model: m, timer: KEEP }

    case "fullscreenOn":
      m.fullscreen = true
      m.pointerInside = false
      var r = closed(m)
      m.rearmLock = false
      return r

    case "fullscreenOff":
      // Stays closed; only a fresh enter event can open it again.
      m.fullscreen = false
      m.pointerInside = false
      return { model: m, timer: KEEP }

    default:
      // Unknown event: model unchanged, pending timer untouched.
      return { model: model, timer: KEEP }
  }
}

// Input-mask zone for the current state: "pill" (pill + 6 px) while closed or
// arming, "card" (card + 12 px) while the card is open or leaving.
function zoneFor(model) {
  return model.state === "open" || model.state === "leaving" ? "card" : "pill"
}

if (typeof module !== "undefined") module.exports = {
  step: step, initial: initial, clampSettings: clampSettings, zoneFor: zoneFor, cardShown: cardShown
}
