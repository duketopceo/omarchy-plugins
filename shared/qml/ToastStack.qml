import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import qs.Commons

// Toast policy and stack shared by service plugins (bumblebee, numbat).
// Pipeline for push(): severity gate -> per-key cooldown -> do-not-disturb ->
// burst coalescing. Suppression is the caller's watermark business; this only
// decides what reaches the screen. Overflow beyond maxToasts is queued, never
// dropped, and drains as cards are dismissed.
Item {
  id: root
  width: 0
  height: 0
  visible: false

  property var shell: null
  property string namespace: "omarchy-plugin-toasts"
  property string glyph: "󰀦"
  property int maxToasts: 3
  // shell.json entry values (LocalSettings-hydrated by the caller).
  property var minSeverity: "medium"
  property var cooldownS: 1800

  readonly property int minRank: {
    var s = String(root.minSeverity === undefined || root.minSeverity === null ? "medium" : root.minSeverity).toLowerCase()
    // Only the five documented values; anything else falls back to medium.
    return ["info", "low", "medium", "high", "critical"].indexOf(s) === -1 ? 2 : sevRank(s)
  }
  readonly property int cooldownMs: {
    var n = Number(root.cooldownS)
    return isFinite(n) && n > 0 ? n * 1000 : 30 * 60 * 1000
  }

  readonly property var notificationService: {
    var host = root.shell
    if (!host || typeof host.serviceFor !== "function") return null
    var id = "omarchy.notifications"
    if (host.pluginRegistry && typeof host.pluginRegistry.resolveEnabledId === "function")
      id = host.pluginRegistry.resolveEnabledId(id)
    return host.serviceFor(id)
  }
  readonly property bool dnd: root.notificationService ? root.notificationService.doNotDisturb === true : false

  readonly property string barPosition: root.shell && root.shell.barConfig
                                        ? String(root.shell.barConfig.position || "top") : "top"
  readonly property int topMargin: (root.barPosition === "top"
      ? Math.max(0, root.shell && root.shell.bar ? root.shell.bar.barSize : 28) : 0) + Style.gapsOut
  readonly property string fontFamily: root.shell && root.shell.bar ? root.shell.bar.fontFamily : Style.font.family

  property var _lastToastByKey: ({})
  property var _pending: []

  function sevRank(sev) {
    var s = String(sev === undefined || sev === null ? "" : sev).toLowerCase()
    if (s === "critical" || s === "crit") return 4
    if (s === "high" || s === "error") return 3
    if (s === "medium" || s === "moderate" || s === "warning" || s === "warn") return 2
    if (s === "low") return 1
    if (s === "info" || s === "debug" || s === "none") return 0
    return 2
  }
  // Critical sticks until clicked (0); the rest fade.
  function toastMsFor(sev) {
    var r = sevRank(sev)
    if (r >= 4) return 0
    if (r === 3) return 15000
    if (r === 2) return 8000
    return 6000
  }
  function severe(sev) {
    var s = String(sev === undefined || sev === null ? "" : sev).toLowerCase()
    return s !== "" && sevRank(s) >= 2
  }

  // items: [{ key, severity, title, detail }]. summaryTitle(n) titles a burst.
  // Returns the number of items that passed the gates.
  function push(items, summaryTitle) {
    var list = Array.isArray(items) ? items : []
    var now = Date.now()
    var allowed = []
    for (var i = 0; i < list.length; i++) {
      var it = list[i]
      if (!it || sevRank(it.severity) < root.minRank) continue
      var key = String(it.key || "")
      var last = Number(root._lastToastByKey[key]) || 0
      if (key !== "" && now - last < root.cooldownMs) continue
      allowed.push(it)
    }
    if (root.dnd || allowed.length === 0) return 0
    var rows = allowed
    Qt.callLater(function() {
      if (root.dnd) return   // DND can flip on before the deferred append
      var top = rows[0]
      for (var t = 1; t < rows.length; t++)
        if (sevRank(rows[t].severity) > sevRank(top.severity)) top = rows[t]
      var row = {
        "title": rows.length === 1 ? String(top.title || "")
                 : (typeof summaryTitle === "function" ? String(summaryTitle(rows.length))
                    : rows.length + " new alerts"),
        "detail": String(top.detail || "").substring(0, 160),
        "severity": String(top.severity === undefined || top.severity === null ? "" : top.severity),
        "stamp": Date.now()
      }
      if (model.count < root.maxToasts) model.append(row)
      else {
        root._pending.push(row)
        while (root._pending.length > root.maxToasts) root._pending.shift()
      }
      for (var m = 0; m < rows.length; m++) {
        var k = String(rows[m].key || "")
        if (k !== "") root._lastToastByKey[k] = now
      }
    })
    return allowed.length
  }

  function dismiss(index) {
    if (index < 0 || index >= model.count) return
    model.remove(index)
    while (root._pending.length > 0 && model.count < root.maxToasts)
      model.append(root._pending.shift())
  }

  property ListModel model: ListModel {}

  Variants {
    model: Quickshell.screens

    PanelWindow {
      required property var modelData
      screen: modelData
      visible: root.model.count > 0
      WlrLayershell.namespace: root.namespace
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      exclusionMode: ExclusionMode.Ignore
      color: "transparent"
      anchors { top: true; bottom: true; left: true; right: true }
      mask: Region { item: column }

      ColumnLayout {
        id: column
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: root.topMargin
        anchors.rightMargin: Style.gapsOut
        spacing: Style.space(8)

        Repeater {
          model: root.model
          delegate: Rectangle {
            id: card
            required property int index
            required property string title
            required property string detail
            required property string severity
            readonly property int lifetimeMs: root.toastMsFor(severity)
            readonly property color tint: root.severe(severity) ? Color.urgent : Color.accent

            Layout.alignment: Qt.AlignRight
            Layout.preferredWidth: cardRow.implicitWidth + Style.space(24)
            implicitHeight: cardRow.implicitHeight + Style.space(14)
            radius: Style.cornerRadius
            color: Color.notifications.background
            border.width: 1
            border.color: Qt.rgba(card.tint.r, card.tint.g, card.tint.b, 0.55)

            Timer {
              interval: Math.max(1, card.lifetimeMs)
              running: card.lifetimeMs > 0
              onTriggered: root.dismiss(card.index)
            }
            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.dismiss(card.index)
            }
            Row {
              id: cardRow
              anchors.centerIn: parent
              spacing: Style.space(10)
              Text {
                text: root.glyph
                textFormat: Text.PlainText
                color: card.tint
                font.pixelSize: Style.space(16)
                anchors.verticalCenter: parent.verticalCenter
              }
              Column {
                spacing: Style.space(1)
                anchors.verticalCenter: parent.verticalCenter
                Text {
                  text: card.title
                  textFormat: Text.PlainText
                  color: Color.notifications.text
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                }
                Text {
                  visible: card.detail !== ""
                  text: card.detail
                  textFormat: Text.PlainText
                  color: Qt.darker(Color.notifications.text, 1.4)
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }
              }
            }
          }
        }
      }
    }
  }
}
