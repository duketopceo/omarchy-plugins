// Pure logic for the Island's media activity (MPRIS players).
// ES5, no Qt types: MediaSource.qml maps Mpris.players to plain objects and
// renders what activity() returns; node tests load it with require().
//
// A player is { dbusName, identity, title, artist, artUrl, playing, length,
// position, canSeek, canGoNext, canGoPrevious, canTogglePlaying } with times in
// seconds. lastPlayedAt maps dbusName -> ms epoch when it was last seen playing.

var PAUSE_GRACE_MS = 600000
var PRIORITY = 50

// Nerd Font Material Design glyphs (plane 15).
var GLYPHS = {
  play: cp(0xF040A),   // nf-md-play
  pause: cp(0xF03E4)   // nf-md-pause
}

function cp(n) {
  n -= 0x10000
  return String.fromCharCode(0xD800 + (n >> 10), 0xDC00 + (n & 0x3FF))
}

function eligible(p, lastPlayedAt, now) {
  if (p.playing) return true
  var t = lastPlayedAt && lastPlayedAt[p.dbusName]
  return typeof t === "number" && now - t <= PAUSE_GRACE_MS
}

// The player to show: held (while eligible), else a playing one, else the most
// recently paused one inside the grace window, else null.
function pick(players, heldName, lastPlayedAt, now) {
  var i, p
  players = players || []
  if (heldName) {
    for (i = 0; i < players.length; i++) {
      if (players[i].dbusName === heldName && eligible(players[i], lastPlayedAt, now)) return players[i]
    }
  }
  for (i = 0; i < players.length; i++) if (players[i].playing) return players[i]
  var best = null, bestAt = -1
  for (i = 0; i < players.length; i++) {
    p = players[i]
    if (!eligible(p, lastPlayedAt, now)) continue
    var t = lastPlayedAt[p.dbusName]
    if (t > bestAt) { best = p; bestAt = t }
  }
  return best
}

// Art loads only from local sources: file: and data: (scheme is case-insensitive).
function artUrl(url) {
  return typeof url === "string" && /^(file|data):/i.test(url) ? url : ""
}

function fmt(seconds) {
  var s = Math.floor(Number(seconds))
  if (isNaN(s) || s < 0) s = 0
  var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60
  var ss = (sec < 10 ? "0" : "") + sec
  if (h > 0) return h + ":" + (m < 10 ? "0" : "") + m + ":" + ss
  return m + ":" + ss
}

function seekTarget(fraction, length) {
  if (!(length > 0)) return 0
  return Math.min(length, Math.max(0, fraction * length))
}

function activity(player, now) {
  if (!player) return { id: "media", active: false, priority: PRIORITY, text: "", glyph: "", card: "" }
  return {
    id: "media", active: true, priority: PRIORITY,
    text: player.title || player.identity || "",
    glyph: player.playing ? GLYPHS.play : GLYPHS.pause,
    card: player.title || "",
    artist: player.artist || "",
    art: artUrl(player.artUrl),
    playing: !!player.playing,
    position: player.position, length: player.length,
    canSeek: !!player.canSeek, canGoNext: !!player.canGoNext, canGoPrevious: !!player.canGoPrevious,
    canTogglePlaying: !!player.canTogglePlaying,
    dbusName: player.dbusName
  }
}

if (typeof module !== "undefined") module.exports = {
  PAUSE_GRACE_MS: PAUSE_GRACE_MS, pick: pick, activity: activity, artUrl: artUrl, fmt: fmt, seekTarget: seekTarget
}
