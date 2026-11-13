import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.Commons as Commons
import "Model.js" as Model
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
  property bool dashboardOpen: false
  function openDashboard() { root.dashboardOpen = true }

  Loader {
    id: dashboard
    active: root.dashboardOpen
    anchors.fill: parent
    source: "Notch.qml"
    onLoaded: if (item) item.shell = root.shell
  }

  Connections {
    target: root
    function onDashboardRequested() { root.openDashboard() }
    function onOpenTabRequested() { root.openDashboard() }
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
      readonly property int camW: Model.cameraWidthFor(root.deviceCompatible, monitor ? monitor.width : 0, modelData.width, root.cameraOverride, cut) || Model.SIZES.cameraWidth
      // The prototype's calibration: the internal panel is the widest camera
      // on omarchy-max; an external panel gets a narrower virtual notch.
      readonly property int sensorWidth: modelData.name === "eDP-1" ? Math.max(186, camW) : 95

      // Expanded geometry from the prototype (KTD3).
      // The compact width leaves room for an ear either side of the camera. A
      // second activity needs two ear widths more, so the width grows with the
      // ranked count rather than staying at the single-activity size: at the
      // old fixed width canSplit() was false on every screen, so the second
      // segment could never appear (R1).
      readonly property int earRoom: 70
      readonly property int compactWidth: Math.max(250, sensorWidth + 120
        + (ranked.length > 1 ? 2 * earRoom : 0))
      readonly property int compactHeight: 37
      readonly property int expandedWidth: 374
      readonly property int expandedHeight: 180

      property bool expanded: false
      // The activity the expanded view is about. Held by id, never by rank, so
      // a reorder cannot move a control onto a different activity (KTD6).
      property string selectedId: ""

      readonly property var ranked: root.ranked
      readonly property var selected: Island.selected(ranked, selectedId)
      readonly property var segments: {
        if (!Island.canSplit(compactWidth, sensorWidth + 40, earRoom, earRoom)) return ranked.slice(0, 1)
        return ranked.slice(0, 2)
      }

      function openIsland(id) {
        selectedId = id
        expanded = true
      }
      function closeIsland() {
        expanded = false
      }
      // When the selected activity ends, keep the window but show a neutral
      // state instead of another activity's controls (KTD6).
      onRankedChanged: {
        if (expanded && selectedId !== "" && Island.selected(ranked, selectedId) === null) selectedId = ""
      }

      Connections {
        target: root
        function onDismissRequested() { win.closeIsland() }
        function onOpenRequested() {
          if (modelData.name !== root.primaryScreenName()) return
          if (win.selectedId === "" && win.ranked.length) win.selectedId = win.ranked[0].id
          win.expanded = true
        }

      }

      // MediaActivity owns the position tick; it only runs while something
      // asks for it, and the expanded media view is what asks.
      onExpandedChanged: media.tracking = expanded && selectedId === "media"
      onSelectedIdChanged: media.tracking = expanded && selectedId === "media"

      HyprlandFocusGrab {
        active: win.expanded
        windows: [win]
        onCleared: win.closeIsland()
      }

      anchors.top: true
      implicitWidth: expandedWidth + 40
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
        Accessible.role: Accessible.Pane
        Accessible.name: win.expanded ? qsTr("Notch island, expanded") : qsTr("Notch island")

        // Reduced motion snaps the shape; the content still cross-fades (R4).
        Behavior on width { enabled: !root.reduceMotion; NumberAnimation { duration: Motion.ISLAND_OPEN_MS; easing.type: Easing.OutBack; easing.overshoot: Motion.ISLAND_OPEN_OVERSHOOT } }
        Behavior on height { enabled: !root.reduceMotion; NumberAnimation { duration: Motion.ISLAND_OPEN_MS; easing.type: Easing.OutBack; easing.overshoot: Motion.ISLAND_HEIGHT_OVERSHOOT } }
        Behavior on radius { enabled: !root.reduceMotion; NumberAnimation { duration: Motion.ISLAND_RADIUS_MS; easing.type: Easing.OutCubic } }

        Shortcut { sequence: "Escape"; enabled: win.expanded; onActivated: win.closeIsland() }
        Connections {
          target: root
          function onDismissRequested() { root.dashboardOpen = false }
        }

        // ---------------------------------------------------------- compact
        Item {
          anchors.fill: parent
          opacity: win.expanded ? 0 : 1
          visible: opacity > 0
          Behavior on opacity { NumberAnimation { duration: root.reduceMotion ? 0 : Motion.ISLAND_FADE_MS; easing.type: Easing.OutCubic } }

          Text {
            anchors.verticalCenter: parent.verticalCenter
            x: 8
            width: Math.max(0, (parent.width - win.sensorWidth) / 2 - 14)
            horizontalAlignment: Text.AlignRight
            text: root.timeText
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: root.brightText
            font.family: root.fontFamily
            font.pixelSize: 13
            font.weight: Font.DemiBold
          }

          // Right ear: the top-ranked activity, else the date. This is the
          // compact half of R1; the second segment lives here too when space
          // allows (segments is capped by canSplit).
          Text {
            anchors.verticalCenter: parent.verticalCenter
            x: (parent.width + win.sensorWidth) / 2 + 6
            width: Math.max(0, parent.width - x - 8)
            text: {
              // Message and screenshot text is externally sourced; PlainText
              // keeps markup inert (KTD7).
              if (win.segments.length > 0) {
                var a = win.segments[0]
                var second = win.segments.length > 1 ? "  ·  " + win.segments[1].text : ""
                return Activity.label(a) + second
              }
              return root.dateText
            }
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: root.brightText
            font.family: root.fontFamily
            font.pixelSize: 12
            Accessible.role: Accessible.StaticText
            Accessible.name: win.segments.length ? win.segments[0].text : root.dateText
          }

          TapHandler {
            enabled: !win.expanded
            onTapped: win.openIsland(win.ranked.length ? win.ranked[0].id : "")
          }
        }

        // ---------------------------------------------------------- expanded
        Item {
          anchors.fill: parent
          opacity: win.expanded ? 1 : 0
          visible: opacity > 0
          Behavior on opacity { NumberAnimation { duration: root.reduceMotion ? 0 : Motion.ISLAND_DETAIL_MS; easing.type: Easing.OutCubic } }

          // Neutral state: the activity that was showing has ended.
          Text {
            anchors.centerIn: parent
            visible: win.expanded && win.selected === null
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
                x: 22; y: 41; width: 60; height: 60; radius: 13
                color: root.pillColor
                Image {
                  anchors.fill: parent
                  // Only while the media view is showing, and decoded at the
                  // 60 px it is drawn at rather than full cover resolution.
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
                  text: "♫"
                  textFormat: Text.PlainText
                  color: root.dimText
                  font.pixelSize: 25
                }
              }
              Text {
                x: 98; y: 44; width: parent.width - x - 26
                text: win.selected !== null ? win.selected.text : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: root.titleText
                font.family: root.fontFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
              }
              Text {
                x: 98; y: 66; width: parent.width - x - 26
                text: media.player ? (media.player.trackArtist || media.player.identity) : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: root.dimText
                font.family: root.fontFamily
                font.pixelSize: 13
              }
              Rectangle {
                x: 23; y: 112; width: parent.width - 46; height: 4; radius: 2
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
                y: 129
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
                      text: transport.modelData === "previous" ? "⏮"
                        : transport.modelData === "next" ? "⏭"
                        : media.player && media.player.isPlaying ? "Ⅱ" : "▶"
                      textFormat: Text.PlainText
                      color: root.altText
                      font.pixelSize: transport.modelData === "toggle" ? 25 : 18
                    }
                    TapHandler {
                      onTapped: {
                        if (!media.player) return
                        if (transport.modelData === "previous") media.player.previous()
                        else if (transport.modelData === "next") media.player.next()
                        else media.player.togglePlaying()
                      }
                    }
                  }
                }
              }
            }

            // Dictation: the only control gated on a live state machine, and it
            // appears only while recording (KTD6). Transcribing and done show
            // text with no action.
            Item {
              anchors.fill: parent
              visible: win.selected !== null && win.selected.id === "dictation"
              Text {
                anchors.centerIn: parent
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
                readonly property string act: Island.action("dictation", dictation.state)
                anchors.horizontalCenter: parent.horizontalCenter
                y: 120
                width: 96; height: 32; radius: 16
                visible: act === "stop"
                color: root.pillColor
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: qsTr("Stop dictation")
                Text {
                  anchors.centerIn: parent
                  text: qsTr("Stop")
                  textFormat: Text.PlainText
                  color: root.labelText
                  font.family: root.fontFamily
                  font.pixelSize: 13
                  font.weight: Font.DemiBold
                }
                TapHandler { onTapped: dictation.toggle() }
              }
            }

            // Agents: a route to herdr. Rendered only when agents are on.
            Item {
              anchors.fill: parent
              visible: win.selected !== null && win.selected.id === "agents"
              Text {
                anchors.centerIn: parent
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
                y: 120
                width: 96; height: 32; radius: 16
                color: root.pillColor
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: qsTr("Open herdr")
                Text {
                  anchors.centerIn: parent
                  text: qsTr("Herdr")
                  textFormat: Text.PlainText
                  color: root.labelText
                  font.family: root.fontFamily
                  font.pixelSize: 13
                  font.weight: Font.DemiBold
                }
                TapHandler { onTapped: agents.openApp() }
              }
            }

            // Messages: a route to Blip. Read-only; never sends (KTD7).
            Item {
              anchors.fill: parent
              visible: win.selected !== null && win.selected.id === "messages"
              Text {
                anchors.centerIn: parent
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
                y: 120
                width: 96; height: 32; radius: 16
                color: root.pillColor
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: qsTr("Open Blip")
                Text {
                  anchors.centerIn: parent
                  text: qsTr("Blip")
                  textFormat: Text.PlainText
                  color: root.labelText
                  font.family: root.fontFamily
                  font.pixelSize: 13
                  font.weight: Font.DemiBold
                }
                TapHandler { onTapped: messagesAct.openBlip() }
              }
            }

            // Screenshots: a route to the library.
            Item {
              anchors.fill: parent
              visible: win.selected !== null && win.selected.id === "screenshots"
              Text {
                anchors.centerIn: parent
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
                y: 120
                width: 96; height: 32; radius: 16
                color: root.pillColor
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: qsTr("Open screenshot library")
                Text {
                  anchors.centerIn: parent
                  text: qsTr("Library")
                  textFormat: Text.PlainText
                  color: root.labelText
                  font.family: root.fontFamily
                  font.pixelSize: 13
                  font.weight: Font.DemiBold
                }
                TapHandler { onTapped: shots.openLibrary() }
              }
            }
          }

          // Dashboard route (R6, KTD8): a deliberate, always-present control.
          Item {
            anchors.right: parent.right
            anchors.rightMargin: 24
            y: 17
            width: 24; height: 24
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Open the dashboard")
            Text {
              anchors.centerIn: parent
              text: "☰"
              textFormat: Text.PlainText
              color: root.mutedText
              font.pixelSize: 16
            }
            TapHandler { onTapped: root.openDashboard() }
          }

          // Close control.
          Item {
            anchors.right: parent.right
            anchors.rightMargin: 24
            y: 132
            width: 24; height: 24
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Close")
            Text {
              anchors.centerIn: parent
              text: "×"
              textFormat: Text.PlainText
              color: root.mutedText
              font.pixelSize: 21
            }
            TapHandler { onTapped: win.closeIsland() }
          }
        }
      }
    }
  }
}
