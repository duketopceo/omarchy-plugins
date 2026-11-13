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

function selected(activities, id) {
  var list = visible(activities)
  for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i]
  return null
}

function action(id, state) {
  if (id === "dictation") return state === "recording" ? "stop" : null
  if (id === "media") return "media"
  if (id === "messages") return "messages"
  if (id === "agents") return "agents"
  if (id === "screenshots") return "screenshots"
  return null
}

function canSplit(available, fixed, first, second) {
  return available > 0 && first > 0 && second > 0 && fixed + first + second <= available
}

if (typeof module !== "undefined") module.exports = { visible: visible, selected: selected, action: action, canSplit: canSplit }
