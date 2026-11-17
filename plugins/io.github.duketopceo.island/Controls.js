// Pure rules for the Island's one reusable control (HoverButton.qml) and its
// hint. ES5, no Qt types; node tests load it with require().

var PRESSED_SCALE = 0.96
var DISABLED_OPACITY = 0.35
var HINT_DELAY_MS = 400

// -> { fill, scale, opacity, pointer, hint }.
// fill: "none" | "hover" | "pressed" | "selected". A disabled control shows
// no hover, no press and no hint. A selected control keeps its selected fill
// while hovered; pressed darkens it.
function look(s) {
  var enabled = !!s && s.enabled !== false
  var hovered = enabled && !!s.hovered
  var pressed = enabled && !!s.pressed
  var selected = !!s && s.selected === true
  var fill = "none"
  if (pressed) fill = "pressed"
  else if (selected) fill = "selected"
  else if (hovered) fill = "hover"
  return {
    fill: fill,
    scale: pressed ? PRESSED_SCALE : 1,
    opacity: enabled ? 1 : DISABLED_OPACITY,
    pointer: enabled,
    hint: hovered && !pressed
  }
}

// Where the hint sits: centered above the control, or below it when there is
// no room above, clamped inside the card so it is never cut off.
// a = { x, y, w, h } of the control in card coordinates; hint = { w, h };
// card = { w, h }. -> { x, y }.
function hintPos(a, hint, card, gap) {
  var g = gap === undefined ? 4 : gap
  var x = a.x + a.w / 2 - hint.w / 2
  x = Math.max(g, Math.min(x, card.w - hint.w - g))
  var y = a.y - hint.h - g
  if (y < g) y = a.y + a.h + g
  y = Math.max(g, Math.min(y, card.h - hint.h - g))
  return { x: Math.round(x), y: Math.round(y) }
}

if (typeof module !== "undefined") module.exports = {
  PRESSED_SCALE: PRESSED_SCALE, DISABLED_OPACITY: DISABLED_OPACITY, HINT_DELAY_MS: HINT_DELAY_MS,
  look: look, hintPos: hintPos
}
