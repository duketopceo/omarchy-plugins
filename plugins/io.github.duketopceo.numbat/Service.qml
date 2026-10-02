import QtQuick
import QtQuick.Layouts
import QtQml.Models
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons

// Persistent findings watcher for io.github.duketopceo.numbat — the radar
// that keeps working with the dropdown closed.
//
// A 5s poll runs `probe_numbat.py tail` (pure file stats — no content
// reads, no scan) and diffs the (size, mtime) signature of the two record
// sinks. On change, a full probe runs and any finding whose observed_at
// is newer than the persisted lastSeen watermark becomes a severity-tinted
// toast in a per-screen overlay window (max 3). Toasts are severity-gated
// (toastMinSeverity, default medium), per-rule|agent cooled-down
// (toastCooldownS, default 30m), coalesced into one summary card per burst,
// lifetime scales with severity (critical sticks until clicked), and all
// toasts suppress while the notification service reports do-not-disturb.
//
// The first observation after load is baseline only: the watermark adopts
// the newest record time on top of whatever was persisted, so a backlog
// can never storm popups. Watermark persists as `lastSeenFinding` on this
// plugin's shell.json entry via the host's scoped updateEntryInline.
Item {
  id: root
  width: 0
  height: 0
  visible: false

  // Injected by the omarchy shell's service loader.
  property var shell: null
  property var manifest: null
  property var pluginRegistry: null
  property var barWidgetRegistry: null
  property string omarchyPath: ""

  readonly property string pluginId: manifest && manifest.id ? String(manifest.id) : "io.github.duketopceo.numbat"

  LocalSettings { id: ls; pluginId: root.pluginId }

  // Watermark in epoch seconds: the newest finding time already absorbed
  // (toasted or baselined). Hydrated once from the persisted entry.
  property double lastSeen: 0
  property bool lastSeenHydrated: false
  property bool observedOnce: false
  property bool probeQueued: false
  property string prevSignature: ""

  readonly property int maxToasts: 3
  readonly property real toastLifetime: 8000

  // Toast policy (shell.json entry keys; LocalSettings-hydrated):
  //   toastMinSeverity — "info"|"low"|"medium"|"high"|"critical", default
  //     "medium". Lower-severity findings still land in the panel.
  //   toastCooldownS — per rule|agent toast cooldown, default 1800.
  readonly property int toastMinRank: {
    var e = ls.loaded ? ls.entry : null
    var s = e && e.toastMinSeverity !== undefined
            ? String(e.toastMinSeverity).toLowerCase() : "medium"
    var r = sevRank(s)
    return r >= 0 ? r : 2
  }
  readonly property int toastCooldownMs: {
    var e = ls.loaded ? ls.entry : null
    var s = e ? Number(e.toastCooldownS) : NaN
    return isFinite(s) && s > 0 ? s * 1000 : 30 * 60 * 1000
  }

  // rule|agent -> epoch ms of the last toast it produced. Session-scoped:
  // a shell restart re-arms cooled-down rules, which is the safe direction.
  property var _ruleLastToast: ({})

  // Do-not-disturb, resolved from whichever notifications service is live
  // (clone-aware — the same call the notification-center panel makes).
  // Fail-open: no service means toasts behave as before.
  readonly property var notificationService: {
    var host = root.shell
    if (!host || typeof host.serviceFor !== "function") return null
    var id = "omarchy.notifications"
    if (root.pluginRegistry
        && typeof root.pluginRegistry.resolveEnabledId === "function")
      id = root.pluginRegistry.resolveEnabledId(id)
    return host.serviceFor(id)
  }
  readonly property bool dnd: notificationService
                              ? notificationService.doNotDisturb === true
                              : false

  readonly property string pluginRoot: {
    var p = Qt.resolvedUrl(".").toString()
    if (p.indexOf("file://") === 0) p = p.substring(7)
    if (p.length > 1 && p.charAt(p.length - 1) === "/") p = p.substring(0, p.length - 1)
    return p
  }
  readonly property string py: "/usr/bin/python3"
  readonly property string probePath: pluginRoot + "/bin/probe_numbat.py"
  // Absolute interpreter + minimal env: a PATH-preceding shadow "python3"
  // must never run inside this long-lived shell process. The helper
  // resolves HOME itself via passwd, so it is not passed through.
  readonly property var procEnv: ({
    "PATH": "/usr/bin:/bin",
    "HOME": null,
    "XDG_RUNTIME_DIR": null,
    "LANG": null,
    "LC_ALL": "C"
  })

  // Toast placement mirrors the notifications service: top-right corner,
  // clearing the bar only when it occupies the top or right edge.
  readonly property string barPosition: shell && shell.barConfig ? String(shell.barConfig.position || "top") : "top"
  readonly property bool barVertical: barPosition === "left" || barPosition === "right"
  readonly property int defaultBarSize: barVertical ? Style.bar.sizeVertical : Style.bar.sizeHorizontal
  readonly property int liveBarSize: shell && shell.bar && !shell.bar.barHidden ? Math.max(0, shell.bar.barSize) : defaultBarSize
  readonly property int barClearance: liveBarSize + Style.gapsOut

  readonly property color foreground: Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.5)
  readonly property color accent: Color.accent
  readonly property color urgent: (Color.urgent === undefined || Color.urgent === null) ? foreground : Color.urgent
  readonly property color cardText: Color.notifications.text
  readonly property color cardDim: Qt.darker(cardText, 1.4)
  readonly property string fontFamily: {
    var f = shell && shell.bar ? String(shell.bar.fontFamily || "") : ""
    return f !== "" ? f : Style.font.family
  }

  // _rgb / accentFill / urgentFill / fgFill — same helpers the panel uses,
  // so every tint derives from theme colors and never a hardcoded hex.
  function _rgb(c) {
    if (typeof c === "string") {
      var h = c.charAt(0) === "#" ? c.substring(1) : c
      if (h.length === 8) h = h.substring(0, 6)
      if (h.length === 3)
        h = h.charAt(0) + h.charAt(0) + h.charAt(1) + h.charAt(1) + h.charAt(2) + h.charAt(2)
      if (h.length === 6) {
        return [parseInt(h.substring(0, 2), 16) / 255,
                parseInt(h.substring(2, 4), 16) / 255,
                parseInt(h.substring(4, 6), 16) / 255]
      }
      return [1, 1, 1]
    }
    if (c === undefined || c === null) return [1, 1, 1]
    return [c.r, c.g, c.b]
  }

  function accentFill(alpha) {
    var rgb = _rgb(accent)
    return Qt.rgba(rgb[0], rgb[1], rgb[2], alpha)
  }

  function urgentFill(alpha) {
    var rgb = _rgb(urgent)
    return Qt.rgba(rgb[0], rgb[1], rgb[2], alpha)
  }

  function fgFill(alpha) {
    var rgb = _rgb(foreground)
    return Qt.rgba(rgb[0], rgb[1], rgb[2], alpha)
  }

  function relTime(iso) {
    if (!iso) return "—"
    var ms = new Date(String(iso)).getTime()
    if (!isFinite(ms)) return "—"
    var m = Math.floor(Math.max(0, Date.now() - ms) / 60000)
    if (m < 1) return "just now"
    var h = Math.floor(m / 60)
    var d = Math.floor(h / 24)
    if (d > 0) return d + "d " + (h % 24) + "h ago"
    if (h > 0) return h + "h " + (m % 60) + "m ago"
    return m + "m ago"
  }

  // Severity ranks drive gating AND lifetime. Unknown/empty → medium (2):
  // an unclassified finding still toasts rather than silently dropping.
  function sevRank(sev) {
    var s = String(sev === undefined || sev === null ? "" : sev).toLowerCase()
    if (s === "critical" || s === "crit") return 4
    if (s === "high" || s === "error") return 3
    if (s === "medium" || s === "moderate" || s === "warning" || s === "warn") return 2
    if (s === "low") return 1
    if (s === "info" || s === "debug" || s === "none" || s === "") return 0
    return 2
  }

  // Meaningful severity tints the card urgent; absent/low stays accent.
  function severe(sev) {
    var s = String(sev === undefined || sev === null ? "" : sev).toLowerCase()
    return s !== "" && sevRank(s) >= 2
  }

  // Lifetime per severity: critical sticks until clicked, the rest fade.
  function toastMsFor(sev) {
    var r = sevRank(sev)
    if (r >= 4) return 0
    if (r === 3) return 15000
    if (r === 2) return 8000
    return 6000
  }

  // --------------------------------------------------------- watermark ---

  function hydrateLastSeen() {
    if (root.lastSeenHydrated || !ls.loaded) return
    root.lastSeenHydrated = true
    var v = Number(ls.entry && ls.entry.lastSeenFinding)
    if (isFinite(v) && v > root.lastSeen) root.lastSeen = v
  }

  // Read-modify-write the plugin's shell.json entry: the stored keys are
  // preserved and only `lastSeenFinding` is added/advanced. remember()
  // keeps the write-through copy even when the host can't persist.
  function setLastSeen(ts) {
    ts = Number(ts)
    if (!isFinite(ts) || ts <= root.lastSeen) return
    root.lastSeen = ts
    var entry = {}
    var cur = ls.entry
    if (cur && typeof cur === "object") {
      for (var k in cur) entry[k] = cur[k]
    }
    entry.lastSeenFinding = ts
    ls.remember(entry)
    if (root.shell && typeof root.shell.updateEntryInline === "function") {
      try { root.shell.updateEntryInline(root.pluginId, entry) } catch (e) {}
    }
  }

  // ------------------------------------------------------------- polls ---

  function pollTail() {
    if (tailProc.running) return
    tailProc.running = true
    tailDeadline.restart()
  }

  function runProbe() {
    if (probeProc.running) {
      // Coalesce: one rerun after the in-flight probe is enough — the
      // watermark diff always converges on whatever is newest.
      root.probeQueued = true
      return
    }
    probeProc.running = true
    probeDeadline.restart()
  }

  function onTail(text) {
    if (!text || text.length > 65536) return
    var data
    try { data = JSON.parse(text) } catch (e) { return }
    if (typeof data !== "object" || data === null) return
    root.hydrateLastSeen()
    var newest = Number(data.newest_finding_ts)
    if (!isFinite(newest) || newest < 0) newest = 0
    var sig = [
      Number(data.findings_count) || 0,
      Number(data.findings_bytes) || 0,
      Number(data.findings_mtime) || 0,
      Number(data.records_count) || 0,
      Number(data.records_bytes) || 0,
      Number(data.records_mtime) || 0
    ].join(":")
    var changed = sig !== root.prevSignature
    root.prevSignature = sig
    if (!root.observedOnce) {
      // Baseline only: adopt the newest record time over the persisted
      // watermark and report nothing — what is already on disk is "the
      // world as it was", not a popup.
      root.observedOnce = true
      if (newest > root.lastSeen) root.setLastSeen(newest)
      return
    }
    if (!changed) return
    root.runProbe()
  }

  function onProbe(text) {
    if (!text || text.length > 300000) return
    var data
    try { data = JSON.parse(text) } catch (e) { return }
    if (typeof data !== "object" || data === null) return
    var findings = Array.isArray(data.findings) ? data.findings : []
    var maxSeen = root.lastSeen
    var fresh = []
    for (var i = 0; i < findings.length; i++) {
      var f = findings[i]
      if (!f || typeof f !== "object") continue
      var ms = Date.parse(String(f.observed_at || ""))
      if (!isFinite(ms)) continue
      var ts = ms / 1000.0
      if (ts > maxSeen) maxSeen = ts
      if (ts > root.lastSeen) fresh.push(f)
    }
    // Toast pipeline: severity gate -> per-rule cooldown -> DND ->
    // coalesce. Suppression never touches the watermark — a silenced
    // finding is still "seen" (panel stays truthful, nothing replays).
    var gated = []
    for (var g = 0; g < fresh.length; g++) {
      if (root.sevRank(fresh[g].severity) >= root.toastMinRank)
        gated.push(fresh[g])
    }
    var now = Date.now()
    var allowed = []
    for (var c = 0; c < gated.length; c++) {
      var fp = String(gated[c].rule || "finding") + "|"
             + String(gated[c].agent || "")
      var last = Number(root._ruleLastToast[fp]) || 0
      if (now - last >= root.toastCooldownMs) allowed.push(gated[c])
    }
    if (!root.dnd && allowed.length > 0 && toastModel.count < root.maxToasts) {
      var rows = allowed
      Qt.callLater(function() {
        if (toastModel.count >= root.maxToasts) return
        if (rows.length === 1) {
          var row = rows[0]
          toastModel.append({
            "count": 0,
            "rule": String(row.rule || "finding"),
            "agent": String(row.agent || ""),
            "observedAt": String(row.observed_at || ""),
            "severity": String(row.severity === undefined || row.severity === null ? "" : row.severity)
          })
        } else {
          // Summary card: one toast per burst. Title reports the worst
          // severity in the batch; the panel carries the full list.
          var top = rows[0]
          for (var t = 1; t < rows.length; t++) {
            if (root.sevRank(rows[t].severity) > root.sevRank(top.severity))
              top = rows[t]
          }
          toastModel.append({
            "count": rows.length,
            "rule": String(top.rule || "finding"),
            "agent": String(top.agent || ""),
            "observedAt": String(top.observed_at || ""),
            "severity": String(top.severity === undefined || top.severity === null ? "" : top.severity)
          })
        }
        for (var m = 0; m < rows.length; m++) {
          var k = String(rows[m].rule || "finding") + "|"
                + String(rows[m].agent || "")
          root._ruleLastToast[k] = now
        }
      })
    }
    if (maxSeen > root.lastSeen) root.setLastSeen(maxSeen)
  }

  function dropToast(index) {
    if (index < 0 || index >= toastModel.count) return
    toastModel.remove(index)
  }

  ListModel { id: toastModel }

  Process {
    id: tailProc
    command: [root.py, root.probePath, "tail"]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        tailDeadline.stop()
        root.onTail(text)
      }
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var err = String(text || "").trim()
        if (err)
          console.warn("probe_numbat tail stderr: " + err.substring(0, 500))
      }
    }
    onExited: tailDeadline.stop()
  }

  // Hard deadline with group-kill: probe_numbat.py calls os.setsid() so
  // killpg reaches the whole tree — same contract as the panel's watchdog.
  Timer {
    id: tailDeadline
    interval: 8000
    onTriggered: {
      if (tailProc.running) {
        var pid = tailProc.pid
        if (pid > 0)
          Quickshell.execDetached(["/usr/bin/kill", "-KILL", "--", "-" + pid.toString()])
        tailProc.signal(9)
      }
    }
  }

  Process {
    id: probeProc
    command: [root.py, root.probePath]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        probeDeadline.stop()
        root.onProbe(text)
      }
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var err = String(text || "").trim()
        if (err)
          console.warn("probe_numbat stderr: " + err.substring(0, 500))
      }
    }
    onExited: {
      probeDeadline.stop()
      if (root.probeQueued) {
        root.probeQueued = false
        root.runProbe()
      }
    }
  }

  // Same backstop contract as the panel's statusDeadline: just past the
  // helper's own JOB_DEADLINE_S (30s) so a slow-but-healthy `numbat scan`
  // (~28s worst case) still lands its packet; group-kill via setsid stays
  // the last resort for a wedged process, not a timeout on useful work.
  Timer {
    id: probeDeadline
    interval: 35000
    onTriggered: {
      if (probeProc.running) {
        var pid = probeProc.pid
        if (pid > 0)
          Quickshell.execDetached(["/usr/bin/kill", "-KILL", "--", "-" + pid.toString()])
        probeProc.signal(9)
      }
    }
  }

  Timer {
    id: pollTimer
    interval: 5000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.pollTail()
  }

  // ----------------------------------------------------------- toast UI --
  //
  // One PanelWindow per output (Variants on Quickshell.screens) holding the
  // stacked finding cards — the same layer-shell pattern the notifications
  // service uses for its toasts. Overlay layer, exclusionMode Ignore, no
  // keyboard focus: passive surfaces that never steal input.

  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: toastWindow
      required property var modelData
      screen: modelData
      visible: toastModel.count > 0

      WlrLayershell.namespace: "omarchy-numbat-findings"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      exclusionMode: ExclusionMode.Ignore
      color: "transparent"

      // Full-screen, fixed-size surface so adding/removing a toast never
      // resizes the Wayland buffer — only the content changes.
      anchors { top: true; bottom: true; left: true; right: true }

      // Click-through except over the toast column.
      mask: Region { item: toastColumn }

      ColumnLayout {
        id: toastColumn
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: root.barPosition === "top" ? root.barClearance : Style.gapsOut
        anchors.rightMargin: root.barPosition === "right" ? root.barClearance : Style.gapsOut
        spacing: Style.space(8)

        Repeater {
          model: toastModel

          // The delegate slot owns the lifetime timer; the card is pure
          // presentation — same split as the notifications stack.
          delegate: Item {
            id: cardSlot
            required property int index
            required property int count
            required property string rule
            required property string agent
            required property string observedAt
            required property string severity

            Layout.preferredWidth: card.implicitWidth
            Layout.alignment: Qt.AlignRight
            implicitHeight: card.implicitHeight

            // 0 = sticky (critical), else severity-scaled fade.
            readonly property real lifetime: root.toastMsFor(cardSlot.severity)
            property real remainingLifetime: 1.0
            readonly property bool ticking: cardSlot.lifetime > 0 && !cardArea.containsMouse

            Timer {
              interval: 50
              repeat: true
              running: cardSlot.ticking
              onTriggered: {
                if (cardSlot.lifetime <= 0) return
                cardSlot.remainingLifetime -= 50.0 / cardSlot.lifetime
                if (cardSlot.remainingLifetime <= 0) {
                  cardSlot.remainingLifetime = 0
                  root.dropToast(cardSlot.index)
                }
              }
            }

            Rectangle {
              id: card
              anchors.right: parent.right
              implicitWidth: Style.space(340)
              implicitHeight: cardColumn.implicitHeight + Style.space(18)
              radius: Style.cornerRadius
              color: Color.notifications.background
              border.color: root.severe(cardSlot.severity) ? root.urgentFill(0.5) : root.accentFill(0.35)
              clip: true

              // Severity edge strip — same idiom as the findings tab rows.
              Rectangle {
                width: Style.space(3)
                height: parent.height - Style.space(16)
                radius: width / 2
                anchors.left: parent.left
                anchors.leftMargin: Style.space(6)
                anchors.verticalCenter: parent.verticalCenter
                color: root.severe(cardSlot.severity) ? root.urgent : root.fgFill(0.14)
              }

              Column {
                id: cardColumn
                anchors.left: parent.left
                anchors.leftMargin: Style.space(16)
                anchors.right: parent.right
                anchors.rightMargin: Style.space(10)
                anchors.top: parent.top
                anchors.topMargin: Style.space(9)
                spacing: Style.space(2)

                Row {
                  width: parent.width
                  spacing: Style.space(6)

                  Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: cardSlot.count > 0
                          ? "NUMBAT · " + cardSlot.count + " FINDINGS"
                          : "NUMBAT FINDING"
                    textFormat: Text.PlainText
                    color: root.severe(cardSlot.severity) ? root.urgent : root.cardDim
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                    font.bold: true
                  }

                  // Severity chip — only when the record carried the field.
                  Rectangle {
                    visible: cardSlot.severity !== ""
                    height: Style.space(16)
                    width: sevText.implicitWidth + Style.space(10)
                    radius: Style.cornerRadius
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.severe(cardSlot.severity) ? root.urgentFill(0.2) : root.accentFill(0.15)
                    border.color: root.severe(cardSlot.severity) ? root.urgentFill(0.4) : root.accentFill(0.3)

                    Text {
                      id: sevText
                      anchors.centerIn: parent
                      text: cardSlot.severity.toUpperCase()
                      textFormat: Text.PlainText
                      color: root.severe(cardSlot.severity) ? root.urgent : root.accent
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      font.bold: true
                    }
                  }
                }

                Text {
                  width: parent.width
                  text: cardSlot.count > 0
                        ? "worst: " + cardSlot.rule
                        : cardSlot.rule
                  textFormat: Text.PlainText
                  color: root.cardText
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                  elide: Text.ElideRight
                }

                Text {
                  width: parent.width
                  text: (cardSlot.agent !== "" ? cardSlot.agent : "unknown agent") + " · " + root.relTime(cardSlot.observedAt)
                  textFormat: Text.PlainText
                  color: root.cardDim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  elide: Text.ElideRight
                }
              }

              // Lifetime strip — drains left-to-right; hover pauses it.
              // Hidden on sticky (critical) cards, which never drain.
              Rectangle {
                visible: cardSlot.lifetime > 0
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                height: Style.space(2)
                width: parent.width * cardSlot.remainingLifetime
                color: root.severe(cardSlot.severity) ? root.urgentFill(0.7) : root.accentFill(0.5)
              }

              MouseArea {
                id: cardArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                // Click dismisses the toast and opens the findings panel via
                // the panel's IpcHandler (target = manifest id).
                onClicked: {
                  root.dropToast(cardSlot.index)
                  Quickshell.execDetached(["/usr/bin/qs", "ipc", "call",
                                           "io.github.duketopceo.numbat", "open"])
                }
              }
            }
          }
        }
      }
    }
  }
}
