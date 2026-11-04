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
  return { ok: false, state: "unavailable", running: false, needsLogin: false, selfName: "", selfIp: "", peers: [], onlineCount: 0, peerCount: 0, authUrl: "" }
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
  var peers = []
  var map = isObject(d.Peer) ? d.Peer : {}
  Object.keys(map).forEach(function (k) {
    var p = map[k]
    if (!isObject(p) || isMullvad(p)) return
    peers.push({ name: shortName(p.HostName, p.DNSName), ip: firstV4(p.TailscaleIPs), online: p.Online === true, os: String(p.OS || ""), exitNode: p.ExitNode === true })
  })
  peers.sort(function (a, b) {
    if (a.online !== b.online) return a.online ? -1 : 1
    return a.name.toLowerCase() < b.name.toLowerCase() ? -1 : a.name.toLowerCase() > b.name.toLowerCase() ? 1 : 0
  })
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

if (typeof module !== "undefined") {
  module.exports = {
    TAILSCALE: TAILSCALE, PYTHON: PYTHON, parseTailscale: parseTailscale, mergePeers: mergePeers,
    tailscaleStatusArgs: tailscaleStatusArgs, tailscaleToggleCommand: tailscaleToggleCommand,
    parseNord: parseNord, nordArgs: nordArgs, nordToggleVerb: nordToggleVerb,
    dotState: dotState, idleDot: idleDot, tailscaleSummary: tailscaleSummary, nordSummary: nordSummary
  }
}
