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
import "Pages.js" as Pages
import "More.js" as More
import "Agents.js" as Agents
import "Status.js" as Status

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
  // The pages open cards are showing now, e.g. ["home"]; kept up to date by the windows.
  property var openPages: []
  function pageOpen(id) { return root.openPages.indexOf(id) >= 0 }

  readonly property string pluginId: manifest && manifest.id ? String(manifest.id) : "io.github.duketopceo.island"

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
    webArt: root.settings.webArt === true
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

  CalendarSource {
    id: calendar
    enabled: root.settings.calendar === true
  }

  // ---- indicators: mic and camera in use, Do Not Disturb (R8-R10) ----
  PrivacySource {
    id: privacy
    enabled: root.settings.privacy === true
    // Omarchy's OSD already shows mic mute unless the owner handed it over.
    watchMute: root.hudEffective && root.settings.alerts === true
    // Home's mic-mute toggle reads the same state while a card is open.
    trackMute: root.opened
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
  // ---- pages (Pages.js): sources run only while their page needs them ----
  readonly property string helperDir: decodeURIComponent(Qt.resolvedUrl("bin").toString().replace("file://", ""))
  property real weatherAt: 0

  // Home: battery, Tailscale and VPN dots; once at load and on every open.
  PollSource {
    id: homeStatus
    command: ["/usr/bin/python3", root.helperDir + "/island-status", "home"]
    Component.onCompleted: homeStatus.refresh()
  }
  readonly property var homeDots: Status.homeDots(homeStatus.data)

  // Weather through Omarchy's own command, only when Omarchy's weather widget
  // is in the bar (its service is already polled), at most every 30 minutes.
  readonly property bool weatherOn: root.settings.weather === true && root.shellText.indexOf('"omarchy.weather"') >= 0
  PollSource {
    id: weatherSrc
    json: false
    command: ["omarchy-weather-status"]
  }
  readonly property var weather: root.weatherOn ? Status.weather(weatherSrc.text) : null
  function refreshWeather() {
    if (!root.weatherOn || Date.now() - root.weatherAt < 1800000) return
    root.weatherAt = Date.now()
    weatherSrc.refresh()
  }

  // System: once at load (so the page sizes from real rows), then every 2 s
  // while a System page is open.
  PollSource {
    id: systemStatus
    command: ["/usr/bin/python3", root.helperDir + "/island-status", "system"]
    active: root.pageOpen("system")
    interval: 2000
    Component.onCompleted: systemStatus.refresh()
  }
  readonly property var systemRows: Status.systemRows(systemStatus.data)
  readonly property bool fanPanel: systemStatus.data !== null && systemStatus.data.fanPanel === true
  function openFanPanel() { Quickshell.execDetached(["omarchy-shell", "shell", "toggle", "lukedaduke.fan"]) }

  // Agents: herdr and Claude Code sessions; at load (detection), on open, and
  // every 3 s while an Agents page is open.
  PollSource {
    id: agentsSrc
    command: ["/usr/bin/python3", root.helperDir + "/island-agents"]
    active: root.settings.agents === true && root.pageOpen("agents")
    interval: 3000
    Component.onCompleted: agentsSrc.refresh()
  }
  readonly property var agentRows: root.settings.agents === true ? Agents.rows(agentsSrc.data) : []
  function focusAgent(row) {
    var cmds = Agents.focusCommands(row)
    for (var i = 0; i < cmds.length; i++) Quickshell.execDetached(cmds[i])
  }

  // More: Dayflow status and Snapdex screenshots; at load and on every open.
  PollSource {
    id: moreStatus
    command: ["/usr/bin/python3", root.helperDir + "/island-status", "more"]
    Component.onCompleted: moreStatus.refresh()
    onUpdated: root.shotsModel = More.shotsStep(root.shotsModel, moreStatus.data ? moreStatus.data.shots : null)
  }
  readonly property var dayflow: root.settings.dayflow === true && moreStatus.data ? moreStatus.data.dayflow : null
  readonly property var dayflowRows: More.dayflowRows(root.dayflow)
  readonly property var shots: root.settings.shots === true && moreStatus.data ? moreStatus.data.shots : null
  readonly property var shotRows: More.shotsRows(root.shots)
  property var shotsModel: More.shotsInitial()
  function markShotsSeen() { root.shotsModel = More.shotsSeen(root.shotsModel) }
  // Opens one Snapdex screenshot; the name comes from Snapdex's own index.
  function openShot(name) {
    var n = String(name || "")
    if (n === "" || n.indexOf("/") >= 0 || n.charAt(0) === ".") return
    Quickshell.execDetached(["xdg-open", Quickshell.env("HOME") + "/Pictures/Screenshots/" + n])
  }

  // Messages: Blip's own state file, counts only (More.js).
  property string blipText: ""
  FileView {
    id: blipFile
    path: root.settings.messages === true ? Quickshell.env("HOME") + "/.local/state/blip/state.json" : ""
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.blipText = blipFile.text()
    onLoadFailed: root.blipText = ""
  }
  readonly property var messages: More.messages(root.settings.messages === true ? root.blipText : "")
  function openBlip() { Quickshell.execDetached(["omarchy-shell", "shell", "toggle", "nixfred.blip"]) }

  // Mic mute quick toggle (Home): the default source through wpctl.
  readonly property bool micMuteAvailable: root.tools.wpctl === true
  readonly property bool micMuted: privacy.micMuted
  function toggleMicMute() {
    if (root.micMuteAvailable) Quickshell.execDetached(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"])
  }

  // The media activity whichever slot it holds, for the Music page.
  readonly property var mediaActivity: media.activity

  readonly property var pageAvail: ({
    music: root.settings.media === true && media.activity !== null && media.activity.active === true,
    agents: root.settings.agents === true && agentsSrc.data !== null && (agentsSrc.data.herdr === true || agentsSrc.data.claude === true),
    messages: root.settings.messages === true && root.messages.ok,
    dayflow: root.dayflow !== null,
    shots: root.shots !== null
  })
  readonly property var pageLive: ({
    messages: root.messages.live,
    shots: More.shotsLive(root.shotsModel),
    dayflow: More.dayflowLive(root.dayflow)
  })

  onOpenedChanged: {
    if (!root.opened) return
    homeStatus.refresh()
    moreStatus.refresh()
    if (root.settings.agents === true) agentsSrc.refresh()
  }
  onOpenPagesChanged: {
    if (root.pageOpen("home")) root.refreshWeather()
    if (root.pageOpen("shots")) root.markShotsSeen()
  }

  readonly property var activities: [dictation.activity, screenrec.activity, hud.activity, root.timerActivity,
                                     media.activity, charging.activity, bluetooth.activity,
                                     calendar.activity]
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
    if (id === "calendar" && action === "join") { calendar.join(); return "ok" }
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
    var pages = []
    var list = windows.instances
    for (var i = 0; i < list.length; i++) {
      if (!list[i].cardShown || list[i].destroying) continue
      any = true
      if (pages.indexOf(list[i].page) < 0) pages.push(list[i].page)
    }
    if (pages.join(",") !== root.openPages.join(",")) root.openPages = pages
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
    return Pages.normalize(page)
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
                       micMuted: root.micMuted }
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
