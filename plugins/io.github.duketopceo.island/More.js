// The More pages' data: Messages (Blip's unread counts), Dayflow status and
// Snapdex screenshots. ES5, no Qt types; node tests load it with require().
//
// Blip state (~/.local/state/blip/state.json, written by Blip): only
// unreadCounts, groups[chat].name and mutedChats are read. Message text is
// never read; a chat without a group name shows as its handle's last four
// characters, so phone numbers are not drawn whole.

var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

function _obj(v) { return v !== null && typeof v === "object" && !Array.isArray(v) }

function _label(chat, groups) {
  var g = groups[chat]
  if (_obj(g) && typeof g.name === "string" && g.name) return g.name
  return "Chat ending " + String(chat).slice(-4)
}

// -> { ok, unread, live, rows: [{ label, value }] }; muted chats are listed
// last and count toward neither `unread` nor `live`.
function messages(text) {
  var out = { ok: false, unread: 0, live: false, rows: [] }
  var d
  try { d = JSON.parse(String(text || "")) } catch (e) { return out }
  if (!_obj(d)) return out
  out.ok = true
  var counts = _obj(d.unreadCounts) ? d.unreadCounts : {}
  var groups = _obj(d.groups) ? d.groups : {}
  var muted = Array.isArray(d.mutedChats) ? d.mutedChats : []
  var list = []
  for (var chat in counts) {
    var n = Math.floor(Number(counts[chat]))
    if (!isFinite(n) || n <= 0) continue
    var isMuted = muted.indexOf(chat) >= 0
    if (!isMuted) { out.unread += n; out.live = true }
    list.push({ label: _label(chat, groups), n: n, muted: isMuted, chat: String(chat), idx: list.length })
  }
  list.sort(function (a, b) {
    return (a.muted ? 1 : 0) - (b.muted ? 1 : 0) || b.n - a.n || a.idx - b.idx
  })
  for (var i = 0; i < list.length; i++)
    out.rows.push({ label: list[i].label, value: list[i].n + " unread" + (list[i].muted ? ", muted" : ""),
                    muted: list[i].muted, chat: list[i].chat, n: list[i].n, badge: badgeText(list[i].n),
                    initials: initials(list[i].label) })
  return out
}

// Blip's IPC call that opens one chat, as an argv list (never a shell
// string). Blip's own toast uses the same call with the leading "+" dropped
// and accepts only this character set; anything else, or an id that
// `qs ipc call` could read as a flag, returns [] and the caller opens Blip
// itself instead. Chat ids are handles: they are never logged.
function blipChatArgv(chat, shellRoot) {
  var c = String(chat === null || chat === undefined ? "" : chat).replace(/^\+/, "")
  if (!/^[A-Za-z0-9._@:;$-]{1,256}$/.test(c) || c.charAt(0) === "-") return []
  return ["qs", "-p", String(shellRoot), "ipc", "call", "nixfred.blip", "notified", c]
}

// "Paused", "Recording", or Dayflow's own state word; "" without Dayflow.
function dayflowState(d) {
  if (!d) return ""
  if (d.paused === true) return "Paused"
  return d.state ? d.state.charAt(0).toUpperCase() + d.state.slice(1) : "Unknown"
}

// The Messages summary line: "3 unread" or "No unread messages".
function unreadText(n) { return n > 0 ? n + " unread" : "No unread messages" }

function dayflowLive(d) { return !!d && (d.state === "recording" || d.paused === true) }

// A badge's text: the count, "99+" past 99, "" for none.
function badgeText(n) {
  var v = Math.floor(Number(n))
  return isFinite(v) && v > 0 ? (v > 99 ? "99+" : String(v)) : ""
}

// Up to two letters for a chat's avatar circle; "" when the chat has no name
// (the page draws a person glyph then, never part of a handle).
function initials(label) {
  var s = String(label === null || label === undefined ? "" : label)
  if (/^Chat ending /.test(s)) return ""
  var words = s.split(/\s+/)
  var out = ""
  for (var i = 0; i < words.length && out.length < 2; i++) {
    var c = words[i].charAt(0)
    if (/[A-Za-z0-9À-ɏ]/.test(c)) out += c.toUpperCase()
  }
  return out
}

