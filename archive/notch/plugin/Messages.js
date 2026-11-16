// Pure logic for the notch's Blip (iMessage) integration. No Qt types, so
// tests run it with node.
//
// Read-only inputs, all produced by Blip itself:
//   ~/.local/state/blip/state.json   { unreadCounts:{chat:n}, groups:{chat:{name}}, ... }
//       (counts and group titles only; Blip never stores message text there)
//   ~/.config/blip/allowlist.json    { allow:[handle,...] }  handles Blip toasts for
//   `qs ipc call nixfred.blip status`   "online=true unread=3 leader=true ..."
//   `qs ipc call nixfred.blip threads`  JSON thread list; only when the user has set
//       automation=on in Blip's bridge config, otherwise a one-line refusal
// Message text, when available, lives in memory only and is never persisted.

var FLASH_MS = 8000
var PRIORITY = 70
var WORDS = 5
var MAX_CHARS = 40

function isObject(v) { return v !== null && typeof v === "object" && !Array.isArray(v) }

// Parse state.json into per-chat unread counts and group titles.
// Returns {ok, unread, counts, groups}; ok=false on junk.
function parseState(text) {
  var out = { ok: false, unread: 0, counts: {}, groups: {} }
  var d
  try { d = JSON.parse(String(text || "")) } catch (e) { return out }
  if (!isObject(d)) return out
  var uc = isObject(d.unreadCounts) ? d.unreadCounts : {}
  Object.keys(uc).forEach(function (chat) {
    var n = Number(uc[chat])
    if (isFinite(n) && n > 0) { out.counts[chat] = Math.floor(n); out.unread += Math.floor(n) }
  })
  var g = isObject(d.groups) ? d.groups : {}
  Object.keys(g).forEach(function (chat) {
    if (isObject(g[chat]) && typeof g[chat].name === "string" && g[chat].name) out.groups[chat] = g[chat].name
  })
  out.ok = true
  return out
}

// "online=true unread=3 leader=true ..." -> {online, unread, leader, threads} or null.
function parseStatus(text) {
  var s = String(text || "")
  if (s.indexOf("online=") < 0) return null
  function field(name) {
    var m = new RegExp("(?:^|\\s)" + name + "=(\\S+)").exec(s)
    return m ? m[1] : ""
  }
  var unread = parseInt(field("unread"), 10)
  var threads = parseInt(field("threads"), 10)
  return {
    online: field("online") === "true",
    leader: field("leader") === "true",
    unread: isFinite(unread) ? unread : 0,
    threads: isFinite(threads) ? threads : 0
  }
}

// IPC `threads` JSON -> [{chat,name,preview,unread,ts}] newest first, or null
// when automation is off / the answer is not a thread list.
function parseThreads(text) {
  var arr
  try { arr = JSON.parse(String(text || "")) } catch (e) { return null }
  if (!Array.isArray(arr)) return null
  var out = arr.filter(isObject).map(function (t) {
    return {
      chat: String(t.chat || ""),
      name: String(t.name || ""),
      preview: String(t.last_text || ""),
      unread: Math.max(0, Math.floor(Number(t.unread) || 0)),
      ts: String(t.last_ts || "")
    }
  }).filter(function (t) { return t.chat !== "" })
  out.sort(function (a, b) { return a.ts < b.ts ? 1 : a.ts > b.ts ? -1 : 0 })
  return out
}

function parseAllowlist(text) {
  var d
  try { d = JSON.parse(String(text || "")) } catch (e) { return [] }
  if (!isObject(d) || !Array.isArray(d.allow)) return []
  return d.allow.filter(function (x) { return typeof x === "string" && x }).map(normHandle)
}

// Phone numbers compare by digits (last 10, so +1 prefixes match); emails and
// anything else compare lowercased.
function normHandle(h) {
  var s = String(h || "").trim().toLowerCase()
  if (s.indexOf("@") >= 0) return s
  var digits = s.replace(/\D/g, "")
  return digits.length >= 7 ? digits.slice(-10) : s
}

function isAllowed(chat, allow) {
  if (!allow || allow.length === 0) return false   // Blip toasts nobody without an allowlist
  return allow.indexOf(normHandle(chat)) >= 0
}

// Chats whose unread count rose between two parseState snapshots.
// prev === null (first read) reports nothing: that is startup, not arrival.
function newMessages(prev, next, allow) {
  if (!prev || !prev.ok || !next || !next.ok) return []
  var out = []
  Object.keys(next.counts).forEach(function (chat) {
    var before = prev.counts[chat] || 0
    if (next.counts[chat] > before) {
      out.push({ chat: chat, delta: next.counts[chat] - before, allowed: isAllowed(chat, allow) })
    }
  })
  return out
}

// A display name for a chat, or "" when only a raw handle is known (never
// show a phone number or address).
function senderName(chat, groups, threads) {
  if (groups && groups[chat]) return groups[chat]
  var list = threads || []
  for (var i = 0; i < list.length; i++) {
    if (list[i].chat === chat && list[i].name && !looksLikeHandle(list[i].name)) return list[i].name
  }
  return ""
}

