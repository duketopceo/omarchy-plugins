import QtQuick
import Quickshell
import Quickshell.Io

// This plugin's own entry in ~/.config/omarchy/shell.json, read straight off
// disk. Omarchy 4.0.3 stopped handing third-party plugins `shell.shellConfig`,
// so without this the lastSeen watermark would fall back to empty every
// restart — and worse, a write that raced the initial async load would
// destroy the rest of the entry (lock-explorer issue #19, same fix shape).
// Writes go through the host's scoped updateEntryInline from Service.qml.
//
// The entry can sit in bar.layout.* (the bar-widget slot) or in plugins[] —
// updateEntryInline writes wherever the id is found, layout first, so the
// reader mirrors that precedence. A bare-string layout entry has no place
// for keys: it reads as "no watermark yet" and the first write upgrades it
// to {id, ...} — same id, nothing lost.
//
// The first read blocks: read-modify-write means a write that raced the
// initial async load would not merely see a stale value, it would destroy
// the rest of the entry. `remember()` keeps a write-through copy of what was
// just written, since the file watcher lands a beat after the host's atomic
// write and two watermark updates back to back must not clobber each other.
Item {
  id: root
  property string pluginId: "io.github.duketopceo.bumblebee"
  property string path: Quickshell.env("HOME") + "/.config/omarchy/shell.json"
  property var entry: ({})
  property bool loaded: false

  function reload() { settingsFile.reload() }

  function remember(next) {
    var copy = {}
    for (var k in next) if (k !== "id") copy[k] = next[k]
    copy.id = root.pluginId
    root.entry = copy
  }

  // Mirror updateEntryInline's precedence: the bar layout slot first (this
  // is where a placed bar-widget lives), then the top-level plugins[] entry.
  function findEntry(parsed) {
    var bar = parsed ? parsed.bar : null
    var layout = bar ? bar.layout : null
    if (layout && typeof layout === "object") {
      var sections = ["left", "center", "right"]
      for (var s = 0; s < sections.length; s++) {
        var arr = layout[sections[s]]
        if (!Array.isArray(arr)) continue
        for (var i = 0; i < arr.length; i++) {
          var e = arr[i]
          var eid = (e && typeof e === "object") ? e.id : e
          if (String(eid || "") === root.pluginId) return e
        }
      }
    }
    var entries = parsed && Array.isArray(parsed.plugins) ? parsed.plugins : []
    for (var j = 0; j < entries.length; j++) {
      var en = entries[j]
      if (en && String(en.id || "") === root.pluginId) return en
    }
    return null
  }

  function parse() {
    var raw = ""
    try { raw = String(settingsFile.text() || "") } catch (e) { raw = "" }
    if (raw.trim().length === 0) {
      // A missing or empty file has no entry to keep; nothing to protect.
      root.entry = {}
      root.loaded = true
      return
    }
    try {
      var parsed = JSON.parse(raw)
      var selected = findEntry(parsed)
      root.entry = (selected && typeof selected === "object") ? selected : {}
      root.loaded = true
    } catch (e) {
      // A partial or invalid write must not reset the last known watermark.
      console.warn("bumblebee: cannot read saved plugin settings: " + e)
    }
  }

  FileView {
    id: settingsFile
    path: root.path
    blockLoading: true
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.parse()
    onLoadFailed: root.parse()
  }

  Component.onCompleted: parse()
}
