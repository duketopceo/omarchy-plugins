// Pure volume/brightness HUD logic for the Island. ES5, no Qt types.
//
// The HUD replaces omarchy.osd, so it only runs when effective(): the `hud`
// setting is on AND omarchy.osd is in shell.json's top-level disabledPlugins.
// Readings are { kind: "volume", value: fraction, muted } or
// { kind: "brightness", value: current, max }. The first reading of each kind
// is only a baseline; a later one that differs flashes the level for
// FLASH_MS. Callers pass `now` (ms epoch).

var FLASH_MS = 1600
var PRIORITY = 80

// nf-md icon, plane 15 codepoint, built as a surrogate pair.
function _cp(code) {
  var c = code - 0x10000
  return String.fromCharCode(0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF))
}
var GLYPHS = {
  volume: _cp(0xF057E),      // nf-md-volume_high
  volumeOff: _cp(0xF0581),   // nf-md-volume_off
  brightness: _cp(0xF00DF)   // nf-md-brightness_6
}

function effective(settings, shellText) {
  if (!settings || settings.hud !== true) return false
  var root = shellText
  if (typeof root === "string") {
    try { root = JSON.parse(root) } catch (e) { return false }
  }
  if (!root || typeof root !== "object" || !Array.isArray(root.disabledPlugins)) return false
  return root.disabledPlugins.indexOf("omarchy.osd") >= 0
}

function initial() {
  return { volume: null, brightness: null, kind: "", until: 0 }
}

function _with(model, kind, record, until) {
  return {
    volume: kind === "volume" ? record : model.volume,
    brightness: kind === "brightness" ? record : model.brightness,
    kind: until > 0 ? kind : model.kind,
    until: until > 0 ? until : model.until
  }
}

function step(model, reading, now) {
  if (!reading) return model
  var record, prev
  if (reading.kind === "volume") {
    record = {
      value: reading.value, pct: Math.round(reading.value * 100), muted: reading.muted === true
    }
    prev = model.volume
    if (!prev) return _with(model, "volume", record, 0)
    if (prev.pct === record.pct && prev.muted === record.muted) return model
    return _with(model, "volume", record, now + FLASH_MS)
  }
  if (reading.kind === "brightness") {
    record = { pct: Math.round(reading.value / reading.max * 100) }
    prev = model.brightness
    if (!prev) return _with(model, "brightness", record, 0)
    if (prev.pct === record.pct) return model
    return _with(model, "brightness", record, now + FLASH_MS)
  }
  return model
}

function activity(model, now) {
  if (!model.kind || !(now < model.until))
    return { id: "hud", active: false, priority: PRIORITY, text: "", glyph: "", card: "" }
  var base = { id: "hud", active: true, priority: PRIORITY, kind: model.kind, until: model.until }
  if (model.kind === "brightness") {
    var b = model.brightness
    base.text = b.pct + "%"
    base.card = "Brightness " + b.pct + "%"
    base.level = b.pct / 100
    base.glyph = GLYPHS.brightness
    return base
  }
  var v = model.volume
  if (v.muted) {
    base.text = "Mute"
    base.card = "Muted"
    base.level = 0
    base.glyph = GLYPHS.volumeOff
    return base
  }
  base.text = v.pct + "%"
  base.card = "Volume " + v.pct + "%"
  base.level = Math.min(1, v.value)
  base.glyph = GLYPHS.volume
  return base
}

if (typeof module !== "undefined") {
  module.exports = {
    FLASH_MS: FLASH_MS, GLYPHS: GLYPHS,
    effective: effective, initial: initial, step: step, activity: activity
  }
}
