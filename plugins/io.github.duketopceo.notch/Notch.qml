import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Services.Mpris
import qs.Commons as Commons
import "Model.js" as Model
import "Watchlist.js" as Watchlist
import "Expand.js" as Expand
import "Tabs.js" as Tabs  // U5 hover expand
import "Settings.js" as Settings
import "Activity.js" as Activity
import "Plugins.js" as Plugins
import "Agents.js" as Agents
import "Screenshots.js" as Screenshots
import "Motion.js" as Motion
import "Dayflow.js" as Dayflow  // local: dayflow integration
import "Theme.js" as Theme

// Notch island: one small layer-shell window per screen at top center.
// On a panel with a camera cutout (Omarchy's display-cutouts.json) it hugs
// the camera and uses the space either side of it; elsewhere it is a
// virtual notch. Idle content: clock and date, with weather sliding in.
Item {
  id: root

  // Injected by the shell's panel loader.
  property var shell: null
  property var manifest: null

  readonly property string pluginDir: {
    var p = Qt.resolvedUrl(".").toString()
    if (p.indexOf("file://") === 0) p = p.substring(7)
    if (p.length > 1 && p.charAt(p.length - 1) === "/") p = p.substring(0, p.length - 1)
    return p
  }

  // ------------------------------------------------------------ settings
  // Stored in this plugin's entry of shell.json (`plugins[]`), edited from the
  // Settings tab. Missing or invalid values fall back to Settings.DEFAULTS.

  readonly property string pluginId: manifest && manifest.id ? String(manifest.id) : "io.github.duketopceo.notch"

  // The injected shell config when present, else shell.json read directly.
  property var fileConfig: null
  FileView {
    id: shellJson
    path: Quickshell.env("HOME") + "/.config/omarchy/shell.json"
    watchChanges: true
    printErrors: false
    onLoaded: { try { root.fileConfig = JSON.parse(text()) } catch (e) { root.fileConfig = null } }
    onLoadFailed: root.fileConfig = null
    onFileChanged: reload()
  }
  readonly property var shellConfig: shell && shell.shellConfig ? shell.shellConfig : fileConfig

  // Values just set from the UI, so they show even before the config reloads.
  property var pending: ({})
  readonly property var settings: Settings.resolve(Settings.pluginEntry(shellConfig, pluginId), pending)

  // Theme (Theme.js): Swift follows the live Omarchy palette, Pxl pins its
  // own retro tokens. Recomputes on load and whenever the Settings tab
  // changes `theme` (settings is reactive via shellConfig/pending).
  readonly property var themeObj: Theme.resolve(settings.theme)
  readonly property string themeId: themeObj.id
  Binding { target: Tk; property: "id"; value: root.themeId }
  Binding { target: Tk; property: "reduce"; value: root.reduceMotion }

  function toggleTheme() { setSetting("theme", themeId === "pxl" ? "swift" : "pxl") }

  function setSetting(key, value) {
    var copy = {}
    for (var k in pending) copy[k] = pending[k]
    copy[key] = value
    pending = copy
    if (!shell || typeof shell.mutateShellConfig !== "function") return
    var patch = {}
    patch[key] = value
    shell.mutateShellConfig(Settings.settingsMutator(pluginId, patch))
  }

  // Wisp: open its panel through the shell (needs its bar widget live); if the
  // shell cannot, fall back to Wisp's own click action, toggle listening.
  function openWisp() { openPluginChecked("io.github.duketopceo.wisp", [Quickshell.env("HOME") + "/.local/bin/wisp-trigger"]) }


  // Tray-section plugins have no live bar widget (the notch slims the bar and
  // drops the tray hosts), so the shell's summon and their IPC target are
  // gone, and a third-party plugin cannot reach the tray's widget registry.
  // The notch therefore hosts one invisible instance of each tray widget
  // itself, loaded straight from the plugin's own barWidget entry point with
  // bar, moduleName and settings injected as the bar does. The instance owns
  // the plugin's IPC target; its panel opens through its own toggle().
  property var hostedItems: ({})
  function openHosted(id) {
    var item = hostedItems[id]
    if (!item || typeof item.toggle !== "function") return false
    item.toggle()
    return true
  }
  Repeater {
    model: Plugins.trayIds(root.shellConfig).concat(["lukedaduke.lidguard"]).filter(function(i) { return i !== "io.github.twiking.omacontrol" })  // omacontrol keeps its own live IPC target
    delegate: Item {
      id: hostRow
      required property var modelData
      readonly property string widgetId: String(modelData)
      readonly property string pluginDir: Quickshell.env("HOME") + "/.config/omarchy/plugins/" + widgetId
      readonly property string entryFile: {
        try { return String(JSON.parse(manifestFile.text()).entryPoints.barWidget || "") } catch (e) { return "" }
      }
      width: 1; height: 1; opacity: 0
      FileView { id: manifestFile; path: hostRow.pluginDir + "/manifest.json" }
      function entrySettings() {
        var list = root.shellConfig && root.shellConfig.bar && root.shellConfig.bar.layout ? root.shellConfig.bar.layout.tray : null
        for (var i = 0; list && i < list.length; i++) if (list[i] && list[i].id === widgetId) return list[i]
        return ({})
      }
      function inject() {
        var t = loader.item
        if (!t) return
        if ("bar" in t) t.bar = root.shell ? root.shell.bar : null
        if ("moduleName" in t) t.moduleName = widgetId
        if ("settings" in t) t.settings = hostRow.entrySettings()
        var copy = {}
        for (var k in root.hostedItems) copy[k] = root.hostedItems[k]
        copy[widgetId] = t
        root.hostedItems = copy
      }
      Loader {
        id: loader
        active: hostRow.entryFile !== ""
        source: active ? "file://" + hostRow.pluginDir + "/" + hostRow.entryFile : ""
        onLoaded: { hostRow.inject(); Qt.callLater(hostRow.inject) }
        onStatusChanged: if (status === Loader.Error) console.warn("notch-host: load failed", hostRow.widgetId)
      }
    }
  }

  // Open a plugin's panel. Tries the shell's summon, then the plugin's own IPC
  // target, then a plugin-specific fallback (see Plugins.openChain).
  property var openSteps: []
  property int openIndex: 0
  property string openFailed: ""   // id whose panel could not be opened, for ~2 s
  Timer { id: openFailedClear; interval: 2200; onTriggered: root.openFailed = "" }
  property string openingId: ""
  function openPlugin(id) { openPluginChecked(id, null) }
  function openPluginChecked(id, fallback) {
    if (opener.running) return
    openingId = String(id)
    if (openHosted(String(id))) return
    openSteps = Plugins.openChain(String(id), fallback)
    openIndex = 0
    runOpenStep()
  }
  function runOpenStep() {
    if (openIndex >= openSteps.length) { openFailed = openingId; openFailedClear.restart(); return }
    opener.command = openSteps[openIndex].cmd
    opener.running = true
  }
  Process {
    id: opener
    stdout: StdioCollector { id: openerOut }
    onExited: function(code) {
      if (Plugins.stepOk(root.openSteps[root.openIndex], code, openerOut.text)) return
      root.openIndex += 1
      root.runOpenStep()
    }
  }

  readonly property int autoCameraWidth: 200   // logical px, 14"/16" MacBook Pro
  readonly property int cameraWidth: settings.cameraWidth > 0 ? settings.cameraWidth : autoCameraWidth
  readonly property int earWidth: 96       // content room either side of the camera
  readonly property int earOuter: 12         // gap between ear content and the island's outer edge
  readonly property int earMargin: 12     // px kept clear of the nearest bar widget
  readonly property int earCap: 280        // widest an ear may grow
  readonly property int earPad: 8          // gap between ear text and the camera edge
  // Camera width override from Settings (0 = auto-detect from the device model).
  readonly property int cameraOverride: settings.cameraWidth > 0 ? settings.cameraWidth : 0
  readonly property int virtualWidth: 300  // island width on screens without a cutout
  readonly property int clockSeconds: settings.clockSeconds
  readonly property int slideSeconds: settings.slideSeconds

  readonly property color islandColor: themeObj.island
  readonly property color textColor: themeObj.text || Commons.Color.foreground
  readonly property color dimColor: themeObj.dim || Commons.Color.muted
  readonly property color faintColor: themeObj.faint || Commons.Color.muted
  readonly property color accentColor: themeObj.accent || Commons.Color.accent
  readonly property color urgentColor: themeObj.urgent || Commons.Color.urgent
  readonly property color goodColor: themeObj.good
  readonly property color warnColor: themeObj.warn
  readonly property color badColor: themeObj.bad
  readonly property string fontFamily: Tk.family
  readonly property int islandRadius: themeObj.islandRadius
  readonly property int cardRadius: themeObj.cardRadius
  readonly property int pillRadius: themeObj.pillRadius
  readonly property int barHeight: Commons.Style.bar && Commons.Style.bar.sizeHorizontal > 0 ? Commons.Style.bar.sizeHorizontal : 32



  // ------------------------------------------------------------ data

  property var cutouts: Model.parseCutouts(cutoutFile.text())
  FileView {
    id: cutoutFile
    path: "/usr/share/omarchy-platform/display-cutouts.json"
    blockLoading: true
    printErrors: false
    onLoaded: root.cutouts = Model.parseCutouts(text())
    onLoadFailed: root.cutouts = []
  }

  // Device model from the device tree (NUL-separated compatible strings).
  property string deviceCompatible: ""
  FileView {
    id: compatFile
    path: "/proc/device-tree/compatible"
    blockLoading: true
    printErrors: false
    onLoaded: root.deviceCompatible = text()
    onLoadFailed: root.deviceCompatible = ""
  }

  // Live bar widget geometry (shell debugBarGeometry), used to size the ears.
  property var barWidgets: []
  property string barSig: ""
  function refreshBar() {
    var list = []
    try { list = shell && shell.bar && typeof shell.bar.debugBarGeometry === "function" ? shell.bar.debugBarGeometry() : [] } catch (e) { list = [] }
    if (!Array.isArray(list)) list = []
    var sig = JSON.stringify(list.map(function (w) { return [w.section, w.x, w.width, w.visible] }))
    if (sig === barSig) return
    barSig = sig
    barWidgets = list
  }
  Timer { interval: 2000; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.refreshBar() }

  property var weather: null
  property var quotes: []  // watchlist hook: from the cache "quotes" key
  FileView {
    id: cacheFile
    path: Quickshell.env("HOME") + "/.cache/omarchy/notch.json"
    watchChanges: true
    printErrors: false
    onLoaded: { root.weather = Model.parseWeather(text()); root.quotes = Watchlist.parseQuotes(text()) }  // watchlist hook
    onLoadFailed: root.weather = null
    onFileChanged: reload()
  }

  Process {
    id: fetcher
    command: [root.pluginDir + "/bin/notch-data"].concat(Settings.dataArgs(root.settings))
    onExited: cacheFile.reload()
  }
  // A new temperature unit refetches (the cache is keyed on the unit).
  readonly property string unitName: settings.unitName
  onUnitNameChanged: if (!fetcher.running) fetcher.running = true
  Timer {
    interval: 10 * 60 * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: if (!fetcher.running) fetcher.running = true
  }

  property date now: new Date()
  Timer {
    interval: 1000
    running: true
    repeat: true
    onTriggered: root.now = new Date()
  }

  readonly property string timeText: Qt.formatTime(now, settings.timeFormat)
  readonly property string dateText: Qt.formatDate(now, "ddd d MMM")
  // Now playing (N3): MediaActivity picks the player (fastpotify, then Spotify,
  // then any playing MPRIS player). Registered in `activities` below.
  MediaActivity { id: media }
  readonly property var mediaActivity: media   // read by MediaTab.qml
  readonly property var player: media.active ? media.player : null
  readonly property string mediaText: media.active ? media.text : ""
  readonly property bool mediaShown: activity !== null && activity !== undefined && activity.id === "media"
  readonly property int eqSpace: mediaShown ? 14 : 0   // room for the equalizer glyph

  // WordInk dictation (U4): follows `wordink logs -f`; takes over the side text.
  WordinkActivity { id: dictation }
  readonly property var dictationActivity: dictation

  // Tailscale + NordVPN (v3): idle status dot, Home dots, Network tab.
  NetworkState { id: networkState }
  readonly property var network: networkState

  // Snapdex (v3): flashes the caption of a newly captioned screenshot.
  ScreenshotsActivity { id: shots; enabled: root.settings.snapdex }

  // Dayflow (local customization): work-journal state for the idle slot, Home
  // tile and Dayflow tab; a paused capture shows as a low-priority activity.
  DayflowState { id: dayflowState; enabled: root.settings.dayflow }
  readonly property var dayflow: dayflowState

  // AI usage, shared by Home (and anything else): refreshed at most every 5 min
  // and only when a visible view asks for it.
  property var usage: ({ ok: false, providers: [] })
  property real usageAt: 0
  function refreshUsage() {
    var t = Date.now()
    if (usageProc.running || t - usageAt < 5 * 60 * 1000) return
    usageAt = t
    usageProc.running = true
  }
  Process {
    id: usageProc
    command: [Quickshell.env("HOME") + "/.local/bin/ai-usagebar-omaseal", "usage", "--json"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 500000) root.usage = Agents.parseUsage(text)
    }
  }

  // Blip iMessage (N5): read-only. Flashes for allowlisted senders; MessagesTab reads `notch.messages`.
  MessagesActivity { id: messagesAct }
  readonly property var messages: messagesAct

  // Agents (N4): herdr agent status. AgentsTab reads it via `agentsActivity`.
  AgentsActivity { id: agents }
  readonly property var agentsActivity: agents

  // Activity contract: each entry is { id, active, priority, text, glyph? }.
  // The side text shows the highest-priority active one (ties: first listed),
  // else the idle cycle. Add a new XActivity as one more line, anywhere in
  // the list; order does not matter beyond ties.
  readonly property var activities: [
    { id: "dictation", active: dictation.active, priority: 90, text: dictation.text },
    { id: "media", active: media.active, priority: 50, text: media.text, glyph: media.glyph },
    { id: "agents", active: agents.active, priority: agents.priority, text: agents.text, glyph: agents.glyph },
    { id: "messages", active: messagesAct.active, priority: messagesAct.priority, text: messagesAct.text, glyph: messagesAct.glyph },
    { id: "screenshots", active: root.settings.snapdex && shots.active, priority: shots.priority, text: shots.text, glyph: shots.glyph },
    { id: "dayflow", active: dayflowState.active, priority: dayflowState.priority, text: dayflowState.text, glyph: dayflowState.glyph }
    // activities:end
  ]
  readonly property var activity: Activity.pick(activities)

  readonly property string idleView: Model.idleSlot(now.getTime() / 1000, Dayflow.idleViews((weather && settings.showWeather ? ["weather"] : []).concat(quotes.length && settings.showStocks ? ["watchlist"] : []), settings.dayflow, dayflowState.status, dayflowState.today), slideSeconds)  // the ONE rotating idle slot ("" = date only); time and date never cycle
  readonly property string view: activity ? "activity" : (idleView || "date")
  readonly property bool slotShown: activity !== null && activity !== undefined || idleView !== ""
  readonly property string dateLead: dateText + (slotShown && (sideText !== "" || mediaShown || view === "watchlist") ? " \u00B7" : "")   // "Wed 4 Nov \u00B7" then the slot
  readonly property string weatherText: weather ? weather.temperature + weather.unit : ""
  readonly property string sideText: activity ? Activity.label(activity) : (idleView === "weather" ? weatherText : idleView === "dayflow" ? dayflowState.slot : "")
  readonly property bool showIcon: view === "weather" && weather !== null

  // ------------------------------------------------------------ windows

  // Click-outside-to-close: a pinned (clicked-open) island holds a Hyprland
  // focus grab, the same mechanism Omarchy's popups use; any click outside it
  // clears the grab and collapses it. Nothing covers the screen.
  property var openScreens: ({})
  signal collapseRequested()
  signal openTabRequested(string id, string screenName)
  readonly property bool reduceMotion: Commons.Style.reduceMotion || (settings && settings.reduceMotion === true)
  function primaryScreenName() {
    var list = Quickshell.screens
    for (var i = 0; i < list.length; i++) if (list[i].name === "eDP-1") return "eDP-1"
    return list.length ? list[0].name : ""
  }
  // `qs ipc call notch openTab <id>` pins the island open on a tab (used for screenshots).
  IpcHandler {
    target: "notch"
    function openTab(id: string): void { root.openTabRequested(id, "") }
    function openTabOn(id: string, screenName: string): void { root.openTabRequested(id, screenName) }
    function close(): void { root.collapseRequested() }
    function openPlugin(id: string): void { root.openPlugin(id) }
    function toggleTheme(): void { root.toggleTheme() }
  }
  function setOpen(name, open) {
    if (!!openScreens[name] === open) return
    var copy = {}
    for (var k in openScreens) copy[k] = openScreens[k]
    if (open) copy[name] = true; else delete copy[name]
    openScreens = copy
  }
  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: win
      required property var modelData
      screen: modelData

      readonly property var monitor: Hyprland.monitorFor(modelData)
      readonly property int cut: monitor ? Model.cutoutTop(root.cutouts, modelData.name, modelData.width, {
        width: monitor.width,
        height: monitor.height,
        transform: monitor.lastIpcObject ? monitor.lastIpcObject.transform : 0
      }) : 0
      readonly property bool notched: cut > 0
      readonly property int camW: Model.cameraWidthFor(root.deviceCompatible, monitor ? monitor.width : 0, modelData.width, root.cameraOverride) || Model.SIZES.cameraWidth
      readonly property int earW: Model.earWidthFor(modelData.width)

      // --- U5 hover expand (state machine in Expand.js, UI in ExpandedPanel.qml) ---
      property string xstate: "collapsed"
      readonly property bool expanded: Expand.isExpanded(xstate)
      readonly property int baseWidth: notched ? camW + 2 * earTarget : root.virtualWidth
      readonly property int baseHeight: notched ? cut : root.barHeight  // exactly the cutout height
      property string currentTab: "home"   // the expanded panel's tab; sizes the panel
      readonly property var panelSz: Expand.panelSize(modelData.width, Tabs.sizeFor(currentTab))
      readonly property int minPanelHeight: Expand.panelSize(modelData.width).height
      // Ears: the base width, grown (right ear text, island stays centered on
      // the camera) up to the live room on the narrower bar side minus margin.
      readonly property int earMax: notched ? Model.maxEarWidth(root.barWidgets, modelData.width, camW, earW, root.earMargin, root.earCap) : earW
      readonly property real slotX: island.earLive + camW + root.earPad + dateMetrics.advanceWidth + 6
      readonly property bool dotShown: root.network.idleDot !== "" && !dictation.active
      readonly property real slotNeed: root.activity || root.idleView === "weather" || root.idleView === "dayflow" ? sideMetrics.advanceWidth + (root.showIcon ? 18 : 0) : (root.idleView === "watchlist" ? 84 : 0)
      readonly property real dateNeed: dateMetrics.advanceWidth + 6
      readonly property real sideNeed: dateNeed + (root.slotShown ? slotNeed + root.eqSpace : 0) + root.earPad + root.earOuter + (dotShown ? 12 : 0)
      readonly property int earTarget: notched ? Model.earWidthFit(sideNeed, earW, earMax) : earW
      // Clicking the island pins it open (hover-leave no longer collapses it);
      // a click anywhere outside (focus grab below) or Esc collapses it.
      property bool pinned: false
      function collapseNow() {
        pinned = false
        xtimer.stop()
        xstate = "collapsed"
      }
      function xevent(e) {
        if (pinned && e !== "timer") { if (e === "enter" && xstate !== "open") xstate = "open"; return }
        var r = Expand.step(xstate, e, root.settings.hoverDelay)
        xstate = r.state
        if (r.timer > 0) { xtimer.interval = r.timer; xtimer.restart() } else xtimer.stop()
      }
      Timer { id: xtimer; onTriggered: win.xevent("timer") }
      onExpandedChanged: root.setOpen(modelData.name, expanded)
      Connections {
        target: root
        function onCollapseRequested() { win.collapseNow() }
        function onOpenTabRequested(id, screenName) {
          var want = screenName !== "" ? screenName : (Quickshell.screens.length ? root.primaryScreenName() : "")
          if (modelData.name !== want) return
          win.currentTab = id
          win.pinned = true
          if (win.xstate !== "open") win.xstate = "open"
        }
      }
      HyprlandFocusGrab {
        active: win.pinned && win.expanded
        windows: [win]
        onCleared: win.collapseNow()
      }
      // --- end U5 ---

      anchors { top: true; left: true; right: true }
      // Window stays tall while expanded or still animating; the mask below is what takes input.
      implicitHeight: expanded || island.height > baseHeight ? Tabs.maxHeight(Expand.PANEL_HEIGHT) + 16 : island.height
      color: "transparent"
      WlrLayershell.namespace: "omarchy-notch"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: win.pinned && win.expanded ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None  // typing (search, add symbol) only after a click opens it; hover never takes focus
      exclusionMode: ExclusionMode.Ignore
      mask: Region { item: island }

      Rectangle {
        id: island
        // Spring morph (Motion.js): opening bounces a little, closing is quicker and settles.
        // Reduce motion snaps the shape and lets the content fade instead.
        width: wSpring.value
        height: hSpring.value
        SpringValue { id: wSpring; target: win.expanded ? win.panelSz.width : win.baseWidth; instant: root.reduceMotion; stepped: Tk.pxl; duration: win.expanded ? Motion.OPEN.duration : Motion.CLOSE.duration; bounce: win.expanded ? Motion.OPEN.bounce : Motion.CLOSE.bounce }
        SpringValue { id: hSpring; target: win.expanded ? win.panelSz.height : win.baseHeight; instant: root.reduceMotion; stepped: Tk.pxl; duration: win.expanded ? Motion.OPEN.duration : Motion.CLOSE.duration; bounce: win.expanded ? Motion.OPEN.bounce : Motion.CLOSE.bounce }
        // Half the island either side of the camera: where the ear text sits.
        readonly property bool earsOn: win.notched && (!Tk.pxl || !(win.expanded || height > win.baseHeight + 1))
        // Idle content (clock, date, slot) only draws while collapsed; otherwise it
        // would sit behind/through the open panel.
        readonly property bool idleShown: !(win.expanded || height > win.baseHeight + 1)
        readonly property real earLive: Math.max(0, (width - win.camW) / 2)
        TextMetrics {
          id: sideMetrics
          font.family: root.fontFamily
          font.pixelSize: 13
          text: root.sideText
        }
        TextMetrics {
          id: dateMetrics
          font.family: root.fontFamily
          font.pixelSize: 13
          text: root.dateLead
        }
        x: Math.round((parent.width - width) / 2)
        y: 0
        color: Tk.pxl ? "transparent" : root.islandColor
        topLeftRadius: 0
        topRightRadius: 0
        bottomLeftRadius: Math.min(root.islandRadius, Math.round(height * 0.45))
        bottomRightRadius: Math.min(root.islandRadius, Math.round(height * 0.45))

        PxlBody { anchors.fill: parent; visible: Tk.pxl; fill: root.islandColor; edge: win.notched && island.earsOn ? root.islandColor : Tk.edge }
        // U5: hover opens the panel; keyboard focus stays None (see window above).
        HoverHandler { onHoveredChanged: win.xevent(hovered ? "enter" : "leave") }
        // A click on the island itself (outside any tab content) pins it open.
        TapHandler { gesturePolicy: TapHandler.ReleaseWithinBounds; onTapped: { win.pinned = true; if (win.xstate !== "open") win.xstate = "open" } }
        Shortcut { sequence: "Escape"; enabled: win.expanded; onActivated: win.collapseNow() }
        Loader {
          anchors.fill: parent
          z: 1
          active: win.expanded || island.height > win.baseHeight + 1
          onActiveChanged: if (!active) win.currentTab = "home"
          sourceComponent: ExpandedPanel {
            active: win.expanded
            currentTab: win.currentTab
            onTabSelected: function (id) { win.currentTab = id }
            progress: Math.max(0, Math.min(1, (island.height - win.baseHeight) / (win.minPanelHeight - win.baseHeight)))
            headerHeight: win.baseHeight
            notch: root
            weather: root.weather
            now: root.now
            islandColor: root.islandColor
            textColor: root.textColor
            dimColor: root.dimColor
            family: root.fontFamily
          }
        }

        // Notched: time in the left ear; right ear = date, then the ONE rotating slot.
        Text {
          visible: island.earsOn
          anchors.verticalCenter: parent.verticalCenter
          width: Math.min(implicitWidth, island.earLive - root.earPad - root.earOuter)
          elide: Text.ElideRight
          x: island.earLive - width - root.earPad   // right-aligned against the camera edge
          text: root.timeText
          color: root.textColor
          font.family: Tk.label
          font.pixelSize: 13
          textFormat: Text.PlainText
          font.weight: Font.DemiBold
        }
        // Date: fixed in the right ear next to the camera; never cycles.
        Text {
          visible: island.earsOn
          anchors.verticalCenter: parent.verticalCenter
          x: island.earLive + win.camW + root.earPad
          text: root.dateLead
          color: root.dimColor
          font.family: root.fontFamily
          font.pixelSize: 13
          textFormat: Text.PlainText
        }
        // watchlist hook: the slide replaces the side text while view === "watchlist".
        WatchlistSlide {
          visible: island.earsOn && root.view === "watchlist"
          anchors.verticalCenter: parent.verticalCenter
          x: win.slotX   // after the date
          quotes: root.quotes
          index: Math.floor(root.now.getTime() / 1000 / (root.clockSeconds + 2 * root.slideSeconds))
          notched: true
          upColor: root.goodColor
          maxWidth: win.earTarget - root.earPad - root.earOuter - (win.slotX - (island.earLive + win.camW))
          family: root.fontFamily
        }
        SlideText {
          visible: island.earsOn && root.view !== "watchlist" && root.view !== "date"
          anchors.verticalCenter: parent.verticalCenter
          x: win.slotX + root.eqSpace
          target: root.sideText
          iconKind: root.weather ? root.weather.kind : ""
          iconOn: root.showIcon
          maxWidth: win.earTarget - root.earPad - root.earOuter - (win.slotX - (island.earLive + win.camW)) - root.eqSpace - (netDot.visible ? 12 : 0)
          color: root.textColor
          family: root.fontFamily
        }

        // N3: animated equalizer beside the title while media plays.
        EqGlyph {
          visible: island.earsOn && root.mediaShown
          playing: media.active
          color: root.textColor
          anchors.verticalCenter: parent.verticalCenter
          x: win.slotX
        }

        // WordInk dictation dot (U4): pulses while recording.
        WordinkDot {
          activity: dictation
          anchors.verticalCenter: parent.verticalCenter
          anchors.right: parent.right
          anchors.rightMargin: root.earOuter
        }

        // Network dot (v3): green while Tailscale or NordVPN is up, amber while
        // one connects; hidden otherwise and while a dictation dot shows.
        Rectangle {
          id: netDot
          visible: island.earsOn && root.network.idleDot !== "" && !dictation.active
          width: 5; height: 5; radius: Tk.r(3)
          anchors.verticalCenter: parent.verticalCenter
          anchors.right: parent.right
          anchors.rightMargin: root.earOuter
          color: root.network.idleDot === "on" ? root.goodColor : root.warnColor
        }

        // Click the right ear while dictation is showing to stop/toggle it.
        MouseArea {
          visible: island.earsOn
          enabled: dictation.active && !win.expanded
          x: island.earLive + win.camW
          width: island.earLive
          height: parent.height
          cursorShape: Qt.PointingHandCursor
          onClicked: dictation.toggle()
        }

        // Virtual notch: one centered line.
        Row {
          visible: !win.notched && island.idleShown
          anchors.centerIn: parent
          spacing: 10
          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.timeText
            color: root.textColor
            font.family: root.fontFamily
            font.pixelSize: 13
            textFormat: Text.PlainText
            font.weight: Font.DemiBold
          }
          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.dateLead
            color: root.dimColor
            font.family: root.fontFamily
            font.pixelSize: 13
            textFormat: Text.PlainText
          }
          EqGlyph {
            visible: root.mediaShown
            playing: media.active
            color: root.textColor
            anchors.verticalCenter: parent.verticalCenter
          }
          // watchlist hook (virtual notch).
          WatchlistSlide {
            visible: root.view === "watchlist"
            anchors.verticalCenter: parent.verticalCenter
            quotes: root.quotes
            index: Math.floor(root.now.getTime() / 1000 / (root.clockSeconds + 2 * root.slideSeconds))
            notched: false
            maxWidth: root.virtualWidth - 110
            family: root.fontFamily
            upColor: root.goodColor
          }
          SlideText {
            visible: root.view !== "watchlist" && root.view !== "date"
            anchors.verticalCenter: parent.verticalCenter
            target: root.sideText
            iconKind: root.weather ? root.weather.kind : ""
            iconOn: root.showIcon
            maxWidth: root.virtualWidth - 110
            color: root.textColor
            family: root.fontFamily
          }
        }
      }
    }
  }

  // A label that slides up and fades when its text changes.
  component SlideText: Item {
    id: slide
    property string target: ""
    property string iconKind: ""     // pixel-art weather icon shown before the text
    property bool iconOn: false
    property color color: "white"
    property string family: ""
    property string shown: ""
    property int maxWidth: 10000
    property int iconSpace: iconOn ? icon.width + 4 : 0
    Behavior on iconSpace { NumberAnimation { duration: 220; easing.type: Easing.OutQuad } }
    implicitWidth: Math.min(maxWidth, label.implicitWidth + iconSpace)
    implicitHeight: label.implicitHeight
    width: implicitWidth
    height: implicitHeight
    clip: false

    Component.onCompleted: shown = target
    onTargetChanged: if (target !== shown) swap.restart()

    PixelWeather {
      id: icon
      kind: slide.iconKind || "cloudy"
      active: slide.iconOn
      anchors.verticalCenter: parent.verticalCenter
      opacity: slide.iconOn ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: 220 } }
    }

    // Long text scrolls slowly (pause, glide to the end, pause, glide back)
    // inside a clipped box instead of eliding.
    Item {
      id: box
      x: slide.iconSpace
      width: slide.width - slide.iconSpace
      height: label.implicitHeight
      clip: slide.overflow > 0
      Text {
        id: label
        text: slide.shown
        color: slide.color
        font.family: slide.family
        font.pixelSize: 13
        textFormat: Text.PlainText
      }
    }
    readonly property real overflow: Math.max(0, label.implicitWidth - box.width)
    onOverflowChanged: if (overflow <= 0) label.x = 0
    SequentialAnimation {
      id: marquee
      running: slide.overflow > 0 && slide.visible
      loops: Animation.Infinite
      onRunningChanged: if (!running) label.x = 0
      PauseAnimation { duration: 1800 }
      NumberAnimation { target: label; property: "x"; to: -slide.overflow; duration: Math.max(1, slide.overflow * 32); easing.type: Easing.Linear }
      PauseAnimation { duration: 1400 }
      NumberAnimation { target: label; property: "x"; to: 0; duration: 500; easing.type: Easing.InOutQuad }
    }

    SequentialAnimation {
      id: swap
      ParallelAnimation {
        NumberAnimation { target: label; property: "opacity"; to: 0; duration: 160; easing.type: Easing.InQuad }
        NumberAnimation { target: label; property: "y"; to: -6; duration: 160; easing.type: Easing.InQuad }
      }
      ScriptAction { script: { slide.shown = slide.target; label.y = 6; label.x = 0 } }
      ParallelAnimation {
        NumberAnimation { target: label; property: "opacity"; to: 1; duration: 220; easing.type: Easing.OutQuad }
        NumberAnimation { target: label; property: "y"; to: 0; duration: 220; easing.type: Easing.OutQuad }
      }
    }
  }
}
