// Pure pointer-speed filter for the Island's hover open ("arriving vs
// passing"). ES5, no Qt types; node tests load it with require().
//
// The window feeds pointer motion samples from its one HoverHandler (position
// in hot-zone coordinates plus a millisecond clock). When the open timer
// fires, moving() says whether the pointer is still travelling fast; Hover.js
// then waits a little longer instead of opening. A resting pointer sends no
// motion events, so it never reads as moving.

var KEEP_MS = 150     // samples older than this are dropped
var MAX_SAMPLES = 12  // cap, newest kept
var WINDOW_MS = 80    // speed is measured over this much recent time
var SPEED = 0.5       // logical px per ms; at or above this the pointer is passing

// New sample list with { x, y, t } appended; the input list is not changed.
function add(samples, x, y, t) {
  var out = []
  var list = Array.isArray(samples) ? samples : []
  for (var i = 0; i < list.length; i++) if (list[i].t >= t - KEEP_MS && list[i].t <= t) out.push(list[i])
  out.push({ x: Number(x), y: Number(y), t: Number(t) })
  if (out.length > MAX_SAMPLES) out = out.slice(out.length - MAX_SAMPLES)
  return out
}

// True when the path covered inside the last WINDOW_MS, divided by the time
// from the window's first sample to `now`, is at least SPEED.
function moving(samples, now) {
  if (!Array.isArray(samples)) return false
  var w = []
  for (var i = 0; i < samples.length; i++) if (samples[i].t >= now - WINDOW_MS && samples[i].t <= now) w.push(samples[i])
  if (w.length < 2) return false
  var dist = 0
  for (var j = 1; j < w.length; j++) {
    var dx = w[j].x - w[j - 1].x
    var dy = w[j].y - w[j - 1].y
    dist += Math.sqrt(dx * dx + dy * dy)
  }
  return dist / Math.max(1, now - w[0].t) >= SPEED
}

if (typeof module !== "undefined") module.exports = {
  KEEP_MS: KEEP_MS, MAX_SAMPLES: MAX_SAMPLES, WINDOW_MS: WINDOW_MS, SPEED: SPEED, add: add, moving: moving
}