function looksLikeHandle(s) {
  return /@/.test(s) || /^[+\d][\d\s().-]{5,}$/.test(String(s).trim())
}

function firstWords(text, n) {
  var words = String(text || "").replace(/\s+/g, " ").trim().split(" ").filter(Boolean)
  var cut = words.slice(0, n || WORDS).join(" ")
  if (cut.length > MAX_CHARS) cut = cut.slice(0, MAX_CHARS - 1).replace(/\s+$/, "") + "…"
  else if (words.length > (n || WORDS)) cut += "…"
  return cut
}

// "<sender>: <first words>". Without a preview just the sender; without a
// sender just the preview words; with neither a generic label.
function formatText(name, preview) {
  var who = String(name || "").trim()
  if (who.length > 18) who = who.replace(/\s+$/, "").slice(0, 17).replace(/\s+$/, "") + "…"
  var body = firstWords(preview)
  if (who && body) return who + ": " + body
  if (who) return who
  return body || "New message"
}

function initial() {
  return { unread: 0, flashUntil: 0, text: "" }
}

// Fold a detection result into the model. `arrivals` is newMessages output;
// `text` the formatted line for the newest allowed one ("" if none).
function step(model, unread, arrivals, text, now) {
  var allowed = (arrivals || []).some(function (a) { return a.allowed })
  if (allowed) return { unread: unread, flashUntil: now + FLASH_MS, text: text }
  if (unread === model.unread) return model
  return { unread: unread, flashUntil: model.flashUntil, text: model.text }
}

function isActive(model, now) { return model.flashUntil > now }

function badgeText(unread) { return unread > 99 ? "99+" : unread > 0 ? String(unread) : "" }

// Rows for the Messages tab. threads may be null (automation off): fall back
// to bare unread chats from state.json, named only when a group title exists.
function tabRows(threads, state, limit) {
  var max = limit || 5
  if (threads && threads.length) {
    return threads.slice(0, max).map(function (t) {
      return { chat: t.chat, name: looksLikeHandle(t.name) || !t.name ? "Contact" : t.name, preview: firstWords(t.preview, 6), unread: t.unread }
    })
  }
  if (!state || !state.ok) return []
  return Object.keys(state.counts).slice(0, max).map(function (chat) {
    return { chat: chat, name: state.groups[chat] || "Conversation", preview: "", unread: state.counts[chat] }
  })
}

// ---- Messages tab helpers --------------------------------------------------

// "now", "2m", "1h", "Tue", "Mar 3" for a thread timestamp. Within a minute is
// "now", under an hour minutes, under a day hours, under a week the weekday,
// older the short date. Unparseable or empty timestamps give "".
var DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
function relTime(ts, now) {
  var t = typeof ts === "number" ? ts : Date.parse(String(ts || ""))
  if (!isFinite(t)) return ""
  var diff = Math.max(0, (now === undefined ? Date.now() : now) - t)
  var min = Math.floor(diff / 60000)
  if (min < 1) return "now"
  if (min < 60) return min + "m"
  var h = Math.floor(min / 60)
  if (h < 24) return h + "h"
  var d = new Date(t)
  if (Math.floor(h / 24) < 7) return DAYS[d.getDay()]
  return MONTHS[d.getMonth()] + " " + d.getDate()
}

// One or two capital letters: first letters of the first and last word, letters
// and digits only. Empty input gives "?".
function initials(name) {
  var words = String(name || "").split(/\s+/).map(function (w) { return w.replace(/[^\p{L}\p{N}]/gu, "") }).filter(Boolean)
  if (!words.length) return "?"
  var first = Array.from(words[0])[0]
  var last = words.length > 1 ? Array.from(words[words.length - 1])[0] : ""
  return (first + last).toUpperCase()
}

// Stable hue from the name (FNV-1a), muted so initials stay readable on dark.
function hashColor(name) {
  var h = 2166136261
  var s = String(name || "")
  for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0 }
  return hslHex(h % 360, 0.45, 0.42)
}

function hslHex(hue, sat, light) {
  var c = (1 - Math.abs(2 * light - 1)) * sat
  var x = c * (1 - Math.abs((hue / 60) % 2 - 1))
  var m = light - c / 2
  var seg = Math.floor(hue / 60) % 6
  var rgb = [[c, x, 0], [x, c, 0], [0, c, x], [0, x, c], [x, 0, c], [c, 0, x]][seg]
  return "#" + rgb.map(function (v) {
    var n = Math.round((v + m) * 255).toString(16)
    return n.length < 2 ? "0" + n : n
  }).join("")
}

