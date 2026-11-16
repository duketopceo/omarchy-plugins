// Pure logic for the Home quick-actions row (R8). No Qt types.
//
// The list itself (shape, seeds, limits, sanitising) lives in Settings.js,
// because shell.json stores it as one setting. This file turns an action into
// what the row needs: the command to run, which binary it depends on, whether
// that binary exists, and the edits the Settings editor makes.

// "FOO=1 omarchy-x --y" -> "omarchy-x". Env assignments before the binary are skipped.
function binaryOf(cmd) {
  var words = String(cmd || "").trim().split(/\s+/)
  for (var i = 0; i < words.length; i++) {
    if (/^[A-Za-z_][A-Za-z0-9_]*=/.test(words[i])) continue
    return words[i].replace(/^["']|["']$/g, "")
  }
  return ""
}

var PATH_FIX = 'PATH="$HOME/.local/bin:$PATH";'

// argv to run an action (detached). The command line is the owner's own text
// from their shell.json, run by sh like any launcher entry.
function runArgs(action) {
  if (!action || !String(action.cmd || "").trim()) return null
  return ["sh", "-c", PATH_FIX + String(action.cmd)]
}

// A one-shot script that prints the binaries (from `names`) that resolve, one
// per line. Names are passed as positional parameters, never spliced in.
function probeArgs(names) {
  var list = (Array.isArray(names) ? names : []).filter(function (n) { return typeof n === "string" && n !== "" && n.length < 200 })
  return ["sh", "-c", PATH_FIX + 'for b in "$@"; do if [ "${b#/}" != "$b" ]; then [ -x "$b" ] && printf "%s\\n" "$b"; else command -v "$b" >/dev/null 2>&1 && printf "%s\\n" "$b"; fi; done; exit 0', "notch-actions"].concat(list)
}

// Distinct binaries the actions need (cmd binaries only; a toggle's check is
// optional and best-effort).
function binaries(actions) {
  var seen = {}
  var out = []
  ;(Array.isArray(actions) ? actions : []).forEach(function (a) {
    var b = binaryOf(a && a.cmd)
    if (b && !seen[b]) { seen[b] = true; out.push(b) }
  })
  return out
}

function parseFound(text) {
  var found = {}
  String(text || "").split("\n").forEach(function (l) { l = l.trim(); if (l) found[l] = true })
  return found
}

// Rows for the Home row: each action plus whether it can run and why not.
//   found  map binary -> true from probeArgs, or null while still probing
// While probing, actions are enabled (a stale "missing" flash is worse).
function view(actions, found) {
  return (Array.isArray(actions) ? actions : []).map(function (a) {
    var bin = binaryOf(a.cmd)
    var ok = found === null || found === undefined || found[bin] === true
    return { id: a.id, label: a.label, kind: a.kind, icon: a.icon, enabled: ok, bin: bin,
             reason: ok ? "" : bin + " not found", hasCheck: a.kind === "toggle" && !!a.check }
  })
}

// Ids of toggles that carry a `check` (the row polls these).
function checkArgs(action) {
  if (!action || action.kind !== "toggle" || !action.check) return null
  return ["sh", "-c", PATH_FIX + String(action.check)]
}

// ---- editor operations (each returns a new list; the caller sanitises on save)

function uniqueId(list, base) {
  var ids = {}
  list.forEach(function (a) { ids[a.id] = true })
  var n = list.length + 1
  var id = base + n
  while (ids[id]) { n++; id = base + n }
  return id
}

function add(list, limit) {
  var l = (Array.isArray(list) ? list : []).slice()
  if (l.length >= limit) return l
  l.push({ id: uniqueId(l, "a"), label: "New action", kind: "command", cmd: "true", icon: "play" })
  return l
}

function remove(list, id) {
  return (Array.isArray(list) ? list : []).filter(function (a) { return a.id !== id })
}

function move(list, id, dir) {
  var l = (Array.isArray(list) ? list : []).slice()
  var at = -1
  l.forEach(function (a, i) { if (a.id === id) at = i })
  var to = at + (Number(dir) < 0 ? -1 : 1)
  if (at < 0 || to < 0 || to >= l.length) return l
  var t = l[at]; l[at] = l[to]; l[to] = t
  return l
}

function update(list, id, patch) {
  return (Array.isArray(list) ? list : []).map(function (a) {
    if (a.id !== id) return a
    var out = {}
    for (var k in a) out[k] = a[k]
    for (var p in patch) out[p] = patch[p]
    return out
  })
}

// Next icon key after `cur` in the order of `keys`.
function nextIcon(keys, cur) {
  var i = keys.indexOf(cur)
  return keys[(i + 1) % keys.length]
}

if (typeof module !== "undefined") {
  module.exports = { binaryOf: binaryOf, runArgs: runArgs, probeArgs: probeArgs, binaries: binaries, parseFound: parseFound, view: view,
    checkArgs: checkArgs, add: add, remove: remove, move: move, update: update, nextIcon: nextIcon }
}
