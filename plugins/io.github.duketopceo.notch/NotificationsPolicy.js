// Pure policy for optional notification hosting. Default installs never claim
// org.freedesktop.Notifications — stock Omarchy keeps the daemon.

var STOCK_ID = "omarchy.notifications"
var OSD_ID = "omarchy.osd"

function disabledList(shellConfig) {
  var raw = shellConfig && shellConfig.disabledPlugins
  return Array.isArray(raw) ? raw.map(String) : []
}

// hostOn: settings.hostNotifications === true
// Returns { ok, code, detail } for Settings / setup UI.
function hostStatus(hostOn, shellConfig) {
  if (!hostOn) {
    return {
      ok: true,
      code: "stock",
      detail: "Stock Omarchy notifications are in use."
    }
  }
  var disabled = disabledList(shellConfig)
  if (disabled.indexOf(STOCK_ID) < 0) {
    return {
      ok: false,
      code: "conflict",
      detail: "Add \"" + STOCK_ID + "\" to disabledPlugins in shell.json before hosting notifications here. Only one D-Bus notification owner is allowed."
    }
  }
  return {
    ok: true,
    code: "ready",
    detail: "Stock notifications are disabled. Island hosting is opted in (Phase A: setup complete; full card UI ships next)."
  }
}

function osdHint(hudOwner) {
  if (hudOwner !== "notch") return ""
  return "Add \"" + OSD_ID + "\" to disabledPlugins in shell.json so Omarchy's OSD does not double with the island HUD."
}

if (typeof module !== "undefined") {
  module.exports = {
    STOCK_ID: STOCK_ID,
    OSD_ID: OSD_ID,
    disabledList: disabledList,
    hostStatus: hostStatus,
    osdHint: osdHint
  }
}
