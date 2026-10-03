import QtQuick
import Quickshell

// One minimal environment for every helper a plugin execs.
//
// Quickshell semantics (verified 2026-10-03 with an offscreen qs run): under
// `clearEnvironment: true`, an `environment` key set to `null` is INHERITED
// from the shell, not unset. So this map never uses null; a variable is either
// set explicitly here or absent. Secrets (*_API_KEY, tokens) are never passed:
// helpers fetch them from omaseal at the moment of use.
QtObject {
  id: root

  // Fixed system PATH; user bins are never searched before system bins.
  readonly property string safePath: "/usr/bin:/bin:/usr/sbin:/sbin"

  // Optional extra keys a plugin needs (non-secret); merged last.
  property var extra: ({})

  readonly property var env: {
    var out = { "PATH": root.safePath, "LC_ALL": "C.UTF-8" }
    var keep = ["HOME", "XDG_RUNTIME_DIR", "XDG_STATE_HOME", "XDG_CONFIG_HOME", "LANG"]
    for (var i = 0; i < keep.length; i++) {
      var v = Quickshell.env(keep[i])
      if (v !== undefined && v !== null && String(v) !== "") out[keep[i]] = String(v)
    }
    var x = root.extra || {}
    for (var k in x) {
      if (/(KEY|TOKEN|SECRET|PASSWORD)/i.test(k)) continue
      if (x[k] !== undefined && x[k] !== null) out[k] = String(x[k])
    }
    return out
  }
}
