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
  readonly property int catalogStaleAfterS: 7 * 24 * 3600  // auto-refresh past a week
  readonly property int maxToasts: 3

  // Session-only throttle so a failed refresh retries next poll, not every
  // poll — the upstream tarball is a ~64MiB fetch.
  property double lastCatalogRefreshMs: 0

  // A refresh that lands while a scan is in flight queues one rescan on the
  // new catalog — otherwise the merged upstream.json sits unread until the
  // next stale tick (~6h).
  property bool _rescanAfterRefresh: false

  // Do-not-disturb, resolved from whichever notifications service is live
  // (clone-aware — same call the notification-center panel makes).
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

  // Exposure ids the user has muted via the panel — `ignoredExposures` on
  // this plugin's shell.json entry. Non-array/missing → empty, no crash.
  readonly property var ignoredExposures: {
    var e = ls.loaded ? ls.entry : null
    return (e && Array.isArray(e.ignoredExposures)) ? e.ignoredExposures : []
  }

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
  // Fields are _clean()'d (ctrl-chars→space, trim, 96/field) and the key
  // is clipped to 200 exactly like the scanner — a drift here silently
  // breaks both name matching and the panel's mute list.
  function _cleanField(v) {
    return String(v === undefined || v === null ? "" : v)
      .replace(/[\u0000-\u001f\u007f]/g, " ")
      .substring(0, 96)
      .replace(/^\s+|\s+$/g, "")
  }

  function exposureId(e) {
    if (!e || typeof e !== "object") return ""
    var key = _cleanField(e.name) + "|" + _cleanField(e.ecosystem)
            + "|" + _cleanField(e.package) + "@" + _cleanField(e.version)
    return key.replace(/[|@]/g, "").length ? key.substring(0, 200) : ""
  }

  // [{id, name, severity}] in scan order. exposure_ids drives the diff;
  // the exposures list supplies display names and catalog severity for
  // matching ids (same order, same source). Missing severity -> "high".
  function pairsFrom(data) {
    var names = {}
    var exposures = Array.isArray(data.exposures) ? data.exposures : []
    for (var i = 0; i < exposures.length && i < 50; i++) {
      var eid = exposureId(exposures[i])
      if (!eid) continue
      var label = String(exposures[i].name || exposures[i].package || "")
      var sv = String(exposures[i].severity === undefined
                      || exposures[i].severity === null
                      ? "" : exposures[i].severity)
      names[eid] = { name: label !== "" ? label : "unnamed exposure", sev: sv }
    }
    var pairs = []
    var ids = Array.isArray(data.exposure_ids) ? data.exposure_ids : []
    for (var j = 0; j < ids.length && j < 50; j++) {
      var s = String(ids[j] || "")
      if (s === "") continue
      var meta = names[s]
      pairs.push({ id: s,
                   name: meta ? meta.name : s,
                   severity: meta && meta.sev !== "" ? meta.sev : "high" })
    }
    if (pairs.length === 0) {
      for (var k in names)
        pairs.push({ id: k, name: names[k].name,
                     severity: names[k].sev !== "" ? names[k].sev : "high" })
    }
    return pairs
  }

  // Panel mute toggles route here so the write is authoritative on the
  // service's own (fresher) entry and lands in memory synchronously —
  // a panel-side shell.json write only reaches this instance on the
  // file watcher's next tick, which a running scan's diff can beat.
  function setMuted(id, muted) {
    if (!id) return
    var cur = ls.entry
    var entry = {}
    if (cur && typeof cur === "object" && !Array.isArray(cur)) {
      for (var k in cur) entry[k] = cur[k]
    }
    var ids = Array.isArray(entry.ignoredExposures)
              ? entry.ignoredExposures.slice() : []
    var i = ids.indexOf(id)
    if (muted && i === -1) ids.push(id)
    if (!muted && i !== -1) ids.splice(i, 1)
    entry.ignoredExposures = ids
    ls.remember(entry)
    if (root.shell && typeof root.shell.updateEntryInline === "function") {
      try { root.shell.updateEntryInline(root.pluginId, entry) } catch (e) {}
    }
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
    var ignored = root.ignoredExposures
    var fresh = []
    for (var i = 0; i < pairs.length; i++) {
      if (seen.indexOf(pairs[i].id) !== -1) continue
      if (ignored.indexOf(pairs[i].id) !== -1) continue  // muted — still seen
      fresh.push(pairs[i])
    }
    if (fresh.length > 0 && !root.dnd) {
      // Summary toast reports the worst severity in the burst.
      var worst = fresh[0]
      for (var w = 1; w < fresh.length; w++) {
        if (sevRank(fresh[w].severity) > sevRank(worst.severity))
          worst = fresh[w]
      }
      enqueueToast(fresh.length, worst.name, worst.severity)
    }
    persistLastSeen(ids)
  }

  // Same severity map as numbat — unknown/empty -> medium.
  function sevRank(sev) {
    var s = String(sev === undefined || sev === null ? "" : sev).toLowerCase()
    if (s === "critical" || s === "crit") return 4
    if (s === "high" || s === "error") return 3
    if (s === "medium" || s === "moderate" || s === "warning" || s === "warn") return 2
    if (s === "low") return 1
    if (s === "info" || s === "debug" || s === "none") return 0
    return 2
  }

  // Lifetime per severity, same map as numbat. Exposures carry the
  // catalog's severity field; ones without it are emitted as "high" by
  // pairsFrom. 0 = sticky.
  function toastMsFor(sev) {
    var s = String(sev === undefined || sev === null ? "" : sev).toLowerCase()
    if (s === "critical" || s === "crit") return 0
    if (s === "high" || s === "error") return 15000
    if (s === "medium" || s === "moderate" || s === "warning" || s === "warn")
      return 8000
    return 6000
  }

  function enqueueToast(count, name, severity) {
    var row = {
      count: count,
      topName: String(name || "").substring(0, 96),
      severity: String(severity || "high"),
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

  // Catalog staleness rides the hourly `age` probe (pure stat — the helper
  // emits upstream.json's age with no exec). Older than a week, or never
  // fetched: refresh once per poll cycle at most. Opt out by setting
  // "autoCatalogRefresh": false on this plugin's shell.json entry.
  function maybeRefreshCatalog(catAgeS) {
    if (ls.loaded && ls.entry && ls.entry.autoCatalogRefresh === false) return
    if (catalogRefreshProc.running) return
    if (catAgeS >= 0 && catAgeS <= catalogStaleAfterS) return
    var now = Date.now()
    if (now - lastCatalogRefreshMs < pollMs) return
    lastCatalogRefreshMs = now
    catalogRefreshProc.running = true
    refreshDeadline.restart()
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
          var catAge = (typeof data.catalog_age_s === "number"
                        && isFinite(data.catalog_age_s))
                       ? data.catalog_age_s : -1
          root.maybeRefreshCatalog(catAge)
          var age = (typeof data.last_scan_age_s === "number"
                     && isFinite(data.last_scan_age_s))
                    ? data.last_scan_age_s : -1
          if (installed && (age < 0 || age > root.staleAfterS)) {
            // Stale or never scanned — rescan, then diff the fresh result.
            // (Runs before the error check so a stale failed-scan cache
            // still triggers a rescan.)
            root.forceScan()
            return
          }
          // Same guard as scanProc: a cached failed scan must not reach the
          // watermark diff — its empty id set would persistLastSeen([]) and
          // clobber the baseline.
          if (data.error) return
          root.diffNow(data)
        } catch (e) {}
      }
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var err = String(text || "").trim()
        if (err)
          console.warn("scan_bumblebee age stderr: " + err.substring(0, 500))
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
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var err = String(text || "").trim()
        if (err)
          console.warn("scan_bumblebee --force stderr: " + err.substring(0, 500))
      }
    }
    onExited: {
      scanDeadline.stop()
      if (root._rescanAfterRefresh) {
        root._rescanAfterRefresh = false
        root.forceScan()
      }
    }
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

  // Auto-refresh of the pinned upstream threat_intel catalog — user-opt-out
  // via autoCatalogRefresh:false; the helper's own JOB_DEADLINE_S is 25s and
  // this deadline group-kills just past it.
  Process {
    id: catalogRefreshProc
    command: [root.py, root.pluginRoot + "/bin/refresh_catalog.py"]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        refreshDeadline.stop()
        try {
          if (!text || text.trim().length === 0) return
          var data = JSON.parse(text)
          if (!data || typeof data !== "object") return
          if (data.error) {
            console.warn("bumblebee: catalog auto-refresh failed: "
                         + String(data.error).substring(0, 120))
            return
          }
          if (data.ok === true) {
            // New catalog on disk — re-scan on it. If a scan is running it
            // may have read the old catalog; queue the rescan at its exit.
            if (scanProc.running) root._rescanAfterRefresh = true
            else root.forceScan()
          }
        } catch (e) {}
      }
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var err = String(text || "").trim()
        if (err)
          console.warn("refresh_catalog stderr: " + err.substring(0, 500))
      }
    }
    onExited: refreshDeadline.stop()
  }

  Timer {
    id: refreshDeadline
    interval: 30000
    onTriggered: {
      if (catalogRefreshProc.running) {
        var pid = catalogRefreshProc.pid
        if (pid > 0)
          Quickshell.execDetached(["/usr/bin/kill", "-KILL", "--", "-" + pid.toString()])
        catalogRefreshProc.signal(9)
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
            required property string severity
            required property double stamp

            // Severity-scaled: high exposures get 15s; critical would stick.
            readonly property int lifetimeMs: root.toastMsFor(severity)

            Layout.alignment: Qt.AlignRight
            Layout.preferredWidth: cardRow.implicitWidth + Style.space(24)
            implicitHeight: cardRow.implicitHeight + Style.space(14)
            radius: Style.cornerRadius
            color: root.popupBg
            border.width: 1
            border.color: Qt.rgba(root.urgent.r, root.urgent.g,
                                  root.urgent.b, 0.55)

            // Lifetime on screen, then it removes itself; a click dismisses
            // now. interval 0 (critical) means sticky — the timer stays off.
            Timer {
              interval: Math.max(1, card.lifetimeMs)
              running: card.lifetimeMs > 0
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
