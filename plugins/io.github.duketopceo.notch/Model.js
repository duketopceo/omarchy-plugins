// Pure logic for the notch island: cutout geometry, the idle cycle and
// weather codes. No Qt types here, so tests can run it with node.

// Same file format the Omarchy bar reads:
//   { "panels": [ { "connector": "eDP", "width": 3456, "height": 2234, "top": 64 } ] }
function parseCutouts(text) {
  var parsed
  try {
    parsed = JSON.parse(String(text || ""))
  } catch (error) {
    return []
  }
  var panels = parsed && Array.isArray(parsed.panels) ? parsed.panels : []
  var out = []
  for (var i = 0; i < panels.length; i++) {
    var p = panels[i] || {}
    var width = Number(p.width), height = Number(p.height), top = Number(p.top)
    if (typeof p.connector !== "string" || p.connector === "") continue
    if (!(width > 0) || !(height > 0) || !(top > 0) || top >= height) continue
    out.push({ connector: p.connector, width: width, height: height, top: top })
  }
  return out
}

// Height in logical px of the camera cutout at the top of this screen, or 0.
// mode is the physical mode Hyprland reports: { width, height, transform }.
function cutoutTop(cutouts, screenName, logicalWidth, mode) {
  var name = String(screenName || "")
  var logical = Number(logicalWidth)
  var width = Number(mode && mode.width), height = Number(mode && mode.height)
  if (!(logical > 0) || !(width > 0) || !(height > 0)) return 0
  var transform = Number(mode && mode.transform) || 0
  if (transform !== 0 && transform !== 4) return 0
  var list = Array.isArray(cutouts) ? cutouts : []
  for (var i = 0; i < list.length; i++) {
    var c = list[i]
    if (name.indexOf(c.connector) !== 0) continue
    if (Math.abs(width - c.width) <= 4 && Math.abs(height - c.height) <= 4)
      return Math.ceil(c.top * logical / width)
  }
  return 0
}

// Default sizes in logical px. cameraWidth is the fallback when a notched
// panel's camera width is unknown; earWidth is the maximum ear.
var SIZES = { cameraWidth: 200, earWidth: 96, virtualWidth: 300, barHeight: 32 }

// ---- model detection ------------------------------------------------------
// Camera-cutout widths in PHYSICAL px, keyed by Apple device-tree codename
// (the "apple,jNNN" prefix of /proc/device-tree/compatible; trailing letters
// such as s/c/g/d for Pro/Max/Ultra/base are ignored).
//
// Sources and confidence: the MacBook Pro 14"/16" notch is Apple's 185 pt
// wide shape (NSScreen.auxiliaryTopLeftArea / safeAreaInsets measurements
// published by notch-app developers, e.g. boring.notch, NotchNook) which is
// 370 px at 2x; I use 372 px to include the corner radius. The MacBook Air
// 13.6"/15.3" notch is narrower, about 161 pt, 322 px at 2x (same
// measurements). Heights come from Omarchy's display-cutouts.json. These are
// community-measured values, not Apple specs; a camera-width override setting
// can correct them. Codenames: Apple Asahi Linux device-tree names
// (j314/j316 M1 Pro/Max, j414/j416 M2 Pro/Max, j504/j514/j516 M3, j604/j614/j616
// M4, j413/j415 M2 Air, j613/j615 M3 Air, j713/j715 M4 Air).
var MBP_CAMERA = 372
var AIR_CAMERA = 322
var CAMERA_BY_MODEL = {
  j314: MBP_CAMERA, j316: MBP_CAMERA, j414: MBP_CAMERA, j416: MBP_CAMERA,
  j504: MBP_CAMERA, j514: MBP_CAMERA, j516: MBP_CAMERA,
  j604: MBP_CAMERA, j614: MBP_CAMERA, j616: MBP_CAMERA,
  j413: AIR_CAMERA, j415: AIR_CAMERA, j613: AIR_CAMERA, j615: AIR_CAMERA,
  j713: AIR_CAMERA, j715: AIR_CAMERA
}
// Notchless Apple Silicon Macs: no cutout, so the notch is virtual.
var PRE_NOTCH = { j293: true, j313: true, j493: true }
// Panel physical width -> camera width, for when the model is unknown but the
// panel matches a display-cutouts.json entry.
var CAMERA_BY_PANEL = { 3024: MBP_CAMERA, 3456: MBP_CAMERA, 2560: AIR_CAMERA, 2880: AIR_CAMERA }
// Marketing size for --simulate: size -> { width, height, model }.
var PANEL_BY_INCH = {
  13: { width: 2560, height: 1664, model: "j413" },
  14: { width: 3024, height: 1964, model: "j314" },
  15: { width: 2880, height: 1864, model: "j415" },
  16: { width: 3456, height: 2234, model: "j316" }
}

