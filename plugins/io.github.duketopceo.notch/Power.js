// Pure logic for the Power tab. No Qt types, so tests run it with node.
//
// Parsing and formatting here is adapted from the lukedaduke.power plugin
// (Model.js: fmtRuntime, parseProfiles, profileIcon, chargeThresholdActive
// ideas) by the same author, extended with sysfs watts, health and history.

var DASH = "—"

function num(v) {
  return (typeof v === "number" && isFinite(v)) ? v : null
}

function toNum(v) {
  if (v === null || v === undefined || String(v).trim() === "") return null
  var n = Number(String(v).trim())
  return isFinite(n) ? n : null
}

// `omarchy-battery-status --shell` prints tab-separated "key<TAB>value" lines:
//   percentage 23%, state charging, rate 52.3W, size 82Wh, time 53m,
//   cycles 290, threshold 75-80%
function parseStatus(raw) {
  var kv = {}
  var lines = String(raw || "").split("\n")
  for (var i = 0; i < lines.length; i++) {
    var idx = lines[i].indexOf("\t")
    if (idx <= 0) continue
    kv[lines[i].substring(0, idx).trim()] = lines[i].substring(idx + 1).trim()
  }
  var pct = toNum(String(kv.percentage || kv.percent || "").replace("%", ""))
  var thr = /^(\d+)\s*-\s*(\d+)\s*%?$/.exec(kv.threshold || "")
  var low = thr ? Number(thr[1]) : null
  var high = thr ? Number(thr[2]) : null
  if (!thr) {
    var single = toNum(String(kv.threshold || "").replace("%", ""))
    if (single !== null) high = single
  }
  return {
    ok: pct !== null,
    percent: pct,
    state: String(kv.state || "").toLowerCase(),
    rateW: toNum(String(kv.rate || "").replace(/W$/i, "")),
    sizeWh: toNum(String(kv.size || "").replace(/Wh$/i, "")),
    timeSeconds: parseDuration(kv.time),
    cycles: toNum(kv.cycles),
    thresholdLow: low,
    thresholdHigh: high
  }
}

// "2h 19m", "53m", "1h", "45s" -> seconds; null when not a duration.
function parseDuration(text) {
  var s = String(text || "").trim()
  if (!s) return null
  var re = /(\d+)\s*([dhms])/g
  var total = 0
  var found = false
  var m
  while ((m = re.exec(s)) !== null) {
    found = true
    var n = Number(m[1])
    total += m[2] === "d" ? n * 86400 : m[2] === "h" ? n * 3600 : m[2] === "m" ? n * 60 : n
  }
  return found ? total : null
}

// Seconds -> "2h 19m". Minutes round up so an estimate never understates.
function fmtTime(seconds) {
  var s = num(seconds)
  if (s === null || s <= 0) return DASH
  var mins = Math.ceil(s / 60)
  var h = Math.floor(mins / 60)
  var m = mins % 60
  return h > 0 ? h + "h " + m + "m" : m + "m"
}

// `tail -n +1 <files>` output ("==> path <==" headers) -> { basename: text }.
function parseSysfsDump(raw) {
  var out = {}
  var cur = null
  var lines = String(raw || "").split("\n")
  for (var i = 0; i < lines.length; i++) {
    var h = /^==> (.+) <==$/.exec(lines[i])
    if (h) {
      var path = h[1]
      var scope = path.indexOf("macsmc-ac") >= 0 ? "ac_" : ""
      cur = scope + path.substring(path.lastIndexOf("/") + 1)
      continue
    }
    if (cur !== null && lines[i].trim() !== "") out[cur] = lines[i].trim()
  }
  return out
}

