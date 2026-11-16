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
import "Alert.js" as Alert
import "Dnd.js" as Dnd

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

  // ---- live activities ----
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
    onCharged: function(m) { root.pushAlert(Alert.charging(m.capacity, m.timeToFull)) }
  }

  ScreenRecordSource {
    id: screenrec
    enabled: root.settings.screenRecording === true && root.tools["omarchy-capture-screenrecording"] === true
  }

  BluetoothSource {
    id: bluetooth
    enabled: root.settings.bluetooth === true
    onConnected: function(e) { root.pushAlert(Alert.bluetooth(e.name, e.battery)) }
  }

  // ---- indicators: mic and camera in use, Do Not Disturb (R8-R10) ----
  PrivacySource {
    id: privacy
    enabled: root.settings.privacy === true
    // Omarchy's OSD already shows mic mute unless the owner handed it over.
    watchMute: root.hudEffective && root.settings.alerts === true
    onMicMuteFlipped: function(muted) { root.pushAlert(Alert.mic(muted)) }
  }
  readonly property bool micInUse: privacy.micInUse
  readonly property bool cameraInUse: privacy.cameraInUse

  readonly property bool dndAvailable: root.settings.dnd === true && Dnd.available(root.shellText)
  DndSource {
    id: dnd
    enabled: root.dndAvailable
    canToggle: root.tools["omarchy-toggle-notification-silencing"] === true
    onToggled: function(edge) { root.pushAlert(Alert.dnd(edge === "on")) }
  }
  readonly property bool dndOn: dnd.on
  function toggleDnd() { dnd.toggle() }

  readonly property color mediaTint: media.tint

  // ---- transient alerts (KTD7) ----
  // At most one; each window shows it, gates it and times its end (KTD7).
  property var alertModel: Alert.initial()
  function pushAlert(a) {
    if (root.settings.alerts !== true || !a) return
    root.alertModel = Alert.push(root.alertModel, a, Date.now())
  }
  // Sample alerts for live checks and previews: `preview charging`.
  function previewAlert(kind) {
    var samples = {
      charging: Alert.charging(62, 4320), timer: Alert.timerDone(),
      bluetooth: Alert.bluetooth("Headphones", 0.8), dnd: Alert.dnd(true), mic: Alert.mic(true)
    }
    if (!samples[kind]) return "unknown"
    root.pushAlert(samples[kind])
    return root.settings.alerts === true ? "ok" : "off"
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
    if (before !== "done" && root.timerModel.state === "done") {
      root.pushAlert(Alert.timerDone())
      if (root.tools["notify-send"] === true)
        Quickshell.execDetached(["/usr/bin/notify-send", "-a", "Island", "Timer done", "Your Island timer finished."])
    }
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
  readonly property var activities: [dictation.activity, screenrec.activity, hud.activity, root.timerActivity,
                                     media.activity, charging.activity, bluetooth.activity]
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
    if (id === "screenrec" && action === "stop") { screenrec.stop(); return "ok" }
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
    for (var i = 0; i < list.length; i++) if (list[i].cardShown && !list[i].destroying) any = true
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
    var activities = root.activitiesJson()
    var indicators = { mic: root.micInUse, camera: root.cameraInUse, dnd: root.dndOn,
                       dndAvailable: root.dndAvailable, recording: screenrec.model.recording === true,
                       mediaTint: String(root.mediaTint) }
    for (var i = 0; i < list.length; i++) {
      var s = list[i].snapshot()
      s.activities = activities
      s.indicators = indicators
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
    // Seeking needs a position, which this call has no argument for, so it is
    // card-only (a 0 here would silently rewind the track).
    function act(id: string, action: string): string {
      if (action === "seek") return "unknown"
      return root.act(id, action, 0)
    }
    // Starts the Island's timer: `timer 5m`, `timer 90s`, `timer 1h30m`.
    function timer(spec: string): string { return root.startTimer(spec) }
    // Shows a sample alert: charging, timer, bluetooth, dnd or mic.
    function preview(kind: string): string { return root.previewAlert(kind) }
  }
}
