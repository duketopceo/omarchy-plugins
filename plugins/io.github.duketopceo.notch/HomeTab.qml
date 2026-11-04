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

// Home tab: a three-column dashboard in the 672 x ~290 content area of the
// 720 x 380 Home panel.
//   left:   big time and date, now playing (art, title, prev/play/next)
//   middle: weather (large pixel icon, temperature, condition, place), calendar
//   right:  agents (working / need you / done), unread messages, top AI usage
//           bar, up to 3 quotes, network dots (Tailscale, NordVPN toggle,
//           Wisp, Dictate)
// Type sizes come from the theme scale (Commons.Style.font).
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

  readonly property var quoteList: notch && Array.isArray(notch.quotes) ? notch.quotes.slice(0, 3) : []

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

  readonly property var font_: Commons.Style.font
  readonly property color up: "#6fbf73"
  readonly property color down: "#e0786f"
  readonly property color warn: "#f5a742"
  readonly property int gap: 28
  readonly property int colW: Math.floor((width - 2 * gap) / 3)
  implicitWidth: 672
  implicitHeight: 290

  component Caption: Text {
    textFormat: Text.PlainText
    color: panel.dimColor
    font.family: panel.family
    font.pixelSize: Commons.Style.font.caption
    font.letterSpacing: 0.8
    font.capitalization: Font.AllUppercase
  }

  component Divider: Rectangle {
    width: 1
    color: Qt.rgba(1, 1, 1, 0.07)
  }

  component Stat: Column {
    id: stat
    property string label: ""
    property string value: "0"
    property color tint: panel.textColor
    spacing: 2
    Text {
      textFormat: Text.PlainText
      text: stat.value
      color: stat.tint
      font.family: panel.family
      font.pixelSize: Commons.Style.font.display
      font.weight: Font.DemiBold
      font.features: ({ "tnum": 1 })
    }
    Caption { text: stat.label }
  }

  component DotButton: Item {
    id: db
    property string name: ""
    property string state: "off"
    signal clicked()
    implicitWidth: dbRow.implicitWidth
    implicitHeight: 20
    Row {
      id: dbRow
      spacing: 6
      anchors.verticalCenter: parent.verticalCenter
      Rectangle { width: 8; height: 8; radius: 4; color: panel.dotColor(db.state); anchors.verticalCenter: parent.verticalCenter }
      Text { textFormat: Text.PlainText; text: db.name; color: dbHit.containsMouse ? panel.textColor : panel.dimColor; font.family: panel.family; font.pixelSize: Commons.Style.font.bodySmall; anchors.verticalCenter: parent.verticalCenter }
    }
    MouseArea { id: dbHit; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: db.clicked() }
  }

  component RoundButton: Rectangle {
    id: rb
    property string glyph: ""
    property int size: 28
    signal clicked()
    width: size; height: size; radius: size / 2
    color: rbHit.containsMouse ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(1, 1, 1, 0.1)
    opacity: panel.player ? 1 : 0.4
    Text {
      textFormat: Text.PlainText
      anchors.centerIn: parent
      text: rb.glyph
      color: panel.textColor
      font.family: panel.family
      font.pixelSize: Commons.Style.font.title
    }
    MouseArea { id: rbHit; anchors.fill: parent; hoverEnabled: true; enabled: !!panel.player; cursorShape: Qt.PointingHandCursor; onClicked: rb.clicked() }
  }

  // ------------------------------------------------------------ left: time + now playing
  Column {
    id: leftCol
    x: 0
    width: panel.colW
    spacing: 4

    Text {
      textFormat: Text.PlainText
      text: notch ? notch.timeText : Qt.formatTime(panel.now, "h:mm AP")
      color: panel.textColor
      font.family: panel.family
      font.pixelSize: 40
      font.weight: Font.DemiBold
      font.features: ({ "tnum": 1 })
    }
    Text {
      textFormat: Text.PlainText
      text: Qt.formatDate(panel.now, "dddd, d MMMM")
      color: panel.dimColor
      font.family: panel.family
      font.pixelSize: Commons.Style.font.subtitle
    }
    Item { width: 1; height: 22 }
    Caption { text: "Now playing" }
    Item { width: 1; height: 4 }

    Item {
      width: leftCol.width; height: 84
      Row {
        anchors.left: art.right
        anchors.leftMargin: 14
        anchors.bottom: parent.bottom
        spacing: 6
        RoundButton { glyph: "\u{F04AE}"; size: 28; onClicked: if (panel.player) panel.player.previous() }
        RoundButton { glyph: panel.player && panel.player.isPlaying ? "\u{F03E4}" : "\u{F040A}"; size: 32; onClicked: if (panel.player) panel.player.togglePlaying() }
        RoundButton { glyph: "\u{F04AD}"; size: 28; onClicked: if (panel.player) panel.player.next() }
      }
    Rectangle {
      id: art
      width: 84; height: 84; radius: 10
      color: Qt.rgba(1, 1, 1, 0.08)
      clip: true
      Text {
        textFormat: Text.PlainText
        anchors.centerIn: parent
        visible: artImage.status !== Image.Ready
        text: "\u{F075A}"
        color: panel.dimColor
        font.family: panel.family
        font.pixelSize: Commons.Style.font.display
      }
      Image {
        id: artImage
        anchors.fill: parent
        source: panel.player && panel.player.trackArtUrl ? String(panel.player.trackArtUrl) : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        visible: status === Image.Ready
      }
    }
    }
    Item { width: 1; height: 4 }
    Text {
      textFormat: Text.PlainText
      width: leftCol.width
      elide: Text.ElideRight
      text: panel.player ? String(panel.player.trackTitle || panel.player.identity || "") : "Nothing playing"
      color: panel.player ? panel.textColor : panel.dimColor
      font.family: panel.family
      font.pixelSize: Commons.Style.font.body
      font.weight: Font.DemiBold
    }
    Text {
      textFormat: Text.PlainText
      width: leftCol.width
      elide: Text.ElideRight
      text: panel.player ? String(panel.player.trackArtist || "") : " "
      color: panel.dimColor
      font.family: panel.family
      font.pixelSize: Commons.Style.font.bodySmall
    }
  }
  Divider { x: panel.colW + panel.gap / 2; height: panel.height }

  // ------------------------------------------------------------ middle: weather + calendar
  Column {
    id: midCol
    x: panel.colW + panel.gap
    width: panel.colW
    spacing: 18

    Item {
      width: parent.width
      height: 60
      visible: panel.weather !== null
      PixelWeather {
        id: wIcon
        px: 4
        kind: panel.weather ? panel.weather.kind : "cloudy"
        active: panel.visible
        anchors.verticalCenter: parent.verticalCenter
      }
      Column {
        anchors.left: wIcon.right
        anchors.leftMargin: 16
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        Text {
          textFormat: Text.PlainText
          text: panel.weather ? panel.weather.temperature + panel.weather.unit : ""
          color: panel.textColor
          font.family: panel.family
          font.pixelSize: Commons.Style.font.displayLarge
          font.weight: Font.DemiBold
        }
        Text {
          textFormat: Text.PlainText
          width: parent.width
          elide: Text.ElideRight
          text: panel.weather ? Expand.conditionText(panel.weather.kind) + (panel.weather.place ? "  \u00B7  " + panel.weather.place : "") : ""
          color: panel.dimColor
          font.family: panel.family
          font.pixelSize: Commons.Style.font.bodySmall
        }
      }
    }
    Item { visible: panel.weather === null; width: 1; height: 60
      Text { textFormat: Text.PlainText; anchors.verticalCenter: parent.verticalCenter; text: "No weather yet"; color: panel.dimColor; font.family: panel.family; font.pixelSize: Commons.Style.font.bodySmall }
    }

    MiniCalendar {
      width: parent.width
      today: panel.now
      cellH: 24
      fontPx: Commons.Style.font.bodySmall
      titlePx: Commons.Style.font.body
      family: panel.family
      textColor: panel.textColor
      dimColor: panel.dimColor
    }
  }

  Divider { x: 2 * panel.colW + panel.gap * 1.5; height: panel.height }

  // ------------------------------------------------------------ right: status
  Column {
    id: rightCol
    x: 2 * (panel.colW + panel.gap)
    width: panel.colW
    spacing: 16

    Row {
      width: parent.width
      spacing: 0
      Stat { width: Math.floor(parent.width / 3); label: "Working"; value: String(panel.agentCounts.working); tint: panel.agentCounts.working > 0 ? Commons.Color.accent : panel.textColor }
      Stat { width: Math.floor(parent.width / 3); label: "Need you"; value: String(panel.agentCounts.blocked); tint: panel.agentCounts.blocked > 0 ? panel.warn : panel.textColor }
      Stat { width: Math.floor(parent.width / 3); label: "Done"; value: String(panel.agentCounts.done); tint: panel.agentCounts.done > 0 ? panel.up : panel.textColor }
    }

    Row {
      spacing: 8
      Text { textFormat: Text.PlainText; text: "\u{F0361}"; color: panel.unread > 0 ? panel.textColor : panel.dimColor; font.family: panel.family; font.pixelSize: Commons.Style.font.title; anchors.verticalCenter: parent.verticalCenter }
      Text { textFormat: Text.PlainText; text: panel.unread === 1 ? "1 unread message" : panel.unread + " unread messages"; color: panel.unread > 0 ? panel.textColor : panel.dimColor; font.family: panel.family; font.pixelSize: Commons.Style.font.body; anchors.verticalCenter: parent.verticalCenter }
    }

    Column {
      width: parent.width
      spacing: 6
      visible: panel.topUsage !== null
      Row {
        width: parent.width
        Caption { text: panel.topUsage ? panel.topUsage.name + " usage" : ""; width: parent.width - pctLabel.implicitWidth }
        Text {
          id: pctLabel
          textFormat: Text.PlainText
          text: panel.topUsage ? panel.topUsage.percent + "%" : ""
          color: panel.topUsage && panel.topUsage.percent >= 90 ? Commons.Color.urgent : panel.textColor
          font.family: panel.family
          font.pixelSize: Commons.Style.font.bodySmall
          font.features: ({ "tnum": 1 })
        }
      }
      Rectangle {
        width: parent.width; height: 6; radius: 3
        color: Qt.rgba(1, 1, 1, 0.1)
        Rectangle {
          width: parent.width * Math.max(0, Math.min(1, (panel.topUsage ? panel.topUsage.percent : 0) / 100))
          height: parent.height; radius: 3
          color: panel.topUsage && panel.topUsage.percent >= 90 ? Commons.Color.urgent : (panel.topUsage && panel.topUsage.percent >= 70 ? panel.warn : Commons.Color.accent)
          Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
        }
      }
    }

    Column {
      width: parent.width
      spacing: 5
      visible: panel.quoteList.length > 0
      Caption { text: "Watchlist" }
      Repeater {
        model: panel.quoteList
        Row {
          required property var modelData
          width: rightCol.width
          Text { textFormat: Text.PlainText; width: 56; text: modelData.symbol; color: panel.textColor; font.family: panel.family; font.pixelSize: Commons.Style.font.bodySmall; font.weight: Font.DemiBold }
          Text { textFormat: Text.PlainText; width: parent.width - 56 - 64; text: modelData.price.toFixed(2); color: panel.dimColor; font.family: panel.family; font.pixelSize: Commons.Style.font.bodySmall; font.features: ({ "tnum": 1 }) }
          Text { textFormat: Text.PlainText; width: 64; horizontalAlignment: Text.AlignRight; text: (modelData.changePercent >= 0 ? "+" : "") + modelData.changePercent.toFixed(2) + "%"; color: modelData.changePercent >= 0 ? panel.up : panel.down; font.family: panel.family; font.pixelSize: Commons.Style.font.bodySmall; font.features: ({ "tnum": 1 }) }
        }
      }
    }

    Flow {
      width: parent.width
      spacing: 10
      DotButton { name: "Tail"; state: panel.net ? panel.net.tsDot : "off"; onClicked: if (panel.notch) panel.notch.network.copyIp(panel.net.ts.selfIp) }
      DotButton { name: "Nord"; state: panel.net ? panel.net.nordDot : "off"; onClicked: if (panel.net) panel.net.toggleNord() }
      DotButton { name: "Wisp"; state: panel.wisp ? "on" : "off"; onClicked: if (panel.notch) panel.notch.openWisp() }
      DotButton { name: "Dict"; state: panel.notch && panel.notch.dictationActivity && panel.notch.dictationActivity.state === "recording" ? "busy" : (panel.notch && panel.notch.dictationActivity && panel.notch.dictationActivity.state !== "not-running" ? "on" : "off"); onClicked: if (panel.notch) panel.notch.dictationActivity.toggle() }
    }
  }
}