// Sysfs power fields are micro-units. Prefer power_now; otherwise
// current_now x voltage_now. `status` gives direction because macsmc reports
// magnitudes. Returns { watts (>= 0), flow: "in" | "out" | "idle", source }.
function wattsFromSysfs(f, status) {
  f = f || {}
  var watts = null
  var i = null
  var source = ""
  var p = toNum(f.power_now)
  if (p !== null && p !== 0) {
    watts = Math.abs(p) / 1e6
    source = "power_now"
  } else {
    i = toNum(f.current_now)
    var v = toNum(f.voltage_now)
    if (i !== null && v !== null && i !== 0) {
      watts = Math.abs(i) * Math.abs(v) / 1e12
      source = "current_now*voltage_now"
    } else if (p === 0 || i === 0) {
      watts = 0
      source = p === 0 ? "power_now" : "current_now"
    }
  }
  if (watts === null) return { watts: null, flow: "idle", source: "" }
  var st = String(status || "").toLowerCase()
  var flow = "idle"
  if (watts >= 0.05) {
    if (st === "discharging") flow = "out"
    else if (st === "charging") flow = "in"
    else if (st === "") flow = (p !== null && p < 0) || (i !== null && i < 0) ? "out" : "in"
  }
  return { watts: Math.round(watts * 100) / 100, flow: flow, source: source }
}

function fmtWatts(w) {
  var n = num(w)
  if (n === null) return DASH
  return (n >= 100 ? n.toFixed(0) : n.toFixed(1)) + " W"
}

// Normalise the battery state: "charging" | "discharging" | "hold" | "full".
// `hold` is the charge-limit plateau: on AC, below full, but not charging.
function chargeState(status, percent, acOnline, thresholdHigh) {
  var st = String(status || "").toLowerCase().replace(/[_ ]/g, "-")
  var p = num(percent)
  if (st === "discharging") return "discharging"
  if (acOnline === false && st !== "charging" && st !== "full") return "discharging"
  if (st === "charging") return "charging"
  if (p !== null && p >= 99) return "full"
  if (st === "full") return thresholdHigh !== null && thresholdHigh !== undefined && p !== null && p >= thresholdHigh - 1 ? "hold" : "full"
  if (st === "not-charging" || st === "pending-charge" || st === "idle" || st === "hold") return "hold"
  return acOnline ? "charging" : "discharging"
}

function stateLabel(state) {
  if (state === "charging") return "Charging"
  if (state === "discharging") return "On battery"
  if (state === "hold") return "Holding at limit"
  if (state === "full") return "Fully charged"
  return DASH
}

// What the time number means for a state.
function timeLabel(state) {
  if (state === "charging") return "to full"
  if (state === "discharging") return "remaining"
  return ""
}

function timeText(state, seconds) {
  var t = fmtTime(seconds)
  if (t === DASH || timeLabel(state) === "") return ""
  return t + " " + timeLabel(state)
}

// Idle notch badge, for the integrator to render beside the clock:
//   state = { percent: number 0-100, state: "charging"|"discharging"|"hold"|"full" }
//   charging "⚡ 77%", full "✓ 100%", hold "⏸ 80%", discharging "77%",
//   discharging at <=15% "▼ 12%"; "" when there is no reading (hide the badge).
function idleBadge(st) {
  var p = st ? num(st.percent) : null
  if (p === null) return ""
  var r = Math.round(Math.max(0, Math.min(100, p)))
  var s = st.state
  if (s === "charging") return "⚡ " + r + "%"
  if (s === "full") return "✓ " + r + "%"
  if (s === "hold") return "⏸ " + r + "%"
  if (s === "discharging" && r <= 15) return "▼ " + r + "%"
  return r + "%"
}

// Health from energy_full vs energy_full_design (micro-Wh), or the charge_*
// pair (micro-Ah). Returns { percent, fullWh, designWh } with nulls if absent.
function health(f) {
  f = f || {}
  var full = toNum(f.energy_full)
  var design = toNum(f.energy_full_design)
  var wh = true
  if (full === null || design === null || design <= 0) {
    full = toNum(f.charge_full)
    design = toNum(f.charge_full_design)
    wh = false
  }
  if (full === null || design === null || design <= 0) return { percent: null, fullWh: null, designWh: null }
  return {
    percent: Math.round(full / design * 100),
    fullWh: wh ? Math.round(full / 1e4) / 100 : null,
    designWh: wh ? Math.round(design / 1e4) / 100 : null
  }
}

