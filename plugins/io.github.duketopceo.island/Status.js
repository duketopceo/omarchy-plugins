// Display text for the Home status dots, the Home weather field and the
// System page rows, from bin/island-status output. ES5, no Qt types; node
// tests load it with require(). Missing sources (null) are hidden, never shown
// as an error.

var DOT = "·"

function _cap(s) {
  var t = String(s || "")
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : ""
}

// Omarchy's `omarchy-weather-status` line ("Place  ·  Temp 12°C  ·  Wind ...")
// -> { place, temp }, or null when Omarchy reports it unavailable.
function weather(text) {
  var s = String(text === null || text === undefined ? "" : text)
  var m = /Temp\s+\+?(-?\d+(?:\.\d+)?\s*°\s*[CF])/.exec(s)
  if (!m) return null
  var place = s.split(DOT)[0].replace(/^\s+|\s+$/g, "")
  return { place: place, temp: m[1].replace(/\s+/g, "") }
}

// True when shell.json places Omarchy's weather widget in the bar and does not
// disable it: the Island only reuses a weather service Omarchy already polls.
function weatherInBar(shellJson) {
  var o
  try { o = JSON.parse(String(shellJson === null || shellJson === undefined ? "" : shellJson)) } catch (e) { return false }
  if (!o || typeof o !== "object" || Array.isArray(o)) return false
  if (Array.isArray(o.disabledPlugins) && o.disabledPlugins.indexOf("omarchy.weather") >= 0) return false
  var layout = o.bar && typeof o.bar === "object" ? o.bar.layout : null
  if (!layout || typeof layout !== "object") return false
  for (var section in layout) {
    var list = layout[section]
    if (!Array.isArray(list)) continue
    for (var i = 0; i < list.length; i++) if (list[i] && list[i].id === "omarchy.weather") return true
  }
  return false
}

function _tailscaleUp(t) { return !!t && t.state === "Running" && t.online === true }

// -> [{ id, text, on }]: battery, Tailscale, and VPN only while one is up.
function homeDots(h) {
  var out = []
  if (!h) return out
  if (h.battery && typeof h.battery.capacity === "number") {
    var charging = h.battery.status === "Charging"
    out.push({ id: "battery", text: h.battery.capacity + "%" + (charging ? " charging" : ""), on: true })
  }
  if (h.tailscale) out.push({ id: "tailscale", text: "Tailscale", on: _tailscaleUp(h.tailscale) })
  if (h.vpn && h.vpn.on === true) out.push({ id: "vpn", text: "VPN", on: true })
  return out
}

// Home's glance tile: battery, CPU and memory as [{ id, label, value, level }],
// level 0..1. Sources that are missing are left out.
function glance(h) {
  var out = []
  if (!h) return out
  if (h.battery && typeof h.battery.capacity === "number") {
    var st = h.battery.status === "Charging" ? " " + DOT + " charging" : (h.battery.status === "Full" ? " " + DOT + " full" : "")
    out.push({ id: "battery", label: "Battery", value: h.battery.capacity + "%" + st, level: h.battery.capacity / 100 })
  }
  if (typeof h.cpu === "number") out.push({ id: "cpu", label: "CPU", value: h.cpu + "%", level: h.cpu / 100 })
  if (h.memory && typeof h.memory.usedPct === "number") {
    out.push({ id: "memory", label: "Memory", value: h.memory.usedPct + "%", level: h.memory.usedPct / 100 })
  }
  return out
}

function _gb(bytes) { return (Number(bytes) / 1073741824).toFixed(1) }

var NET_KIND = { wifi: "Wi-Fi", ethernet: "Ethernet" }

// -> [{ id, label, value, level? }] in a fixed order; level is 0..1 for meters.
function systemRows(s) {
  var out = []
  if (!s) return out
  if (s.battery && typeof s.battery.capacity === "number") {
    out.push({ id: "battery", label: "Battery", value: s.battery.capacity + "% " + DOT + " " + (s.battery.status || "Unknown"),
               level: s.battery.capacity / 100 })
  }
  if (s.profile) out.push({ id: "profile", label: "Power profile", value: _cap(String(s.profile).replace(/-/g, " ")) })
  if (s.fan) out.push({ id: "fan", label: "Fan", value: _cap(s.fan) })
  if (typeof s.cpu === "number") out.push({ id: "cpu", label: "CPU", value: s.cpu + "%", level: s.cpu / 100 })
  if (s.memory && typeof s.memory.usedPct === "number") {
    out.push({ id: "memory", label: "Memory", level: s.memory.usedPct / 100,
               value: s.memory.usedPct + "% " + DOT + " " + _gb(s.memory.used) + " of " + _gb(s.memory.total) + " GB" })
  }
  if (s.network && s.network.iface) {
    var kind = NET_KIND[s.network.type] || _cap(s.network.type) || "Network"
    out.push({ id: "network", label: "Network", value: kind + " " + DOT + " " + (s.network.name || s.network.iface) })
  }
  if (s.tailscale) {
    var t = s.tailscale
    var v = _tailscaleUp(t) ? "Connected " + DOT + " " + t.peers + (t.peers === 1 ? " peer" : " peers") : (_cap(t.state) || "Down")
    out.push({ id: "tailscale", label: "Tailscale", value: v })
  }
  return out
}

