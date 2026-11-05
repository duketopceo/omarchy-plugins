// Pure logic for the notch's Network tab and idle status dot. No Qt types, so
// tests run it with node.
//
// Inputs:
//   `tailscale status --json`  BackendState, Self, Peer{ id: {...} }, AuthURL
//   the nordvpn plugin's `probe_nordvpn.py` (status / connect / disconnect):
//       {"ok":true,"cli":bool,"logged_in":bool,"status":{"state":
//        "connected|disconnected|connecting","server","hostname","ip",
//        "country","city",...},...}
// Everything is parsed defensively: junk in, a quiet "unavailable" out.

var TAILSCALE = "/usr/bin/tailscale"
var PYTHON = "/usr/bin/python3"
var NORD_PROBE_REL = "/.config/omarchy/plugins/io.github.duketopceo.nordvpn/bin/probe_nordvpn.py"
var MAX_PEERS = 64

function isObject(v) { return v !== null && typeof v === "object" && !Array.isArray(v) }

function emptyTailscale() {
  return { ok: false, state: "unavailable", running: false, needsLogin: false, selfName: "", selfIp: "", selfDns: "", exitNode: null, exitOptions: [], peers: [], onlineCount: 0, peerCount: 0, authUrl: "" }
}

function firstV4(ips) {
  if (!Array.isArray(ips)) return ""
  for (var i = 0; i < ips.length; i++) if (/^\d{1,3}(\.\d{1,3}){3}$/.test(String(ips[i]))) return String(ips[i])
  return ""
}

function shortName(host, dns) {
  var h = String(host || "")
  if (h && h.toLowerCase() !== "localhost") return h
  var d = String(dns || "").replace(/\.$/, "")
  return d.split(".")[0] || h || "unknown"
}

function isMullvad(p) {
  var d = String(p.DNSName || "").toLowerCase().replace(/\.$/, "")
  return /\.mullvad\.ts\.net$/.test(d)
}

// Parse `tailscale status --json` text. With `--peers=false` the peer list is
// empty; callers keep their previous peers in that case (see mergePeers).
function parseTailscale(text) {
  var d
  try { d = JSON.parse(String(text || "")) } catch (e) { return emptyTailscale() }
  if (!isObject(d)) return emptyTailscale()
  var backend = String(d.BackendState || "")
  var out = emptyTailscale()
  out.ok = backend !== ""
  out.state = backend === "Running" ? "running" : backend === "Stopped" ? "stopped" : backend === "NeedsLogin" ? "needslogin" : backend === "Starting" ? "starting" : "unavailable"
  out.running = out.state === "running"
  out.needsLogin = out.state === "needslogin"
  out.authUrl = typeof d.AuthURL === "string" ? d.AuthURL : ""
  var self = isObject(d.Self) ? d.Self : {}
  out.selfName = shortName(self.HostName, self.DNSName)
  out.selfIp = firstV4(self.TailscaleIPs) || firstV4(d.TailscaleIPs)
  out.selfDns = String(self.DNSName || "").replace(/\.$/, "")
  var peers = []
  var map = isObject(d.Peer) ? d.Peer : {}
  Object.keys(map).forEach(function (k) {
    var p = map[k]
    if (!isObject(p) || isMullvad(p)) return
    peers.push({ name: shortName(p.HostName, p.DNSName), ip: firstV4(p.TailscaleIPs), online: p.Online === true, os: String(p.OS || ""), exitNode: p.ExitNode === true,
      exitOption: p.ExitNodeOption === true, dns: String(p.DNSName || "").replace(/\.$/, ""), lastSeen: String(p.LastSeen || "") })
  })
  peers.sort(function (a, b) {
    if (a.online !== b.online) return a.online ? -1 : 1
    return a.name.toLowerCase() < b.name.toLowerCase() ? -1 : a.name.toLowerCase() > b.name.toLowerCase() ? 1 : 0
  })
  out.exitOptions = peers.filter(function (p) { return p.exitOption && p.ip })
  for (var i = 0; i < peers.length; i++) if (peers[i].exitNode) { out.exitNode = { name: peers[i].name, ip: peers[i].ip }; break }
  out.peerCount = peers.length
  out.onlineCount = peers.filter(function (p) { return p.online }).length
  out.peers = peers.slice(0, MAX_PEERS)
  out.peersKnown = Object.keys(map).length > 0
  return out
}

