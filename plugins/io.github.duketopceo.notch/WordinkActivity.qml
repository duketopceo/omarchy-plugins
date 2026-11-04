import QtQuick
import Quickshell.Io
import "Wordink.js" as Wordink

// WordInk dictation state for the notch. Follows `wordink logs -f` (NDJSON
// events); while WordInk is not running or the follow has ended it polls
// `wordink status --json` every 5 s and restarts the follow on return.
// Talks only to the local `wordink` CLI. Never touches voxtype.
QtObject {
  id: wi  // QtObject, not Item: Item already owns a `state` property

  // "idle" | "recording" | "transcribing" | "error" | "not-running" | "done"
  readonly property string state: Wordink.current(model, clock)
  readonly property bool active: Wordink.isActive(model, clock)
  readonly property string text: Wordink.displayText(state)

  property var model: Wordink.initial()
  property real clock: Date.now()   // bumped when a flash needs to expire

  function apply(base) {
    var now = Date.now()
    var next = Wordink.step(wi.model, base, now)
    if (next === wi.model) return
    wi.model = next
    wi.clock = now
    if (next.doneUntil > now) flash.interval = next.doneUntil - now + 20
    else if (next.base === "error") flash.interval = Wordink.ERROR_MS + 20
    else { flash.stop(); return }
    flash.restart()
  }

  // Re-evaluate once a flash (done / error takeover) has run out.
  Timer { id: flash; onTriggered: wi.clock = Date.now() }

  // /bin/sh keeps PATH independent of the shell's ambient environment.
  // Exit 127 = wordink not installed, 3 = not running.
  function cli(args) {
    return ["/bin/sh", "-c",
      'PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"; command -v wordink >/dev/null 2>&1 || exit 127; exec wordink "$@"',
      "wordink"].concat(args)
  }

  function poll() { if (!statusProc.running) statusProc.running = true }

  Process {
    id: statusProc
    command: wi.cli(["status", "--json"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 200000) wi.apply(Wordink.statusToState(text))
    }
    onExited: function(code) {
      if (code === 0) { if (!follow.running) follow.running = true }
      else wi.apply("not-running")
    }
  }

  Process {
    id: follow
    command: wi.cli(["logs", "-f", "-n", "0"])
    stdout: SplitParser {
      onRead: function(line) {
        if (line.indexOf("api_server_stopped") >= 0) { wi.poll(); return }
        wi.apply(Wordink.eventToState(line))
      }
    }
    // Follow ended (app quit, crash): fall back to polling.
    onExited: wi.poll()
  }

  Timer {
    interval: 5000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: if (!follow.running) wi.poll()
  }
}
