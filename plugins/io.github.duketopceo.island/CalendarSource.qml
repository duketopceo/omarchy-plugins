import QtQuick 6.11
import Quickshell
import Quickshell.Io
import "Calendar.js" as Calendar

// Next calendar event for the Island. Runs bin/island-calendar (read-only)
// once a minute, or every 10 minutes while it finds no calendar source, and
// keeps the next 24 hours of events. Calendar.js turns them into the activity:
// an ear countdown inside 10 minutes, otherwise a card row. Join opens the
// event's allowlisted meeting link with xdg-open.
Scope {
  id: src

  property bool enabled: false

  // The helper's last answer: { source, events }.
  property string source: ""
  property var events: []
  property real now: Date.now()
  // Reassigned only when what it shows changes, so an idle poll or tick does
  // not rebuild the Island's activity list.
  property var activity: Calendar.activity([], Date.now())
  function refresh() {
    var next = Calendar.activity(src.events, src.now)
    if (JSON.stringify(next) !== JSON.stringify(src.activity)) src.activity = next
  }
  onEventsChanged: src.refresh()
  onNowChanged: src.refresh()
  readonly property string helperPath: decodeURIComponent(Qt.resolvedUrl("bin/island-calendar").toString().replace("file://", ""))

  onEnabledChanged: {
    if (!src.enabled) {
      src.events = []
      src.source = ""
    }
  }

  function poll() {
    if (src.enabled && !proc.running) proc.running = true
  }

  // Opens the next event's meeting link. Calendar.js only keeps an https
  // Zoom, Meet or Teams URL; it goes to xdg-open as one argument, no shell.
  function join() {
    var url = src.activity.url
    if (src.enabled && typeof url === "string" && url !== "") Quickshell.execDetached(["xdg-open", url])
  }

  Process {
    id: proc
    command: [src.helperPath]
    stderr: StdioCollector {}
    stdout: StdioCollector {
      onStreamFinished: {
        var r = null
        try { r = JSON.parse(text) } catch (e) { r = null }
        src.now = Date.now()
        // A poll that finishes after the setting went off must not refill it.
        if (!src.enabled || !r || !Array.isArray(r.events)) return
        src.source = String(r.source || "")
        src.events = r.events
      }
    }
  }

  // Poll: once a minute, every 10 minutes while no source exists (KTD3).
  Timer {
    interval: src.source === "none" ? 600000 : 60000
    running: src.enabled
    repeat: true
    triggeredOnStart: true
    onTriggered: src.poll()
  }

  // Countdown redraw between polls while an event is coming up.
  Timer {
    interval: 30000
    running: src.enabled && src.events.length > 0
    repeat: true
    onTriggered: src.now = Date.now()
  }
}