// Split /proc/device-tree/compatible (NUL-separated) into its strings.
function parseCompatible(text) {
  return String(text || "").split("\u0000").map(function(x) { return x.trim() }).filter(function(x) { return x !== "" })
}

// "apple,j316c" (or a whole compatible list/NUL string, or a model string such
// as "Apple MacBook Pro (16-inch, 2021)") -> "j316", or "" when not Apple.
function deviceModel(input) {
  var list = Array.isArray(input) ? input : parseCompatible(input)
  for (var i = 0; i < list.length; i++) {
    var m = /^apple,(j\d{3})[a-z]?$/.exec(String(list[i]).trim())
    if (m) return m[1]
  }
  return ""
}

// Is this a known Apple Silicon Mac without a notch?
function isPreNotch(modelOrCompatible) {
  return PRE_NOTCH[deviceModel(modelOrCompatible)] === true
}

// Camera width in logical px, or 0 when unknown. Physical width/logical width
// give the scale, so fractional scales work. `override` (logical px, > 0)
// wins. Known pre-notch models always return 0.
function cameraWidthFor(modelOrCompatible, physicalWidth, logicalWidth, override) {
  var o = Number(override)
  if (o > 0) return Math.round(o)
  var physical = Number(physicalWidth), logical = Number(logicalWidth)
  if (!(physical > 0) || !(logical > 0)) return 0
  var code = deviceModel(modelOrCompatible)
  if (PRE_NOTCH[code] === true) return 0
  var px = CAMERA_BY_MODEL[code]
  if (!px) {
    var keys = Object.keys(CAMERA_BY_PANEL)
    for (var i = 0; i < keys.length; i++)
      if (Math.abs(physical - Number(keys[i])) <= 4) px = CAMERA_BY_PANEL[keys[i]]
  }
  return px ? Math.round(px * logical / physical) : 0
}

// Ear width scaled to the screen so the island stays sensible on a small
// logical width (13" Air at 1280): 96 px on 1728+, down to 64.
function earWidthFor(logicalWidth) {
  var w = Number(logicalWidth)
  if (!(w > 0)) return SIZES.earWidth
  return Math.max(64, Math.min(SIZES.earWidth, Math.round(w * 0.0556)))
}

// The island's rectangle on a screen `screenWidth` logical px wide, given the
// cutout height (0 for a screen without one). `sizes` overrides SIZES (and
// pins the ear width); `cameraWidth` (logical px, > 0) is the detected or
// overridden camera width.
function islandRect(screenWidth, cut, sizes, cameraWidth) {
  var s = sizes || SIZES
  var notched = Number(cut) > 0
  var camera = Number(cameraWidth) > 0 ? Number(cameraWidth) : s.cameraWidth
  var ear = sizes ? s.earWidth : earWidthFor(screenWidth)
  var width = notched ? camera + 2 * ear : s.virtualWidth
  var height = notched ? Math.max(Number(cut), s.barHeight) : s.barHeight
  return { x: Math.round((Number(screenWidth) - width) / 2), y: 0, width: width, height: height, notched: notched }
}

// Lay bar widgets (from the shell's debugBarGeometry) against the island:
// each visible widget gets its gap to the previous widget and whether the
// island covers it. Returns { rows, blocked }.
function layoutReport(widgets, island) {
  var rows = (Array.isArray(widgets) ? widgets : [])
    .filter(function(w) { return w && w.visible && w.width > 0 })
    .slice()
    .sort(function(a, b) { return a.x - b.x })
  var out = []
  var blocked = []
  var prevEnd = null
  for (var i = 0; i < rows.length; i++) {
    var w = rows[i]
    var end = w.x + w.width
    var covered = island && end > island.x && w.x < island.x + island.width
    var row = { id: w.id, section: w.section, x: w.x, width: w.width, gap: prevEnd === null ? null : w.x - prevEnd, blocked: !!covered }
    if (covered) blocked.push(w.id)
    out.push(row)
    prevEnd = end
  }
  return { rows: out, blocked: blocked }
}

