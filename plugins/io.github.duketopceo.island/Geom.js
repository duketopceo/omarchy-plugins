// Pure geometry for the Island: camera width, cutout matching, compact pill
// and card sizes. ES5, no Qt types. All outputs are logical pixels.
//
// probe  = { cutouts: [{connector, width, height, top}], model: "j316" }
// screen = { name, width, height, physicalWidth, physicalHeight }

var COMPACT_H = 28
var COMPACT_MIN_W = 220
var EAR_CAP = 56
var SCREEN_MARGIN = 16
var CARD_W = 720
var CARD_H = 380
var VIRTUAL_CAMERA_W = 160   // logical px for a pill with no real cutout
var MATCH_TOLERANCE = 4      // physical px
var FALLBACK_FRACTION = 0.12

// Camera width in physical px, by Apple model id. 0 = pre-notch, no cutout.
var MODEL_CAMERA = {
  j314: 372, j316: 372, j414: 372, j416: 372, j504: 372,
  j514: 372, j516: 372, j604: 372, j614: 372, j616: 372,
  j413: 322, j415: 322, j613: 322, j615: 322, j713: 322, j715: 322,
  j293: 0, j313: 0, j493: 0
}
var PANEL_WIDTH_CAMERA = { 3024: 372, 3456: 372, 2560: 322, 2880: 322 }

function _num(v) {
  var n = Number(v)
  return isFinite(n) ? n : 0
}

function isRotated(screen) {
  var s = screen || {}
  return (_num(s.physicalWidth) >= _num(s.physicalHeight)) !== (_num(s.width) >= _num(s.height))
}

// The cutout entry matching this screen, or null. Rotated outputs never match.
function matchCutout(cutouts, screen) {
  var s = screen || {}
  if (!Array.isArray(cutouts) || isRotated(s)) return null
  var name = String(s.name || "")
  for (var i = 0; i < cutouts.length; i++) {
    var c = cutouts[i]
    if (!c || !c.connector || name.indexOf(String(c.connector)) !== 0) continue
    if (Math.abs(_num(c.width) - _num(s.physicalWidth)) <= MATCH_TOLERANCE &&
        Math.abs(_num(c.height) - _num(s.physicalHeight)) <= MATCH_TOLERANCE) return c
  }
  return null
}

function scaleOf(screen) {
  var s = screen || {}
  var w = _num(s.width)
  var p = _num(s.physicalWidth)
  return w > 0 && p > 0 ? p / w : 1
}

// Camera width in physical px for a matched cutout; 0 means "no cutout".
function cameraPhysical(model, cutout) {
  if (!cutout) return 0
  var key = String(model || "")
  if (Object.prototype.hasOwnProperty.call(MODEL_CAMERA, key)) return MODEL_CAMERA[key]
  var byPanel = PANEL_WIDTH_CAMERA[_num(cutout.width)]
  if (byPanel) return byPanel
  return Math.round(_num(cutout.width) * FALLBACK_FRACTION)
}

function compactWidth(cameraWidth, screenWidth) {
  var w = Math.max(COMPACT_MIN_W, _num(cameraWidth) + 2 * EAR_CAP)
  return Math.max(0, Math.min(w, _num(screenWidth) - SCREEN_MARGIN))
}

function cardSize(screenWidth) {
  return { width: Math.min(CARD_W, _num(screenWidth) - SCREEN_MARGIN), height: CARD_H }
}

// override: the plugin's cameraWidth setting in logical px, 0 = auto.
function compute(probe, screen, override) {
  var p = probe || {}
  var s = screen || {}
  var cutout = matchCutout(p.cutouts, s)
  var phys = cameraPhysical(p.model, cutout)
  var hasCutout = phys > 0
  var camera
  if (_num(override) > 0) camera = Math.round(_num(override))
  else if (hasCutout) camera = Math.round(phys / scaleOf(s))
  else camera = VIRTUAL_CAMERA_W
  var width = compactWidth(camera, s.width)
  var ear = Math.max(0, Math.min(EAR_CAP, Math.floor((width - camera) / 2)))
  return {
    hasCutout: hasCutout,
    cutoutTop: hasCutout ? _num(cutout.top) : 0,
    cameraWidth: camera,
    compactWidth: width,
    compactHeight: COMPACT_H,
    earWidth: ear,
    card: cardSize(s.width)
  }
}

if (typeof module !== "undefined") {
  module.exports = {
    COMPACT_H: COMPACT_H, COMPACT_MIN_W: COMPACT_MIN_W, EAR_CAP: EAR_CAP,
    SCREEN_MARGIN: SCREEN_MARGIN, CARD_W: CARD_W, CARD_H: CARD_H,
    VIRTUAL_CAMERA_W: VIRTUAL_CAMERA_W,
    isRotated: isRotated, matchCutout: matchCutout, scaleOf: scaleOf,
    cameraPhysical: cameraPhysical, compactWidth: compactWidth,
    cardSize: cardSize, compute: compute
  }
}
