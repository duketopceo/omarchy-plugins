import QtQuick
import Quickshell
import Quickshell.Io
import "Network.js" as Network

// Live state and actions for the Network tab's two cards. Polls only while
// `active` (the tab is visible); every action updates the view optimistically
// first, then re-reads the real state when the command exits.
//   Tailscale: `tailscale status --json`, `debug prefs` (operator check),
//              `up|down`, `set --exit-node=<ip>`
//   NordVPN:   `nordvpn status` / `nordvpn countries` (text), connect and
//              disconnect through the nordvpn plugin's probe.
Scope {
  id: ops

  property bool active: false
  property var favoritesSetting: null          // value of network.nordFavorites
  signal favoritesWanted(var list)

  readonly property string home: Quickshell.env("HOME")
  readonly property string user: Quickshell.env("USER")

  property var ts: Network.parseTailscale("")
  property var nord: Network.parseNordText("")
  property var countries: []
  property bool exitFeasible: false
  property string tsDesired: ""                // "" | "up" | "down"
  property string exitDesired: ""              // "" | "none" | ip
  property string nordDesired: ""              // "" | "connect" | "disconnect"
  property string nordTarget: ""               // country id being connected to
  property bool nordLoaded: false
  property bool tsLoaded: false
  property double now: Date.now()

  readonly property bool tsOn: tsDesired === "up" ? true : tsDesired === "down" ? false : ts.running
  readonly property bool tsBusy: tsAct.running
  readonly property bool nordOn: nordDesired === "connect" ? true : nordDesired === "disconnect" ? false : (nord.state === "connected" || nord.state === "connecting")
  readonly property bool nordBusy: nordAct.running
  readonly property var favorites: Network.cleanFavorites(favoritesSetting)
  readonly property string exitName: exitDesired === "none" ? "" : exitDesired !== "" ? exitLabel(exitDesired) : (ts.exitNode ? ts.exitNode.name : "")

  function exitLabel(ip) {
    var o = ts.exitOptions
    for (var i = 0; i < o.length; i++) if (o[i].ip === ip) return o[i].name
    return ip
  }

  function refresh() {
    now = Date.now()
    if (!tsProc.running) { tsProc.command = Network.tailscaleStatusArgs(true); tsProc.running = true }
    if (!nordProc.running && !nordAct.running) { nordProc.command = Network.nordStatusArgs(); nordProc.running = true }
  }

  function toggleTailscale() {
    var cmd = Network.tailscaleToggleCommand(ts)
    if (!cmd || tsAct.running) return
    tsDesired = cmd[cmd.length - 1]
    tsAct.command = cmd
    tsAct.running = true
  }

  function setExitNode(ip) {
    if (!exitFeasible || exitAct.running) return
    exitDesired = ip === "" ? "none" : ip
    exitAct.command = Network.exitNodeArgs(ip)
    exitAct.running = true
  }

  // `country` is a countries-list id such as United_States; "" = recommended.
  function connectNord(country) {
    if (nordAct.running) return
    nordDesired = "connect"
    nordTarget = country || ""
    nordAct.command = Network.nordConnectArgs(home, country)
    nordAct.running = true
  }

  function disconnectNord() {
    if (nordAct.running) return
    nordDesired = "disconnect"
    nordTarget = ""
    nordAct.command = Network.nordArgs(home, "disconnect")
    nordAct.running = true
  }

  function toggleNord() {
    if (nordOn) disconnectNord()
    else connectNord("")
  }

  function toggleFavorite(country) { favoritesWanted(Network.toggleFavorite(favorites, country)) }

  function copy(text) {
    if (!text) return
    Quickshell.execDetached(["/usr/bin/wl-copy", String(text)])
  }

  onActiveChanged: {
    if (!active) return
    refresh()
    if (!prefsProc.running) { prefsProc.command = Network.tailscalePrefsArgs(); prefsProc.running = true }
    if (countries.length === 0 && !countriesProc.running) { countriesProc.command = Network.nordCountriesArgs(); countriesProc.running = true }
  }

  Process {
    id: tsProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (!text || text.length > 8000000) return
        var t = Network.parseTailscale(text)
        if (tsAct.running || exitAct.running) return
        ops.ts = t
        ops.tsLoaded = true
        ops.tsDesired = ""
        ops.exitDesired = ""
      }
    }
    onExited: function(code) { if (code !== 0 && !tsAct.running) { ops.ts = Network.parseTailscale(""); ops.tsLoaded = true } }
  }

  Process {
    id: prefsProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: ops.exitFeasible = Network.exitNodeFeasible(text, ops.user)
    }
  }

  Process {
    id: nordProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (nordAct.running || text.length > 100000) return
        ops.nord = Network.parseNordText(text)
        ops.nordLoaded = true
        ops.nordDesired = ""
        ops.nordTarget = ""
      }
    }
  }

  Process {
    id: countriesProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text.length < 100000) ops.countries = Network.parseCountries(text)
    }
  }

  Process {
    id: tsAct
    onExited: { settle.restart(); ops.refresh() }
  }
  Process {
    id: exitAct
    onExited: { settle.restart(); ops.refresh() }
  }
  Process {
    id: nordAct
    onExited: { settle.restart(); ops.refresh() }
  }

  // Safety net: an optimistic value never outlives the re-read by long.
  Timer {
    id: settle
    interval: 12000
    onTriggered: { ops.tsDesired = ""; ops.exitDesired = ""; ops.nordDesired = ""; ops.nordTarget = "" }
  }

  Timer {
    interval: 6000
    running: ops.active
    repeat: true
    onTriggered: ops.refresh()
  }
}