// ---- the System page: rings, chips and the power-profile control ----

var PROFILE_NAMES = ["power-saver", "balanced", "performance"]
var PROFILE_LABEL = { "power-saver": "Saver", balanced: "Balanced", performance: "Performance" }
var PROFILE_HINT = { "power-saver": "Power saver", balanced: "Balanced", performance: "Performance" }

// `powerprofilesctl list` text -> { names: [profile names, in the daemon's
// order], active } . Header lines look like "* balanced:" or "  power-saver:".
function parseProfiles(raw) {
  var names = []
  var active = ""
  var lines = String(raw === null || raw === undefined ? "" : raw).split("\n")
  for (var i = 0; i < lines.length; i++) {
    var m = /^([* ]) ([a-z][a-z-]{0,31}):\s*$/.exec(lines[i])
    if (!m) continue
    names.push(m[2])
    if (m[1] === "*") active = m[2]
  }
  return { names: names, active: active }
}

// The command that sets a profile, as an argv list, or [] when `name` is not
// one the daemon listed (nothing is ever built from free text).
function profileArgv(name, raw) {
  var listed = parseProfiles(raw).names
  var n = String(name === null || name === undefined ? "" : name)
  return listed.indexOf(n) >= 0 ? ["powerprofilesctl", "set", n] : []
}

// A ring's accent: urgent when the machine is under strain (CPU or memory at
// 90% or more, battery at 15% or less and not charging), else the accent.
function ringTone(id, pct, charging) {
  if (id === "battery") return pct <= 15 && !charging ? "urgent" : "accent"
  return pct >= 90 ? "urgent" : "accent"
}

function _pct(n) { return Math.max(0, Math.min(100, Math.round(Number(n)))) }

// -> { rings: [{ id, caption, pct, level, tone, charging }],
//      chips: [{ id, icon, text, on, action }],
//      profiles: { names: [{ name, label, hint }], active, available } }
// Rings and chips whose source is missing are left out.
function system(s) {
  var out = { rings: [], chips: [], profiles: { names: [], active: "", available: false } }
  if (!s) return out
  if (s.battery && typeof s.battery.capacity === "number") {
    var charging = s.battery.status === "Charging"
    var b = _pct(s.battery.capacity)
    out.rings.push({ id: "battery", caption: "Battery", pct: b, level: b / 100, tone: ringTone("battery", b, charging), charging: charging })
  }
  if (typeof s.cpu === "number") {
    var c = _pct(s.cpu)
    out.rings.push({ id: "cpu", caption: "CPU", pct: c, level: c / 100, tone: ringTone("cpu", c, false), charging: false })
  }
  if (s.memory && typeof s.memory.usedPct === "number") {
    var m = _pct(s.memory.usedPct)
    out.rings.push({ id: "memory", caption: "Memory", pct: m, level: m / 100, tone: ringTone("memory", m, false), charging: false })
  }
  if (s.network && s.network.iface) {
    out.chips.push({ id: "network", icon: s.network.type === "wifi" ? "wifi" : "ethernet", on: true, action: "",
                     text: s.network.name || NET_KIND[s.network.type] || "Network" })
  }
  if (s.tailscale) {
    var t = s.tailscale
    var up = _tailscaleUp(t)
    out.chips.push({ id: "tailscale", icon: "vpn", on: up, action: "",
                     text: up ? t.peers + (t.peers === 1 ? " peer" : " peers") : "Off" })
  }
  if (s.fan || s.fanPanel === true) {
    out.chips.push({ id: "fan", icon: "fan", on: true, action: s.fanPanel === true ? "fan" : "", text: s.fan ? _cap(s.fan) : "Fan" })
  }
  var parsed = parseProfiles(s.profiles)
  var names = parsed.names.length > 0 ? parsed.names : PROFILE_NAMES
  for (var i = 0; i < names.length; i++) {
    out.profiles.names.push({ name: names[i], label: PROFILE_LABEL[names[i]] || _cap(names[i].replace(/-/g, " ")),
                              hint: PROFILE_HINT[names[i]] || _cap(names[i].replace(/-/g, " ")) })
  }
  out.profiles.active = String(s.profile || parsed.active || "")
  out.profiles.available = parsed.names.length > 0
  return out
}

if (typeof module !== "undefined") module.exports = {
  weather: weather, weatherInBar: weatherInBar, homeDots: homeDots, glance: glance, systemRows: systemRows,
  parseProfiles: parseProfiles, profileArgv: profileArgv, ringTone: ringTone, system: system
}
