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
  readonly property string removeHelper: pluginDir + "/bin/copyq-remove.sh"
  readonly property string pinHelper: pluginDir + "/bin/copyq-pin.sh"

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
  property int thumbSize: Style.space(36)
  property int cardWidth: Math.min(Style.space(720), panel.width - Style.gapsOut * 2)
  property int cardHeight: Math.min(Style.space(560), panel.height - Style.gapsOut * 2)
  property int rowHeight: Math.max(Style.space(48), Style.font.body + Style.spacing.rowPaddingX * 2)

  // One window. Any summon payload (including the retired {"mode":"cursor"})
  // opens the same centered picker, so old keybindings keep working.
  function open(payloadJson) {
    root.opened = true
    root.filterText = ""
    root.selectedIndex = 0
    root.cursorActive = true
    root.errorText = ""
    Quickshell.execDetached(["/usr/bin/copyq", "hide"])
    root.reloadList()
    Qt.callLater(function() {
      keyCatcher.forceActiveFocus()
      filterField.forceActiveFocus()
    })
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

  function reloadList(force) {
    if (root.listInFlight) {
      if (!force) return
      listProc.running = false
      root.listInFlight = false
      listWatchdog.stop()
    }
    root.listInFlight = true
    root.statusText = "Loading…"
    root.errorText = ""
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
      var pins = payload.pinCount || 0
      var clips = payload.clipCount || 0
      var hot = payload.hotCount || 0
      var bits = []
      if (payload.hotError) bits.push("hot vault unavailable")
      if (hot > 0) bits.push(hot + " hot")
      if (pins > 0) bits.push(pins + " pinned")
      bits.push(clips + " items")
      root.statusText = bits.join(" · ")
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
    var hay = String(entry.preview || entry.text || entry.type || "").toLowerCase()
    if (entry.pinned) hay = "pin " + hay
    if (entry.hot || entry.hotId) hay = "hot key api " + hay
    return hay.indexOf(q) !== -1
  }

  function rebuildDisplay() {
    displayModel.clear()
    for (var i = 0; i < root.entries.length; i++) {
      var entry = root.entries[i]
      if (!root.matchesFilter(entry)) continue
      displayModel.append({
        copyqIndex: entry.index === undefined || entry.index === null ? -1 : entry.index,
        tabName: String(entry.tab || "&clipboard"),
        pinned: !!entry.pinned,
        hot: !!(entry.hot || entry.hotId),
        hotId: String(entry.hotId || ""),
        entryType: String(entry.type || "text"),
        previewText: String(entry.preview || ""),
        fullText: String(entry.text || ""),
        previewPath: String(entry.previewPath || "")
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

  function selectAbsolute(index) {
    if (displayModel.count === 0) return
    root.cursorActive = true
    root.selectedIndex = Math.max(0, Math.min(index, displayModel.count - 1))
    resultList.positionViewAtIndex(root.selectedIndex, ListView.Contain)
  }

  function page(deltaPages) {
    var step = Math.max(1, Math.floor(resultList.height / root.rowHeight) - 1)
    root.selectAbsolute(root.selectedIndex + deltaPages * step)
  }

  function currentRow() {
    if (displayModel.count === 0) return null
    return displayModel.get(root.selectedIndex)
  }

  function activateSelected(copyOnly) {
    var row = root.currentRow()
    if (!row) return
    var args
    if (row.hotId && String(row.hotId).length > 0) {
      args = [root.activateHelper, "--hot-id", String(row.hotId)]
    } else {
      args = [
        root.activateHelper,
        "--index", String(row.copyqIndex),
        "--tab", String(row.tabName || "&clipboard")
      ]
    }
    if (copyOnly) args.push("--copy-only")
    // Dismiss first so the previous window can take focus before paste.
    root.dismiss()
    Quickshell.execDetached(args)
  }

  function removeSelected() {
    var row = root.currentRow()
    if (!row) return
    if (row.hotId && String(row.hotId).length > 0) {
      Quickshell.execDetached([root.removeHelper, "--hot-id", String(row.hotId)])
    } else {
      Quickshell.execDetached([
        root.removeHelper,
        "--index", String(row.copyqIndex),
        "--tab", String(row.tabName || "&clipboard")
      ])
    }
    // Give CopyQ a beat to finish the remove before re-listing.
    reloadAfterMutate.restart()
  }

  function togglePinSelected() {
    var row = root.currentRow()
    if (!row) return
    // Hot vault keys are not pin-able. Pin must not delete them; Delete does.
    if (row.hotId && String(row.hotId).length > 0)
      return
    // Pins tab → remove (unpin). Clipboard tab → copy into Pins.
    Quickshell.execDetached([
      root.pinHelper,
      "--index", String(row.copyqIndex),
      "--tab", String(row.tabName || "&clipboard")
    ])
    reloadAfterMutate.restart()
  }

  function handleKeys(event, fromFilter) {
    if (event.key === Qt.Key_Down) { root.select(1); event.accepted = true }
    else if (event.key === Qt.Key_Up) { root.select(-1); event.accepted = true }
    else if (event.key === Qt.Key_PageDown) { root.page(1); event.accepted = true }
    else if (event.key === Qt.Key_PageUp) { root.page(-1); event.accepted = true }
    else if (event.key === Qt.Key_Home) { root.selectAbsolute(0); event.accepted = true }
    else if (event.key === Qt.Key_End) { root.selectAbsolute(displayModel.count - 1); event.accepted = true }
    else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
      root.activateSelected(event.modifiers & Qt.ShiftModifier)
      event.accepted = true
    } else if (event.key === Qt.Key_Escape) {
      root.dismiss()
      event.accepted = true
    } else if (event.key === Qt.Key_Delete) {
      // Never delete history while the search field owns the key (char delete).
      if (fromFilter) return
      root.removeSelected()
      event.accepted = true
    } else if (event.key === Qt.Key_J && (event.modifiers & Qt.ControlModifier)) {
      root.select(1); event.accepted = true
    } else if (event.key === Qt.Key_K && (event.modifiers & Qt.ControlModifier)) {
      root.select(-1); event.accepted = true
    } else if (event.key === Qt.Key_R) {
      // While the search field is focused, R (and Shift+R) is a letter.
      // Reload is Ctrl+R there, and bare R only when focus is on the list.
      var ctrl = !!(event.modifiers & Qt.ControlModifier)
      if (ctrl || !fromFilter) {
        root.reloadList(true)
        event.accepted = true
      }
    } else if (event.key === Qt.Key_P && (event.modifiers & Qt.ControlModifier)) {
      root.togglePinSelected(); event.accepted = true
    }
  }

  ListModel { id: displayModel }

  Timer {
    id: reloadAfterMutate
    interval: 180
    repeat: false
    onTriggered: root.reloadList()
  }

  Timer {
    id: listWatchdog
    interval: 9000
    repeat: false
    onTriggered: {
      if (!root.listInFlight) return
      listProc.running = false
      root.listInFlight = false
      root.errorText = "CopyQ list timed out"
      root.statusText = root.errorText
    }
  }

  Process {
    id: listProc
    command: ["/usr/bin/python3", root.listHelper, "80"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        listWatchdog.stop()
        root.applyListPayload(text)
      }
    }
    onRunningChanged: {
      if (running) listWatchdog.restart()
      else listWatchdog.stop()
    }
    onExited: function(code) {
      listWatchdog.stop()
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
      x: Math.round((panel.width - width) / 2)
      y: Math.round((panel.height - height) / 2)
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
            Keys.onPressed: function(event) { root.handleKeys(event, true) }
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
          interactive: true
          pressDelay: 0
          model: displayModel
          spacing: Style.spacing.xs
          currentIndex: root.cursorActive ? root.selectedIndex : -1
          delegate: Rectangle {
            id: rowDelegate
            required property int index
            required property string previewText
            required property int copyqIndex
            required property string tabName
            required property bool pinned
            required property bool hot
            required property string hotId
            required property string entryType
            required property string previewPath
            width: resultList.width
            height: root.rowHeight
            radius: Math.max(6, root.cornerRadius - 2)
            color: (root.cursorActive && index === root.selectedIndex)
              ? root.selectedBackground
              : "transparent"

            RowLayout {
              anchors.fill: parent
              anchors.margins: Style.spacing.rowPaddingX
              spacing: Style.spacing.sm
              z: 0

              Text {
                text: rowDelegate.hot ? "⏱" : (rowDelegate.pinned ? "★" : " ")
                color: (root.cursorActive && rowDelegate.index === root.selectedIndex)
                  ? root.selectedText
                  : root.foreground
                opacity: (rowDelegate.hot || rowDelegate.pinned) ? 0.9 : 0.25
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                textFormat: Text.PlainText
                Layout.preferredWidth: Style.space(16)
              }

              Image {
                visible: rowDelegate.entryType === "image" && rowDelegate.previewPath.length > 0
                source: rowDelegate.previewPath.length > 0 ? ("file://" + rowDelegate.previewPath) : ""
                fillMode: Image.PreserveAspectCrop
                Layout.preferredWidth: root.thumbSize
                Layout.preferredHeight: root.thumbSize
                asynchronous: true
                cache: false
              }

              Text {
                Layout.fillWidth: true
                Layout.fillHeight: true
                verticalAlignment: Text.AlignVCenter
                text: rowDelegate.previewText
                color: (root.cursorActive && rowDelegate.index === root.selectedIndex)
                  ? root.selectedText
                  : root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                elide: Text.ElideRight
                textFormat: Text.PlainText
              }
            }

            MouseArea {
              anchors.fill: parent
              z: 1
              hoverEnabled: true
              preventStealing: true
              cursorShape: Qt.PointingHandCursor
              acceptedButtons: Qt.LeftButton | Qt.RightButton
              onEntered: {
                root.cursorActive = true
                root.selectedIndex = rowDelegate.index
              }
              onPressed: function(mouse) {
                root.cursorActive = true
                root.selectedIndex = rowDelegate.index
                mouse.accepted = true
              }
              onClicked: function(mouse) {
                root.selectedIndex = rowDelegate.index
                if (mouse.button === Qt.RightButton) root.togglePinSelected()
                else root.activateSelected(false)
              }
            }
          }
        }

        Text {
          Layout.fillWidth: true
          // One line, never wrapped: the most-used keys first, the rest elide.
          text: root.errorText || "Enter paste  ·  Shift+Enter copy  ·  Ctrl+P pin  ·  Del remove  ·  Ctrl+R reload  ·  Esc close"
          color: root.foreground
          opacity: root.errorText ? 0.9 : 0.45
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: root.errorText ? Text.WordWrap : Text.NoWrap
          elide: Text.ElideRight
          textFormat: Text.PlainText
        }
      }
    }

    Item {
      id: keyCatcher
      focus: root.opened
      Keys.onPressed: function(event) { root.handleKeys(event, false) }
    }
  }
}
