// Pure helpers for Hyprland fullscreen step-aside. No Qt types — node-testable.
// Matches Omarchy notifications: only real fullscreen (mode bit 2) counts;
// maximized alone must not hide the island.

var MODE_FULLSCREEN = 2

// `workspace` is a Hyprland workspace-like object with hasFullscreen and
// toplevels.values[].lastIpcObject.fullscreen. Returns true when this output
// has a real fullscreen client.
function isFullscreen(workspace) {
  if (!workspace || !workspace.hasFullscreen) return false
  var windows = workspace.toplevels && workspace.toplevels.values
    ? workspace.toplevels.values
    : []
  for (var i = 0; i < windows.length; i++) {
    var ipc = windows[i] && windows[i].lastIpcObject ? windows[i].lastIpcObject : {}
    if ((Number(ipc.fullscreen) & MODE_FULLSCREEN) !== 0) return true
  }
  return false
}

// Idle island should step aside (unmap) under real FS so Overlay does not
// block direct scanout. Expanded/pinned content may stay visible.
function shouldStepAside(hideEnabled, fullscreen, expanded) {
  return hideEnabled === true && fullscreen === true && expanded !== true
}

if (typeof module !== "undefined") {
  module.exports = {
    MODE_FULLSCREEN: MODE_FULLSCREEN,
    isFullscreen: isFullscreen,
    shouldStepAside: shouldStepAside
  }
}
