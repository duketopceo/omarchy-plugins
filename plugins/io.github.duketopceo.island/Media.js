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

var ART_MAX = 2048

// Art URLs the card may load: local file: and data: always (scheme is
// case-insensitive); https: only when allowWeb is true, and never with
// credentials in the URL, an empty host, or a loopback or IP-literal host
// (art is for display, not for probing the local network).
function artUrl(url, allowWeb) {
  if (typeof url !== "string" || url === "" || url.length > ART_MAX) return ""
  if (/^(file|data):/i.test(url)) return url
  if (allowWeb !== true) return ""
  var m = /^https:\/\/([^\/?#]*)/i.exec(url)
  if (!m) return ""
  var auth = m[1]
  if (auth === "" || auth.indexOf("@") >= 0) return ""
  var host = auth.replace(/:\d*$/, "").toLowerCase()
  if (host === "" || host === "localhost" || host.charAt(0) === "[" || /^\d+(\.\d+){3}$/.test(host)) return ""
  return url
}

function fmt(seconds) {
  var s = Math.floor(Number(seconds))
  if (isNaN(s) || s < 0) s = 0
  var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60
  var ss = (sec < 10 ? "0" : "") + sec
  if (h > 0) return h + ":" + (m < 10 ? "0" : "") + m + ":" + ss
  return m + ":" + ss
}

// Time left as "-M:SS", or "" when the length is unknown.
function fmtRemaining(position, length) {
  var len = Number(length)
  if (!(len > 0)) return ""
  var left = Math.max(0, len - Math.max(0, Number(position) || 0))
  return "-" + fmt(left)
}

function seekTarget(fraction, length) {
  if (!(length > 0)) return 0
  return Math.min(length, Math.max(0, fraction * length))
}

// allowWeb: the owner's "Load album art from the web" setting.
function activity(player, now, allowWeb) {
  if (!player) return { id: "media", active: false, priority: PRIORITY, text: "", glyph: "", card: "" }
  return {
    id: "media", active: true, priority: PRIORITY,
    text: player.title || player.identity || "",
    glyph: player.playing ? GLYPHS.play : GLYPHS.pause,
    card: player.title || "",
    artist: player.artist || "",
    subtitle: player.artist || player.album || "",
    identity: player.identity || "",
    desktopEntry: player.desktopEntry || "",
    art: artUrl(player.artUrl, allowWeb),
    playing: !!player.playing,
    position: player.position, length: player.length,
    canSeek: !!player.canSeek, canGoNext: !!player.canGoNext, canGoPrevious: !!player.canGoPrevious,
    canTogglePlaying: !!player.canTogglePlaying,
    dbusName: player.dbusName
  }
}

if (typeof module !== "undefined") module.exports = {
  PAUSE_GRACE_MS: PAUSE_GRACE_MS, pick: pick, activity: activity, artUrl: artUrl, fmt: fmt, fmtRemaining: fmtRemaining, seekTarget: seekTarget
}
