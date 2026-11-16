import QtQuick 6.11
import Quickshell
import Quickshell.Services.Mpris
import "Media.js" as Media

// MPRIS media for the Island (KTD5). Maps Quickshell's MprisPlayer objects to
// plain records for Media.js, remembers when each player last played, and
// forwards the card's transport and scrub actions to the chosen player.
Scope {
  id: src

  property bool enabled: false
  // True while some window's card is shown; position is ticked only then.
  property bool cardShown: false

  // dbusName -> ms when last seen playing.
  property var lastPlayedAt: ({})
  // The player chosen last time, kept across refreshes (KTD5). Mutated in
  // place, never reassigned, so `chosen` does not depend on its own write.
  property var hold: ({ name: "" })
  property real now: Date.now()

  readonly property var mprisPlayers: Mpris.players ? Mpris.players.values : []
  readonly property var records: src.toRecords(src.mprisPlayers, src.now)
  readonly property var chosen: src.enabled ? Media.pick(src.records, src.hold.name, src.lastPlayedAt, src.now) : null
  readonly property var activity: Media.activity(src.chosen, src.now)
  onChosenChanged: src.hold.name = src.chosen ? src.chosen.dbusName : ""

  // Reads each player's properties inside the `records` binding, so a play,
  // pause or track change re-evaluates it. lastPlayedAt is mutated in place,
  // never reassigned, so the binding does not depend on its own write.
  function toRecords(list, t) {
    var out = []
    var seen = src.lastPlayedAt
    for (var i = 0; i < list.length; i++) {
      var p = list[i]
      if (!p) continue
      var name = String(p.dbusName || "")
      if (p.isPlaying) seen[name] = t
      out.push({
        dbusName: name,
        identity: String(p.identity || ""),
        title: String(p.trackTitle || ""),
        artist: String(p.trackArtist || ""),
        artUrl: String(p.trackArtUrl || ""),
        playing: p.isPlaying === true,
        length: Number(p.length) || 0,
        position: Number(p.position) || 0,
        canSeek: p.canSeek === true,
        canGoNext: p.canGoNext === true,
        canGoPrevious: p.canGoPrevious === true,
        canTogglePlaying: p.canTogglePlaying === true
      })
    }
    return out
  }

  function player() {
    if (!src.chosen) return null
    var list = src.mprisPlayers
    for (var i = 0; i < list.length; i++) if (list[i] && String(list[i].dbusName) === src.chosen.dbusName) return list[i]
    return null
  }

  function toggle() { var p = src.player(); if (p && p.canTogglePlaying) p.togglePlaying() }
  function next() { var p = src.player(); if (p && p.canGoNext) p.next() }
  function previous() { var p = src.player(); if (p && p.canGoPrevious) p.previous() }
  function seek(fraction) {
    var p = src.player()
    if (!p || !p.canSeek) return
    p.position = Media.seekTarget(Number(fraction), Number(p.length) || 0)
    src.now = Date.now()
  }

  // Quickshell does not emit position changes by itself: tick once a second
  // while a card is shown and the player plays. The paused-grace window is
  // re-checked by the slower tick below.
  Timer {
    interval: 1000
    running: src.enabled && src.cardShown && src.chosen !== null && src.chosen.playing
    repeat: true
    onTriggered: {
      var p = src.player()
      if (p) p.positionChanged()
      src.now = Date.now()
    }
  }
  // With no players there is no paused-grace window to expire.
  Timer {
    interval: 30000
    running: src.enabled && src.mprisPlayers.length > 0
    repeat: true
    onTriggered: src.now = Date.now()
  }
}