// A light poll (no peers) must not wipe a list a full poll already fetched.
function mergePeers(prev, next) {
  if (!next || next.peersKnown || !prev || !next.running) return next
  var copy = {}
  for (var k in next) copy[k] = next[k]
  copy.peers = prev.peers || []
  copy.peerCount = prev.peerCount || 0
  copy.onlineCount = prev.onlineCount || 0
  copy.exitOptions = prev.exitOptions || []
  copy.exitNode = prev.exitNode || null
  return copy
}

function tailscaleStatusArgs(full) {
  return [TAILSCALE, "status", "--json"].concat(full ? [] : ["--peers=false"])
}

// Connect when it is off, disconnect when it is on. null while a login is
// still pending (the toggle is disabled then).
function tailscaleToggleCommand(ts) {
  if (!ts || !ts.ok || ts.needsLogin) return null
  return [TAILSCALE, ts.running ? "down" : "up"]
}

function emptyNord() {
  return { ok: false, state: "unavailable", country: "", city: "", server: "", detail: "" }
}

function niceCountry(name) { return String(name || "").replace(/_/g, " ") }

function parseNord(text) {
  var d
  try { d = JSON.parse(String(text || "")) } catch (e) { return emptyNord() }
  if (!isObject(d) || d.cli === false || d.logged_in === false || !isObject(d.status)) return emptyNord()
  var st = String(d.status.state || "")
  if (st !== "connected" && st !== "disconnected" && st !== "connecting") return emptyNord()
  var out = emptyNord()
  out.ok = true
  out.state = st
  out.country = niceCountry(d.status.country)
  out.city = niceCountry(d.status.city)
  out.server = String(d.status.hostname || d.status.server || "")
  out.detail = [out.country, out.city].filter(function (s) { return s }).join(", ")
  return out
}

// ["status"] by default; "connect" / "disconnect" are the plugin's own verbs.
function nordArgs(home, verb) {
  var v = verb === "connect" || verb === "disconnect" ? verb : "status"
  return [PYTHON, String(home) + NORD_PROBE_REL, v]
}

function nordToggleVerb(nord) {
  if (!nord || !nord.ok) return null
  return nord.state === "disconnected" ? "connect" : "disconnect"
}

// "on" | "busy" | "off" for one service.
function dotState(state) {
  if (state === "running" || state === "connected") return "on"
  if (state === "starting" || state === "connecting") return "busy"
  return "off"
}

// The single idle-notch dot: green if either VPN/tailnet is up, amber while
// one is connecting, "" (hidden) otherwise.
function idleDot(ts, nord) {
  var a = dotState(ts ? ts.state : ""), b = dotState(nord ? nord.state : "")
  if (a === "on" || b === "on") return "on"
  if (a === "busy" || b === "busy") return "busy"
  return ""
}

function tailscaleSummary(ts) {
  if (!ts || !ts.ok) return "Unavailable"
  if (ts.needsLogin) return "Sign in needed"
  if (ts.state === "starting") return "Starting"
  if (!ts.running) return "Off"
  return ts.onlineCount + " of " + ts.peerCount + " online"
}

function nordSummary(nord) {
  if (!nord || !nord.ok) return "Unavailable"
  if (nord.state === "connecting") return "Connecting"
  if (nord.state === "connected") return "Connected"
  return "Off"
}

// ---------------------------------------------------------------- v4 additions

