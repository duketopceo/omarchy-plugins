// Sentinel for "no reading yet" so every readout can bind a raw nullable
// field without each call site re-implementing the guard.
var DASH = "—"

function num(v) {
  return (typeof v === "number" && isFinite(v)) ? v : null
}

function flowWord(flow) {
  if (flow === "in") return "in"
  if (flow === "out") return "out"
  return "idle"
}

// The kernel reports power negative while discharging; that sign is the most
// honest statement of direction we have, so it is kept rather than abs()'d.
function fmtPower(watts, flow) {
  var n = num(watts)
  if (n === null) return DASH
  if (n === 0) return "0.00 W idle"
  return n.toFixed(2) + " W " + flowWord(flow)
}

function fmtTemp(c) {
  var n = num(c)
  return n === null ? DASH : n.toFixed(1) + " °C"
}

// "31.13 / 84.50 Wh" — present and full side by side, because a bare Wh number
// hides how much of the pack is actually left.
function fmtEnergy(now, full) {
  var a = num(now), b = num(full)
  if (a === null || b === null) return DASH
  return a.toFixed(2) + " / " + b.toFixed(2) + " Wh"
}

// Seconds -> "2h 19m". Minutes round up, so the estimate never understates
// what is left: 7140s is exactly "1h 59m", and 7141s carries to "2h 0m".
function fmtRuntime(seconds) {
  var s = num(seconds)
  if (s === null || s <= 0) return DASH
  var mins = Math.ceil(s / 60)
  var h = Math.floor(mins / 60)
  var m = mins % 60
  return h > 0 ? h + "h " + m + "m" : m + "m"
}

function fmtLimit(end, resume) {
  var e = num(end)
  if (e === null) return DASH
  var r = num(resume)
  return r === null ? e + "%" : e + "% · resumes " + r + "%"
}

// "2022-07-09" -> "2022-07". Day precision is noise on a widget.
function fmtAge(manufactured) {
  if (!manufactured) return DASH
  var parts = String(manufactured).split("-")
  if (parts.length !== 3) return DASH
  return parts[0] + "-" + parts[1]
}

function clampIndex(index, length) {
  if (length <= 0) return 0
  return Math.max(0, Math.min(length - 1, index))
}

function selectProfileIndex(index, delta, profiles) {
  var values = Array.isArray(profiles) ? profiles : []
  if (values.length === 0) return 0
  return clampIndex(index + delta, values.length)
}

function parseKeyValue(raw) {
  var next = {}
  var lines = String(raw || "").split("\n")
  for (var i = 0; i < lines.length; i++) {
    var idx = lines[i].indexOf("\t")
    if (idx <= 0) continue
    next[lines[i].substring(0, idx)] = lines[i].substring(idx + 1).trim()
  }
  return next
}

function parseProfiles(raw, previousIndex) {
  var lines = String(raw || "").split("\n")
  var list = []
  var active = ""
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].trim()
    if (!line) continue
    var parts = line.split("\t")
    list.push(parts[0])
    if (parts[1] === "1") active = parts[0]
  }
  return {
    profiles: list,
    activeProfile: active,
    profileIndex: clampIndex(previousIndex || 0, list.length)
  }
}

function profileIcon(name) {
  if (name === "power-saver") return "󰌪"
  if (name === "balanced") return "󰊚"
  if (name === "performance") return "󰓅"
  return "󰂄"
}

function batteryFraction(device) {
  return device && device.isPresent ? Math.max(0, Math.min(1, device.percentage)) : 0
}

function chargeThresholdActive(device, onBattery, states) {
  var d = device || {}
  var s = states || {}
  if (!(d && d.isPresent && !onBattery)) return false

  var fraction = batteryFraction(d)
  if (d.state === s.Discharging) return false
  if (d.state === s.PendingCharge) return true
  if (d.state === s.FullyCharged && fraction < 0.99) return true
  if (d.state !== s.Charging || fraction >= 0.99) return false

  return Number(d.changeRate || 0) <= 0.2 || Number(d.timeToFull || 0) >= 8 * 60 * 60
}

function batteryIcon(device, onBattery, states) {
  var d = device || {}
  if (!d.isPresent) return ""

  var chargingIcons = ["󰢜", "󰂆", "󰂇", "󰂈", "󰢝", "󰂉", "󰢞", "󰂊", "󰂋", "󰂅"]
  var defaultIcons = ["󰁺", "󰁻", "󰁼", "󰁽", "󰁾", "󰁿", "󰂀", "󰂁", "󰂂", "󰁹"]
  var index = Math.max(0, Math.min(9, Math.floor(d.percentage * 10)))
  var threshold = chargeThresholdActive(d, onBattery, states)

  if (threshold) return defaultIcons[index]
  if (d.state === states.FullyCharged) return "󰂅"
  if (!onBattery) return chargingIcons[index]
  return defaultIcons[index]
}

function modeLabel(device, onBattery, states) {
  var d = device || {}
  if (!d.isPresent) return ""

  var percentage = d.isPresent ? d.percentage : 0
  if (chargeThresholdActive(d, onBattery, states)) return "Threshold"
  if (onBattery) return "On battery"
  if (!onBattery && percentage >= 1) return "Fully charged"
  return "Charging"
}

if (typeof module !== "undefined") {
  module.exports = {
    clampIndex: clampIndex,
    selectProfileIndex: selectProfileIndex,
    parseKeyValue: parseKeyValue,
    parseProfiles: parseProfiles,
    profileIcon: profileIcon,
    batteryFraction: batteryFraction,
    chargeThresholdActive: chargeThresholdActive,
    batteryIcon: batteryIcon,
    modeLabel: modeLabel,
    DASH: DASH,
    flowWord: flowWord,
    fmtPower: fmtPower,
    fmtTemp: fmtTemp,
    fmtEnergy: fmtEnergy,
    fmtRuntime: fmtRuntime,
    fmtLimit: fmtLimit,
    fmtAge: fmtAge
  }
}
