import QtQuick 6.11
import Quickshell
import Quickshell.Io
import "Dictation.js" as Dictation

// WordInk dictation state for the Island (KTD4). Follows `wordink logs -f`
// NDJSON state events; while WordInk is not running or the follow has ended it
// polls `wordink status --json` every 5 s and restarts the follow on return.
// Talks only to the local `wordink` CLI. Dictation.js owns every rule.
Scope {
  id: src

  // Setting on and the probe found `wordink`.
  property bool enabled: false

  property var model: Dictation.initial()
  // Bumped once a second while recording so the elapsed time redraws.
  property real now: Date.now()
  readonly property var activity: src.enabled ? Dictation.activity(src.model, src.now)
                                              : Dictation.activity(Dictation.initial(), src.now)

  // Bounded output: the status reply is a few kB; anything far larger is not WordInk.
  readonly property int maxText: 200000

  // A repeated state (e.g. "off" every 5 s while WordInk is not running)
  // returns the same model and writes nothing; the 1 s timer below keeps the
  // elapsed time moving while recording.
  function apply(state) {
    if (!state) return
    var t = Date.now()
    var next = Dictation.step(src.model, state, t)
    if (next === src.model) return
    src.model = next
    src.now = t
  }

  // /bin/sh keeps PATH independent of the shell's ambient environment.
  // Exit 127 = wordink not installed, 3 = not running.
  function cli(args) {
    return ["/bin/sh", "-c",
      'PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"; command -v wordink >/dev/null 2>&1 || exit 127; exec wordink "$@"',
      "wordink"].concat(args)
  }

  // Stop: transcribe and paste like the shortcut. The follow stream reports the result.
  function stop() { if (src.enabled) Quickshell.execDetached(src.cli(["dictation", "stop"])) }

  function poll() { if (src.enabled && !statusProc.running) statusProc.running = true }

  onEnabledChanged: {
    if (src.enabled) src.poll()
    else { follow.running = false; src.model = Dictation.initial() }
  }

  Process {
    id: statusProc
    command: src.cli(["status", "--json"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < src.maxText) src.apply(Dictation.fromStatus(text))
    }
    onExited: function(code) {
      if (code === 0) { if (src.enabled && !follow.running) follow.running = true }
      else src.apply("off")
    }
  }

  Process {
    id: follow
    command: src.cli(["logs", "-f", "-n", "0"])
    stdout: SplitParser {
      onRead: function(line) {
        if (line.indexOf("api_server_stopped") >= 0) { src.poll(); return }
        src.apply(Dictation.fromEvent(line))
      }
    }
    // Follow ended (app quit, crash): fall back to polling.
    onExited: src.poll()
  }

  Timer {
    interval: 5000
    running: src.enabled
    repeat: true
    triggeredOnStart: true
    onTriggered: if (!follow.running) src.poll()
  }

  // Elapsed-time redraw, only while recording.
  Timer {
    interval: 1000
    running: src.enabled && src.activity.state === "recording"
    repeat: true
    onTriggered: src.now = Date.now()
  }
}
