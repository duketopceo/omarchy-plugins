import QtQuick 6.11
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "Settings.js" as Settings
import "Entry.js" as Entry
import "Screens.js" as Screens
import "Fullscreen.js" as Fullscreen
import "Timer.js" as IslandTimer
import "Hud.js" as Hud

// The Island's root: loads settings and the capability probe, creates one
// IslandWindow per screen, watches fullscreen state, and owns the single
// "island" IPC target. The shell's summon contract (open/close/toggle/opened)
// goes through the same paths as IPC.
Item {
  id: root

  property var shell: null
  property var manifest: null
  // True while any screen's card is shown; kept up to date by the windows.
  property bool opened: false

  readonly property string pluginId: manifest && manifest.id ? String(manifest.id) : "io.github.duketopceo.island"
  readonly property var pages: ["now", "settings"]

  // ---- clock, re-armed to each minute boundary ----
  property date now: new Date()
  function msToNextMinute() {
    var d = new Date()
    return 60000 - (d.getSeconds() * 1000 + d.getMilliseconds()) + 50
  }
  Timer {
    id: clock
    interval: 60000
    repeat: false
    running: true
    onTriggered: {
      root.now = new Date()
      clock.interval = root.msToNextMinute()
      clock.restart()
    }
  }
  Component.onCompleted: {
    clock.interval = root.msToNextMinute()
    clock.restart()
    Hyprland.refreshToplevels()
    hyprSettle.restart()
  }

  // ---- settings: read through a file watch, written through updateEntryInline ----
  property string shellText: ""
  readonly property var resolved: Settings.resolve(root.shellText, root.pluginId)
  readonly property var settings: root.resolved.settings
  // A primitive, so an unrelated shell.json edit does not re-run each window's geometry.
  readonly property int cameraWidth: root.settings ? (root.settings.cameraWidth || 0) : 0
  readonly property bool entryExists: root.resolved.entryExists

  FileView {
    id: shellFile
    path: Quickshell.env("HOME") + "/.config/omarchy/shell.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.shellText = shellFile.text()
    onLoadFailed: root.shellText = ""
  }

  // "saved" | "unchanged" | "noentry". Writes only this plugin's own entry
  // (the shell's updateEntryInline replaces exactly that entry).
  function saveSettings(edit) {
    var current = Entry.find(root.shellText, root.pluginId)
    if (!current) return "noentry"
    var merged = Settings.merge(current, edit, root.pluginId)
    if (!Settings.changed(current, merged)) return "unchanged"
    var ok = false
    try { ok = root.shell.updateEntryInline(root.pluginId, merged) === true } catch (e) { ok = false }
    return ok ? "saved" : "noentry"
  }

  // ---- capability probe, once at load ----
  property var probe: ({})
  readonly property string probePath: decodeURIComponent(Qt.resolvedUrl("bin/island-probe").toString().replace("file://", ""))

  Process {
    id: probeProc
    command: [root.probePath]
    running: true
    stdout: StdioCollector {
      onStreamFinished: {
        try { root.probe = JSON.parse(text) } catch (e) { root.probe = ({}) }
      }
    }
  }

  // ---- live activities (P2) ----
  readonly property var tools: root.probe && root.probe.tools ? root.probe.tools : ({})
  readonly property var power: root.probe && root.probe.power ? root.probe.power : ({})

  DictationSource {
    id: dictation
    enabled: root.settings.dictation === true && root.tools.wordink === true
  }

  MediaSource {
    id: media
    enabled: root.settings.media === true
    cardShown: root.opened
  }

  ChargingSource {
    id: charging
    enabled: root.settings.charging === true
    battery: root.power.batteries && root.power.batteries.length > 0 ? String(root.power.batteries[0]) : ""
  }

  readonly property bool hudEffective: Hud.effective(root.settings, root.shellText)

  HudSource {
    id: hud
    effective: root.hudEffective
    backlight: root.power.backlights && root.power.backlights.length > 0 ? String(root.power.backlights[0]) : ""
  }

  // The Island's own timer (KTD6): an end time, redrawn at each whole second.
  property var timerModel: IslandTimer.initial()
  property real timerNow: Date.now()
  readonly property var timerActivity: IslandTimer.activity(root.timerModel, root.timerNow)

  function timerUpdate(next) {
    var t = Date.now()
    var before = root.timerModel.state
    root.timerModel = IslandTimer.tick(next, t)
    root.timerNow = t
    if (before !== "done" && root.timerModel.state === "done" && root.tools["notify-send"] === true)
      Quickshell.execDetached(["/usr/bin/notify-send", "-a", "Island", "Timer done", "Your Island timer finished."])
    var wait = IslandTimer.nextTickMs(root.timerModel, t)
    if (wait > 0) { timerTick.interval = wait; timerTick.restart() }
    else timerTick.stop()
  }

  // One-shot, re-armed to the next whole second while a timer shows.
  Timer {
    id: timerTick
    interval: 1000 // always overwritten by timerUpdate() before it starts
    onTriggered: root.timerUpdate(root.timerModel)
  }

  // "ok" | "invalid": starts (or restarts) the timer from a spec like 90s, 5m, 1h30m.
  function startTimer(spec) {
    var ms = IslandTimer.parse(String(spec || ""))
    if (ms <= 0) return "invalid"
    root.timerUpdate(IslandTimer.start(IslandTimer.initial(), ms, Date.now()))
    return "ok"
  }

  // Every source's activity in one list; Activity.js lays it out per window.
  readonly property var activities: [dictation.activity, hud.activity, root.timerActivity, media.activity, charging.activity]
  // When the list last changed, for Activity.js's expiry check.
  property real activityClock: Date.now()
  onActivitiesChanged: root.activityClock = Date.now()

  // One entry point for card controls and IPC (KTD11). Returns "ok" or "unknown".
  function act(id, action, value) {
    var now = Date.now()
    if (id === "dictation" && action === "stop") {
      // Release keyboard focus first so the paste lands where the owner dictated.
      var list = windows.instances
      for (var i = 0; i < list.length; i++) list[i].unfocus()
      dictation.stop()
      return "ok"
    }
    if (id === "media") {
      if (action === "toggle") { media.toggle(); return "ok" }
      if (action === "next") { media.next(); return "ok" }
      if (action === "previous") { media.previous(); return "ok" }
      if (action === "seek") { media.seek(Number(value)); return "ok" }
    }
    if (id === "timer") {
      if (action === "pause") { root.timerUpdate(IslandTimer.pause(root.timerModel, now)); return "ok" }
      if (action === "resume") { root.timerUpdate(IslandTimer.resume(root.timerModel, now)); return "ok" }
      if (action === "add") { root.timerUpdate(IslandTimer.add(root.timerModel, 60000, now)); return "ok" }
      if (action === "cancel") { root.timerUpdate(IslandTimer.cancel(root.timerModel)); return "ok" }
    }
    return "unknown"
  }

  function activitiesJson() {
    var out = []
    var list = root.activities
    for (var i = 0; i < list.length; i++) {
      var a = list[i]
      if (a && a.active) out.push({ id: a.id, priority: a.priority, text: a.text, card: a.card })
    }
    return out
  }

  // ---- the pointer position, read on demand ----
  property var cursorWaiters: []

  // Calls cb(pos) once with { x, y }, or null when it cannot be read.
  function readCursor(cb) {
    root.cursorWaiters.push(cb)
    if (!cursorProc.running) cursorProc.running = true
  }
  function cursorDone(text) {
    var pos = Screens.parseCursor(text)
    var waiters = root.cursorWaiters
    root.cursorWaiters = []
    for (var i = 0; i < waiters.length; i++) waiters[i](pos)
  }

  Process {
    id: cursorProc
    command: ["hyprctl", "cursorpos", "-j"]
    stdout: StdioCollector { onStreamFinished: root.cursorDone(text) }
    // A request that arrived after the stream ended gets a fresh read.
    onExited: if (root.cursorWaiters.length > 0) cursorProc.running = true
  }

  // ---- fullscreen watcher (KTD6) ----
  // Bumped after Hyprland's window snapshot refreshes so fullscreenOn() re-evaluates.
  property int hyprRevision: 0

  function fullscreenOn(screen) {
    var revision = root.hyprRevision
    var monitor = screen ? Hyprland.monitorFor(screen) : null
    var workspace = monitor ? monitor.activeWorkspace : null
    if (!workspace || !workspace.hasFullscreen) return false
    var list = workspace.toplevels ? workspace.toplevels.values : []
    var ipcs = []
    for (var i = 0; i < list.length; i++) ipcs.push(list[i].lastIpcObject || ({}))
    return Fullscreen.isReal(workspace.hasFullscreen, ipcs)
  }

  Connections {
    target: Hyprland
    function onRawEvent(event) {
      if (Fullscreen.isRefreshEvent(event.name)) hyprRefresh.restart()
    }
  }
  // Debounce a fullscreen burst (100 ms), then let Hyprland's IPC answer land
  // (250 ms) before re-reading; both are one-shot, as in Omarchy's notifications.
  Timer {
    id: hyprRefresh
    interval: 100
    onTriggered: { Hyprland.refreshToplevels(); hyprSettle.restart() }
  }
  Timer {
    id: hyprSettle
    interval: 250
    onTriggered: root.hyprRevision++
  }

  // ---- one window per screen ----
  Variants {
    id: windows
    model: Quickshell.screens

    IslandWindow {
      island: root
    }
  }

  function refreshOpened() {
    var any = false
    var list = windows.instances
    for (var i = 0; i < list.length; i++) if (list[i].cardShown) any = true
    root.opened = any
  }

  function windowFor(name) {
    var list = windows.instances
    for (var i = 0; i < list.length; i++) if (list[i].screen && list[i].screen.name === name) return list[i]
    return null
  }

  function screenRects() {
    var out = []
    for (var i = 0; i < Quickshell.screens.length; i++) {
      var s = Quickshell.screens[i]
      out.push({ name: String(s.name), x: s.x, y: s.y, width: s.width, height: s.height })
    }
    return out
  }

  // Runs fn(window) on the screen under the pointer; the focused monitor only
  // when the pointer position cannot be read.
  function withTarget(fn) {
    root.readCursor(function(pos) {
      var focused = Hyprland.focusedMonitor
      var name = Screens.pick(root.screenRects(), pos, focused ? String(focused.name) : "")
      var win = name ? root.windowFor(name) : null
      if (win) fn(win)
    })
  }

  function pageOf(payload) {
    var page = ""
    try {
      var obj = JSON.parse(payload)
      page = obj && typeof obj === "object" ? String(obj.page || "") : String(obj || "")
    } catch (e) {
      page = String(payload || "")
    }
    return root.pages.indexOf(page) >= 0 ? page : ""
  }

  function openPage(page) {
    root.withTarget(function(win) { win.summon(page) })
  }

  function open(payload) { root.openPage(root.pageOf(payload)) }

  function close() {
    var list = windows.instances
    for (var i = 0; i < list.length; i++) list[i].closeByIpc()
  }

  function toggle() {
    root.withTarget(function(win) {
      if (win.cardShown) win.closeByIpc()
      else win.summon("")
    })
  }

  function focusCard() {
    root.withTarget(function(win) { win.focusCard() })
  }

  function stateJson() {
    var out = []
    var list = windows.instances
    for (var i = 0; i < list.length; i++) {
      var s = list[i].snapshot()
      s.activities = root.activitiesJson()
      out.push(s)
    }
    return JSON.stringify(out)
  }

  IpcHandler {
    target: "island"

    function toggle(): void { root.toggle() }
    function open(page: string): void { root.openPage(root.pageOf(page)) }
    function close(): void { root.close() }
    function focus(): void { root.focusCard() }
    function state(): string { return root.stateJson() }
    // Same actions as the card's controls, e.g. `act media toggle`, `act timer add`.
    function act(id: string, action: string): string { return root.act(id, action, 0) }
    // Starts the Island's timer: `timer 5m`, `timer 90s`, `timer 1h30m`.
    function timer(spec: string): string { return root.startTimer(spec) }
  }
}
