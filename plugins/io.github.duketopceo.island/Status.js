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

if (typeof module !== "undefined") module.exports = { weather: weather, homeDots: homeDots, systemRows: systemRows }
