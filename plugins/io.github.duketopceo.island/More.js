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
    list.push({ label: _label(chat, groups), n: n, muted: isMuted, idx: list.length })
  }
  list.sort(function (a, b) {
    return (a.muted ? 1 : 0) - (b.muted ? 1 : 0) || b.n - a.n || a.idx - b.idx
  })
  for (var i = 0; i < list.length; i++)
    out.rows.push({ label: list[i].label, value: list[i].n + " unread" + (list[i].muted ? ", muted" : "") })
  return out
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
  if (!model || model.seen === null) return { seen: newest, newest: newest }
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
  messages: messages, unreadText: unreadText, dayflowState: dayflowState, dayflowLive: dayflowLive, dayflowRows: dayflowRows,
  shotsInitial: shotsInitial, shotsStep: shotsStep, shotsLive: shotsLive, shotsSeen: shotsSeen, shotsRows: shotsRows
}