var OS_ICONS = {
  linux: { glyph: "\uF17C", label: "Linux" },
  macos: { glyph: "\uF179", label: "macOS" },
  ios: { glyph: "\uF179", label: "iOS" },
  windows: { glyph: "\uF17A", label: "Windows" },
  android: { glyph: "\uF17B", label: "Android" },
  other: { glyph: "\uF108", label: "Device" }
}

// OS string from the tailnet ("linux", "macOS", "iOS", "windows", ...) to an icon.
function osIcon(os) {
  var k = String(os || "").toLowerCase()
  if (k === "darwin") k = "macos"
  return OS_ICONS[k] || OS_ICONS.other
}

// Peers whose name, IP or OS contains the query (case-insensitive).
function filterPeers(peers, query) {
  var q = String(query || "").trim().toLowerCase()
  if (!Array.isArray(peers) || q === "") return Array.isArray(peers) ? peers : []
  return peers.filter(function (p) {
    return (String(p.name) + " " + String(p.ip) + " " + String(p.os)).toLowerCase().indexOf(q) >= 0
  })
}

// "now", "5m ago", "3h ago", "2d ago" for an ISO time; "" when unknown
// (Tailscale reports 0001-01-01 for peers that never went offline).
function relTime(iso, nowMs) {
  var t = Date.parse(String(iso || ""))
  if (!isFinite(t) || t < Date.UTC(2000, 0, 1)) return ""
  var s = Math.max(0, Math.round((Number(nowMs) - t) / 1000))
  if (s < 60) return "now"
  if (s < 3600) return Math.floor(s / 60) + "m ago"
  if (s < 86400) return Math.floor(s / 3600) + "h ago"
  return Math.floor(s / 86400) + "d ago"
}

// Right-hand text of a peer row: its IP when online, else when it was last seen.
function peerStatus(peer, nowMs) {
  if (!peer) return ""
  if (peer.online) return "online"
  return relTime(peer.lastSeen, nowMs) || "offline"
}

// `tailscale debug prefs` JSON: can `user` run `tailscale set --exit-node`
// without sudo? True when the operator is that user.
function exitNodeFeasible(prefsText, user) {
  var d
  try { d = JSON.parse(String(prefsText || "")) } catch (e) { return false }
  return isObject(d) && String(user || "") !== "" && d.OperatorUser === String(user)
}

// `tailscale set --exit-node=<ip>`; empty/invalid ip clears it. Never a shell.
function exitNodeArgs(ip) {
  var v = /^\d{1,3}(\.\d{1,3}){3}$/.test(String(ip || "")) ? String(ip) : ""
  return [TAILSCALE, "set", "--exit-node=" + v]
}

function tailscalePrefsArgs() { return [TAILSCALE, "debug", "prefs"] }

// Why the picker is read-only, or "" when it can be used.
function exitNodeNote(feasible) {
  return feasible ? "" : "Read-only: needs tailscale set --operator=$USER (sudo, once)"
}

// `nordvpn status` text ("Key: value" lines) -> fields. Disconnected prints
// only the Status line.
function parseNordText(text) {
  var out = { ok: false, state: "unavailable", server: "", hostname: "", ip: "", country: "", city: "", technology: "", protocol: "", transfer: "", uptime: "" }
  var lines = String(text || "").split(/\r?\n/)
  var kv = {}
  for (var i = 0; i < lines.length; i++) {
    var m = /^\s*([A-Za-z][A-Za-z \/-]*?)\s*:\s*(.*\S)\s*$/.exec(lines[i])
    if (m) kv[m[1].toLowerCase().replace(/[ \/-]+/g, "_")] = m[2]
  }
  var st = String(kv.status || "").toLowerCase()
  if (st !== "connected" && st !== "disconnected" && st !== "connecting") return out
  out.ok = true
  out.state = st
  out.hostname = kv.hostname || ""
  out.server = kv.server || ""
  out.ip = kv.ip || ""
  out.country = niceCountry(kv.country)
  out.city = niceCountry(kv.city)
  out.technology = kv.current_technology || kv.technology || ""
  out.protocol = kv.current_protocol || kv.protocol || ""
  out.transfer = kv.transfer || ""
  out.uptime = kv.uptime || ""
  return out
}