function fmtLimit(low, high) {
  if (high === null || high === undefined) return DASH
  return low !== null && low !== undefined ? low + "–" + high + "%" : high + "%"
}

// Charge limit from sysfs fields (read only), falling back to the status line.
function chargeLimit(f, st) {
  f = f || {}
  var hi = toNum(f.charge_control_end_threshold)
  var lo = toNum(f.charge_control_start_threshold)
  if (hi === null && st) { hi = st.thresholdHigh; lo = st.thresholdLow }
  return { low: lo, high: hi, text: fmtLimit(lo, hi) }
}

// Adapter ceiling in watts from macsmc-ac input_power_limit (micro-W).
function adapterLimitW(f) {
  var v = toNum((f || {}).ac_input_power_limit)
  return v === null || v <= 0 ? null : Math.round(v / 1e6 * 10) / 10
}

function acOnline(f) {
  var v = (f || {}).ac_online
  return v === undefined ? null : String(v).trim() === "1"
}

// ---- history: ~/.local/state/omarchy/battery_history.json from the power
// plugin's helper: [{ time (unix s), cap (0-100), status, w (signed, opt) }]
// Last `hours` hours, at most `maxPoints` (bucket-averaged). Returns
// { cap: [..], watts: [..], count, spanSeconds }.
function historySeries(raw, nowSeconds, hours, maxPoints) {
  var list = []
  try { list = typeof raw === "string" ? JSON.parse(raw) : raw } catch (e) { list = [] }
  if (!Array.isArray(list)) list = []
  var cutoff = nowSeconds - hours * 3600
  var pts = []
  for (var i = 0; i < list.length; i++) {
    var p = list[i]
    if (!p || typeof p !== "object") continue
    var t = num(p.time), c = num(p.cap)
    if (t === null || c === null || t < cutoff || t > nowSeconds + 60) continue
    pts.push({ t: t, c: c, w: num(p.w) })
  }
  pts.sort(function (a, b) { return a.t - b.t })
  var limit = Math.max(2, maxPoints || 120)
  var buckets = pts
  if (pts.length > limit) {
    buckets = []
    var size = pts.length / limit
    for (var b = 0; b < limit; b++) {
      var from = Math.floor(b * size), to = Math.max(from + 1, Math.floor((b + 1) * size))
      var cs = 0, ws = 0, wn = 0, n = 0
      for (var k = from; k < to && k < pts.length; k++) {
        cs += pts[k].c; n++
        if (pts[k].w !== null) { ws += pts[k].w; wn++ }
      }
      buckets.push({ t: pts[from].t, c: cs / n, w: wn ? ws / wn : null })
    }
  }
  var cap = [], watts = []
  for (var j = 0; j < buckets.length; j++) {
    cap.push(buckets[j].c)
    watts.push(buckets[j].w === null ? 0 : buckets[j].w)
  }
  return {
    cap: cap,
    watts: watts,
    count: buckets.length,
    lastTime: pts.length ? pts[pts.length - 1].t : 0,
    spanSeconds: buckets.length > 1 ? buckets[buckets.length - 1].t - buckets[0].t : 0
  }
}

// In-memory 60 s samples (used when the history log is missing or stale).
function addSample(samples, nowSeconds, cap, signedWatts, maxSamples) {
  var next = (samples || []).slice()
  next.push({ time: nowSeconds, cap: cap, w: signedWatts })
  var cap_ = maxSamples || 360
  return next.length > cap_ ? next.slice(next.length - cap_) : next
}

// Signed watts (negative when discharging), matching the history log.
function signedWatts(w) {
  if (!w || w.watts === null) return null
  return w.flow === "out" ? -w.watts : w.watts
}

