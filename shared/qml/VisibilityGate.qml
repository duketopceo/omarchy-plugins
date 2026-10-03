import QtQuick
import Quickshell
import Quickshell.Hyprland

// Decides whether a plugin's polling should run (plan KTD10, R7).
// Visible = panel open, OR bar text shown while the session is unlocked and
// at least one output is powered. Lid state is deliberately not an input:
// output power already covers it and lid events are unreliable on Asahi.
// Services and spawn-free timers do not bind to this gate.
QtObject {
  id: root

  // Injected: the shell object (shell.serviceFor) and the plugin's own state.
  property var shell: null
  property bool panelOpen: false
  property bool barShown: true

  readonly property var lockService: {
    var host = root.shell
    if (!host || typeof host.serviceFor !== "function") return null
    var id = "omarchy.lock"
    if (host.pluginRegistry && typeof host.pluginRegistry.resolveEnabledId === "function")
      id = host.pluginRegistry.resolveEnabledId(id)
    return host.serviceFor(id)
  }
  // Fail-open: an unknown lock state never pauses a visible plugin.
  readonly property bool locked: root.lockService ? root.lockService.locked === true : false

  // dpmsStatus comes from Hyprland's monitor JSON; unknown counts as powered.
  property int _dpmsTick: 0
  readonly property bool outputPowered: {
    root._dpmsTick
    var mons = Hyprland.monitors ? Hyprland.monitors.values : []
    if (!mons || mons.length === 0) return true
    for (var i = 0; i < mons.length; i++) {
      var o = mons[i] ? mons[i].lastIpcObject : null
      if (!o || o.dpmsStatus === undefined || o.dpmsStatus === true) return true
    }
    return false
  }

  readonly property bool visible: root.panelOpen
                                  || (root.barShown && !root.locked && root.outputPowered)

  // Fires once on each false -> true edge so callers refresh immediately.
  signal revealed()
  property bool _was: false
  onVisibleChanged: {
    if (root.visible && !root._was) root.revealed()
    root._was = root.visible
  }

  property Connections _hypr: Connections {
    target: Hyprland
    function onRawEvent(event) {
      var n = event && event.name ? String(event.name) : ""
      if (n === "dpms" || n === "monitoradded" || n === "monitorremoved") {
        Hyprland.refreshMonitors()
        root._dpmsTick++
      }
    }
  }
  Component.onCompleted: root._was = root.visible
}
