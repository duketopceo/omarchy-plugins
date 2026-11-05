import QtQuick 6.11
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// Which keybindings you actually use. The bar glyph shows total activations;
// clicking opens a ranked, filterable list. All data comes from
// bin/hotkey-tally.py, which only ever sees the bindings wrapped in
// ~/.config/hypr/bindings.lua — never keystrokes, text, or clipboard.
Panel {
  id: root
  moduleName: "io.github.duketopceo.hotkey-tally"
  ipcTarget: "io.github.duketopceo.hotkey-tally"

  property bool loaded: false
  property var rows: []
  property string query: ""
  property string lastError: ""

  readonly property color foreground: bar ? bar.foreground : Commons.Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.6)
  readonly property color accent: Commons.Color.accent
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property string pluginRoot: {
    var p = Qt.resolvedUrl(".").toString()
    if (p.indexOf("file://") === 0) p = p.substring(7)
    if (p.length > 1 && p.charAt(p.length - 1) === "/") p = p.substring(0, p.length - 1)
    return p
  }
  readonly property string py: "/usr/bin/python3"
  readonly property var procEnv: ({ "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C" })

  readonly property int total: {
    var n = 0
    for (var i = 0; i < rows.length; i++) n += Number(rows[i].count) || 0
    return n
  }

  readonly property var filtered: {
    var q = root.query.trim().toLowerCase()
    if (!q) return rows
    var out = []
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i]
      var key = String(r.key || "").toLowerCase()
      var label = String(r.label || "").toLowerCase()
      if (key.indexOf(q) >= 0 || label.indexOf(q) >= 0) out.push(r)
    }
    return out
  }

  function refresh() {
    if (listProc.running) return
    listProc.running = true
  }

  function clearAll() {
    if (resetProc.running) return
    resetProc.running = true
  }

  function fmtAge(ms) {
    if (!ms) return ""
    var d = Math.floor(Date.now() / 1000 - Number(ms) / 1000)
    if (d < 60) return d + "s ago"
    if (d < 3600) return Math.floor(d / 60) + "m ago"
    if (d < 86400) return Math.floor(d / 3600) + "h ago"
    return Math.floor(d / 86400) + "d ago"
  }

  onOpenedChanged: if (opened) root.refresh()

  Process {
    id: listProc
    command: [root.py, root.pluginRoot + "/bin/hotkey-tally.py", "list", "--json"]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var text = this.text || ""
        try {
          var parsed = JSON.parse(text || "[]")
          root.rows = Array.isArray(parsed) ? parsed : []
          root.lastError = ""
        } catch (e) {
          root.lastError = "could not read tally data"
        }
        root.loaded = true
      }
    }
    stderr: StdioCollector { waitForEnd: true }
  }

  Process {
    id: resetProc
    command: [root.py, root.pluginRoot + "/bin/hotkey-tally.py", "reset"]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector { waitForEnd: true }
    onExited: root.refresh()
  }

  // Bar face
  Item {
    implicitWidth: barRow.implicitWidth + Style.margin(1.4)
    implicitHeight: bar ? bar.barHeight : 26

    RowLayout {
      id: barRow
      anchors.centerIn: parent
      spacing: Style.margin(0.6)

      Text {
        textFormat: Text.PlainText
        text: "\u2328"
        color: root.opened ? root.accent : root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.fontSize
      }
      Text {
        textFormat: Text.PlainText
        text: root.loaded ? String(root.total) : "\u2026"
        color: root.opened ? root.accent : root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.fontSize
      }
    }

    MouseArea {
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      onClicked: root.opened = !root.opened
    }
  }

  // Popup
  PopupWindow {
    anchor.window: root.bar ? root.bar : null
    anchor.rect.x: root.bar ? root.bar.width - 460 : 0
    anchor.rect.y: root.bar ? root.bar.height : 0
    visible: root.opened
    implicitWidth: 440
    implicitHeight: Math.min(520, 120 + root.filtered.length * 30)
    color: "transparent"

    Rectangle {
      anchors.fill: parent
      color: Commons.Color.background
      border.color: Commons.Color.menu.border
      border.width: 1
      radius: Style.radius

      ColumnLayout {
        anchors.fill: parent
        anchors.margins: Style.margin(1.2)
        spacing: Style.margin(0.8)

        RowLayout {
          Layout.fillWidth: true
          spacing: Style.margin(0.8)

          TextInput {
            id: search
            Layout.fillWidth: true
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.fontSize
            selectionColor: root.accent
            selectedTextColor: Commons.Color.background
            onTextChanged: root.query = text
            Text {
              textFormat: Text.PlainText
              anchors.fill: parent
              text: "filter by key or action"
              color: root.dim
              font: search.font
              visible: search.text.length === 0
            }
          }

          Text {
            textFormat: Text.PlainText
            text: "clear"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.fontSize - 1
            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.clearAll()
            }
          }
        }

        Rectangle {
          Layout.fillWidth: true
          Layout.preferredHeight: 1
          color: Commons.Color.menu.border
        }

        ListView {
          Layout.fillWidth: true
          Layout.fillHeight: true
          model: root.filtered
          clip: true
          spacing: Style.margin(0.3)

          delegate: RowLayout {
            required property var modelData
            width: ListView.view.width
            spacing: Style.margin(0.8)

            Text {
              textFormat: Text.PlainText
              text: modelData.key || modelData.id
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.fontSize - 1
              elide: Text.ElideRight
              Layout.preferredWidth: 150
            }
            Text {
              textFormat: Text.PlainText
              text: modelData.label || ""
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.fontSize - 1
              elide: Text.ElideRight
              Layout.fillWidth: true
            }
            Text {
              textFormat: Text.PlainText
              text: String(modelData.count)
              color: root.accent
              font.family: root.fontFamily
              font.pixelSize: Style.fontSize - 1
            }
            Text {
              textFormat: Text.PlainText
              text: root.fmtAge(modelData.last)
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.fontSize - 2
              Layout.preferredWidth: 52
              horizontalAlignment: Text.AlignRight
            }
          }
        }

        Text {
          textFormat: Text.PlainText
          Layout.fillWidth: true
          visible: root.loaded && root.filtered.length === 0
          text: root.query ? "nothing matches that filter"
                          : "no bindings are wrapped yet — see the README"
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.fontSize - 1
          wrapMode: Text.WordWrap
        }

        Text {
          textFormat: Text.PlainText
          Layout.fillWidth: true
          visible: root.lastError.length > 0
          text: root.lastError
          color: Commons.Color.urgent
          font.family: root.fontFamily
          font.pixelSize: Style.fontSize - 1
        }
      }
    }
  }
}