function fmtSpan(seconds) {
  var s = num(seconds)
  if (s === null || s < 60) return ""
  var h = Math.floor(s / 3600)
  if (h >= 1) return h + "h"
  return Math.round(s / 60) + "m"
}

// ---- profiles (same mechanism as the power plugin)
function parseProfiles(raw) {
  var list = []
  var active = ""
  var lines = String(raw || "").split("\n")
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].trim()
    if (!line) continue
    var parts = line.split("\t")
    list.push(parts[0])
    if (parts[1] === "1") active = parts[0]
  }
  return { profiles: list, active: active }
}

var PROFILE_ORDER = ["power-saver", "balanced", "performance"]

function profileTitle(name) {
  if (name === "power-saver") return "Saver"
  if (name === "balanced") return "Balanced"
  if (name === "performance") return "Performance"
  return String(name || "")
}

function profileIcon(name) {
  if (name === "power-saver") return "\u{F0F2A}"
  if (name === "balanced") return "\u{F02DA}"
  if (name === "performance") return "\u{F04C5}"
  return "\u{F0084}"
}

// Available profiles in saver/balanced/performance order.
function orderedProfiles(profiles) {
  var have = Array.isArray(profiles) ? profiles : []
  var out = []
  for (var i = 0; i < PROFILE_ORDER.length; i++) if (have.indexOf(PROFILE_ORDER[i]) >= 0) out.push(PROFILE_ORDER[i])
  for (var j = 0; j < have.length; j++) if (out.indexOf(have[j]) < 0) out.push(have[j])
  return out
}

// argv for switching profile, no sudo: the Omarchy helper remembers the
// choice per ac/battery key.
function profileSetArgs(name, onBattery) {
  return ["/usr/bin/omarchy-powerprofiles-set", onBattery ? "battery" : "ac", String(name)]
}

var SYSFS_BATTERY = "/sys/class/power_supply/macsmc-battery"
var SYSFS_AC = "/sys/class/power_supply/macsmc-ac"
var SYSFS_FILES = ["power_now", "current_now", "voltage_now", "status", "capacity", "cycle_count",
  "energy_full", "energy_full_design", "charge_full", "charge_full_design",
  "charge_control_end_threshold", "charge_control_start_threshold",
  "time_to_empty_now", "time_to_full_now", "energy_now", "health"]

// argv that dumps every field (and the adapter's online/limit) in one exec;
// "==> path <==" headers let parseSysfsDump attribute each value.
function sysfsArgs() {
  var args = ["/usr/bin/tail", "-n", "+1"]
  for (var i = 0; i < SYSFS_FILES.length; i++) args.push(SYSFS_BATTERY + "/" + SYSFS_FILES[i])
  args.push(SYSFS_AC + "/online", SYSFS_AC + "/input_power_limit")
  return args
}

if (typeof module !== "undefined") {
  module.exports = {
    DASH: DASH, parseStatus: parseStatus, parseDuration: parseDuration, fmtTime: fmtTime,
    parseSysfsDump: parseSysfsDump, wattsFromSysfs: wattsFromSysfs, fmtWatts: fmtWatts,
    chargeState: chargeState, stateLabel: stateLabel, timeLabel: timeLabel, timeText: timeText,
    idleBadge: idleBadge, health: health, fmtLimit: fmtLimit, chargeLimit: chargeLimit,
    adapterLimitW: adapterLimitW, acOnline: acOnline, historySeries: historySeries,
    addSample: addSample, signedWatts: signedWatts, fmtSpan: fmtSpan, parseProfiles: parseProfiles,
    orderedProfiles: orderedProfiles, profileTitle: profileTitle, profileIcon: profileIcon,
    profileSetArgs: profileSetArgs, SYSFS_BATTERY: SYSFS_BATTERY, SYSFS_AC: SYSFS_AC,
    SYSFS_FILES: SYSFS_FILES, sysfsArgs: sysfsArgs
  }
}