// `nordvpn countries`: names separated by newlines, tabs, commas or spaces.
// Returns [{ id: "United_States", label: "United States" }], sorted, unique.
function parseCountries(text) {
  var seen = {}, out = []
  String(text || "").split(/[\s,]+/).forEach(function (w) {
    if (!/^[A-Za-z][A-Za-z_]{1,40}$/.test(w) || seen[w]) return
    seen[w] = true
    out.push({ id: w, label: niceCountry(w) })
  })
  out.sort(function (a, b) { return a.label < b.label ? -1 : a.label > b.label ? 1 : 0 })
  return out
}

function nordStatusArgs() { return ["/usr/bin/nordvpn", "status"] }
function nordCountriesArgs() { return ["/usr/bin/nordvpn", "countries"] }

// Probe `connect <country>`; no country = the recommended server. The probe
// matches the name against `nordvpn countries` again before use.
function nordConnectArgs(home, country) {
  var c = String(country || "")
  var a = nordArgs(home, "connect")
  if (/^[A-Za-z][A-Za-z_]{1,40}$/.test(c)) a.push(c)
  return a
}

var DEFAULT_FAVORITES = ["United_States", "Canada", "Netherlands", "Switzerland"]
var MAX_FAVORITES = 6

function cleanFavorites(v) {
  if (!Array.isArray(v)) return DEFAULT_FAVORITES.slice()
  var out = []
  v.forEach(function (c) {
    c = String(c)
    if (/^[A-Za-z][A-Za-z_]{1,40}$/.test(c) && out.indexOf(c) < 0 && out.length < MAX_FAVORITES) out.push(c)
  })
  return out
}

function toggleFavorite(list, country) {
  var cur = cleanFavorites(list), c = String(country || "").replace(/ /g, "_")
  if (!/^[A-Za-z][A-Za-z_]{1,40}$/.test(c)) return cur
  var i = cur.indexOf(c)
  if (i >= 0) { cur.splice(i, 1); return cur }
  if (cur.length >= MAX_FAVORITES) cur.shift()
  cur.push(c)
  return cur
}

var CODES = { United_States: "US", Canada: "CA", Netherlands: "NL", Switzerland: "CH", United_Kingdom: "UK", Germany: "DE", France: "FR", Japan: "JP", Australia: "AU", Sweden: "SE", Singapore: "SG", Spain: "ES", Italy: "IT" }

// Short chip label for a favorite: the usual code, else the name's first word.
function favoriteLabel(country) {
  var c = String(country || "")
  return CODES[c] || c.split("_")[0]
}

if (typeof module !== "undefined") {
  module.exports = {
    TAILSCALE: TAILSCALE, PYTHON: PYTHON, parseTailscale: parseTailscale, mergePeers: mergePeers,
    tailscaleStatusArgs: tailscaleStatusArgs, tailscaleToggleCommand: tailscaleToggleCommand,
    parseNord: parseNord, nordArgs: nordArgs, nordToggleVerb: nordToggleVerb,
    osIcon: osIcon, filterPeers: filterPeers, relTime: relTime, peerStatus: peerStatus, exitNodeFeasible: exitNodeFeasible,
    exitNodeArgs: exitNodeArgs, tailscalePrefsArgs: tailscalePrefsArgs, exitNodeNote: exitNodeNote, parseNordText: parseNordText,
    parseCountries: parseCountries, nordStatusArgs: nordStatusArgs, nordCountriesArgs: nordCountriesArgs, nordConnectArgs: nordConnectArgs,
    cleanFavorites: cleanFavorites, toggleFavorite: toggleFavorite, favoriteLabel: favoriteLabel, DEFAULT_FAVORITES: DEFAULT_FAVORITES,
    dotState: dotState, idleDot: idleDot, tailscaleSummary: tailscaleSummary, nordSummary: nordSummary
  }
}