// Grow widgets to new widths the way the bar lays them out: left-section
// widgets push the ones after them to the right; right-section widgets are
// right-anchored, so growth pushes the ones before them to the left. A widget
// that was hidden (width 0) appears when given a width. `grow` maps id to its
// expanded width. Returns new widget objects; the input is not changed.
function expandLayout(widgets, grow) {
  var list = (Array.isArray(widgets) ? widgets : []).map(function(w) {
    var copy = {}
    for (var k in w) copy[k] = w[k]
    return copy
  })
  var g = grow || {}
  var sections = ["left", "right"]
  for (var s = 0; s < sections.length; s++) {
    var name = sections[s]
    var inSection = list.filter(function(w) { return w.section === name }).sort(function(a, b) { return a.x - b.x })
    for (var i = 0; i < inSection.length; i++) {
      var w = inSection[i]
      if (!Object.prototype.hasOwnProperty.call(g, w.id)) continue
      var target = Number(g[w.id])
      var delta = target - (w.visible ? w.width : 0)
      if (delta <= 0) continue
      if (name === "left") {
        w.width = target
        for (var j = i + 1; j < inSection.length; j++) inSection[j].x += delta
      } else {
        w.x -= delta
        w.width = target
        for (var j2 = 0; j2 < i; j2++) inSection[j2].x -= delta
      }
      w.visible = true
    }
  }
  return list
}

// Which idle view to show at `seconds` (wall clock). The clock holds for
// clockSeconds, then each extra view for slideSeconds, then the clock again.
// `views` lists the extra views that currently have data, e.g. ["weather"].
function idleView(seconds, views, clockSeconds, slideSeconds) {
  var extra = Array.isArray(views) ? views : []
  var hold = Math.max(1, Number(clockSeconds) || 20)
  var slide = Math.max(1, Number(slideSeconds) || 6)
  if (extra.length === 0) return "clock"
  var period = hold + extra.length * slide
  var t = ((Math.floor(Number(seconds) || 0) % period) + period) % period
  if (t < hold) return "clock"
  return extra[Math.min(extra.length - 1, Math.floor((t - hold) / slide))]
}

// WMO weather code (Open-Meteo) to a small set of icon names.
function weatherKind(code, isDay) {
  var c = Number(code)
  var day = isDay !== false && isDay !== 0
  if (c === 0 || c === 1) return day ? "clear" : "night"
  if (c === 2) return day ? "partly" : "night-cloudy"
  if (c === 3) return "cloudy"
  if (c === 45 || c === 48) return "fog"
  if ((c >= 51 && c <= 67) || (c >= 80 && c <= 82)) return "rain"
  if ((c >= 71 && c <= 77) || c === 85 || c === 86) return "snow"
  if (c >= 95) return "storm"
  return "cloudy"
}

// Nerd Font glyphs for v0.1 (pixel-art sprites replace these later).
var WEATHER_GLYPHS = {
  "clear": "\u{F0599}", "night": "\u{F0594}", "partly": "\u{F0595}",
  "night-cloudy": "\u{F0F31}", "cloudy": "\u{F0590}", "fog": "\u{F0591}",
  "rain": "\u{F0597}", "snow": "\u{F0598}", "storm": "\u{F0593}"
}

function weatherGlyph(kind) {
  return WEATHER_GLYPHS[kind] || WEATHER_GLYPHS["cloudy"]
}

// The cache the helper writes, or null when it is missing or malformed.
function parseWeather(text) {
  var d
  try {
    d = JSON.parse(String(text || ""))
  } catch (error) {
    return null
  }
  var w = d && d.weather
  if (!w || typeof w.temperature !== "number") return null
  return {
    temperature: Math.round(w.temperature),
    unit: String(w.unit || "°"),
    kind: weatherKind(w.code, w.isDay),
    place: String(w.place || "")
  }
}

if (typeof module !== "undefined") {
  module.exports = {
    SIZES: SIZES,
    islandRect: islandRect,
    cameraWidthFor: cameraWidthFor,
    earWidthFor: earWidthFor,
    deviceModel: deviceModel,
    parseCompatible: parseCompatible,
    isPreNotch: isPreNotch,
    PANEL_BY_INCH: PANEL_BY_INCH,
    layoutReport: layoutReport,
    expandLayout: expandLayout,
    parseCutouts: parseCutouts,
    cutoutTop: cutoutTop,
    idleView: idleView,
    weatherKind: weatherKind,
    weatherGlyph: weatherGlyph,
    parseWeather: parseWeather
  }
}
