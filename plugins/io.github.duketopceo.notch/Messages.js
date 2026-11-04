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
  if (cut.length > MAX_CHARS) cut = cut.slice(0, MAX_CHARS - 1).trimEnd() + "…"
  else if (words.length > (n || WORDS)) cut += "…"
  return cut
}

// "<sender>: <first words>". Without a preview just the sender; without a
// sender just the preview words; with neither a generic label.
function formatText(name, preview) {
  var who = String(name || "").trim()
  if (who.length > 18) who = who.slice(0, 17).trimEnd() + "…"
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

if (typeof module !== "undefined") {
  module.exports = {
    FLASH_MS: FLASH_MS, PRIORITY: PRIORITY,
    parseState: parseState, parseStatus: parseStatus, parseThreads: parseThreads,
    parseAllowlist: parseAllowlist, normHandle: normHandle, isAllowed: isAllowed,
    newMessages: newMessages, senderName: senderName, firstWords: firstWords,
    formatText: formatText, initial: initial, step: step, isActive: isActive,
    badgeText: badgeText, tabRows: tabRows
  }
}
