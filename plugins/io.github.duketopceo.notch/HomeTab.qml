import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Mpris
import "Model.js" as Model
import "Expand.js" as Expand

// Home tab: the expanded panel's original content (date, media controls,
// weather, quotes, calendar, status dots). The panel sets `notch` to the
// root Notch.qml item.
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

  // ------------------------------------------------------------ state

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
      try { panel.quotes = Expand.quotesLine(JSON.parse(text()).quotes) } catch (e) { panel.quotes = "" }
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

  // NordVPN: reuse the nordvpn plugin's read-only status probe (default verb
  // is status, no control verbs). Polled every 30 s, and only while open.
  property string nord: "unavailable"
  Process {
    id: nordProc
    command: ["/usr/bin/python3", panel.home + "/.config/omarchy/plugins/io.github.duketopceo.nordvpn/bin/probe_nordvpn.py"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: panel.nord = Expand.parseNord(text)
    }
  }
  Timer {
    interval: 30 * 1000
    running: panel.active
    repeat: true
    triggeredOnStart: true
    onTriggered: if (!nordProc.running) nordProc.running = true
  }

  // ------------------------------------------------------------ layout

  Item {
    id: body
    anchors.fill: parent

    // Left column: date, media, weather, quotes.
    Column {
      id: leftCol
      width: 190
      spacing: 5

      Text {
        textFormat: Text.PlainText
        text: Qt.formatDate(panel.now, "dddd, d MMM")
        color: panel.textColor
        font.family: panel.family
        font.pixelSize: 12
        font.weight: Font.DemiBold
      }

      Row {
        spacing: 8
        Rectangle {
          width: 40; height: 40; radius: 6
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
          width: leftCol.width - 48
          Text {
            textFormat: Text.PlainText
            width: parent.width
            elide: Text.ElideRight
            text: panel.player ? String(panel.player.trackTitle || panel.player.identity || "") : "Nothing playing"
            color: panel.player ? panel.textColor : panel.dimColor
            font.family: panel.family
            font.pixelSize: 12
          }
          Text {
            textFormat: Text.PlainText
            width: parent.width
            elide: Text.ElideRight
            text: panel.player ? String(panel.player.trackArtist || "") : ""
            color: panel.dimColor
            font.family: panel.family
            font.pixelSize: 11
          }
        }
      }

      Row {
        spacing: 6
        Repeater {
          model: [
            { glyph: "\u{F04AE}", act: "prev" },
            { glyph: panel.player && panel.player.isPlaying ? "\u{F03E4}" : "\u{F040A}", act: "toggle" },
            { glyph: "\u{F04AD}", act: "next" }
          ]
          Rectangle {
            id: btn
            required property var modelData
            width: 40; height: 22; radius: 11
            color: hit.containsMouse ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(1, 1, 1, 0.1)
            opacity: panel.player ? 1 : 0.4
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: btn.modelData.glyph
              color: panel.textColor
              font.family: panel.family
              font.pixelSize: 14
            }
            MouseArea {
              id: hit
              anchors.fill: parent
              hoverEnabled: true
              enabled: !!panel.player
              onClicked: {
                var p = panel.player
                if (!p) return
                if (btn.modelData.act === "prev") p.previous()
                else if (btn.modelData.act === "next") p.next()
                else p.togglePlaying()
              }
            }
          }
        }
      }

      Text {
        textFormat: Text.PlainText
        visible: text !== ""
        width: leftCol.width
        elide: Text.ElideRight
        text: Expand.weatherLine(panel.weather) ? Model.weatherGlyph(panel.weather.kind) + " " + Expand.weatherLine(panel.weather) : ""
        color: panel.textColor
        font.family: panel.family
        font.pixelSize: 11
      }

      Text {
        textFormat: Text.PlainText
        visible: text !== ""
        width: leftCol.width
        elide: Text.ElideRight
        text: panel.quotes
        color: panel.dimColor
        font.family: panel.family
        font.pixelSize: 10
      }
    }

    // Right column: calendar, status dots.
    MiniCalendar {
      anchors.right: parent.right
      anchors.top: parent.top
      width: 154
      today: panel.now
      family: panel.family
      textColor: panel.textColor
      dimColor: panel.dimColor
    }

    Row {
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      spacing: 10
      Repeater {
        model: [
          { name: "Wisp", color: panel.wisp ? "#7fbf7f" : "#555a60" },
          { name: "VPN", color: panel.nord === "connected" ? "#7fbf7f" : (panel.nord === "connecting" ? "#e0b050" : "#555a60") }
        ]
        Row {
          id: dot
          required property var modelData
          spacing: 4
          Rectangle { width: 7; height: 7; radius: 4; color: dot.modelData.color; anchors.verticalCenter: parent.verticalCenter }
          Text { textFormat: Text.PlainText; text: dot.modelData.name; color: panel.dimColor; font.family: panel.family; font.pixelSize: 9 }
        }
      }
    }
  }
}

