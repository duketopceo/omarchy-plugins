import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons

// Always-on watcher for io.github.duketopceo.bumblebee — the radar that keeps
// working with the dropdown closed.
//
// Once an hour it execs `scan_bumblebee.py age` — a pure-stat probe (~1 file
// read, no scan). When the cached scan is older than 6h (or missing) it runs
// a real `scan_bumblebee.py --force` under a 35s group-kill deadline. The
// result is watermark-diffed against `lastSeenExposures` persisted in this
// plugin's shell.json entry: only NEW exposure ids raise an urgent toast.
// The first observation ever recorded is the baseline — silent, so a fresh
// install never alerts on exposures it already had. Zero exposures is
// always silent.
//
// Toasts are the plugin's own PanelWindows (like first-party notifications):
// Overlay layer, click-through except the card column, ~10s lifetime, click
// dismisses, at most 3 stacked.
Item {
  id: root
  width: 0
  height: 0
  visible: false

  // Injected by the shell's service loader (ensureService in shell.qml).
  property var shell: null
  property var manifest: null
  property var pluginRegistry: null
  property var barWidgetRegistry: null
  property string omarchyPath: ""

  readonly property string pluginId: "io.github.duketopceo.bumblebee"
  readonly property string pluginRoot: {
    var p = Qt.resolvedUrl(".").toString()
    if (p.indexOf("file://") === 0) p = p.substring(7)
    if (p.length > 1 && p.charAt(p.length - 1) === "/") p = p.substring(0, p.length - 1)
    return p
  }

  // Absolute interpreter + minimal env — same contract as the panel.
  readonly property string py: "/usr/bin/python3"
  readonly property var procEnv: ({
    "PATH": "/usr/bin:/bin",
    "HOME": null,
    "XDG_RUNTIME_DIR": null,
    "LANG": null,
    "LC_ALL": "C"
  })

  readonly property int staleAfterS: 6 * 3600   // helper's default interval
  readonly property int pollMs: 60 * 60 * 1000  // 1 stat per hour
  readonly property int toastMs: 10000
  readonly property int maxToasts: 3

  readonly property color urgent: Color.urgent
  readonly property color popupBg: Color.notifications.background
  readonly property color popupText: Color.notifications.text
  readonly property color dimText: Qt.darker(Color.notifications.text, 1.4)
  readonly property string fontFamily: root.shell && root.shell.bar
                                       ? root.shell.bar.fontFamily
                                       : Style.font.family

  // Toasts only clear the bar when it sits on the top edge (same read the
  // notifications service makes).
  readonly property string barPosition: root.shell && root.shell.barConfig
                                        ? String(root.shell.barConfig.position || "top")
                                        : "top"
  readonly property int topMargin: (barPosition === "top"
      ? Math.max(0, root.shell && root.shell.bar
                 ? root.shell.bar.barSize : 28)
      : 0) + Style.gapsOut

  // Toast queue for bursts that outnumber maxToasts on screen.
  property var _pending: []

  LocalSettings { id: ls; pluginId: root.pluginId }
  ListModel { id: popupModel }

  // "name|ecosystem|package@version" — mirrors _exposure_ids in
  // scan_bumblebee.py so display names can be matched to emitted ids.
  function exposureId(e) {
    if (!e || typeof e !== "object") return ""
    var key = String(e.name || "") + "|" + String(e.ecosystem || "")
            + "|" + String(e.package || "") + "@" + String(e.version || "")
    return key.replace(/[|@]/g, "").length ? key : ""
  }

  // [{id, name}] in scan order. exposure_ids drives the diff; the exposures
  // list supplies display names for matching ids (same order, same source).
  function pairsFrom(data) {
    var names = {}
    var exposures = Array.isArray(data.exposures) ? data.exposures : []
    for (var i = 0; i < exposures.length && i < 50; i++) {
      var eid = exposureId(exposures[i])
      if (!eid) continue
      var label = String(exposures[i].name || exposures[i].package || "")
      names[eid] = label !== "" ? label : "unnamed exposure"
    }
    var pairs = []
    var ids = Array.isArray(data.exposure_ids) ? data.exposure_ids : []
    for (var j = 0; j < ids.length && j < 50; j++) {
      var s = String(ids[j] || "")
      if (s !== "") pairs.push({ id: s, name: names[s] || s })
    }
    if (pairs.length === 0) {
      for (var k in names) pairs.push({ id: k, name: names[k] })
    }
    return pairs
  }

  function lastSeen() {
    var e = ls.entry
    if (e && typeof e === "object" && !Array.isArray(e)
        && Array.isArray(e.lastSeenExposures))
      return e.lastSeenExposures
    return null  // no persisted watermark — first observation
  }

  // Read-modify-write via the host's scoped updateEntryInline; remember()
  // keeps the write-through copy coherent until the file watcher lands.
  // Falls back to in-memory only when the host API is absent — a restart
  // then rebaselines silently, which is the safe direction.
  function persistLastSeen(ids) {
    var cur = ls.entry
    var entry = {}
    if (cur && typeof cur === "object" && !Array.isArray(cur)) {
      for (var k in cur) entry[k] = cur[k]
    }
    entry.lastSeenExposures = ids
    ls.remember(entry)
    if (root.shell && typeof root.shell.updateEntryInline === "function") {
      try { root.shell.updateEntryInline(root.pluginId, entry) } catch (e) {}
    }
  }

  function diffNow(data) {
    if (!ls.loaded) return  // settings not read yet; the next poll diffs
    var pairs = pairsFrom(data)
    var ids = pairs.map(function (p) { return p.id })
    var seen = lastSeen()
    if (seen === null) {
      // First observation: record the baseline silently.
      persistLastSeen(ids)
      return
    }
    var fresh = []
    for (var i = 0; i < pairs.length; i++) {
      if (seen.indexOf(pairs[i].id) === -1) fresh.push(pairs[i])
    }
    if (fresh.length > 0) enqueueToast(fresh.length, fresh[0].name)
    persistLastSeen(ids)
  }

  function enqueueToast(count, name) {
    var row = {
      count: count,
      topName: String(name || "").substring(0, 96),
      stamp: Date.now()
    }
    if (popupModel.count < maxToasts) {
      popupModel.append(row)
    } else {
      _pending.push(row)
      while (_pending.length > maxToasts) _pending.shift()
    }
  }

  function dismissToast(index) {
    if (index < 0 || index >= popupModel.count) return
    popupModel.remove(index)
    while (_pending.length > 0 && popupModel.count < maxToasts) {
      popupModel.append(_pending.shift())
    }
  }

  function poll() {
    if (ageProc.running || scanProc.running) return
    ageProc.command = [root.py, root.pluginRoot + "/bin/scan_bumblebee.py", "age"]
    ageProc.running = true
    ageDeadline.restart()
  }

  function forceScan() {
    if (scanProc.running) return
    scanProc.command = [root.py, root.pluginRoot + "/bin/scan_bumblebee.py", "--force"]
    scanProc.running = true
    scanDeadline.restart()
  }

  // ------------------------------------------------------------- watcher

  Timer {
    id: pollTimer
    interval: root.pollMs
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.poll()
  }

  Process {
    id: ageProc
    command: [root.py, root.pluginRoot + "/bin/scan_bumblebee.py", "age"]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        ageDeadline.stop()
        try {
          if (!text || text.trim().length === 0) return
          if (text.length > 300000) return
          var data = JSON.parse(text)
          if (!data || typeof data !== "object") return
          var installed = data.installed === true
          var age = (typeof data.last_scan_age_s === "number"
                     && isFinite(data.last_scan_age_s))
                    ? data.last_scan_age_s : -1
          if (installed && (age < 0 || age > root.staleAfterS)) {
            // Stale or never scanned — rescan, then diff the fresh result.
            root.forceScan()
            return
          }
          root.diffNow(data)
        } catch (e) {}
      }
    }
    onExited: ageDeadline.stop()
  }

  // Cheap stat probe: the helper answers in ms, so 8s is generous.
  Timer {
    id: ageDeadline
    interval: 8000
    onTriggered: {
      if (ageProc.running) {
        var pid = ageProc.pid
        if (pid > 0)
          Quickshell.execDetached(["/usr/bin/kill", "-KILL", "--", "-" + pid.toString()])
        ageProc.signal(9)
      }
    }
  }

  Process {
    id: scanProc
    command: [root.py, root.pluginRoot + "/bin/scan_bumblebee.py", "--force"]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        scanDeadline.stop()
        try {
          if (!text || text.trim().length === 0) return
          if (text.length > 300000) return
          var data = JSON.parse(text)
          if (!data || typeof data !== "object") return
          if (data.error) return  // a failed scan must not advance the watermark
          root.diffNow(data)
        } catch (e) {}
      }
    }
    onExited: scanDeadline.stop()
  }

  // Cold scans walk the whole package inventory — allow real time. The
  // helper's own backstop is 30s; group-kill reaps its session tree.
  Timer {
    id: scanDeadline
    interval: 35000
    onTriggered: {
      if (scanProc.running) {
        var pid = scanProc.pid
        if (pid > 0)
          Quickshell.execDetached(["/usr/bin/kill", "-KILL", "--", "-" + pid.toString()])
        scanProc.signal(9)
      }
    }
  }

  // ------------------------------------------------------------- toasts
  //
  // One PanelWindow per output holding the toast stack — Overlay layer,
  // click-through outside the card column, never keyboard focus.

  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: popupWindow
      required property var modelData
      screen: modelData
      visible: popupModel.count > 0

      WlrLayershell.namespace: "omarchy-bumblebee-alerts"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      exclusionMode: ExclusionMode.Ignore
      color: "transparent"
      anchors { top: true; bottom: true; left: true; right: true }
      mask: Region { item: popupColumn }

      ColumnLayout {
        id: popupColumn
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: root.topMargin
        anchors.rightMargin: Style.gapsOut
        spacing: Style.space(8)

        Repeater {
          model: popupModel

          delegate: Rectangle {
            id: card
            required property int index
            required property int count
            required property string topName
            required property double stamp

            Layout.alignment: Qt.AlignRight
            Layout.preferredWidth: cardRow.implicitWidth + Style.space(24)
            implicitHeight: cardRow.implicitHeight + Style.space(14)
            radius: Style.cornerRadius
            color: root.popupBg
            border.width: 1
            border.color: Qt.rgba(root.urgent.r, root.urgent.g,
                                  root.urgent.b, 0.55)

            // ~10s on screen, then it removes itself; a click dismisses now.
            Timer {
              interval: root.toastMs
              running: true
              onTriggered: root.dismissToast(card.index)
            }

            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.dismissToast(card.index)
            }

            Row {
              id: cardRow
              anchors.centerIn: parent
              spacing: Style.space(10)

              Rectangle {
                width: Style.space(30)
                height: Style.space(30)
                radius: Style.cornerRadius
                color: Qt.rgba(root.urgent.r, root.urgent.g,
                               root.urgent.b, 0.15)
                anchors.verticalCenter: parent.verticalCenter

                Text {
                  anchors.centerIn: parent
                  text: "󰒃"
                  textFormat: Text.PlainText
                  color: root.urgent
                  font.pixelSize: Style.space(16)
                }
              }

              Column {
                spacing: Style.space(1)
                anchors.verticalCenter: parent.verticalCenter

                Text {
                  text: card.count === 1
                        ? "1 component matches a known compromise"
                        : card.count + " components match known compromises"
                  textFormat: Text.PlainText
                  color: root.popupText
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                }
                Text {
                  visible: card.topName !== ""
                  text: card.topName
                  textFormat: Text.PlainText
                  color: root.urgent
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }
                Text {
                  text: "supply-chain exposure · click to dismiss"
                  textFormat: Text.PlainText
                  color: root.dimText
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
