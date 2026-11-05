import QtQuick
import Quickshell
import Quickshell.Io
import "Network.js" as Network

// Tailscale and NordVPN state for the notch: the idle status dot, the Home
// tab's network dots and the Network tab. A cheap status read (no peer list)
// runs every 60 s; while a tab that shows the details is visible (`viewers`
// > 0) it polls every 8 s and fetches the peer list.
// Controls call the CLIs directly: `/usr/bin/tailscale up|down` and the
// nordvpn plugin's own probe (`connect` / `disconnect`). Nothing else.
Scope {
  id: net

  property var ts: Network.parseTailscale("")
  property var nord: Network.parseNord("")
  property int viewers: 0                 // tabs currently showing network details
  property string tsBusy: ""              // "up" | "down" while a toggle runs
  property string nordBusy: ""            // "connect" | "disconnect"
  property string copied: ""              // ip just copied, shown for a moment

  readonly property string home: Quickshell.env("HOME")
  readonly property string idleDot: Network.idleDot(ts, nord)
  readonly property string tsDot: tsBusy !== "" ? "busy" : Network.dotState(ts.state)
  readonly property string nordDot: nordBusy !== "" ? "busy" : Network.dotState(nord.state)

  function refresh() {
    var full = net.viewers > 0
    if (!tsProc.running) { tsProc.command = Network.tailscaleStatusArgs(full); tsProc.running = true }
    if (!nordProc.running && nordBusy === "") { nordProc.command = Network.nordArgs(net.home, "status"); nordProc.running = true }
  }

  function toggleTailscale() {
    var cmd = Network.tailscaleToggleCommand(net.ts)
    if (!cmd || tsAct.running) return
    net.tsBusy = cmd[cmd.length - 1]
    tsAct.command = cmd
    tsAct.running = true
  }

  function toggleNord() {
    var verb = Network.nordToggleVerb(net.nord)
    if (!verb || nordAct.running) return
    net.nordBusy = verb
    nordAct.command = Network.nordArgs(net.home, verb)
    nordAct.running = true
  }

  function copyIp(ip) {
    if (!ip) return
    Quickshell.execDetached(["/usr/bin/wl-copy", String(ip)])
    net.copied = String(ip)
    copiedTimer.restart()
  }
  Timer { id: copiedTimer; interval: 1500; onTriggered: net.copied = "" }

  onViewersChanged: if (viewers > 0) refresh()

  Process {
    id: tsProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 8000000) net.ts = Network.mergePeers(net.ts, Network.parseTailscale(text))
    }
    onExited: function(code) { if (code !== 0) net.ts = Network.parseTailscale("") }
  }

  Process {
    id: nordProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 100000 && net.nordBusy === "") net.nord = Network.parseNord(text)
    }
  }

  Process {
    id: tsAct
    onExited: { net.tsBusy = ""; net.refresh() }
  }

  // The probe prints the fresh status after connect/disconnect.
  Process {
    id: nordAct
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 100000) { var n = Network.parseNord(text); if (n.ok) net.nord = n }
    }
    onExited: { net.nordBusy = ""; net.refresh() }
  }

  Timer {
    interval: 60000
    running: net.viewers === 0
    repeat: true
    triggeredOnStart: true
    onTriggered: net.refresh()
  }
  Timer {
    interval: 8000
    running: net.viewers > 0
    repeat: true
    onTriggered: net.refresh()
  }
}
