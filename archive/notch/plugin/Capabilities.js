// Pure logic for optional-module detection and first-run setup. No Qt types.
//
// Built-in tabs (Home, Media, Network, Power, System, Stocks, Plugins,
// Settings) always ship. Optional modules below start off; first-run setup
// offers Enable when a probe finds the capability on this host. Enabling only
// flips a setting — it never installs sibling plugins or touches private
// shell config beyond this plugin's shell.json entry.

var MODULES = [
  {
    id: "screenshots",
    label: "Screenshots",
    setting: "snapdex",
    tab: "screenshots",
    probe: "screenshots",
    hint: "Needs the snapdex plugin (snapdex-ctl)"
  },
  {
    id: "agents",
    label: "Agents",
    setting: "optAgents",
    tab: "agents",
    probe: "agents",
    hint: "Needs herdr (`herdr-app` in ~/.local/bin)"
  },
  {
    id: "messages",
    label: "Messages",
    setting: "optMessages",
    tab: "messages",
    probe: "messages",
    hint: "Needs Blip (nixfred.blip) running"
  },
  {
    id: "wordink",
    label: "Dictation",
    setting: "optWordink",
    tab: null,
    probe: "wordink",
    hint: "Needs the wordink CLI"
  },
  {
    id: "wisp",
    label: "Wisp",
    setting: "optWisp",
    tab: null,
    probe: "wisp",
    hint: "Needs the wisp plugin"
  },
  {
    id: "finance",
    label: "Finance watchlist",
    setting: "showStocks",
    tab: null,
    probe: "finance",
    hint: "Uses Omarchy finance.json or notch stocks.watchlist; Yahoo fetch is built in"
  },
  {
    id: "fan",
    label: "Fan modes",
    setting: "optFan",
    tab: null,
    probe: "fan",
    hint: "Mode writes need lukedaduke.fan; RPM reads work from sysfs alone"
  }
]

function byId(id) {
  for (var i = 0; i < MODULES.length; i++) if (MODULES[i].id === id) return MODULES[i]
  return null
}

function emptyProbe() {
  return {
    ok: false,
    platform: "unknown",
    system: "",
    machine: "",
    appleSilicon: false,
    macos: false,
    omarchyHost: false,
    screenshots: false,
    agents: false,
    messages: false,
    wordink: false,
    wisp: false,
    finance: false,
    fan: false,
    clipboard: false,
    hud: false,
    plugins: false,
    tailscale: false,
    nordvpn: false,
    gpu: { kind: "none", label: "GPU", util: false, note: "n/a" },
    npu: { kind: "none", label: "NPU", present: false },
    display: { model: "", cutouts: 0, note: "" }
  }
}

function isObject(v) { return v !== null && typeof v === "object" && !Array.isArray(v) }

// Parse `bin/notch-probe` JSON (or junk → emptyProbe).
function parseProbe(text) {
  var out = emptyProbe()
  var d
  try { d = JSON.parse(String(text || "")) } catch (e) { return out }
  if (!isObject(d)) return out
  out.ok = d.ok === true
  out.platform = typeof d.platform === "string" ? d.platform : out.platform
  out.system = typeof d.system === "string" ? d.system : ""
  out.machine = typeof d.machine === "string" ? d.machine : ""
  out.appleSilicon = d.appleSilicon === true
  out.macos = d.macos === true
  out.omarchyHost = d.omarchyHost === true
  ;["screenshots", "agents", "messages", "wordink", "wisp", "finance", "fan", "clipboard", "hud", "plugins", "tailscale", "nordvpn"].forEach(function (k) {
    out[k] = d[k] === true
  })
  if (isObject(d.gpu)) {
    out.gpu = {
      kind: String(d.gpu.kind || "none"),
      label: String(d.gpu.label || "GPU"),
      util: d.gpu.util === true,
      note: String(d.gpu.note || "")
    }
  }
  if (isObject(d.npu)) {
    out.npu = {
      kind: String(d.npu.kind || "none"),
      label: String(d.npu.label || "NPU"),
      present: d.npu.present === true
    }
  }
  if (isObject(d.display)) {
    out.display = {
      model: String(d.display.model || ""),
      cutouts: Math.max(0, Math.floor(Number(d.display.cutouts) || 0)),
      note: String(d.display.note || "")
    }
  }
  return out
}

function detected(probe, moduleId) {
  var m = byId(moduleId)
  if (!m || !probe) return false
  return probe[m.probe] === true
}

// Rows for the Setup / Optional section. Each: { id, label, setting, hint,
// detected, enabled, offer }. `offer` = detected and not yet enabled (or
// showStocks false when finance file found).
function setupRows(probe, settings) {
  var rows = []
  for (var i = 0; i < MODULES.length; i++) {
    var m = MODULES[i]
    var on = !!(settings && settings[m.setting] === true)
    var det = detected(probe, m.id)
    rows.push({
      id: m.id,
      label: m.label,
      setting: m.setting,
      hint: m.hint,
      tab: m.tab,
      detected: det,
      enabled: on,
      offer: det && !on
    })
  }
  return rows
}

function offers(probe, settings) {
  return setupRows(probe, settings).filter(function (r) { return r.offer })
}

function needsSetup(settings) {
  return !(settings && settings.setupDone === true)
}

// Built-in surface that never depends on sibling plugins.
var STANDALONE = [
  { id: "home", label: "Home" },
  { id: "media", label: "Media (MPRIS)" },
  { id: "network", label: "Network (tailscale/nordvpn CLIs)" },
  { id: "power", label: "Power (sysfs)" },
  { id: "system", label: "System (sysfs; GPU/NPU labels from probe)" },
  { id: "stocks", label: "Stocks (Yahoo via notch-data)" },
  { id: "plugins", label: "Plugins (bar tray list)" },
  { id: "settings", label: "Settings / setup" }
]

// Honest platform blurb for README / status (not marketing).
function platformTruth(probe) {
  var p = probe || emptyProbe()
  if (p.macos) {
    return "This plugin targets Omarchy (Linux + Quickshell/Wayland). It does not run on macOS."
  }
  if (p.appleSilicon && p.omarchyHost) {
    return "Omarchy on Apple Silicon (Asahi/ARM Linux): cutout geometry from display-cutouts.json + device-tree model; ANE when /sys/class/accel is present. Not macOS."
  }
  if (p.omarchyHost) {
    return "Omarchy on Linux (" + (p.machine || "unknown arch") + "): virtual notch on panels without a cutout; camera width auto-detects from model/panel when cutouts exist."
  }
  return "Omarchy / Quickshell on Linux only. Not a macOS app; MacBook hardware is supported only when running Omarchy (e.g. Asahi Linux), never stock macOS."
}

if (typeof module !== "undefined") {
  module.exports = {
    MODULES: MODULES, STANDALONE: STANDALONE, byId: byId, emptyProbe: emptyProbe,
    parseProbe: parseProbe, detected: detected, setupRows: setupRows, offers: offers,
    needsSetup: needsSetup, platformTruth: platformTruth
  }
}
