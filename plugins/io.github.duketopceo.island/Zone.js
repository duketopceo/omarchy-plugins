// Window layout and input-mask rectangles for the Island. ES5, no Qt types.
//
// The window is fixed: card size plus a slop margin on both sides and below,
// so it never resizes (resizing a layer surface under the pointer is what made
// hover unreliable). The mask follows the state-driven hot zone, never the
// animating shape: pill + 6 px while closed or arming, card + 12 px while the
// card is open or leaving. Rectangles are in window coordinates; the window is
// anchored to the top edge and centered, so everything is symmetric around
// width / 2.
//
// g = Geom.compute(...) output.

var PILL_SLOP = 6
var CARD_SLOP = 12

function _num(v) {
  var n = Number(v)
  return isFinite(n) ? n : 0
}

function windowSize(g) {
  return { width: _num(g.card.width) + 2 * CARD_SLOP, height: _num(g.card.height) + CARD_SLOP }
}

function _clip(r, w) {
  var x = Math.max(0, r.x)
  var right = Math.min(w.width, r.x + r.width)
  var bottom = Math.min(w.height, r.y + r.height)
  return { x: x, y: 0, width: Math.max(0, right - x), height: Math.max(0, bottom) }
}

// zone: "pill" | "card" (Hover.zoneFor). Hot-zone rectangle including slop.
// target (optional, pill only): Presentation.compact() result. The pill zone
// then follows its width and extends right to cover the bubble.
// cardHeight (optional, card only): the committed card height when the open
// card is shorter than the window's full card height.
function rect(zone, g, target, cardHeight) {
  var w = windowSize(g)
  if (zone === "card") {
    var h = cardHeight > 0 ? Math.min(_num(cardHeight), g.card.height) : g.card.height
    return _clip({ x: (w.width - g.card.width) / 2 - CARD_SLOP, y: 0,
                   width: g.card.width + 2 * CARD_SLOP, height: h + CARD_SLOP }, w)
  }
  if (target) {
    var extra = target.bubble ? target.bubble.offset - target.width + target.bubble.size : 0
    return _clip({ x: (w.width - target.width) / 2 - PILL_SLOP, y: 0,
                   width: target.width + 2 * PILL_SLOP + extra, height: target.height + PILL_SLOP }, w)
  }
  return _clip({ x: (w.width - g.compactWidth) / 2 - PILL_SLOP, y: 0,
                 width: g.compactWidth + 2 * PILL_SLOP, height: g.compactHeight + PILL_SLOP }, w)
}

// One screen's entry in the IPC `state` reply.
function snapshot(screenName, model, zoneRect) {
  var m = model || {}
  return {
    screen: String(screenName),
    state: m.state,
    flags: {
      pinned: !!m.pinned, focused: !!m.focused, held: !!m.held, summoned: !!m.summoned,
      rearmLock: !!m.rearmLock, pointerInside: !!m.pointerInside, fullscreen: !!m.fullscreen
    },
    rect: zoneRect
  }
}

if (typeof module !== "undefined") module.exports = {
  PILL_SLOP: PILL_SLOP, CARD_SLOP: CARD_SLOP,
  windowSize: windowSize, rect: rect, snapshot: snapshot
}