// SHA-256 hex of a string (UTF-8), so the tab can find Blip's avatar cache file
// without a subprocess. Blip names files sha256(handle.trim().toLowerCase())[0:32].
function sha256(str) {
  var bytes = []
  var enc = unescape(encodeURIComponent(String(str)))
  for (var i = 0; i < enc.length; i++) bytes.push(enc.charCodeAt(i))
  var K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]
  var H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
  var bitLen = bytes.length * 8
  bytes.push(0x80)
  while (bytes.length % 64 !== 56) bytes.push(0)
  var hi = Math.floor(bitLen / 4294967296), lo = bitLen >>> 0
  ;[hi, lo].forEach(function (w) { bytes.push((w >>> 24) & 255, (w >>> 16) & 255, (w >>> 8) & 255, w & 255) })
  function rotr(x, n) { return (x >>> n) | (x << (32 - n)) }
  for (var off = 0; off < bytes.length; off += 64) {
    var W = []
    for (var t = 0; t < 16; t++) W[t] = ((bytes[off + 4 * t] << 24) | (bytes[off + 4 * t + 1] << 16) | (bytes[off + 4 * t + 2] << 8) | bytes[off + 4 * t + 3]) | 0
    for (t = 16; t < 64; t++) {
      var s0 = rotr(W[t - 15], 7) ^ rotr(W[t - 15], 18) ^ (W[t - 15] >>> 3)
      var s1 = rotr(W[t - 2], 17) ^ rotr(W[t - 2], 19) ^ (W[t - 2] >>> 10)
      W[t] = (W[t - 16] + s0 + W[t - 7] + s1) | 0
    }
    var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7]
    for (t = 0; t < 64; t++) {
      var S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)
      var t1 = (h + S1 + ((e & f) ^ (~e & g)) + K[t] + W[t]) | 0
      var S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)
      var t2 = (S0 + ((a & b) ^ (a & c) ^ (b & c))) | 0
      h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0
    }
    H = [H[0] + a, H[1] + b, H[2] + c, H[3] + d, H[4] + e, H[5] + f, H[6] + g, H[7] + h].map(function (v) { return v | 0 })
  }
  return H.map(function (v) { var x = (v >>> 0).toString(16); return "00000000".slice(x.length) + x }).join("")
}

function avatarKey(chat) { return sha256(String(chat || "").trim().toLowerCase()).slice(0, 32) }

// `ls` of the avatar cache dir -> set {key:true} of keys that have a photo.
function parseAvatarList(text) {
  var out = {}
  String(text || "").split("\n").forEach(function (f) {
    var m = /^([0-9a-f]{32})\.jpg$/.exec(f.trim())
    if (m) out[m[1]] = true
  })
  return out
}

// Rows for the list: one per thread, newest first, with everything the view
// needs so QML stays dumb. A raw handle is never shown as a name.
function buildRows(threads, state, limit) {
  var max = limit || 50
  var base = tabRows(threads, state, max)
  var byChat = {}
  ;(threads || []).forEach(function (t) { byChat[t.chat] = t })
  return base.map(function (r) {
    var t = byChat[r.chat]
    var full = t ? String(t.preview || "").replace(/\s+/g, " ").trim() : ""
    var name = r.name
    if (t && (t.name === t.chat || /^chat\d+$|^[0-9a-f]{32}$/i.test(t.name))) name = (state && state.ok && state.groups[r.chat]) || "Group"
    return {
      chat: r.chat, name: name, preview: full || r.preview, unread: r.unread,
      ts: t ? t.ts : "", initials: initials(name), color: hashColor(name), avatar: avatarKey(r.chat)
    }
  })
}

// Case-insensitive substring match on name or preview; empty query keeps all.
function filterRows(rows, query) {
  var q = String(query || "").trim().toLowerCase()
  if (!q) return rows
  return rows.filter(function (r) {
    return r.name.toLowerCase().indexOf(q) >= 0 || String(r.preview || "").toLowerCase().indexOf(q) >= 0
  })
}

function totalUnread(rows) { return rows.reduce(function (n, r) { return n + (r.unread > 0 ? r.unread : 0) }, 0) }

// `qs ipc call` reads a leading "+" as a flag, so Blip accepts bare digits.
function gotoArg(chat) { return String(chat || "").replace(/^\+/, "") }

// Banner text when the list cannot be trusted; "" when all is well.
// `running`: Blip answered IPC; `online`: its bridge to the Mac is up.
function offlineLabel(running, online) {
  if (online) return ""
  return running ? "Mac offline" : "Blip not reachable"
}

if (typeof module !== "undefined") {
  module.exports = {
    FLASH_MS: FLASH_MS, PRIORITY: PRIORITY,
    parseState: parseState, parseStatus: parseStatus, parseThreads: parseThreads,
    parseAllowlist: parseAllowlist, normHandle: normHandle, isAllowed: isAllowed,
    newMessages: newMessages, senderName: senderName, firstWords: firstWords,
    formatText: formatText, initial: initial, step: step, isActive: isActive,
    badgeText: badgeText, tabRows: tabRows,
    relTime: relTime, initials: initials, hashColor: hashColor, sha256: sha256, avatarKey: avatarKey,
    parseAvatarList: parseAvatarList, buildRows: buildRows, filterRows: filterRows,
    totalUnread: totalUnread, gotoArg: gotoArg, offlineLabel: offlineLabel
  }
}
