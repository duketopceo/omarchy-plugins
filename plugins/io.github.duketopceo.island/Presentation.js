// Pure presentation rules for the Island: compact sizing, surface choice,
// text contrast, alert size and visibility. ES5, no Qt types.
//
// geom = Geom.compute(...) output. Colors are {r, g, b} in 0..1.

var EAR_MIN = 56
var EAR_MAX = 120
var BUBBLE_GAP = 6
var DOT_SIZE = 8
var DOT_GAP = 4
var DOT_PAD = 6     // space between the camera cutout and the first dot
var DOT_SLOT = 2 * DOT_SIZE + DOT_GAP + DOT_PAD   // 26: two dots, their gap, and the pad
var ALERT_W = 360
var ALERT_H = 76

// Same values as Geom.COMPACT_MIN_W / SCREEN_MARGIN; QML imports this file alone.
var COMPACT_MIN_W = 220
var SCREEN_MARGIN = 16

function _num(v) {
  var n = Number(v)
  return isFinite(n) ? n : 0
}

// "notch" (black, matches the cutout) only for the compact pill on a cutout.
function surface(hasCutout, mode) {
  return hasCutout && (mode === "compact" || mode === "split") ? "notch" : "theme"
}

function _lin(c) {
  var v = _num(c)
  return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)
}

function _luminance(c) {
  return 0.2126 * _lin(c.r) + 0.7152 * _lin(c.g) + 0.0722 * _lin(c.b)
}

// WCAG contrast ratio, 1..21.
function contrast(a, b) {
  var la = _luminance(a)
  var lb = _luminance(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

// Text color for text drawn on the black notch: the theme text color when it
// reads on black, else the theme background color (light on dark themes).
function textOnBlack(text, background) {
  return contrast(text, { r: 0, g: 0, b: 0 }) >= 4.5 ? "text" : "background"
}

// wantEar: content width the widest ear needs, padding included.
// opts = { bubble: bool, dots: int, screenWidth?: number }
function compact(geom, wantEar, opts) {
  var o = opts || {}
  var dotSlot = o.dots > 0 ? DOT_SLOT : 0
  var cam = _num(geom.cameraWidth)
  var ear = Math.max(EAR_MIN, Math.min(EAR_MAX, _num(wantEar) + dotSlot))
  var width = Math.max(COMPACT_MIN_W, cam + 2 * ear)
  if (o.screenWidth !== undefined && o.screenWidth !== null) {
    width = Math.max(0, Math.min(width, _num(o.screenWidth) - SCREEN_MARGIN))
  }
  ear = Math.min(EAR_MAX, Math.floor((width - cam) / 2))
  var height = geom.compactHeight
  return {
    width: width,
    height: height,
    earWidth: ear,
    textWidth: Math.max(0, ear - dotSlot),
    dotSlot: dotSlot,
    bubble: o.bubble ? { offset: width + BUBBLE_GAP, size: height } : null
  }
}

function alertSize(geom) {
  return { width: Math.min(ALERT_W, geom.card.width), height: ALERT_H }
}

// s = { cardShown, fullscreen, state }
function showAlert(s) {
  return s.state === "closed" && !s.fullscreen && !s.cardShown
}

function bubbleVisible(hasSecond, alertShowing, cardShown) {
  return !!hasSecond && !alertShowing && !cardShown
}

if (typeof module !== "undefined") module.exports = {
  EAR_MIN: EAR_MIN, EAR_MAX: EAR_MAX, BUBBLE_GAP: BUBBLE_GAP, DOT_SIZE: DOT_SIZE,
  DOT_GAP: DOT_GAP, DOT_PAD: DOT_PAD, DOT_SLOT: DOT_SLOT, ALERT_W: ALERT_W, ALERT_H: ALERT_H,
  surface: surface, contrast: contrast, textOnBlack: textOnBlack,
  compact: compact, alertSize: alertSize, showAlert: showAlert, bubbleVisible: bubbleVisible
}
