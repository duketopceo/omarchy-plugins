// Pure colour helpers for the Island's artwork tint. ES5, no Qt types.
// Colours are { r, g, b } in 0..1.

function _lin(v) {
  return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)
}

function _luminance(c) {
  return 0.2126 * _lin(c.r) + 0.7152 * _lin(c.g) + 0.0722 * _lin(c.b)
}

// WCAG contrast ratio, 1..21.
function contrast(a, b) {
  var la = _luminance(a)
  var lb = _luminance(b)
  var hi = Math.max(la, lb)
  var lo = Math.min(la, lb)
  return (hi + 0.05) / (lo + 0.05)
}

function _saturation(c) {
  var max = Math.max(c.r, c.g, c.b)
  var min = Math.min(c.r, c.g, c.b)
  var l = (max + min) / 2
  if (max === min) return 0
  return (max - min) / (1 - Math.abs(2 * l - 1))
}

// The most saturated colour with at least 3:1 contrast on the surface, or null.
function pick(colors, surface) {
  if (!Array.isArray(colors)) return null
  var best = null
  var bestSat = -1
  for (var i = 0; i < colors.length; i++) {
    var c = colors[i]
    if (contrast(c, surface) < 3) continue
    var s = _saturation(c)
    if (s > bestSat) {
      best = c
      bestSat = s
    }
  }
  return best
}

if (typeof module !== "undefined") module.exports = { contrast: contrast, pick: pick }
