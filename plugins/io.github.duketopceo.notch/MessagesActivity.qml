import QtQuick
import Quickshell
import Quickshell.Io
import "Messages.js" as Messages

// Blip (iMessage) state for the notch. READ-ONLY: it never marks anything
// read and never sends. Sources, all written by Blip itself:
//   - ~/.local/state/blip/state.json (unread counts per chat, via FileView)
//   - ~/.config/blip/allowlist.json  (handles Blip would toast for)
//   - `qs ipc call nixfred.blip status` every 10 s (bridge online/offline)
//   - `... threads` only when a flash needs a sender name; it answers only if
//     the user turned Blip's automation on, otherwise the flash is generic.
// Activity contract: active / priority / text / glyph. The flash fires only for
// allowlisted handles; everything else just counts toward `unread`.
// Message text is held in memory for the flash and never written anywhere.
Scope {
  id: msgs

  // ---- activity contract
  readonly property bool active: Messages.isActive(model, clock)
  readonly property int priority: Messages.PRIORITY
  readonly property string text: model.text
  readonly property string glyph: "\u{F0B79}"

  // ---- extras for the idle badge and the Messages tab
  readonly property int unread: model.unread
  readonly property string badge: Messages.badgeText(model.unread)
  readonly property bool online: bridge !== null && bridge.online
  readonly property bool running: bridge !== null      // Blip widget answered IPC
  readonly property var threads: threadList            // null until automation allows it
  readonly property var rows: Messages.buildRows(threadList, snapshot, 50)

  readonly property string home: Quickshell.env("HOME")
  readonly property var qsBase: ["qs", "-p", "/usr/share/omarchy/shell", "ipc", "call", "nixfred.blip"]

  property var model: Messages.initial()
  property real clock: Date.now()
  property var snapshot: null        // last parsed state.json
  property var allow: []
  property var bridge: null          // parsed `status`, null when Blip is not running
  property var threadList: null
  property var pending: []           // allowlisted arrivals waiting for a name lookup

  // ---- actions (user-initiated only)
  function openBlip() { Quickshell.execDetached(qsBase.concat(["open"])) }
  function openThread(chat) {
    // `goto` needs Blip automation=on; without it just open the panel. A bare
    // "+" would be read by `qs ipc` as a flag; Blip accepts the digits alone.
    if (threadList) Quickshell.execDetached(qsBase.concat(["goto", Messages.gotoArg(chat)]))
    else openBlip()
  }
  // Read-only: the Messages tab asks for the thread list while it is visible.
  function fetchThreads() { if (!threadsProc.running) threadsProc.running = true }
  function markAllRead() { Quickshell.execDetached(qsBase.concat(["read"])) }

  function apply(next) {
    var now = Date.now()
    var arrivals = msgs.pending
    msgs.pending = []
    var text = ""
    if (arrivals.length) {
      var a = arrivals[arrivals.length - 1]
      var name = Messages.senderName(a.chat, next.groups, msgs.threadList)
      var preview = ""
      var list = msgs.threadList || []
      for (var i = 0; i < list.length; i++) if (list[i].chat === a.chat) preview = list[i].preview
      text = Messages.formatText(name, preview)
    }
    var m = Messages.step(msgs.model, next.unread, arrivals, text, now)
    msgs.clock = now
    if (m === msgs.model) return
    msgs.model = m
    if (m.flashUntil > now) flash.interval = m.flashUntil - now + 20, flash.restart()
  }

  function onState(textIn) {
    var next = Messages.parseState(textIn)
    if (!next.ok) return
    var arrivals = Messages.newMessages(msgs.snapshot, next, msgs.allow).filter(function (a) { return a.allowed })
    msgs.snapshot = next
    msgs.pending = arrivals
    if (arrivals.length && !threadsProc.running) { threadsProc.running = true; return }
    msgs.apply(next)
  }

  // Re-evaluate once a flash has run out.
  Timer { id: flash; onTriggered: msgs.clock = Date.now() }

  FileView {
    path: msgs.home + "/.local/state/blip/state.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: msgs.onState(text())
  }

  FileView {
    path: msgs.home + "/.config/blip/allowlist.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: msgs.allow = Messages.parseAllowlist(text())
    onLoadFailed: msgs.allow = []
  }

  Process {
    id: statusProc
    command: msgs.qsBase.concat(["status"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: msgs.bridge = text.length < 4000 ? Messages.parseStatus(text) : null
    }
    onExited: function(code) { if (code !== 0) msgs.bridge = null }
  }

  // Names and previews. Answers a thread list only with Blip automation on.
  Process {
    id: threadsProc
    command: msgs.qsBase.concat(["threads"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: msgs.threadList = text.length < 400000 ? Messages.parseThreads(text) : null
    }
    onExited: if (msgs.snapshot) msgs.apply(msgs.snapshot)
  }

  Timer {
    interval: 10000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: {
      if (!statusProc.running) statusProc.running = true
    }
  }
}
