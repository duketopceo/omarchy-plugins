// Pure logic for the notch's side-text activities. No Qt types.
//
// An activity is { id, active, priority, text, glyph? }. The side text shows
// the highest-priority active one; ties go to the earlier entry in the list.
// Activities with no text are skipped so they never blank the side text.

function pick(activities) {
  var selected = top(activities, 1)
  return selected.length ? selected[0] : null
}

function top(activities, limit) {
  if (!Array.isArray(activities)) return []
  var selected = []
  for (var i = 0; i < activities.length; i++) {
    var a = activities[i]
    if (!a || typeof a !== "object" || a.active !== true) continue
    if (typeof a.text !== "string" || a.text === "") continue
    var p = Number(a.priority)
    if (isNaN(p)) p = 0
    var j = 0
    while (j < selected.length && selected[j].p >= p) j++
    selected.splice(j, 0, { a: a, p: p })
  }
  return selected.slice(0, Math.max(0, Number(limit) || 0)).map(function (entry) { return entry.a })
}

function tabFor(id, settings) {
  if (id === "media") return "media"
  if (id === "agents" && settings && settings.optAgents === true) return "agents"
  if (id === "messages" && settings && settings.optMessages === true) return "messages"
  if (id === "screenshots" && settings && settings.snapdex === true) return "screenshots"
  return "home"
}

function splitFits(available, fixed, first, second, hasSecond) {
  return hasSecond === true && available > 0 && first > 0 && second > 0 && fixed + first + second <= available
}

function splitGeometry(width, capsuleX, gap) {
  if (width <= 0 || gap < 0 || capsuleX <= gap || capsuleX >= width) return null
  return { primaryWidth: capsuleX - gap, capsuleX: capsuleX, capsuleWidth: width - capsuleX }
}

// Text as drawn: the optional glyph, a space, then the text.
function label(activity) {
  if (!activity) return ""
  var glyph = typeof activity.glyph === "string" ? activity.glyph : ""
  return glyph ? glyph + " " + activity.text : String(activity.text)
}

if (typeof module !== "undefined") module.exports = { pick: pick, top: top, tabFor: tabFor, splitFits: splitFits, splitGeometry: splitGeometry, label: label }
