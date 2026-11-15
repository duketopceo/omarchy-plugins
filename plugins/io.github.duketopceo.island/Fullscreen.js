// Fullscreen predicate and refresh triggers for the Island. ES5, no Qt types.
//
// Same recipe as Omarchy's notifications service: a workspace reports
// maximized windows as fullscreen too, so only mode bit 2 (real fullscreen)
// counts.

var REFRESH_EVENTS = {
  fullscreen: true, openwindow: true, closewindow: true, movewindowv2: true,
  activewindowv2: true, workspacev2: true, focusedmonv2: true, changefloatingmode: true
}

// hasFullscreen: the active workspace's flag; ipcObjects: its toplevels'
// lastIpcObject values.
function isReal(hasFullscreen, ipcObjects) {
  if (!hasFullscreen || !Array.isArray(ipcObjects)) return false
  for (var i = 0; i < ipcObjects.length; i++) {
    var ipc = ipcObjects[i]
    if (ipc && (Number(ipc.fullscreen) & 2) !== 0) return true
  }
  return false
}

function isRefreshEvent(name) {
  return Object.prototype.hasOwnProperty.call(REFRESH_EVENTS, String(name)) && REFRESH_EVENTS[name] === true
}

if (typeof module !== "undefined") module.exports = {
  REFRESH_EVENTS: REFRESH_EVENTS, isReal: isReal, isRefreshEvent: isRefreshEvent
}
