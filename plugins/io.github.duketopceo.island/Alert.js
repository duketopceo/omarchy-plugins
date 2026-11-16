// Pure transient-alert logic for the Island. ES5, no Qt types.
//
// At most one alert is current; a newer push replaces it. Each Island window
// asks gate() whether to show the current alert: an alert that arrives while
// the window is blocked (for example a fullscreen window) is remembered as
// blocked and never shows on that window later. Callers pass `now` (ms epoch).

var ALERT_MS = 3000

// nf-md icon, plane 15 codepoint, built as a surrogate pair.
function _cp(code) {
  var c = code - 0x10000
  return String.fromCharCode(0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF))
}
var GLYPHS = {
  charging: _cp(0xF0084),   // nf-md-battery_charging
  timer: _cp(0xF012C),      // nf-md-check
  bluetooth: _cp(0xF02CB),  // nf-md-headphones
  dnd: _cp(0xF009B),        // nf-md-bell_off
  mic: _cp(0xF036D)         // nf-md-microphone_off
}

function initial() {
  return { current: null, seq: 0 }
}

function push(model, alert, now) {
  var id = model.seq + 1
  return {
    seq: id,
    current: {
      id: id, kind: alert.kind, title: alert.title, detail: alert.detail,
      glyph: alert.glyph,
      level: typeof alert.level === "number" ? alert.level : null,
      at: now, until: now + ALERT_MS
    }
  }
}

function current(model, now) {
  return model.current && now < model.current.until ? model.current : null
}

function gate(model, blockedId, blocked, now) {
  var a = current(model, now)
  if (!a) return { show: false, blockedId: blockedId }
  if (a.id === blockedId) return { show: false, blockedId: blockedId }
  if (blocked) return { show: false, blockedId: a.id }
  return { show: true, blockedId: blockedId }
}

function charging(capacity, timeToFullSeconds) {
  var detail = capacity + "%"
  if (timeToFullSeconds > 0) {
    var m = Math.round(timeToFullSeconds / 60)
    var h = Math.floor(m / 60)
    detail += " · " + (h > 0 ? h + "h " : "") + (m % 60) + "m to full"
  }
  return { kind: "charging", title: "Charging", detail: detail, glyph: GLYPHS.charging,
           level: capacity / 100 }
}

function timerDone() {
  return { kind: "timer", title: "Timer done", detail: "Your Island timer finished",
           glyph: GLYPHS.timer }
}

function bluetooth(name, battery) {
  var detail = "Connected"
  if (typeof battery === "number") detail += " · " + Math.round(battery * 100) + "%"
  return { kind: "bluetooth", title: name, detail: detail, glyph: GLYPHS.bluetooth }
}

function dnd(on) {
  return { kind: "dnd", title: "Do Not Disturb", detail: on ? "On" : "Off", glyph: GLYPHS.dnd }
}

function mic(muted) {
  return { kind: "mic", title: "Microphone", detail: muted ? "Muted" : "On", glyph: GLYPHS.mic }
}

if (typeof module !== "undefined") module.exports = {
  ALERT_MS: ALERT_MS, GLYPHS: GLYPHS, initial: initial, push: push, current: current,
  gate: gate, charging: charging, timerDone: timerDone, bluetooth: bluetooth,
  dnd: dnd, mic: mic
}
