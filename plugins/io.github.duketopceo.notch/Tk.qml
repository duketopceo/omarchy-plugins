pragma Singleton
import QtQuick
import qs.Commons as Commons
import "Theme.js" as Theme

// Shared theme state. Notch.qml binds `id` to the live setting; every view
// reads colours, radii, fonts and motion from here. Swift returns exactly the
// values the views used to hardcode; Pxl returns a fixed 16-colour palette,
// square corners, 2px borders, stepped motion.
QtObject {
  id: tk
  property string id: "swift"
  property bool reduce: false
  readonly property var t: Theme.resolve(id)
  readonly property bool pxl: id === "pxl"

  // Live Omarchy colours in Swift, pinned palette in Pxl.
  readonly property color text: t.text || Commons.Color.foreground
  readonly property color dim: t.dim || Commons.Color.muted
  readonly property color accent: t.accent || Commons.Color.accent
  readonly property color urgent: t.urgent || Commons.Color.urgent
  readonly property color bg: pxl ? t.island : Commons.Color.background
  readonly property color island: t.island
  readonly property color good: t.good
  readonly property color warn: t.warn
  readonly property color bad: t.bad
  readonly property color info: t.info
  readonly property color hold: t.hold
  readonly property color danger: t.danger
  readonly property color bubble: t.bubble
  readonly property color bubbleText: t.bubbleText
  readonly property color amber: t.amber
  readonly property color gray: t.gray
  readonly property color sky: t.sky
  readonly property color purple: t.purple
  readonly property color pink: t.pink
  readonly property color white: t.white
  readonly property color black: t.black
  readonly property color card: pxl ? t.card : Qt.rgba(1, 1, 1, 0.07)
  readonly property color chip: pxl ? t.chip : Qt.rgba(1, 1, 1, 0.1)
  readonly property color chipHover: pxl ? t.chipHover : Qt.rgba(1, 1, 1, 0.16)
  readonly property color edge: pxl ? t.border : Qt.rgba(1, 1, 1, 0.22)
  readonly property color faint: pxl ? t.faint : Commons.Color.muted

  // Fonts
  readonly property FontLoader pixelify: FontLoader { source: Qt.resolvedUrl("fonts/PixelifySans/PixelifySans[wght].ttf") }
  readonly property FontLoader silk: FontLoader { source: Qt.resolvedUrl("fonts/Silkscreen/Silkscreen-Regular.ttf") }
  readonly property string family: !pxl ? Commons.Style.font.family
    : (pixelify.status === FontLoader.Ready ? pixelify.name : t.fallbackFamily)
  readonly property string label: !pxl ? family
    : (silk.status === FontLoader.Ready ? silk.name : t.fallbackFamily)

  // White-overlay tints: Swift keeps the exact alpha, Pxl snaps to palette steps.
  function tint(a) {
    if (!pxl) return Qt.rgba(1, 1, 1, a)
    if (a < 0.05) return "transparent"
    if (a < 0.09) return t.card
    if (a < 0.14) return t.chip
    if (a < 0.2) return t.chipHover
    if (a < 0.5) return t.border
    return t.dim
  }
  // A colour at alpha: Swift exact; Pxl is the solid colour or a dark chip.
  function alpha(c, a) {
    if (!pxl) return Qt.rgba(c.r, c.g, c.b, a)
    if (a <= 0.01) return "transparent"
    return a < 0.35 ? t.chip : c
  }
  // Dark translucent surfaces: Swift exact, Pxl solid ink.
  function surface(r, g, b, a) { return pxl ? t.island : Qt.rgba(r, g, b, a) }
  // Radius: Pxl is square (2px max on big cards).
  function r(n) { return pxl ? (n >= 8 ? 2 : 0) : n }
  function bw(n) { return pxl ? Math.max(2, Math.round(n)) : n }
  // Behavior duration: Pxl snaps (stepped panel handles its own frames).
  function ms(n) { return (pxl || reduce) ? 0 : n }
  // Whole pixels in Pxl.
  function px(n) { return pxl ? Math.round(n) : n }
}