// Dayflow's `last_frame` is a clock time of today ("8:31 PM"). -> "just now",
// "2 min ago", "3 h ago", "yesterday", or the text itself when it is not a
// clock time. A time in the future means yesterday's.
function relTime(text, nowMs) {
  var m = /^\s*(\d{1,2}):(\d{2})\s*([AaPp][Mm])?\s*$/.exec(String(text === null || text === undefined ? "" : text))
  if (!m) return String(text || "")
  var h = Number(m[1])
  var min = Number(m[2])
  if (m[3]) {
    var pm = m[3].toLowerCase() === "pm"
    h = (h % 12) + (pm ? 12 : 0)
  }
  if (h > 23 || min > 59) return String(text)
  var now = new Date(Number(nowMs))
  var then = new Date(now.getFullYear(), now.getMonth(), now.getDate(), h, min, 0, 0).getTime()
  var diff = Math.floor((now.getTime() - then) / 60000)
  if (diff < 0) diff += 1440
  if (diff < 1) return "just now"
  if (diff < 60) return diff + " min ago"
  if (diff < 1440 - 60) return Math.floor(diff / 60) + " h ago"
  return "yesterday"
}

// The Dayflow page: -> { state: "recording" | "paused" | "idle", title,
// action: "pause" | "resume" | "", frames, last, storage, pending, panel }.
// Only recording and paused have an action: the command is `dayflow <action>`.
function dayflowView(d, nowMs) {
  if (!d) return null
  var state = d.paused === true ? "paused" : (d.state === "recording" ? "recording" : "idle")
  return {
    state: state,
    title: state === "recording" ? "Recording" : (state === "paused" ? "Paused" : (dayflowState(d) || "Idle")),
    action: state === "recording" ? "pause" : (state === "paused" ? "resume" : ""),
    frames: String(d.framesToday || 0),
    last: d.lastFrame ? relTime(d.lastFrame, nowMs) : "none yet",
    storage: String(d.storage || ""),
    pending: Math.max(0, Math.floor(Number(d.pending) || 0)),
    panel: d.panel === true
  }
}

// The only argv the Dayflow button may run.
function dayflowArgv(action) { return action === "pause" || action === "resume" ? ["dayflow", action] : [] }

function dayflowRows(d) {
  if (!d) return []
  var rows = [{ label: "Capture", value: dayflowState(d) }, { label: "Frames today", value: String(d.framesToday || 0) }]
  if (d.lastFrame) rows.push({ label: "Last frame", value: String(d.lastFrame) })
  rows.push({ label: "Blocks pending", value: String(d.pending || 0) })
  if (d.storage) rows.push({ label: "Storage", value: String(d.storage) })
  return rows
}

// Unseen-screenshot tracking, in memory only. The first read is the baseline;
// a newer newest name afterwards is live until the Shots page is shown.
function shotsInitial() { return { seen: null, newest: "" } }

function _newest(shots) {
  return shots && Array.isArray(shots.items) && shots.items.length > 0 ? String(shots.items[0].name || "") : ""
}

function shotsStep(model, shots) {
  var newest = _newest(shots)
  // No inventory yet (Snapdex missing or the read failed): no baseline either,
  // so screenshots that already exist never read as new once it appears.
  if (!model || model.seen === null) return shots ? { seen: newest, newest: newest } : shotsInitial()
  return { seen: model.seen, newest: newest }
}

function shotsLive(model) { return !!model && model.seen !== null && model.newest !== "" && model.newest > model.seen }

function shotsSeen(model) { return { seen: model ? model.newest : "", newest: model ? model.newest : "" } }

function _when(name) {
  var m = /^(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})/.exec(String(name || ""))
  if (!m) return ""
  return MONTHS[Number(m[2]) - 1] + " " + Number(m[3]) + " " + m[4] + ":" + m[5]
}

function shotsRows(shots) {
  var items = shots && Array.isArray(shots.items) ? shots.items : []
  var out = []
  for (var i = 0; i < items.length; i++) {
    var it = items[i]
    if (!_obj(it) || !it.name) continue
    out.push({ label: String(it.caption || it.name), value: _when(it.name), name: String(it.name) })
  }
  return out
}

if (typeof module !== "undefined") module.exports = {
  messages: messages, blipChatArgv: blipChatArgv, unreadText: unreadText, badgeText: badgeText, initials: initials, relTime: relTime,
  dayflowView: dayflowView, dayflowArgv: dayflowArgv, dayflowState: dayflowState, dayflowLive: dayflowLive, dayflowRows: dayflowRows,
  shotsInitial: shotsInitial, shotsStep: shotsStep, shotsLive: shotsLive, shotsSeen: shotsSeen, shotsRows: shotsRows
}
