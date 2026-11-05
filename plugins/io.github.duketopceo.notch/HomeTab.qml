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

// Home tab: a header row and three equal columns in the 688 x ~298 content
// area of the 720 x 380 panel (same gutters as every other tab).
//   header: time + date | greeting and status line | working / unread
//   col 1:  now playing (art, title, prev/play/next), weather
//   col 2:  agents (working / need you / done), top AI usage bar, network dots
//   col 3:  calendar, watchlist (two quotes)
// Type sizes come from the theme scale (Commons.Style.font); colours from
// Commons.Color (accent = live, urgent = needs attention / down).
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

  readonly property var quoteList: notch && Array.isArray(notch.quotes) ? notch.quotes.slice(0, 2) : []

  // Optional Wisp integration: hide the Home dot unless the plugin (or its
  // runtime state) is present so a clean install does not show a dead control.
  property var wisp: null
  property bool wispPresent: false
  FileView {
    path: Quickshell.env("HOME") + "/.config/omarchy/plugins/io.github.duketopceo.wisp/manifest.json"
    watchChanges: true
    printErrors: false
    onLoaded: panel.wispPresent = true
    onLoadFailed: panel.wispPresent = false
    onFileChanged: reload()
  }
  FileView {
    path: Quickshell.env("XDG_RUNTIME_DIR") + "/wisp/state.json"
    watchChanges: true
    printErrors: false
    onLoaded: panel.wisp = Expand.parseWisp(text())
    onLoadFailed: panel.wisp = null
    onFileChanged: reload()
  }
  readonly property bool wispOptIn: !(notch && notch.settings) || notch.settings.optWisp !== false
  readonly property bool dictOptIn: !(notch && notch.settings) || notch.settings.optWordink !== false
  readonly property bool showWisp: wispOptIn && (wispPresent || wisp !== null)

  // Network dots share NetworkState's slow poll; no fast polling from Home.
  function dotColor(kind) { return kind === "on" ? Commons.Color.accent : kind === "busy" ? Commons.Color.foreground : Commons.Color.muted }
  function greeting() {
    var h = now.getHours()
    return h < 5 ? "Up late" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"
  }
  function statusLine() {
    var c = agentCounts
    if (c.blocked > 0) return c.blocked === 1 ? "1 agent needs you" : c.blocked + " agents need you"
    if (c.working > 0) return c.working === 1 ? "1 agent working" : c.working + " agents working"
    if (unread > 0) return unread === 1 ? "1 unread message" : unread + " unread messages"
    return appName !== "" ? "In " + appName : "All quiet"
  }

  readonly property int gap: 16
  readonly property int headerH: 52
  readonly property int colW: Math.floor((width - 2 * gap) / 3)
  readonly property int bodyTop: headerH + 12
  implicitWidth: 688
  implicitHeight: 298

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
    spacing: 0
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

  // ------------------------------------------------------------ header
  Item {
    id: header
    width: parent.width
    height: panel.headerH

    Column {
      x: 0
      width: panel.colW
      anchors.verticalCenter: parent.verticalCenter
      spacing: 0
      Text {
        textFormat: Text.PlainText
        text: notch ? notch.timeText : Qt.formatTime(panel.now, "h:mm AP")
        color: panel.textColor
        font.family: panel.family
        font.pixelSize: Commons.Style.font.displayLarge
        font.weight: Font.DemiBold
        font.features: ({ "tnum": 1 })
      }
      Text {
        textFormat: Text.PlainText
        text: Qt.formatDate(panel.now, "dddd, d MMMM")
        color: panel.dimColor
        font.family: panel.family
        font.pixelSize: Commons.Style.font.bodySmall
      }
    }

    Column {
      x: panel.colW + panel.gap
      width: panel.colW
      anchors.verticalCenter: parent.verticalCenter
      spacing: 2
      Text {
        textFormat: Text.PlainText
        width: parent.width
        elide: Text.ElideRight
        text: panel.greeting()
        color: panel.textColor
        font.family: panel.family
        font.pixelSize: Commons.Style.font.heading
        font.weight: Font.DemiBold
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        elide: Text.ElideRight
        text: panel.statusLine()
        color: panel.agentCounts.blocked > 0 ? Commons.Color.urgent : panel.dimColor
        font.family: panel.family
        font.pixelSize: Commons.Style.font.bodySmall
      }
    }

    Row {
      x: 2 * (panel.colW + panel.gap)
      width: panel.colW
      anchors.verticalCenter: parent.verticalCenter
      Stat { width: Math.floor(parent.width / 2); label: "Working"; value: String(panel.agentCounts.working); tint: panel.agentCounts.working > 0 ? Commons.Color.accent : panel.textColor }
      Stat { width: Math.floor(parent.width / 2); label: "Unread"; value: String(panel.unread); tint: panel.unread > 0 ? Commons.Color.accent : panel.textColor }
    }
  }
  Rectangle { y: panel.headerH + 5; width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.07) }

  // ------------------------------------------------------------ col 1: now playing + weather
  Item {
    id: col1
    x: 0
    y: panel.bodyTop
    width: panel.colW
    height: panel.height - panel.bodyTop

    Caption { id: npCap; text: "Now playing" }
    Rectangle {
      id: art
      anchors.top: npCap.bottom
      anchors.topMargin: 8
      width: 80; height: 80; radius: 10
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
    Column {
      anchors.left: art.right
      anchors.leftMargin: 12
      anchors.right: parent.right
      anchors.top: art.top
      anchors.bottom: art.bottom
      spacing: 2
      Text {
        textFormat: Text.PlainText
        width: parent.width
        elide: Text.ElideRight
        text: panel.player ? String(panel.player.trackTitle || panel.player.identity || "") : "Nothing playing"
        color: panel.player ? panel.textColor : panel.dimColor
        font.family: panel.family
        font.pixelSize: Commons.Style.font.body
        font.weight: Font.DemiBold
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        elide: Text.ElideRight
        text: panel.player ? String(panel.player.trackArtist || "") : " "
        color: panel.dimColor
        font.family: panel.family
        font.pixelSize: Commons.Style.font.bodySmall
      }
    }
    Row {
      anchors.left: art.right
      anchors.leftMargin: 12
      anchors.bottom: art.bottom
      spacing: 6
      RoundButton { glyph: "\u{F04AE}"; size: 26; onClicked: if (panel.player) panel.player.previous() }
      RoundButton { glyph: panel.player && panel.player.isPlaying ? "\u{F03E4}" : "\u{F040A}"; size: 30; onClicked: if (panel.player) panel.player.togglePlaying() }
      RoundButton { glyph: "\u{F04AD}"; size: 26; onClicked: if (panel.player) panel.player.next() }
    }

    // weather, pinned to the column's bottom
    Item {
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      height: 64
      Rectangle { width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.07) }
      PixelWeather {
        id: wIcon
        px: 3
        visible: panel.weather !== null
        kind: panel.weather ? panel.weather.kind : "cloudy"
        active: panel.visible
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 6
      }
      Column {
        anchors.left: wIcon.right
        anchors.leftMargin: 14
        anchors.right: parent.right
        anchors.verticalCenter: wIcon.verticalCenter
        spacing: 0
        Text {
          textFormat: Text.PlainText
          text: panel.weather ? panel.weather.temperature + panel.weather.unit : "No weather yet"
          color: panel.weather ? panel.textColor : panel.dimColor
          font.family: panel.family
          font.pixelSize: panel.weather ? Commons.Style.font.displayLarge : Commons.Style.font.bodySmall
          font.weight: Font.DemiBold
        }
        Text {
          textFormat: Text.PlainText
          width: parent.width
          elide: Text.ElideRight
          visible: panel.weather !== null
          text: panel.weather ? Expand.conditionText(panel.weather.kind) + (panel.weather.place ? "  \u00B7  " + panel.weather.place : "") : ""
          color: panel.dimColor
          font.family: panel.family
          font.pixelSize: Commons.Style.font.bodySmall
        }
      }
    }
  }
  Divider { x: panel.colW + panel.gap / 2; y: panel.bodyTop; height: panel.height - panel.bodyTop }

  // ------------------------------------------------------------ col 2: agents + usage + network
  Item {
    id: col2
    x: panel.colW + panel.gap
    y: panel.bodyTop
    width: panel.colW
    height: panel.height - panel.bodyTop

    Caption { id: agCap; text: "Agents" }
    Row {
      id: agRow
      anchors.top: agCap.bottom
      anchors.topMargin: 6
      width: parent.width
      Stat { width: Math.floor(parent.width / 3); label: "Working"; value: String(panel.agentCounts.working); tint: panel.agentCounts.working > 0 ? Commons.Color.accent : panel.textColor }
      Stat { width: Math.floor(parent.width / 3); label: "Need you"; value: String(panel.agentCounts.blocked); tint: panel.agentCounts.blocked > 0 ? Commons.Color.urgent : panel.textColor }
      Stat { width: Math.floor(parent.width / 3); label: "Done"; value: String(panel.agentCounts.done); tint: panel.textColor }
    }

    Column {
      anchors.top: agRow.bottom
      anchors.topMargin: 22
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
          color: panel.topUsage && panel.topUsage.percent >= 90 ? Commons.Color.urgent : Commons.Color.accent
          Behavior on width { SpringAnimation { spring: 3; damping: 0.4; epsilon: 0.25 } }
        }
      }
    }

    Item {
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      height: 64
      Rectangle { width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.07) }
      Caption { id: netCap; anchors.top: parent.top; anchors.topMargin: 10; text: "Network" }
      Flow {
        anchors.top: netCap.bottom
        anchors.topMargin: 6
        width: parent.width
        spacing: 12
        DotButton { name: "Tail"; state: panel.net ? panel.net.tsDot : "off"; onClicked: if (panel.notch) panel.notch.network.copyIp(panel.net.ts.selfIp) }
        DotButton { name: "Nord"; state: panel.net ? panel.net.nordDot : "off"; onClicked: if (panel.net) panel.net.toggleNord() }
        DotButton { visible: panel.showWisp; name: "Wisp"; state: panel.wisp ? "on" : "off"; onClicked: if (panel.notch) panel.notch.openWisp() }
        DotButton { visible: panel.dictOptIn; name: "Dict"; state: panel.notch && panel.notch.dictationActivity && panel.notch.dictationActivity.state === "recording" ? "busy" : (panel.notch && panel.notch.dictationActivity && panel.notch.dictationActivity.state !== "not-running" ? "on" : "off"); onClicked: if (panel.notch) panel.notch.dictationActivity.toggle() }
      }
    }
  }
  Divider { x: 2 * panel.colW + panel.gap * 1.5; y: panel.bodyTop; height: panel.height - panel.bodyTop }

  // ------------------------------------------------------------ col 3: calendar + watchlist
  Item {
    id: col3
    x: 2 * (panel.colW + panel.gap)
    y: panel.bodyTop
    width: panel.colW
    height: panel.height - panel.bodyTop

    MiniCalendar {
      id: cal
      width: parent.width
      today: panel.now
      cellH: 20
      fontPx: Commons.Style.font.bodySmall
      titlePx: Commons.Style.font.body
      family: panel.family
      textColor: panel.textColor
      dimColor: panel.dimColor
    }

    Column {
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      spacing: 3
      visible: panel.quoteList.length > 0
      Caption { text: "Watchlist" }
      Repeater {
        model: panel.quoteList
        Row {
          required property var modelData
          width: col3.width
          Text { textFormat: Text.PlainText; width: 56; text: modelData.symbol; color: panel.textColor; font.family: panel.family; font.pixelSize: Commons.Style.font.bodySmall; font.weight: Font.DemiBold }
          Text { textFormat: Text.PlainText; width: parent.width - 56 - 64; text: modelData.price.toFixed(2); color: panel.dimColor; font.family: panel.family; font.pixelSize: Commons.Style.font.bodySmall; font.features: ({ "tnum": 1 }) }
          Text { textFormat: Text.PlainText; width: 64; horizontalAlignment: Text.AlignRight; text: (modelData.changePercent >= 0 ? "+" : "") + modelData.changePercent.toFixed(2) + "%"; color: modelData.changePercent >= 0 ? panel.textColor : Commons.Color.urgent; font.family: panel.family; font.pixelSize: Commons.Style.font.bodySmall; font.features: ({ "tnum": 1 }) }
        }
      }
    }
  }
}
