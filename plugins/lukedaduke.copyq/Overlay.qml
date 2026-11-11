import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import QtQuick 6.11
import QtQuick.Layouts
import qs.Commons
import qs.Commons as Commons
import qs.Ui

Item {
  id: root

  property var shell: null
  property var manifest: null
  property bool opened: false
  property string filterText: ""
  property int selectedIndex: 0
  property bool cursorActive: false
  property var entries: []
  property string statusText: "Loading…"
  property string errorText: ""
  property bool listInFlight: false

  readonly property string pluginDir: {
    var url = Qt.resolvedUrl(".")
    return url.toString().replace("file://", "").replace(/\/$/, "")
  }
  readonly property string listHelper: pluginDir + "/bin/copyq-list.py"
  readonly property string activateHelper: pluginDir + "/bin/copyq-activate.sh"

  property color background: Commons.Color.menu.background
  property color foreground: Commons.Color.menu.text
  property color border: Commons.Color.menu.border
  property color scrim: Commons.Color.menu.scrim
  property color selectedBackground: Commons.Color.menu.selectedBackground
  property color selectedText: Commons.Color.menu.selectedText
  readonly property int cornerRadius: Style.cornerRadius
  property string fontFamily: Style.font.menuFamily
  property int contentMargin: Style.spacing.panelPadding
  property int headerHeight: Math.max(Style.space(34), Style.font.title + Style.spacing.controlPaddingY * 2)
  property int contentSpacing: Style.spacing.md
  property int cardWidth: Math.min(Style.space(720), panel.width - Style.gapsOut * 2)
  property int cardHeight: Math.min(Style.space(560), panel.height - Style.gapsOut * 2)
  property int rowHeight: Math.max(Style.space(48), Style.font.body + Style.spacing.rowPaddingX * 2)

  function open(payloadJson) {
    root.opened = true
    root.filterText = ""
    root.selectedIndex = 0
    root.cursorActive = true
    root.errorText = ""
    Quickshell.execDetached(["/usr/bin/copyq", "hide"])
    root.reloadList()
    Qt.callLater(function() { keyCatcher.forceActiveFocus(); filterField.forceActiveFocus() })
  }

  function close() {
    root.opened = false
  }

  function dismiss() {
    root.close()
    if (root.shell && typeof root.shell.hide === "function") {
      root.shell.hide((root.manifest && root.manifest.id) || "lukedaduke.copyq")
    }
  }

  function toggle() {
    if (root.opened) root.dismiss()
    else root.open("{}")
  }

  function reloadList() {
    if (root.listInFlight) return
    root.listInFlight = true
    root.statusText = "Loading…"
    listProc.running = true
  }

  function applyListPayload(raw) {
    root.listInFlight = false
    try {
      var payload = JSON.parse(String(raw || "{}"))
      if (!payload || payload.ok !== true || !Array.isArray(payload.entries)) {
        root.entries = []
        root.errorText = String((payload && payload.error) || "CopyQ history unavailable")
        root.statusText = root.errorText
        root.rebuildDisplay()
        return
      }
      root.entries = payload.entries
      root.errorText = ""
      root.statusText = payload.count + " items"
      root.rebuildDisplay()
    } catch (e) {
      root.entries = []
      root.errorText = "Could not parse CopyQ history"
      root.statusText = root.errorText
      root.rebuildDisplay()
    }
  }

  function matchesFilter(entry) {
    if (!root.filterText) return true
    var q = String(root.filterText).toLowerCase()
    var hay = String(entry.preview || entry.text || "").toLowerCase()
    return hay.indexOf(q) !== -1
  }

  function rebuildDisplay() {
    displayModel.clear()
    for (var i = 0; i < root.entries.length; i++) {
      var entry = root.entries[i]
      if (!root.matchesFilter(entry)) continue
      displayModel.append({
        copyqIndex: entry.index,
        previewText: String(entry.preview || ""),
        fullText: String(entry.text || "")
      })
    }
    if (displayModel.count === 0) root.selectedIndex = 0
    else if (root.selectedIndex >= displayModel.count) root.selectedIndex = displayModel.count - 1
    else if (root.selectedIndex < 0) root.selectedIndex = 0
  }

  function setFilter(next) {
    root.filterText = next
    root.selectedIndex = 0
    root.cursorActive = true
    root.rebuildDisplay()
  }

  function select(delta) {
    if (displayModel.count === 0) return
    if (!root.cursorActive) {
      root.cursorActive = true
      root.selectedIndex = delta < 0 ? displayModel.count - 1 : 0
    } else {
      root.selectedIndex = (root.selectedIndex + delta + displayModel.count) % displayModel.count
    }
    resultList.positionViewAtIndex(root.selectedIndex, ListView.Contain)
  }

  function activateSelected(copyOnly) {
    if (displayModel.count === 0) return
    var row = displayModel.get(root.selectedIndex)
    if (!row) return
    root.dismiss()
    var args = [root.activateHelper, "--index", String(row.copyqIndex)]
    if (copyOnly) args.push("--copy-only")
    Quickshell.execDetached(args)
  }

  ListModel { id: displayModel }

  Process {
    id: listProc
    command: ["/usr/bin/python3", root.listHelper, "80"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.applyListPayload(text)
    }
    onExited: function(code) {
      if (code !== 0 && root.listInFlight) {
        root.listInFlight = false
        if (!root.errorText) {
          root.errorText = "CopyQ list failed"
          root.statusText = root.errorText
        }
      }
    }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    color: "transparent"
    WlrLayershell.layer: WlrLayershell.Overlay
    WlrLayershell.keyboardFocus: root.opened ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
    anchors {
      top: true
      bottom: true
      left: true
      right: true
    }

    Rectangle {
      anchors.fill: parent
      color: root.scrim
      opacity: root.opened ? 0.45 : 0
      Behavior on opacity { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

      MouseArea {
        anchors.fill: parent
        onClicked: root.dismiss()
      }
    }

    Rectangle {
      id: card
      width: root.cardWidth
      height: root.cardHeight
      anchors.centerIn: parent
      radius: root.cornerRadius
      color: root.background
      border.color: root.border
      border.width: Math.max(1, Style.space(1))
      opacity: root.opened ? 1 : 0
      scale: root.opened ? 1 : 0.98
      Behavior on opacity { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
      Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

      ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.contentMargin
        spacing: root.contentSpacing

        RowLayout {
          Layout.fillWidth: true
          Layout.preferredHeight: root.headerHeight
          spacing: Style.spacing.sm

          Text {
            text: "Clipboard"
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.title
            font.bold: true
            textFormat: Text.PlainText
          }

          Item { Layout.fillWidth: true }

          Text {
            text: root.statusText
            color: root.foreground
            opacity: 0.55
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            textFormat: Text.PlainText
          }
        }

        Rectangle {
          Layout.fillWidth: true
          Layout.preferredHeight: root.headerHeight
          radius: Math.max(6, root.cornerRadius - 2)
          color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.06)
          border.color: root.border
          border.width: 1

          TextInput {
            id: filterField
            anchors.fill: parent
            anchors.leftMargin: Style.spacing.controlPaddingX
            anchors.rightMargin: Style.spacing.controlPaddingX
            verticalAlignment: TextInput.AlignVCenter
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            clip: true
            selectByMouse: true
            text: root.filterText
            onTextChanged: root.setFilter(text)
            Keys.onPressed: function(event) {
              if (event.key === Qt.Key_Down) { root.select(1); event.accepted = true }
              else if (event.key === Qt.Key_Up) { root.select(-1); event.accepted = true }
              else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                root.activateSelected(event.modifiers & Qt.ShiftModifier)
                event.accepted = true
              } else if (event.key === Qt.Key_Escape) {
                root.dismiss()
                event.accepted = true
              } else if (event.key === Qt.Key_J && (event.modifiers & Qt.ControlModifier)) {
                root.select(1); event.accepted = true
              } else if (event.key === Qt.Key_K && (event.modifiers & Qt.ControlModifier)) {
                root.select(-1); event.accepted = true
              } else if (event.key === Qt.Key_R && (event.modifiers & Qt.ControlModifier)) {
                root.reloadList(); event.accepted = true
              }
            }
          }

          Text {
            anchors.fill: parent
            anchors.leftMargin: Style.spacing.controlPaddingX
            verticalAlignment: Text.AlignVCenter
            text: "Search history…"
            color: root.foreground
            opacity: 0.35
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            visible: filterField.text.length === 0 && !filterField.activeFocus
            textFormat: Text.PlainText
          }
        }

        ListView {
          id: resultList
          Layout.fillWidth: true
          Layout.fillHeight: true
          clip: true
          model: displayModel
          spacing: Style.spacing.xs
          currentIndex: root.cursorActive ? root.selectedIndex : -1
          delegate: Rectangle {
            required property int index
            required property string previewText
            required property int copyqIndex
            width: resultList.width
            height: root.rowHeight
            radius: Math.max(6, root.cornerRadius - 2)
            color: (root.cursorActive && index === root.selectedIndex)
              ? root.selectedBackground
              : "transparent"

            Text {
              anchors.fill: parent
              anchors.margins: Style.spacing.rowPaddingX
              verticalAlignment: Text.AlignVCenter
              text: previewText
              color: (root.cursorActive && index === root.selectedIndex)
                ? root.selectedText
                : root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
              elide: Text.ElideRight
              textFormat: Text.PlainText
            }

            MouseArea {
              anchors.fill: parent
              hoverEnabled: true
              onEntered: {
                root.cursorActive = true
                root.selectedIndex = index
              }
              onClicked: {
                root.selectedIndex = index
                root.activateSelected(false)
              }
            }
          }
        }

        Text {
          Layout.fillWidth: true
          text: root.errorText || "↑↓ / Ctrl+J/K  ·  Enter paste  ·  Shift+Enter copy  ·  Esc"
          color: root.foreground
          opacity: root.errorText ? 0.9 : 0.45
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
        }
      }
    }

    // Global key catcher when filter is not focused.
    Item {
      id: keyCatcher
      focus: root.opened
      Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Escape) { root.dismiss(); event.accepted = true }
      }
    }
  }
}
