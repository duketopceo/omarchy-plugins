// Pure activity model for the Island. ES5, no Qt types.
//
// Every source (dictation, media, timer, charging, hud) reports one activity
// object: { id, active, priority, text, glyph, card, until? }. layout() turns
// the list into what the pill and card draw: the top activity, the second one
// (shown as a small icon in the ear) and up to two card rows.
//
// Card closed: plain priority order, ties keep list order.
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

function _result(slots) {
  var ids = []
  for (var i = 0; i < slots.length; i++) ids.push(slots[i].id)
  return {
    top: slots[0] || null,
    second: slots[1] || null,
    rows: slots.slice(1, 3),
    held: ids
  }
}

function layout(list, held, cardShown, now) {
  var sorted = _sorted(list, now)

  if (!cardShown) {
    var r = _result(sorted.slice(0, MAX_SLOTS))
    r.held = []
    return r
  }

  var byId = {}
  for (var i = 0; i < sorted.length; i++) byId[sorted[i].id] = sorted[i]

  // Survivors keep their slot index; ids that left become gaps (null).
  var slots = [null, null, null]
  var used = {}
  var prev = Array.isArray(held) ? held : []
  for (var h = 0; h < prev.length && h < MAX_SLOTS; h++) {
    var a = byId[prev[h]]
    if (a && !used[a.id]) {
      slots[h] = a
      used[a.id] = true
    }
  }
  // Fill gaps, top slot first, with live activities not already held.
  var next = 0
  for (var s = 0; s < MAX_SLOTS; s++) {
    if (slots[s]) continue
    while (next < sorted.length && used[sorted[next].id]) next++
    if (next >= sorted.length) break
    slots[s] = sorted[next]
    used[sorted[next].id] = true
  }
  // A gap that could not be filled would leave the top slot empty above a
  // row, so close it up.
  var packed = []
  for (var p = 0; p < MAX_SLOTS; p++) if (slots[p]) packed.push(slots[p])
  return _result(packed)
}

if (typeof module !== "undefined") module.exports = { isLive: isLive, layout: layout }
