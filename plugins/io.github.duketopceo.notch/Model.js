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

// Default sizes in logical px. The camera on 14"/16" MacBook Pros is about
// 200 px wide at scale 2.
var SIZES = { cameraWidth: 200, earWidth: 96, virtualWidth: 300, barHeight: 32 }

// The island's rectangle on a screen `screenWidth` logical px wide, given the
// cutout height (0 for a screen without one). Sizes default to SIZES.
function islandRect(screenWidth, cut, sizes) {
  var s = sizes || SIZES
  var notched = Number(cut) > 0
  var width = notched ? s.cameraWidth + 2 * s.earWidth : s.virtualWidth
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
