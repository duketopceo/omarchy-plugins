// Pure activity model for the Island. ES5, no Qt types.
//
// Every source (dictation, media, timer, charging, hud) reports one activity
// object: { id, active, priority, text, glyph, card, until? }. layout() turns
// the list into what the pill and card draw: the top activity, the second one
// (shown as a small icon in the ear) and up to two card rows.
//
// Card closed: plain priority order, ties keep list order.
// An activity with cardOnly === true never takes the top or second slot: it
// shows only as a card row (and not at all while the card is closed).
//
// Card shown: the window holds the ids it is showing (slot 0 = top, slots 1-2
// = rows). A held id keeps its slot while it stays live, so a control never
// moves under the pointer; a newly live activity only fills a free slot.

var MAX_SLOTS = 3

// An activity counts when it is active, has ear text and has not expired.
function isLive(a, now) {
  if (!a || a.active !== true) return false
  if (typeof a.text !== "string" || a.text === "") return false
  if (a.until !== undefined && a.until !== null && !(now < a.until)) return false
  return true
}

// Live activities in priority order (highest first); ties keep list order.
function _sorted(list, now) {
  var live = []
  if (!Array.isArray(list)) return []
  for (var i = 0; i < list.length; i++) {
    if (isLive(list[i], now)) live.push({ a: list[i], i: i })
  }
  live.sort(function (x, y) {
    if (y.a.priority !== x.a.priority) return y.a.priority - x.a.priority
    return x.i - y.i
  })
  var out = []
  for (var j = 0; j < live.length; j++) out.push(live[j].a)
  return out
}

function _result(top, rows) {
  var held = []
  if (top || rows.length > 0) {
    held.push(top ? top.id : "")
    for (var i = 0; i < rows.length; i++) held.push(rows[i].id)
  }
  return {
    top: top || null,
    second: rows[0] && rows[0].cardOnly !== true ? rows[0] : null,
    rows: rows,
    held: held
  }
}

function layout(list, held, cardShown, now) {
  var sorted = _sorted(list, now)

  if (!cardShown) {
    var shown = []
    for (var c = 0; c < sorted.length && shown.length < MAX_SLOTS; c++)
      if (sorted[c].cardOnly !== true) shown.push(sorted[c])
    var r = _result(shown[0] || null, shown.slice(1))
    r.held = []
    return r
  }

  var byId = {}
  for (var i = 0; i < sorted.length; i++) byId[sorted[i].id] = sorted[i]

  // Survivors keep their slot index; ids that left become gaps (null). A
  // cardOnly activity never holds the top slot.
  var slots = [null, null, null]
  var used = {}
  var prev = Array.isArray(held) ? held : []
  for (var h = 0; h < prev.length && h < MAX_SLOTS; h++) {
    var a = byId[prev[h]]
    if (a && !used[a.id] && !(h === 0 && a.cardOnly === true)) {
      slots[h] = a
      used[a.id] = true
    }
  }
  // Fill gaps, top slot first, with live activities not already held. The top
  // slot takes only a non-cardOnly activity.
  for (var s = 0; s < MAX_SLOTS; s++) {
    if (slots[s]) continue
    for (var n = 0; n < sorted.length; n++) {
      if (used[sorted[n].id] || (s === 0 && sorted[n].cardOnly === true)) continue
      slots[s] = sorted[n]
      used[sorted[n].id] = true
      break
    }
  }
  // An empty top slot above rows closes up when a row holds a non-cardOnly
  // activity; otherwise it stays empty and the rows are cardOnly only.
  var rows = []
  for (var p = 1; p < MAX_SLOTS; p++) if (slots[p]) rows.push(slots[p])
  var top = slots[0]
  if (!top) {
    for (var q = 0; q < rows.length; q++) {
      if (rows[q].cardOnly !== true) {
        top = rows[q]
        rows.splice(q, 1)
        break
      }
    }
  }
  return _result(top, rows)
}

if (typeof module !== "undefined") module.exports = { isLive: isLive, layout: layout }
