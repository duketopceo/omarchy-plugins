import QtQuick
import Quickshell
import Quickshell.Io

// This plugin's own entry in ~/.config/omarchy/shell.json, read straight off
// disk. Third-party services are not handed the shell config tree, so the
// persisted findings watermark (entry.lastSeenFinding) is hydrated here.
// Writes still go through the host's scoped updateEntryInline — this file
// only reads, and remember() keeps a write-through copy so a write is never
// lost while the file watcher lands a beat behind the host's atomic write.
//
// Lookup order mirrors updateEntryInline in shell.qml: bar.layout.* entries
// first (the bar widget slot), then top-level plugins[] — whichever the
// write will replace is the entry we hydrate from.
Item {
  id: root
  property string pluginId: "io.github.duketopceo.numbat"
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

  function _matches(item) {
    if (typeof item === "string") return item === root.pluginId
    return item && String(item.id || "") === root.pluginId
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
      var selected = {}
      var found = false
      var layout = parsed && parsed.bar && parsed.bar.layout
      var sections = ["left", "center", "right"]
      for (var s = 0; s < sections.length && !found; s++) {
        var arr = layout && Array.isArray(layout[sections[s]]) ? layout[sections[s]] : []
        for (var i = 0; i < arr.length; i++) {
          if (root._matches(arr[i])) {
            selected = typeof arr[i] === "string" ? { id: arr[i] } : arr[i]
            found = true
            break
          }
        }
      }
      if (!found) {
        var entries = parsed && Array.isArray(parsed.plugins) ? parsed.plugins : []
        for (var j = 0; j < entries.length; j++) {
          if (root._matches(entries[j])) {
            selected = entries[j]
            break
          }
        }
      }
      root.entry = selected
      root.loaded = true
    } catch (e) {
      // A partial or invalid write must not reset the last known settings.
      console.warn("numbat: cannot read saved plugin settings: " + e)
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
