// Dynamic Island geometry tokens + sizing helpers. No Qt types — node-testable.
// Compact is a floating pill (not cutout-fill). Keep numbers here so Island.qml
// stays a view, not a magic-number dump.

var COMPACT_H = 28          // pill height (prototype 37 was too tall on this panel)
var EXPANDED_W = 374
var EXPANDED_H = 168
var WINDOW_H_SLACK = 4      // PanelWindow slack beyond the island (was +20)
var WINDOW_W_SLACK = 16     // was +40
var EAR_CAP = 56            // max ear either side of the camera while compact
var COMPACT_MIN_W = 220
var SCREEN_MARGIN = 16

function compactHeight() { return COMPACT_H }

function expandedSize() { return { width: EXPANDED_W, height: EXPANDED_H } }

// Compact width: camera + capped ears so the pill does not balloon.
function compactWidth(camW, earTarget, screenW) {
  var cam = Math.max(0, Number(camW) || 0)
  var ear = Math.max(0, Math.min(EAR_CAP, Number(earTarget) || 0))
  var w = Math.max(COMPACT_MIN_W, Math.round(cam + 2 * ear))
  if (!(Number(screenW) > 0)) return w
  // Tiny screens may go below COMPACT_MIN_W rather than overflow the display.
  return Math.min(Math.max(1, Number(screenW) - SCREEN_MARGIN), w)
}

function windowWidth(expanded, compactW) {
  return (expanded ? EXPANDED_W : Math.max(0, Number(compactW) || 0)) + WINDOW_W_SLACK
}

function windowHeight(expanded) {
  return (expanded ? EXPANDED_H : COMPACT_H) + WINDOW_H_SLACK
}

if (typeof module !== "undefined") {
  module.exports = {
    COMPACT_H: COMPACT_H, EXPANDED_W: EXPANDED_W, EXPANDED_H: EXPANDED_H,
    WINDOW_H_SLACK: WINDOW_H_SLACK, WINDOW_W_SLACK: WINDOW_W_SLACK,
    EAR_CAP: EAR_CAP, COMPACT_MIN_W: COMPACT_MIN_W,
    compactHeight: compactHeight, expandedSize: expandedSize,
    compactWidth: compactWidth, windowWidth: windowWidth, windowHeight: windowHeight
  }
}
