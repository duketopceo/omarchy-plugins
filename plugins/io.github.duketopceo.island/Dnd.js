// Pure Do Not Disturb logic for the Island. ES5, no Qt types.
//
// The adapter reads omarchy's notification state file and shell.json every
// few seconds. step() reports an edge only for a change after the first
// reading, so a DND that is already on at startup shows nothing.

function _cp(code) {
  var c = code - 0x10000
  return String.fromCharCode(0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF))
}
var GLYPH = _cp(0xF009B)   // nf-md-bell_off

function _json(text) {
  try { return JSON.parse(String(text === undefined || text === null ? "" : text)) } catch (e) { return null }
}

function parse(text) {
  var o = _json(text)
  return !!o && typeof o === "object" && o.dnd === true
}

// False only when shell.json disables the notifications plugin.
function available(shellJson) {
  var o = _json(shellJson)
  var d = o && typeof o === "object" ? o.disabledPlugins : null
  return !(Array.isArray(d) && d.indexOf("omarchy.notifications") >= 0)
}

function initial() {
  return { seen: false, on: false }
}

function step(model, on) {
  var v = on === true
  if (model.seen && model.on === v) return { model: model, edge: "" }
  var edge = model.seen ? (v ? "on" : "off") : ""
  return { model: { seen: true, on: v }, edge: edge }
}

if (typeof module !== "undefined") module.exports = {
  GLYPH: GLYPH, parse: parse, available: available, initial: initial, step: step
}
