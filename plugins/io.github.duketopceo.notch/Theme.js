// Theme tokens for the notch island: Swift (current polished look) and Pxl
// (retro pixel). Pure data and lookup, no Qt types, so tests run it with node.
//
// Swift is the polished default: its text/dim/accent/urgent, card and font
// tokens are "" meaning "follow the live Omarchy theme" (Commons.Color /
// Commons.Style.font.family, resolved by Island.qml). Only the tokens that
// were already hardcoded in the island (black island, green/amber status,
// blue info, bubble colors, radii) are pinned here, so Swift looks exactly
// as it did before themes existed.
//
// Pxl pins every token to a retro-pixel palette: dark indigo-black island,
// warm off-white text, chunky yellow accent, square corners, and a mono
// font stack. PixelArt.js sprites stay fixed in both themes (they are icon
// art, not chrome).

var DEFAULT_THEME = "swift"

var THEMES = {
  swift: {
    id: "swift",
    label: "Swift",
    island: "#000000",
    text: "",            // follow Commons.Color.foreground
    dim: "",             // follow Commons.Color.muted
    faint: "",
    accent: "",          // follow Commons.Color.accent
    urgent: "",          // follow Commons.Color.urgent
    good: "#6fbf73",
    warn: "#e0b050",
    bad: "#d9695f",
    info: "#4aa3ff",
    hold: "#6aa9e0",
    danger: "#f53d3d",
    card: "",            // translucent white overlays, as before
    chip: "",
    chipHover: "",
    hairline: "",
    border: "",
    bubble: "#f2f2f4",
    bubbleText: "#06121f",
    amber: "#f5a742",
    gray: "#8b8f98",
    sky: "#6fa8ff",
    purple: "#b48cf2",
    pink: "#ff8fc7",
    white: "white",
    black: "black",
    fontFamily: "",      // follow Commons.Style.font.family
    labelFamily: "",     // follow fontFamily
    fallbackFamily: "",
    steps: 0,            // 0 = springs
    stepMs: 0,
    islandRadius: 24,
    cardRadius: 8,
    pillRadius: 13,
    borderWidth: 1
  },
  pxl: {
    id: "pxl",
    label: "Pxl",
    island: "#0d0d1a",
    text: "#f4f4e8",
    dim: "#a0a8c0",
    faint: "#5a6480",
    accent: "#ffd23f",
    urgent: "#ff5252",
    good: "#58d068",
    warn: "#ff9f1c",
    bad: "#ff5252",
    info: "#4cc9f0",
    hold: "#6aa9e0",
    danger: "#ff5252",
    card: "#16162a",
    chip: "#22223c",
    chipHover: "#2e2e4e",
    hairline: "#22223c",
    border: "#3a3a5c",
    bubble: "#f4f4e8",
    bubbleText: "#0d0d1a",
    amber: "#ff9f1c",
    gray: "#a0a8c0",
    sky: "#6aa9e0",
    purple: "#b48cf2",
    pink: "#ff8fc7",
    white: "#f4f4e8",
    black: "#0d0d1a",
    fontFamily: "Pixelify Sans",
    labelFamily: "Silkscreen",
    fallbackFamily: "Terminus",
    steps: 3,            // stepped animation frames
    stepMs: 45,
    islandRadius: 0,
    cardRadius: 2,
    pillRadius: 0,
    borderWidth: 2
  }
}

function ids() {
  return Object.keys(THEMES)
}

function isTheme(id) {
  return typeof id === "string" && Object.prototype.hasOwnProperty.call(THEMES, id)
}

// The theme object for `id`; unknown or junk ids fall back to the default.
function resolve(id) {
  return isTheme(id) ? THEMES[id] : THEMES[DEFAULT_THEME]
}

// Token for `key` on theme `id`, falling back to the Swift value (and then
// to "" for follow-the-Omarchy-theme tokens) when the theme leaves it blank.
function token(id, key) {
  var t = resolve(id)
  if (t[key] !== undefined && t[key] !== "") return t[key]
  var d = THEMES[DEFAULT_THEME][key]
  return d === undefined ? "" : d
}

// WCAG contrast helpers. The island is a fixed dark surface, so text that
// follows a LIGHT Omarchy theme (dark foreground) would vanish on it. These
// take 0..1 rgb triples and lift a colour toward white until it reads.
function lin(c) { return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4) }
function luminance(r, g, b) { return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b) }
function contrast(a, b) {
  var la = luminance(a[0], a[1], a[2]), lb = luminance(b[0], b[1], b[2])
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}
// Returns [r,g,b] lifted toward white (or black when `bg` is light) so that
// contrast(result, bg) >= min. Unchanged when it already passes.
function ensureContrast(fg, bg, min) {
  var target = luminance(bg[0], bg[1], bg[2]) < 0.5 ? 1 : 0
  var out = [fg[0], fg[1], fg[2]]
  for (var i = 0; i <= 20 && contrast(out, bg) < min; i++) {
    var t = i / 20
    out = [fg[0] + (target - fg[0]) * t, fg[1] + (target - fg[1]) * t, fg[2] + (target - fg[2]) * t]
  }
  return out
}

if (typeof module !== "undefined") {
  module.exports = { DEFAULT_THEME: DEFAULT_THEME, THEMES: THEMES, ids: ids, isTheme: isTheme, resolve: resolve, token: token, contrast: contrast, luminance: luminance, ensureContrast: ensureContrast }
}
