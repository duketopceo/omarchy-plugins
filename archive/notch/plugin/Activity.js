// Pure logic for the notch's side-text activities. No Qt types.
//
// An activity is { id, active, priority, text, glyph? }. The side text shows
// the highest-priority active one; ties go to the earlier entry in the list.
// Activities with no text are skipped so they never blank the side text.

function pick(activities) {
  if (!Array.isArray(activities)) return null
  var best = null
  for (var i = 0; i < activities.length; i++) {
    var a = activities[i]
    if (!a || typeof a !== "object" || a.active !== true) continue
    if (typeof a.text !== "string" || a.text === "") continue
    var p = Number(a.priority)
    if (isNaN(p)) p = 0
    if (best === null || p > best.p) best = { a: a, p: p }
  }
  return best ? best.a : null
}

// Text as drawn: the optional glyph, a space, then the text.
function label(activity) {
  if (!activity) return ""
  var glyph = typeof activity.glyph === "string" ? activity.glyph : ""
  return glyph ? glyph + " " + activity.text : String(activity.text)
}

if (typeof module !== "undefined") module.exports = { pick: pick, label: label }
