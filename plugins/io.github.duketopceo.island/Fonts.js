// The Island's UI typeface, decided in one place. ES5, no Qt types; node
// tests load it with require().
//
// The shell's monospace face is a terminal look; the card reads better in a
// proportional sans. `sansFont` (an Island setting, default on) picks
// "Adwaita Sans" (Inter-based) when it is installed, and the shell's own face
// otherwise or when the setting is off. Glyph text always uses the shell face
// (it carries the Nerd Font symbols).

var SANS = "Adwaita Sans"

// Qt hands back a list-like sequence, which Array.isArray() rejects; only
// length and index access are relied on here.
function hasFamilies(f) { return f !== null && f !== undefined && typeof f.length === "number" }
function has(f, name) {
  for (var i = 0; i < f.length; i++) if (f[i] === name) return true
  return false
}

// families: Qt.fontFamilies() (an array), or null when it cannot be read.
function family(sans, base, families) {
  if (sans !== true) return base
  if (hasFamilies(families) && !has(families, SANS)) return base
  return SANS
}

if (typeof module !== "undefined") module.exports = { SANS: SANS, family: family }
