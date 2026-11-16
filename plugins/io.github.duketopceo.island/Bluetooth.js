// Pure Bluetooth logic for the Island. ES5, no Qt types.
//
// audio() keeps connected audio devices. step() tracks the connected set: the
// first call is only a baseline, later calls report one edge per newly
// connected address. activity() is a card-only activity for the first device.

var PRIORITY = 20

function _cp(code) {
  var c = code - 0x10000
  return String.fromCharCode(0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF))
}
var GLYPHS = {
  headphones: _cp(0xF02CB)   // nf-md-headphones
}

function audio(devices) {
  var out = []
  if (!Array.isArray(devices)) return out
  for (var i = 0; i < devices.length; i++) {
    var d = devices[i]
    if (d && d.connected === true && String(d.icon).indexOf("audio-") === 0) out.push(d)
  }
  return out
}

function initial() {
  return { seen: false, addrs: {} }
}

function step(model, list) {
  var addrs = {}
  var keys = []
  var edges = []
  for (var i = 0; i < list.length; i++) {
    var d = list[i]
    addrs[d.address] = true
    keys.push(d.address)
    if (model.seen && !model.addrs[d.address]) {
      edges.push({
        address: d.address,
        name: d.name,
        battery: d.batteryAvailable === true ? d.battery : null
      })
    }
  }
  var same = model.seen
  if (same) {
    for (var k = 0; k < keys.length; k++) if (!model.addrs[keys[k]]) same = false
    for (var old in model.addrs) if (!addrs[old]) same = false
  }
  return { model: same ? model : { seen: true, addrs: addrs }, edges: edges }
}

function activity(list) {
  if (!list || list.length === 0)
    return { id: "bluetooth", active: false, priority: PRIORITY, cardOnly: true, text: "", glyph: "", card: "" }
  var d = list[0]
  var name = String(d.name)
  var pct = d.batteryAvailable === true ? Math.round(d.battery * 100) + "%" : ""
  return {
    id: "bluetooth", active: true, priority: PRIORITY, cardOnly: true,
    text: pct !== "" ? pct : name,
    glyph: GLYPHS.headphones,
    card: pct !== "" ? name + " " + pct : name
  }
}

if (typeof module !== "undefined") {
  module.exports = { GLYPHS: GLYPHS, audio: audio, initial: initial, step: step, activity: activity }
}
