// Stable priorities prevent a changing list from silently redirecting controls.
function visible(activities) {
  if (!Array.isArray(activities)) return []
  var result = []
  for (var i = 0; i < activities.length; i++) {
    var activity = activities[i]
    if (!activity || activity.active !== true || typeof activity.text !== "string" || !activity.text) continue
    var priority = Number(activity.priority)
    if (!isFinite(priority)) priority = 0
    var at = 0
    while (at < result.length && result[at].priority >= priority) at++
    result.splice(at, 0, { activity: activity, priority: priority })
  }
  return result.map(function (row) { return row.activity })
}

// Lookup in an already-ranked list (the output of visible). Re-ranking here
// would re-sort the whole list on every change for no new information.
function selected(ranked, id) {
  if (!Array.isArray(ranked)) return null
  for (var i = 0; i < ranked.length; i++) if (ranked[i] && ranked[i].id === id) return ranked[i]
  return null
}

// The only state-changing control the island offers is stopping dictation,
// and only while it is recording. Other detail views select by activity id.
function action(id, state) {
  return id === "dictation" && state === "recording" ? "stop" : null
}

function canSplit(available, fixed, first, second) {
  return available > 0 && first > 0 && second > 0 && fixed + first + second <= available
}

if (typeof module !== "undefined") module.exports = { visible: visible, selected: selected, action: action, canSplit: canSplit }
