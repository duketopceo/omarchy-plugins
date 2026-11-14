import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.Commons as Commons
import "Agents.js" as Agents
import "Capabilities.js" as Caps
import "Expand.js" as Expand
import "Plugins.js" as Plugins
import "Tabs.js" as Tabs
import "Model.js" as Model
import "Watchlist.js" as Watchlist
import "Settings.js" as Settings
import "Activity.js" as Activity
import "Media.js" as Media
import "Motion.js" as Motion
import "IslandActivity.js" as Island

// Island: the notch's primary surface. Compact shows the clock and up to two
// live activities either side of the camera; expanded shows controls for the
// activity that is showing. Replaces the dashboard as what a glance reveals;
// the dashboard stays reachable behind an explicit control (R6, KTD8).
//
// The five collectors are the existing ones, unchanged (KTD2). Selection is
// pure logic in IslandActivity.js so it can be tested with node (KTD3).
Item {
  id: root

  // Injected by the shell's panel loader.
  property var shell: null
  property var manifest: null

  readonly property string pluginId: manifest && manifest.id ? String(manifest.id) : "io.github.duketopceo.notch"

  // ------------------------------------------------------------ settings
  // Same read path as Notch.qml: the injected shell config when present, else
  // shell.json read directly. Missing or invalid values fall back to DEFAULTS.
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
  property var pending: ({})
  readonly property var settings: Settings.resolve(Settings.pluginEntry(shellConfig, pluginId), pending)

  // The tabs were written against Notch.qml's API and are unchanged, so the
  // island exposes the same surface: settings writes, capability probe, plugin
  // launching, network and usage state.
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

  readonly property string pluginDir: {
    var p = Qt.resolvedUrl(".").toString()
    if (p.indexOf("file://") === 0) p = p.substring(7)
    if (p.length > 1 && p.charAt(p.length - 1) === "/") p = p.substring(0, p.length - 1)
    return p
  }

  // Optional-module probe (bin/notch-probe), for the Settings tab.
  property var capabilities: Caps.emptyProbe()
  Process {
    id: capProbe
    command: [root.pluginDir + "/bin/notch-probe"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 100000) root.capabilities = Caps.parseProbe(text)
    }
    onExited: function (code) { if (code !== 0) root.capabilities = Caps.emptyProbe() }
  }
  Timer {
    interval: 400
    running: true
    repeat: false
    onTriggered: if (!capProbe.running) capProbe.running = true
  }
  readonly property string platformNote: Caps.platformTruth(capabilities)

  // Opening another plugin's panel, from the Plugins and Home tabs.
  property var openSteps: []
  property int openIndex: 0
  property string openFailed: ""
  property string openingId: ""
  Timer { id: openFailedClear; interval: 2200; onTriggered: root.openFailed = "" }
  function openPlugin(id) { openPluginChecked(id, null) }
  function openPluginChecked(id, fallback) {
    if (opener.running) return
    openingId = String(id)
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
    onExited: function (code) {
      if (Plugins.stepOk(root.openSteps[root.openIndex], code, openerOut.text)) return
      root.openIndex += 1
      root.runOpenStep()
    }
  }
  function openWisp() { openPluginChecked("io.github.duketopceo.wisp", [Quickshell.env("HOME") + "/.local/bin/wisp-trigger"]) }

  // Tailscale / NordVPN state for the Network tab and the idle dot.
  NetworkState { id: networkState }
  readonly property var network: networkState

  // AI usage, refreshed at most every 5 minutes, only when a view asks.
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

  readonly property color textColor: Commons.Color.foreground
  readonly property color dimColor: Commons.Color.muted
  readonly property string textColorStr: String(textColor)

  readonly property color islandColor: "black"
  // Surface colours, named once. These keep the prototype's values (KTD3);
  // Notch.qml's textColor/dimColor come from Commons.Color, so switching to
  // those is a visual change and stays a separate decision.
  readonly property color brightText: "#f8f8f8"
  readonly property color titleText: "#ffffff"
  readonly property color altText: "#fafafa"
  readonly property color labelText: "#f2f2f2"
  readonly property color dimText: "#a4a4a4"
  readonly property color mutedText: "#8f8f8f"
  readonly property color pillColor: "#2a2a2a"
  readonly property color trackColor: "#393939"
  readonly property string fontFamily: Commons.Style.font.family
  readonly property bool reduceMotion: Commons.Style.reduceMotion || (settings && settings.reduceMotion === true)

  // ------------------------------------------------------------ cutouts
  property var cutouts: []
  FileView {
    id: cutoutFile
    path: "/usr/share/omarchy-platform/display-cutouts.json"
    blockLoading: true
    watchChanges: false
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
  readonly property int cameraOverride: settings.cameraWidth > 0 ? settings.cameraWidth : 0

  // Live bar geometry, so the ears can grow into the room beside them
  // (Model.maxEarWidth). Same source and cadence as Notch.qml.
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

  // The ambient idle cycle: weather and the stock watchlist, read from the
  // same cache `bin/notch-data` fills. This is the content the old compact
  // notch showed beside the clock, and its absence is what made the island
  // look empty when nothing was happening.
  property var weather: null
  property var quotes: []
  readonly property string weatherText: weather ? weather.temperature + weather.unit : ""
  FileView {
    id: cacheFile
    path: Quickshell.env("HOME") + "/.cache/omarchy/notch.json"
    watchChanges: true
    printErrors: false
    onLoaded: {
      root.weather = Model.parseWeather(text())
      root.quotes = Watchlist.parseQuotes(text())
    }
    onLoadFailed: root.weather = null
    onFileChanged: reload()
  }
  Process {
    id: fetcher
    command: [Qt.resolvedUrl("bin/notch-data").toString().replace("file://", "")].concat(Settings.dataArgs(root.settings))
    onExited: cacheFile.reload()
  }
  readonly property string unitName: settings.unitName
  onUnitNameChanged: if (!fetcher.running) fetcher.running = true
  Timer {
    interval: 10 * 60 * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: if (!fetcher.running) fetcher.running = true
  }

  // ------------------------------------------------------------ collectors
  // The same five entries Notch.qml builds, in the same shape: each activity is
  // { id, active, priority, text, glyph? } (KTD2: no parallel collectors).
  MediaActivity { id: media }
  WordinkActivity { id: dictation }
  readonly property bool wordinkOn: settings.optWordink !== false
  MessagesActivity { id: messagesAct; enabled: root.settings.optMessages === true }
  AgentsActivity { id: agents; enabled: root.settings.optAgents === true }
  ScreenshotsActivity { id: shots; enabled: root.settings.snapdex }

  readonly property var activities: [
    { id: "dictation", active: wordinkOn && dictation.active, priority: 90, text: dictation.text },
    { id: "media", active: media.active, priority: media.priority, text: media.text, glyph: media.glyph },
    { id: "agents", active: agents.active, priority: agents.priority, text: agents.text, glyph: agents.glyph },
    { id: "messages", active: root.settings.optMessages === true && messagesAct.active, priority: messagesAct.priority, text: messagesAct.text, glyph: messagesAct.glyph },
    { id: "screenshots", active: root.settings.snapdex && shots.active, priority: shots.priority, text: shots.text, glyph: shots.glyph }
  ]

  readonly property var ranked: Island.visible(activities)

  property date now: new Date()
  // The clock has no seconds field (Settings.js timeFormat), so this wakes on
  // the minute boundary instead of 60 times a minute for an identical string.
  Timer {
    id: clock
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: {
      root.now = new Date()
      // +50 ms so a boundary that lands early does not skip a minute.
      interval = 60000 - (Date.now() % 60000) + 50
    }
  }

  readonly property string timeText: Qt.formatTime(now, settings.timeFormat)
  readonly property string dateText: Qt.formatDate(now, "ddd d MMM")

  // ------------------------------------------------------------ IPC (R5)
  // `qs ipc call notch open` focuses the Island for keyboard use; `close`
  // dismisses it. openTab is kept for v0.1 callers and opens the dashboard.
  signal dismissRequested()
  signal openRequested()
  signal dashboardRequested()
  signal openTabRequested(string id)
  IpcHandler {
    target: "notch"
    function open(): void { root.openRequested() }
    function close(): void { root.dismissRequested() }
    function dashboard(): void { root.dashboardRequested() }
    // Tabs live in the dashboard, so a v0.1 `openTab` call opens the
    // dashboard rather than failing with "target not found".
    function openTab(id: string): void { root.openTabRequested(id) }
  }

  // Which screens currently want MediaActivity's position tick.
  property var trackingScreens: ({})
  function setTracking(name, on) {
    if (!!trackingScreens[name] === on) return
    var copy = {}
    for (var k in trackingScreens) copy[k] = trackingScreens[k]
    if (on) copy[name] = true; else delete copy[name]
    trackingScreens = copy
    media.tracking = Object.keys(copy).length > 0
  }

  function primaryScreenName() {
    var list = Quickshell.screens || []
    for (var i = 0; i < list.length; i++) if (list[i].name === "eDP-1") return list[i].name
    return list.length ? list[0].name : ""
  }

  // The dashboard (KTD8/R6). The plugin has one entry point, so there is no
  // separate panel to summon: the old surface is Notch.qml, loaded here on a
  // deliberate action.
  //
  // Known: Notch.qml registers its own `notch` IpcHandler, so while it is
  // loaded QML logs "Handler was registered but will not be used" and drops
  // the dashboard's copy. Nothing depends on it — the island's handler
  // forwards openTab — and the alternative would edit Notch.qml, which is the
  // rollback target and stays untouched (KTD1).
  // The shell calls `open()` on a panel's root item when it summons the plugin
  // (shell.qml deliverIfLoaded). Without it `summon` prints ok and nothing
  // appears, which is how a panel reads as enabled but never shows.
  function open() { root.openRequested() }
  function close() { root.dismissRequested() }

  property bool dashboardOpen: false
  property string pendingTab: ""
  function openDashboard(tab) { root.pendingTab = tab || ""; root.dashboardOpen = true }

  Loader {
    id: dashboard
    active: root.dashboardOpen
    source: "Notch.qml"
    // Notch.qml builds its own per-screen windows, so this item needs no size.
    onLoaded: {
      if (!item) return
      item.shell = root.shell
      if (root.pendingTab !== "") item.openTabRequested(root.pendingTab)
    }
    // Notch.qml's own Escape / outside-click ends in collapseRequested. While
    // loaded as the dashboard that must return us to the island, or the
    // island stays hidden for the rest of the session.
    Connections {
      target: dashboard.item
      ignoreUnknownSignals: true
      function onCollapseRequested() { root.dashboardOpen = false }
      function onOpenTabRequested(id) { root.dashboardOpen = true }
    }
  }

  Connections {
    target: root
    function onDashboardRequested() { root.openDashboard() }
    function onOpenTabRequested(id) { root.openDashboard(id) }
    // `close` dismisses whichever surface is showing.
    function onDismissRequested() { root.dashboardOpen = false }
  }

  // Click-outside-to-close, as its own transparent surface under the island.
  Variants {
    model: Quickshell.screens
    PanelWindow {
      id: catcher
      required property var modelData
      screen: modelData
      visible: root.anyExpanded && !root.dashboardOpen
      anchors { top: true; bottom: true; left: true; right: true }
      color: "transparent"
      WlrLayershell.namespace: "omarchy-notch-catcher"
      WlrLayershell.layer: WlrLayer.Overlay
      exclusionMode: ExclusionMode.Ignore
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      TapHandler { onTapped: root.dismissRequested() }
    }
  }

  // True while any screen's island is open, for the catcher above.
  property bool anyExpanded: false

  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: win
      required property var modelData
      screen: modelData

      readonly property var monitor: Hyprland.monitorFor(modelData)
      // Hyprland.monitorFor() reports 0x0 here, so the physical size comes
      // from the screen and its scale factor; the monitor object is used only
      // when it actually carries a size.
      readonly property real dpr: modelData.devicePixelRatio > 0 ? modelData.devicePixelRatio : 1
      readonly property int physW: monitor && monitor.width > 0 ? monitor.width : Math.round(modelData.width * dpr)
      readonly property int physH: monitor && monitor.height > 0 ? monitor.height : Math.round(modelData.height * dpr)
      readonly property int cut: Model.cutoutTop(root.cutouts, modelData.name, modelData.width, {
        width: physW,
        height: physH,
        transform: monitor && monitor.lastIpcObject ? monitor.lastIpcObject.transform : 0
      })
      readonly property int camW: Model.cameraWidthFor(root.deviceCompatible, monitor ? monitor.width : 0, modelData.width, root.cameraOverride, cut) || Model.SIZES.cameraWidth
      // Ear widths come from the notch's own screen math (Model.earWidthFor /
      // earWidthFit / maxEarWidth), not from constants: a hardcoded pair gave
      // 46 px boxes on this panel, narrower than the time string, so the
      // compact island looked empty.
      readonly property int earBase: Model.earWidthFor(modelData.width)
      readonly property int earMax: Model.maxEarWidth(root.barWidgets, modelData.width, camW, earBase, 12, 280)

      // The compact island is the camera cutout tall when the panel has one
      // (so it reads as the notch, not a pill floating below it) and the bar
      // height when it does not. The prototype's 37 was a constant that sat
      // a few px below the bar on this panel.
      readonly property int barHeight: 32
      readonly property int compactHeight: cut > 0 ? Math.max(cut, barHeight) : barHeight
      // Expanded is the tabbed panel the dashboard already had, sized per tab
      // (Tabs.js) and clamped to the screen. Home hosts the activity views.
      property string currentTab: "home"
      // Room above the content for the tab strip, and below it for the footer.
      readonly property int stripH: 44
      readonly property int footerH: 34
      readonly property var panelSz: Expand.panelSize(modelData.width, Tabs.sizeFor(currentTab))
      // The tab file reports its own natural height; grow to fit it rather
      // than clipping the bottom rows inside a fixed box.
      readonly property int contentH: tabLoader.item && tabLoader.item.implicitHeight > 0
        ? tabLoader.item.implicitHeight
        : (win.currentTab === "activity" ? 180 : panelSz.height - stripH - footerH)
      readonly property int expandedWidth: panelSz.width
      readonly property int expandedHeight: stripH + contentH + footerH

      // What the right ear must show: the top activity, else the idle slot.
      readonly property string idleSlot: Model.idleSlot(root.now.getTime() / 1000,
        (root.weather && settings.showWeather ? ["weather"] : [])
          .concat(root.quotes.length && settings.showStocks ? ["watchlist"] : []),
        settings.slideSeconds)
      readonly property var segments: ranked.slice(0, 2)
      readonly property real sideNeed: {
        if (segments.length > 0) return mSide + 8
        if (idleSlot === "weather") return mWeather + 8
        if (idleSlot === "watchlist") return mDate + 96
        return mDate
      }
      readonly property int earTarget: Model.earWidthFit(sideNeed, earBase, earMax)
      readonly property int compactWidth: Math.min(modelData.width - 16, camW + 2 * earTarget)

      // Measures the ear text so the island grows to fit it, as Notch.qml does.
      // TextMetrics measures its own `text` (advanceWidth), so each shape the
      // ear can take gets an instance.
      readonly property int mClock: clockMetrics.advanceWidth
      readonly property int mDate: dateMetrics.advanceWidth
      readonly property int mWeather: weatherMetrics.advanceWidth
      readonly property int mSide: sideMetrics.advanceWidth
      TextMetrics { id: clockMetrics; font.family: root.fontFamily; font.pixelSize: 13; text: root.timeText }
      TextMetrics { id: dateMetrics; font.family: root.fontFamily; font.pixelSize: 13; text: root.dateText }
      TextMetrics { id: weatherMetrics; font.family: root.fontFamily; font.pixelSize: 13; text: root.dateText + "  \u00b7 " + root.weatherText }
      TextMetrics { id: sideMetrics; font.family: root.fontFamily; font.pixelSize: 13; text: win.segments.length > 1 ? win.segments[0].text + "  \u00b7  " + win.segments[1].text : (win.segments.length ? win.segments[0].text : "") }

      // Hover expands after a delay; leaving collapses; a click pins it open
      // so it survives the pointer leaving. Escape or a click outside closes
      // it. The timing state machine is Expand.js, the same one the old notch
      // used, so hover/leave/arm behaviour matches what you already know.
      property string xstate: "collapsed"
      property bool pinned: false
      readonly property bool expanded: Expand.isExpanded(xstate)
      Timer {
        id: xtimer
        onTriggered: win.xevent("timer")
      }
      function xevent(e) {
        if (pinned && e !== "timer") {
          if (e === "enter" && xstate !== "open") xstate = "open"
          return
        }
        var r = Expand.step(xstate, e, root.settings.hoverDelay)
        xstate = r.state
        if (r.timer > 0) { xtimer.interval = r.timer; xtimer.restart() } else xtimer.stop()
        if (xstate === "open") { adopt(); root.anyExpanded = true }
        else if (xstate === "collapsed") root.anyExpanded = false
      }
      // Click: pin open and hold a selection, so leaving does not collapse it.
      function pinOpen() {
        pinned = true
        adopt()
        xtimer.stop()
        xstate = "open"
        root.anyExpanded = true
      }
      // Take the top activity when nothing is held. Called on open and on every
      // rank change, because `ranked` is usually already populated when the
      // window is built, so no change signal fires on the first open.
      function adopt() {
        if (selectedId === "" && ranked.length) selectedId = ranked[0].id
        root.setTracking(modelData.name, selectedId === "media")
      }
      function closeIsland() {
        pinned = false
        xtimer.stop()
        xstate = "collapsed"
        root.setTracking(modelData.name, false)
        root.anyExpanded = false
      }
      function openIsland(id) {
        if (id) selectedId = id
        pinOpen()
      }

      // The activity the expanded view is about. Held by id, never by rank, so
      // a reorder cannot move a control onto a different activity (KTD6).
      property string selectedId: ""

      readonly property var ranked: root.ranked
      readonly property var selected: Island.selected(ranked, selectedId)
      // When the selected activity ends, keep the window but show a neutral
      // state instead of another activity's controls (KTD6).
      onRankedChanged: {
        // Keep the held id honest in both directions: drop it when its
        // activity ends, and take the top one when there is none held. Only
        // clearing left the expanded view saying "Nothing active" after it was
        // opened while idle and an activity then started.
        if (selectedId !== "" && Island.selected(ranked, selectedId) === null) selectedId = ""
        // `adopt()` is called from the open paths instead of here: reading
        // `expanded` in this handler closes a loop with xevent, which writes
        // xstate. A rank change only ever drops a dead selection.
      }

      Connections {
        target: root
        function onDismissRequested() { win.closeIsland() }  // dashboard close is handled at root
        function onOpenRequested() {
          if (modelData.name !== root.primaryScreenName()) return
          // Re-select when the held id is gone, not only when it is empty.
          if (win.selected === null && win.ranked.length) win.selectedId = win.ranked[0].id
          win.pinOpen()
        }

      }

      // MediaActivity owns the position tick; the expanded media view asks for
      // it. Recorded per screen, because the flag is a singleton and the last
      // writer would otherwise stop the tick another screen still needs.
      // The position tick is requested imperatively from openIsland/closeIsland
      // rather than bound: a binding here reads `expanded`, and writing the
      // collector from it closed a loop through `ranked`.

      // Outside-click closes: a transparent catcher fills the screen while
      // expanded and takes the next click. HyprlandFocusGrab was used first,
      // but it clears on its own within a few seconds here and force-collapsed
      // a pinned island, which is why the expanded view kept vanishing.

      anchors.top: true
      // Sized from the island itself, plus slack for the shadow-less edge: a
      // constant here clips the island whenever compactWidth grows (two
      // activities, or a camera-width override).
      implicitWidth: Math.max(expandedWidth, compactWidth) + 40
      implicitHeight: expanded ? expandedHeight + 20 : compactHeight + 20
      color: "transparent"
      WlrLayershell.namespace: "omarchy-notch-island"
      WlrLayershell.layer: WlrLayer.Overlay
      // Keyboard focus only once opened, so hover never steals it (R5).
      WlrLayershell.keyboardFocus: win.expanded ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
      exclusionMode: ExclusionMode.Ignore
      mask: Region { item: island }

      Rectangle {
        id: island
        anchors.horizontalCenter: parent.horizontalCenter
        width: win.expanded ? win.expandedWidth : win.compactWidth
        height: win.expanded ? win.expandedHeight : win.compactHeight
        radius: win.expanded ? Motion.ISLAND_RADIUS : compactHeight / 2
        color: root.islandColor
        clip: true
        visible: !root.dashboardOpen
        // Half the island either side of the camera: where the ears sit.
        readonly property real earLive: Math.max(0, (width - win.camW) / 2)
        Accessible.role: Accessible.Pane
        Accessible.name: win.expanded ? qsTr("Notch island, expanded") : qsTr("Notch island")

        // Reduced motion snaps the shape; the content still cross-fades (R4).
        Behavior on width { enabled: !root.reduceMotion; NumberAnimation { duration: Motion.ISLAND_OPEN_MS; easing.type: Easing.OutBack; easing.overshoot: Motion.ISLAND_OPEN_OVERSHOOT } }
        Behavior on height { enabled: !root.reduceMotion; NumberAnimation { duration: Motion.ISLAND_OPEN_MS; easing.type: Easing.OutBack; easing.overshoot: Motion.ISLAND_HEIGHT_OVERSHOOT } }
        Behavior on radius { enabled: !root.reduceMotion; NumberAnimation { duration: Motion.ISLAND_RADIUS_MS; easing.type: Easing.OutCubic } }

        // Escape only while the island is expanded and no dashboard covers it.
        Shortcut {
          sequence: "Escape"
          enabled: win.expanded && !root.dashboardOpen
          onActivated: win.closeIsland()
        }

        // ---------------------------------------------------------- compact
        Item {
          anchors.fill: parent
          opacity: win.expanded ? 0 : 1
          visible: opacity > 0
          Behavior on opacity { NumberAnimation { duration: root.reduceMotion ? 0 : Motion.ISLAND_FADE_MS; easing.type: Easing.OutCubic } }

          // Hover expands (after the configured delay), leaving collapses;
          // a click pins it open. Same pointer handlers the old notch used.
          HoverHandler {
            id: hover
            enabled: !win.expanded
            onHoveredChanged: {
              if (hovered) win.xevent("enter")
              else win.xevent("leave")
            }
          }

          // Left ear: the clock, right-aligned against the camera.
          Text {
            anchors.verticalCenter: parent.verticalCenter
            x: 8
            width: Math.max(0, island.earLive - 14)
            horizontalAlignment: Text.AlignRight
            text: root.timeText
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: root.brightText
            font.family: root.fontFamily
            font.pixelSize: 13
            font.weight: Font.DemiBold
          }

          // Right ear: the top activity if anything is live, else the ambient
          // idle cycle (weather, then the watchlist), else the date. The "·"
          // separates the date from the slot, as the old notch did.
          Text {
            anchors.verticalCenter: parent.verticalCenter
            x: island.earLive + win.camW + 6
            width: Math.max(0, parent.width - x - 8)
            // Message and screenshot text is externally sourced; PlainText
            // keeps markup inert (KTD7).
            text: {
              if (win.segments.length > 0) {
                var a = win.segments[0]
                var second = win.segments.length > 1 ? "  \u00b7  " + win.segments[1].text : ""
                return Activity.label(a) + second
              }
              if (win.idleSlot === "weather") return root.dateText + "  \u00b7 " + root.weatherText
              if (win.idleSlot === "watchlist") return root.dateText + "  \u00b7 " + watch.slideText
              return root.dateText
            }
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: root.dimText
            font.family: root.fontFamily
            font.pixelSize: 13
            Accessible.role: Accessible.StaticText
            Accessible.name: win.segments.length ? win.segments[0].text : root.dateText
          }

          // The watchlist slide renders quotes in colour, so it replaces the
          // plain text while that slot is showing.
          WatchlistSlide {
            id: watch
            visible: win.idleSlot === "watchlist" && win.segments.length === 0
            anchors.verticalCenter: parent.verticalCenter
            x: island.earLive + win.camW + 6 + mDate + 4
            quotes: root.quotes
            index: Math.floor(root.now.getTime() / 1000 / (root.clockSeconds + 2 * root.slideSeconds))
            notched: true
            maxWidth: Math.max(0, parent.width - x - 8)
            family: root.fontFamily
          }

          TapHandler {
            enabled: !win.expanded
            onTapped: win.pinOpen()
          }
        }

        // ---------------------------------------------------------- expanded
        // The real panel: a tab strip and the tab's own content. Home carries
        // the activity views below; every other tab is the unchanged file from
        // Tabs.js, which reads this root as its `notch`.
        Item {
          anchors.fill: parent
          opacity: win.expanded ? 1 : 0
          visible: opacity > 0
          Behavior on opacity { NumberAnimation { duration: root.reduceMotion ? 0 : Motion.ISLAND_DETAIL_MS; easing.type: Easing.OutCubic } }

          // Tab strip
          Row {
            id: strip
            anchors.top: parent.top
            anchors.topMargin: 10
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 6
            Repeater {
              model: Tabs.visibleTabs(root.settings)
              Rectangle {
                required property var modelData
                readonly property bool sel: win.currentTab === modelData.id
                width: chip.implicitWidth + 20
                height: 26
                radius: 13
                color: sel ? root.pillColor : "transparent"
                Accessible.role: Accessible.Button
                Accessible.name: modelData.title
                activeFocusOnTab: true
                Text {
                  id: chip
                  anchors.centerIn: parent
                  text: modelData.title
                  textFormat: Text.PlainText
                  color: sel ? root.titleText : root.dimText
                  font.family: root.fontFamily
                  font.pixelSize: 12
                }
                TapHandler { onTapped: win.currentTab = modelData.id }
                Keys.onPressed: function (e) {
                  if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Space) {
                    win.currentTab = modelData.id; e.accepted = true
                  }
                }
              }
            }
          }

          // Home: the dashboard's own Home tab, unchanged, so the island
          // carries every feature the old notch had.
          Loader {
            anchors.fill: parent
            anchors.topMargin: win.stripH
            anchors.bottomMargin: win.footerH
            active: win.expanded && win.currentTab === "home"
            source: "HomeTab.qml"
            onLoaded: if (item) item.notch = root
          }

          // The live-activity surface, reachable as its own tab.
          Item {
            anchors.fill: parent
            anchors.topMargin: win.stripH
            anchors.bottomMargin: win.footerH
            visible: win.currentTab === "activity"

            // Neutral state: the activity that was showing has ended.
            Text {
              anchors.centerIn: parent
              visible: win.currentTab === "activity" && win.selected === null
              text: qsTr("Nothing active")
              textFormat: Text.PlainText
              color: root.mutedText
              font.family: root.fontFamily
              font.pixelSize: 13
            }

            // Per-activity detail. Each control is bound to its own id, so a
            // reorder cannot move it (KTD6).
            Item {
              anchors.fill: parent
              visible: win.selected !== null

              // Media: artwork, title, artist, progress, transport.
              Item {
                id: mediaView
                anchors.fill: parent
                visible: win.selected !== null && win.selected.id === "media"
                Rectangle {
                  id: artwork
                  x: 22; y: 4; width: 60; height: 60; radius: 13
                  color: root.pillColor
                  Image {
                    anchors.fill: parent
                    source: win.expanded && win.selected !== null && win.selected.id === "media"
                      && media.player && media.player.trackArtUrl ? media.player.trackArtUrl : ""
                    sourceSize.width: 120
                    sourceSize.height: 120
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    visible: status === Image.Ready
                  }
                  Text {
                    anchors.centerIn: parent
                    visible: !media.player || !media.player.trackArtUrl
                    text: "\u266b"
                    textFormat: Text.PlainText
                    color: root.dimText
                    font.pixelSize: 25
                  }
                }
                Text {
                  x: 98; y: 6; width: parent.width - x - 26
                  text: win.selected !== null ? win.selected.text : ""
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  color: root.titleText
                  font.family: root.fontFamily
                  font.pixelSize: 15
                  font.weight: Font.DemiBold
                }
                Text {
                  x: 98; y: 28; width: parent.width - x - 26
                  text: media.player ? (media.player.trackArtist || media.player.identity) : ""
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  color: root.dimText
                  font.family: root.fontFamily
                  font.pixelSize: 13
                }
                Rectangle {
                  x: 23; y: 74; width: parent.width - 46; height: 4; radius: 2
                  color: root.trackColor
                  visible: !!media.player && media.player.length > 0
                  Rectangle {
                    width: parent.width * Media.fraction(media.player ? media.player.position : 0, media.player ? media.player.length : 0)
                    height: parent.height
                    radius: 2
                    color: root.titleText
                  }
                }
                Row {
                  anchors.horizontalCenter: parent.horizontalCenter
                  y: 88
                  spacing: 38
                  visible: !!media.player
                  Repeater {
                    model: ["previous", "toggle", "next"]
                    Item {
                      id: transport
                      required property string modelData
                      width: 42; height: 38
                      activeFocusOnTab: true
                      Accessible.role: Accessible.Button
                      Accessible.name: transport.modelData === "previous" ? qsTr("Previous track")
                        : transport.modelData === "next" ? qsTr("Next track")
                        : media.player && media.player.isPlaying ? qsTr("Pause") : qsTr("Play")
                      Text {
                        anchors.centerIn: parent
                        text: transport.modelData === "previous" ? "\u23ee"
                          : transport.modelData === "next" ? "\u23ed"
                          : media.player && media.player.isPlaying ? "\u2161" : "\u25b6"
                        textFormat: Text.PlainText
                        color: root.altText
                        font.pixelSize: transport.modelData === "toggle" ? 25 : 18
                      }
                      function activate() {
                        if (!media.player) return
                        if (transport.modelData === "previous") media.player.previous()
                        else if (transport.modelData === "next") media.player.next()
                        else media.player.togglePlaying()
                      }
                      TapHandler { onTapped: transport.activate() }
                      Keys.onPressed: function (e) {
                        if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Space) {
                          transport.activate(); e.accepted = true
                        }
                      }
                    }
                  }
                }
              }

              // The four single-action activities share one shape: a label and
              // one pill, differing only in id, text and what the pill runs.
              Repeater {
                model: [
                  { act: "dictation",   label: qsTr("Stop"),    named: qsTr("Stop dictation") },
                  { act: "agents",      label: qsTr("Herdr"),   named: qsTr("Open herdr") },
                  { act: "messages",    label: qsTr("Blip"),    named: qsTr("Open Blip") },
                  { act: "screenshots", label: qsTr("Library"), named: qsTr("Open screenshot library") }
                ]
                Item {
                  id: detail
                  required property var modelData
                  anchors.fill: parent
                  visible: win.selected !== null && win.selected.id === detail.modelData.act
                  Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: 10
                    width: parent.width - 44
                    horizontalAlignment: Text.AlignHCenter
                    text: win.selected !== null ? win.selected.text : ""
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    color: root.brightText
                    font.family: root.fontFamily
                    font.pixelSize: 14
                  }
                  Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: 74
                    width: 96; height: 32; radius: 16
                    color: root.pillColor
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: detail.modelData.named
                    // Dictation's control is state-gated; the rest are always
                    // offered because their activity is only active when the
                    // backend is really there. Library needs its folder.
                    visible: detail.modelData.act !== "dictation"
                      || Island.action("dictation", dictation.state) === "stop"
                    Text {
                      anchors.centerIn: parent
                      text: detail.modelData.label
                      textFormat: Text.PlainText
                      color: root.labelText
                      font.family: root.fontFamily
                      font.pixelSize: 13
                      font.weight: Font.DemiBold
                    }
                    function activate() {
                      if (detail.modelData.act === "dictation") dictation.toggle()
                      else if (detail.modelData.act === "agents") agents.openApp()
                      else if (detail.modelData.act === "messages") messagesAct.openBlip()
                      else shots.openLibrary()
                    }
                    TapHandler { onTapped: parent.activate() }
                    Keys.onPressed: function (e) {
                      if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Space) {
                        parent.activate(); e.accepted = true
                      }
                    }
                  }
                }
              }
            }
          }

          // Every other tab is the unchanged dashboard file.
          Loader {
            id: tabLoader
            anchors.fill: parent
            anchors.topMargin: win.stripH
            anchors.bottomMargin: win.footerH
            active: win.expanded && win.currentTab !== "home"
            readonly property var tab: Tabs.select(win.currentTab, Tabs.visibleTabs(root.settings))
            source: tab && tab.source ? tab.source : ""
            onLoaded: if (item) item.notch = root
          }

          // Dashboard controls, bottom-right.
          Item {
            anchors.right: parent.right
            anchors.rightMargin: 64
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 14
            width: 24; height: 24
            visible: win.currentTab !== "home"
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Back to activities")
            Text {
              anchors.centerIn: parent
              text: "\u2630"
              textFormat: Text.PlainText
              color: root.mutedText
              font.pixelSize: 16
            }
            TapHandler { onTapped: win.currentTab = "home" }
            Keys.onPressed: function (e) {
              if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Space) {
                win.currentTab = "home"; e.accepted = true
              }
            }
          }

          Item {
            anchors.right: parent.right
            anchors.rightMargin: 24
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 12
            width: 24; height: 24
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Close")
            Text {
              anchors.centerIn: parent
              text: "\u00d7"
              textFormat: Text.PlainText
              color: root.mutedText
              font.pixelSize: 21
            }
            TapHandler { onTapped: win.closeIsland() }
            Keys.onPressed: function (e) {
              if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Space) {
                win.closeIsland(); e.accepted = true
              }
            }
          }
        }
      }
    }
  }
}
