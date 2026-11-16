// The raw plugin entry in shell.json, for a whole-entry write. ES5, no Qt types.
//
// updateEntryInline replaces the entry, so the writer needs the entry as it
// stands (unknown keys included) to merge an edit into it.

function find(shellJson, id) {
  var root = shellJson
  if (typeof root === "string") {
    try { root = JSON.parse(root) } catch (e) { return null }
  }
  var list = root && typeof root === "object" && Array.isArray(root.plugins) ? root.plugins : []
  for (var i = 0; i < list.length; i++) {
    var e = list[i]
    if (e && typeof e === "object" && e.id === id) return e
  }
  return null
}

if (typeof module !== "undefined") module.exports = { find: find }
