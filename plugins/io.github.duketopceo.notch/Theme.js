// Theme tokens for the notch island: Swift (current polished look) and Pxl
// (retro pixel). Pure data and lookup, no Qt types, so tests run it with node.
//
// Swift is the polished default: its text/dim/accent/urgent, card and font
// tokens are "" meaning "follow the live Omarchy theme" (Commons.Color /
// Commons.Style.font.family, resolved by Notch.qml). Only the tokens that
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
    fontFamily: "",      // follow Commons.Style.font.family
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
    hairline: "#2a2a44",
    border: "#3a3a5c",
    bubble: "#f4f4e8",
    bubbleText: "#0d0d1a",
    fontFamily: "'VT323', 'Press Start 2P', monospace",
    islandRadius: 4,
    cardRadius: 2,
    pillRadius: 2,
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

if (typeof module !== "undefined") {
  module.exports = { DEFAULT_THEME: DEFAULT_THEME, THEMES: THEMES, ids: ids, isTheme: isTheme, resolve: resolve, token: token }
}
