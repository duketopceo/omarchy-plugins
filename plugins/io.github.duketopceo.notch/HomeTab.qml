import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Services.Mpris
import qs.Commons as Commons
import "Model.js" as Model
import "Expand.js" as Expand
import "Agents.js" as Agents
import "Network.js" as Network

// Home tab: an at-a-glance dashboard in the 428 x ~164 content area.
//   left:  date, weather (pixel icon), now playing (compact), quotes, active app
//   right: month calendar, then one row of counters (agents, unread messages,
//          top AI usage) and one row of status dots (Tailscale, NordVPN with a
//          quick toggle, Wisp, dictation).
// Everything is read from the root Notch item (`notch`) or small local files;
// the AI usage fetch is shared and rate-limited in Notch.qml.
Item {
  id: panel

  property var notch: null

  readonly property bool active: visible
  readonly property var weather: notch ? notch.weather : null
  readonly property date now: notch ? notch.now : new Date()
  readonly property color textColor: notch ? notch.textColor : "white"
  readonly property color dimColor: notch ? notch.dimColor : "gray"
  readonly property string family: notch ? notch.fontFamily : ""
  readonly property string home: Quickshell.env("HOME")
  readonly property var net: notch ? notch.network : null
  readonly property var agentCounts: notch && notch.agentsActivity ? notch.agentsActivity.summary.counts : ({ working: 0, blocked: 0, done: 0, idle: 0 })
  readonly property int unread: notch && notch.messages ? notch.messages.unread : 0
  readonly property var topUsage: Agents.topUsage(notch ? notch.usage : null)
  readonly property string appName: {
    var t = Hyprland.activeToplevel
    return t ? Agents.prettyApp(t.lastIpcObject ? t.lastIpcObject.class : "") : ""
  }

  onVisibleChanged: if (visible && notch) notch.refreshUsage()
  onNotchChanged: if (visible && notch) notch.refreshUsage()
  Component.onCompleted: if (visible && notch) notch.refreshUsage()

  readonly property var player: {
    var list = Mpris.players ? Mpris.players.values : []
    var first = null
    for (var i = 0; i < list.length; i++) {
      if (!list[i]) continue
      if (list[i].isPlaying) return list[i]
      if (!first) first = list[i]
    }
    return first
  }

  property string quotes: ""
  FileView {
    path: panel.home + "/.cache/omarchy/notch.json"
    watchChanges: true
    printErrors: false
    onLoaded: {
      try { panel.quotes = Expand.quotesLine(JSON.parse(text()).quotes, 2) } catch (e) { panel.quotes = "" }
    }
    onLoadFailed: panel.quotes = ""
    onFileChanged: reload()
  }

  property var wisp: null
  FileView {
    path: Quickshell.env("XDG_RUNTIME_DIR") + "/wisp/state.json"
    watchChanges: true
    printErrors: false
    onLoaded: panel.wisp = Expand.parseWisp(text())
    onLoadFailed: panel.wisp = null
    onFileChanged: reload()
  }

  // Network dots share NetworkState's slow poll; no fast polling from Home.
  function dotColor(kind) { return kind === "on" ? "#6fbf73" : kind === "busy" ? "#e0b050" : "#555a60" }

  component Chip: Item {
    id: chip
    property string glyph: ""
    property string label: ""
    property color tint: panel.dimColor
    implicitWidth: row.implicitWidth
    implicitHeight: 16
    Row {
      id: row
      spacing: 3
      anchors.verticalCenter: parent.verticalCenter
      Text { textFormat: Text.PlainText; text: chip.glyph; color: chip.tint; font.family: panel.family; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
      Text { textFormat: Text.PlainText; text: chip.label; color: panel.textColor; font.family: panel.family; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
    }
  }

  component DotButton: Item {
    id: db
    property string name: ""
    property string state: "off"
    signal clicked()
    implicitWidth: dbRow.implicitWidth
    implicitHeight: 16
    Row {
      id: dbRow
      spacing: 4
      anchors.verticalCenter: parent.verticalCenter
      Rectangle { width: 7; height: 7; radius: 4; color: panel.dotColor(db.state); anchors.verticalCenter: parent.verticalCenter }
      Text { textFormat: Text.PlainText; text: db.name; color: dbHit.containsMouse ? panel.textColor : panel.dimColor; font.family: panel.family; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
    }
    MouseArea { id: dbHit; anchors.fill: parent; anchors.margins: -3; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: db.clicked() }
  }

  // ------------------------------------------------------------ layout

  // Left column.
  Column {
    id: leftCol
    width: 200
    spacing: 6

    Text {
      textFormat: Text.PlainText
      text: Qt.formatDate(panel.now, "dddd, d MMM")
      color: panel.textColor
      font.family: panel.family
      font.pixelSize: 13
      font.weight: Font.DemiBold
    }

    Row {
      id: weatherRow
      spacing: 6
      visible: Expand.weatherLine(panel.weather) !== ""
      height: 16
      PixelWeather {
        kind: panel.weather ? panel.weather.kind : "cloudy"
        active: panel.visible
        anchors.verticalCenter: parent.verticalCenter
      }
      Text {
        textFormat: Text.PlainText
        anchors.verticalCenter: parent.verticalCenter
        width: leftCol.width - 22
        elide: Text.ElideRight
        text: Expand.weatherLine(panel.weather)
        color: panel.textColor
        font.family: panel.family
        font.pixelSize: 11
      }
    }

    // Now playing, compact: art, title / artist, one play-pause button.
    Row {
      spacing: 8
      height: 32
      Rectangle {
        width: 32; height: 32; radius: 6
        color: Qt.rgba(1, 1, 1, 0.08)
        clip: true
        Image {
          anchors.fill: parent
          source: panel.player && panel.player.trackArtUrl ? String(panel.player.trackArtUrl) : ""
          fillMode: Image.PreserveAspectCrop
          asynchronous: true
          visible: status === Image.Ready
        }
      }
      Column {
        anchors.verticalCenter: parent.verticalCenter
        width: leftCol.width - 40 - 30
        Text {
          textFormat: Text.PlainText
          width: parent.width
          elide: Text.ElideRight
          text: panel.player ? String(panel.player.trackTitle || panel.player.identity || "") : "Nothing playing"
          color: panel.player ? panel.textColor : panel.dimColor
          font.family: panel.family
          font.pixelSize: 11
        }
        Text {
          textFormat: Text.PlainText
          width: parent.width
          elide: Text.ElideRight
          text: panel.player ? String(panel.player.trackArtist || "") : ""
          color: panel.dimColor
          font.family: panel.family
          font.pixelSize: 10
        }
      }
      Rectangle {
        width: 24; height: 24; radius: 12
        anchors.verticalCenter: parent.verticalCenter
        color: playHit.containsMouse ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(1, 1, 1, 0.1)
        opacity: panel.player ? 1 : 0.4
        Text {
          textFormat: Text.PlainText
          anchors.centerIn: parent
          text: panel.player && panel.player.isPlaying ? "\u{F03E4}" : "\u{F040A}"
          color: panel.textColor
          font.family: panel.family
          font.pixelSize: 13
        }
        MouseArea {
          id: playHit
          anchors.fill: parent
          hoverEnabled: true
          enabled: !!panel.player
          onClicked: if (panel.player) panel.player.togglePlaying()
        }
      }
    }

    Text {
      textFormat: Text.PlainText
      visible: text !== ""
      width: leftCol.width
      elide: Text.ElideRight
      text: panel.quotes
      color: panel.dimColor
      font.family: panel.family
      font.pixelSize: 9
    }

    Text {
      textFormat: Text.PlainText
      visible: text !== ""
      width: leftCol.width
      elide: Text.ElideRight
      text: panel.appName !== "" ? "\u{F05A0}  " + panel.appName : ""
      color: panel.dimColor
      font.family: panel.family
      font.pixelSize: 9
    }
  }

  // Right column.
  Item {
    id: rightCol
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    width: 208

    MiniCalendar {
      id: cal
      anchors.top: parent.top
      anchors.horizontalCenter: parent.horizontalCenter
      width: 154
      today: panel.now
      family: panel.family
      textColor: panel.textColor
      dimColor: panel.dimColor
    }

    Row {
      id: counters
      anchors.top: cal.bottom
      anchors.topMargin: 6
      anchors.horizontalCenter: parent.horizontalCenter
      spacing: 9
      Chip { glyph: "\u25CF"; label: String(panel.agentCounts.working); tint: Commons.Color.accent }
      Chip { glyph: "!"; label: String(panel.agentCounts.blocked); tint: panel.agentCounts.blocked > 0 ? "#f5a742" : panel.dimColor }
      Chip { glyph: "\u2713"; label: String(panel.agentCounts.done); tint: panel.agentCounts.done > 0 ? "#6fbf73" : panel.dimColor }
      Chip { glyph: "\u{F0361}"; label: String(panel.unread); tint: panel.unread > 0 ? panel.textColor : panel.dimColor }
      Chip { visible: panel.topUsage !== null; glyph: "\u{F0E4D}"; label: panel.topUsage ? panel.topUsage.name + " " + panel.topUsage.percent + "%" : ""; tint: panel.topUsage && panel.topUsage.percent >= 90 ? Commons.Color.urgent : panel.dimColor }
    }

    Row {
      id: dots
      anchors.top: counters.bottom
      anchors.topMargin: 6
      anchors.horizontalCenter: parent.horizontalCenter
      spacing: 9
      DotButton { name: "TS"; state: panel.net ? panel.net.tsDot : "off"; onClicked: if (panel.notch) panel.notch.network.copyIp(panel.net.ts.selfIp) }
      DotButton { name: "Nord"; state: panel.net ? panel.net.nordDot : "off"; onClicked: if (panel.net) panel.net.toggleNord() }
      DotButton { name: "Wisp"; state: panel.wisp ? "on" : "off"; onClicked: if (panel.notch) panel.notch.openWisp() }
      DotButton { name: "Dictate"; state: panel.notch && panel.notch.dictationActivity && panel.notch.dictationActivity.state === "recording" ? "busy" : (panel.notch && panel.notch.dictationActivity && panel.notch.dictationActivity.state !== "not-running" ? "on" : "off"); onClicked: if (panel.notch) panel.notch.dictationActivity.toggle() }
    }
  }
}
