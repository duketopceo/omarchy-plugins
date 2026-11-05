import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Mpris
import "Media.js" as Media

// Media state for the notch. Follows the activity contract (active, priority,
// text, glyph) and adds player details for MediaTab.
// Player preference: fastpotify, then Spotify, then any playing MPRIS player
// (see Media.pick). fastpotify-only actions (like, shuffle, repeat, transfer,
// seek) run its CLI through an absolute path found with `command -v`.
// Note: fastpotify has no queue command, so there is no queue control.
Scope {
  id: m

  // --- activity contract ---
  readonly property bool active: !!player && player.isPlaying
  readonly property int priority: 50
  readonly property string text: player ? Media.formatTitle(player.trackTitle || player.identity, player.trackArtist, 120) : ""
  readonly property string glyph: player ? (Media.glyphFor(snap(player)) || Media.MUSIC_GLYPH) : ""

  // --- details ---
  property string preferred: ""   // dbusName chosen in the source picker; "" = auto
  property bool tracking: false   // MediaTab sets this while visible so position ticks
  readonly property var players: Mpris.players ? Mpris.players.values : []
  readonly property var player: {
    var best = Media.pick(players.map(snap), preferred)
    if (!best) return null
    for (var i = 0; i < players.length; i++) if (players[i] && players[i].dbusName === best.dbusName) return players[i]
    return null
  }
  readonly property string source: player ? Media.kind(snap(player)) : ""
  readonly property bool isFastpotify: source === "fastpotify"
  readonly property string artUrl: player && player.trackArtUrl ? String(player.trackArtUrl) : ""
  readonly property real position: player ? player.position : 0
  readonly property real length: player ? player.length : 0

  // fastpotify-reported extras (CLI): liked, shuffle, repeat.
  property bool liked: false
  property bool likedKnown: false
  property bool shuffleOn: false
  property string repeatMode: "off"
  readonly property bool cliReady: bin !== ""

  function snap(p) {
    return { identity: p.identity, desktopEntry: p.desktopEntry, dbusName: p.dbusName, isPlaying: p.isPlaying }
  }

  // ---- fastpotify CLI ----
  property string bin: ""
  Process {
    id: resolver
    // Fixed PATH keeps this independent of the shell's ambient environment.
    command: ["/bin/sh", "-c", 'PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"; command -v fastpotify']
    running: true
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: m.bin = text.trim().split("\n")[0]
    }
  }

  function run(argv) { if (argv.length) Quickshell.execDetached(argv) }
  function like() { run(Media.likeArgv(bin)); liked = !liked; refreshSoon.restart() }
  function toggleShuffle() { run(Media.shuffleArgv(bin, !shuffleOn)); shuffleOn = !shuffleOn; refreshSoon.restart() }
  function cycleRepeat() { var n = Media.nextRepeat(repeatMode); run(Media.repeatArgv(bin, n)); repeatMode = n; refreshSoon.restart() }
  function seekTo(seconds) {
    if (isFastpotify && cliReady) run(Media.seekToArgv(bin, seconds))
    else if (player && player.canSeek && player.positionSupported) player.position = seconds
  }
  function openApp() { run(Media.showArgv(bin)) }

  Timer { id: refreshSoon; interval: 600; onTriggered: m.refresh() }

  function refresh() { if (cliReady && isFastpotify && !stateProc.running) stateProc.running = true }
  Process {
    id: stateProc
    command: Media.nowPlayingArgv(m.bin)
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var s = Media.parseNowPlaying(text)
        if (!s) return
        m.liked = s.saved; m.likedKnown = true
        m.shuffleOn = s.shuffle; m.repeatMode = s.repeat
      }
    }
  }
  // Liked/shuffle/repeat come from the CLI: poll while the tab is open or the track changes.
  Timer { interval: 5000; running: m.tracking && m.isFastpotify; repeat: true; triggeredOnStart: true; onTriggered: m.refresh() }
  Connections {
    target: m.player
    ignoreUnknownSignals: true
    function onTrackTitleChanged() { m.likedKnown = false; refreshSoon.restart() }
  }

  // Quickshell does not tick MprisPlayer.position by itself.
  Timer {
    interval: 1000
    running: m.tracking && m.active
    repeat: true
    onTriggered: if (m.player) m.player.positionChanged()
  }
}
