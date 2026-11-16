// Pure logic for the notch's media view (Spotify / fastpotify / MPRIS). No Qt
// types, so tests run it with node.
//
// Players are plain objects: { identity, desktopEntry, dbusName, isPlaying }.
// fastpotify (a native Spotify client) shows up on MPRIS as
// org.mpris.MediaPlayer2.spotifast, identity "Spotifast", desktop entry
// "spotifast". Official Spotify is org.mpris.MediaPlayer2.spotify.
// `fastpotify now-playing --raw` prints tab-separated fields:
//   state, title, artists, album, position_ms, duration_ms, volume,
//   shuffle, repeat, art_url, saved, device

var ELLIPSIS = "…"
var SPOTIFY_GLYPH = "\u{F04C7}"   // nf-md-spotify
var MUSIC_GLYPH = "\u{F075A}"     // nf-md-music

function blob(p) {
  if (!p) return ""
  return [p.identity, p.desktopEntry, p.dbusName].map(function (s) { return String(s || "").toLowerCase() }).join(" ")
}

// "fastpotify" | "spotify" | "other"
function kind(p) {
  var b = blob(p)
  if (b.indexOf("spotifast") >= 0 || b.indexOf("fastpotify") >= 0) return "fastpotify"
  if (b.indexOf("spotify") >= 0) return "spotify"
  return "other"
}

function rank(p) {
  var k = kind(p)
  return k === "fastpotify" ? 0 : k === "spotify" ? 1 : 2
}

// Best player: playing ones first (fastpotify, then spotify, then any other
// playing); with none playing, the same order over paused players. Stable.
// `preferred` (a dbusName) overrides when that player still exists.
function pick(players, preferred) {
  var list = (players || []).filter(function (p) { return !!p })
  if (preferred) {
    for (var i = 0; i < list.length; i++) if (list[i].dbusName === preferred) return list[i]
  }
  var best = null, bestScore = 1e9
  for (var j = 0; j < list.length; j++) {
    var score = (list[j].isPlaying ? 0 : 10) + rank(list[j])
    if (score < bestScore) { best = list[j]; bestScore = score }
  }
  return best
}

function glyphFor(p) {
  var k = kind(p)
  return k === "other" ? "" : SPOTIFY_GLYPH
}

function elide(s, max) {
  s = String(s || "")
  if (max <= 0 || s.length <= max) return s
  if (max === 1) return ELLIPSIS
  return s.substring(0, max - 1).replace(/\s+$/, "") + ELLIPSIS
}

// "Title — Artist", elided to `max` chars. The title is kept whole as long
// as it fits; the artist gives way first, then the title.
function formatTitle(title, artist, max) {
  title = String(title || "").trim()
  artist = String(artist || "").trim()
  if (!title && !artist) return ""
  if (!artist) return elide(title, max)
  if (!title) return elide(artist, max)
  var full = title + " — " + artist
  if (!(max > 0) || full.length <= max) return full
  var room = max - title.length - 3
  if (room >= 4) return title + " — " + elide(artist, room)
  return elide(title, max)
}

// Seconds -> "m:ss" or "h:mm:ss". Bad input -> "0:00".
function formatTime(sec) {
  var n = Number(sec)
  if (!isFinite(n) || n < 0) n = 0
  n = Math.floor(n)
  var h = Math.floor(n / 3600), m = Math.floor((n % 3600) / 60), s = n % 60
  var ss = (s < 10 ? "0" : "") + s
  if (h > 0) return h + ":" + (m < 10 ? "0" : "") + m + ":" + ss
  return m + ":" + ss
}

function fraction(position, length) {
  var p = Number(position), l = Number(length)
  if (!isFinite(p) || !isFinite(l) || l <= 0) return 0
  return Math.max(0, Math.min(1, p / l))
}

// ---- fastpotify CLI argv builders. `bin` is an absolute path resolved with
// `command -v`; they return [] when it is missing so callers can no-op.

function argv(bin, args) {
  if (!bin || String(bin).charAt(0) !== "/") return []
  return [String(bin)].concat(args)
}

function likeArgv(bin) { return argv(bin, ["like"]) }
function shuffleArgv(bin, on) { return argv(bin, on === undefined ? ["shuffle"] : ["shuffle", on ? "on" : "off"]) }
function repeatArgv(bin, mode) {
  return argv(bin, mode === undefined ? ["repeat"] : ["repeat", mode === "context" || mode === "track" ? mode : "off"])
}
function transferArgv(bin, deviceId) { return deviceId ? argv(bin, ["transfer", String(deviceId)]) : [] }
function seekToArgv(bin, seconds) {
  var n = Number(seconds)
  if (!isFinite(n)) return []
  return argv(bin, ["seek-to", String(Math.max(0, Math.round(n)))])
}
function showArgv(bin) { return argv(bin, ["show"]) }
function nowPlayingArgv(bin) { return argv(bin, ["now-playing", "--raw"]) }
function devicesArgv(bin) { return argv(bin, ["devices"]) }

// Next mode in the off -> context -> track cycle.
function nextRepeat(mode) {
  return mode === "off" ? "context" : mode === "context" ? "track" : "off"
}

// Parse `now-playing --raw`. Null when it is not a playing/paused line.
function parseNowPlaying(text) {
  var line = String(text || "").split("\n")[0]
  var f = line.split("\t")
  if (f.length < 11) return null
  return {
    state: f[0], title: f[1], artists: f[2], album: f[3],
    positionMs: Number(f[4]) || 0, durationMs: Number(f[5]) || 0,
    volume: Number(f[6]) || 0,
    shuffle: f[7] === "on", repeat: f[8] || "off",
    artUrl: f[9], saved: f[10] === "yes", device: f[11] || ""
  }
}

if (typeof module !== "undefined") {
  module.exports = {
    kind: kind, rank: rank, pick: pick, glyphFor: glyphFor,
    elide: elide, formatTitle: formatTitle, formatTime: formatTime, fraction: fraction,
    likeArgv: likeArgv, shuffleArgv: shuffleArgv, repeatArgv: repeatArgv,
    transferArgv: transferArgv, seekToArgv: seekToArgv, showArgv: showArgv,
    nowPlayingArgv: nowPlayingArgv, devicesArgv: devicesArgv,
    nextRepeat: nextRepeat, parseNowPlaying: parseNowPlaying,
    SPOTIFY_GLYPH: SPOTIFY_GLYPH, MUSIC_GLYPH: MUSIC_GLYPH
  }
}
