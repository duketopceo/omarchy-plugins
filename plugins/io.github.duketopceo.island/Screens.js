// Monitor-under-pointer helpers for the Island's IPC. ES5, no Qt types.
//
// screens = [{ name, x, y, width, height }] in logical layout coordinates, the
// same space `hyprctl cursorpos -j` reports.

function _num(v) {
  var n = Number(v)
  return isFinite(n) ? n : 0
}

// { name, width, height, physicalWidth, physicalHeight } for Geom.compute.
// ipc: the Hyprland monitor's lastIpcObject (physical width/height) or null;
// without it, physical size is logical size times the device pixel ratio.
function describe(screen, ipc) {
  var s = screen || {}
  var pw = ipc ? _num(ipc.width) : 0
  var ph = ipc ? _num(ipc.height) : 0
  var dpr = _num(s.devicePixelRatio) || 1
  return {
    name: String(s.name),
    width: _num(s.width),
    height: _num(s.height),
    physicalWidth: pw > 0 && ph > 0 ? pw : Math.round(_num(s.width) * dpr),
    physicalHeight: pw > 0 && ph > 0 ? ph : Math.round(_num(s.height) * dpr)
  }
}

// Output of `hyprctl cursorpos -j` -> { x, y } or null.
function parseCursor(text) {
  var o
  try { o = JSON.parse(text) } catch (e) { return null }
  if (!o || typeof o !== "object" || Array.isArray(o)) return null
  if (typeof o.x !== "number" || typeof o.y !== "number" || !isFinite(o.x) || !isFinite(o.y)) return null
  return { x: o.x, y: o.y }
}

function screenAt(screens, x, y) {
  var list = screens || []
  for (var i = 0; i < list.length; i++) {
    var s = list[i]
    if (x >= s.x && x < s.x + s.width && y >= s.y && y < s.y + s.height) return String(s.name)
  }
  return null
}

// The screen an IPC call targets: the one under the pointer; the focused
// monitor only when the position is unknown or lies on no screen.
function pick(screens, cursor, focusedName) {
  var name = cursor ? screenAt(screens, cursor.x, cursor.y) : null
  if (name) return name
  return focusedName ? String(focusedName) : null
}

if (typeof module !== "undefined") module.exports = {
  describe: describe, parseCursor: parseCursor, screenAt: screenAt, pick: pick
}
