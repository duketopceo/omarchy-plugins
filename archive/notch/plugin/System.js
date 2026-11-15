// Pure logic for the System tab (Apple Silicon / Asahi first, tolerant of
// other machines). No Qt types, so tests run it with node.
//
// Data paths and the hwmon / fan-helper conventions are taken from Luke's own
// plugins: lukedaduke.fan (macsmc_hwmon fan RPM + targets, the omarchy-fan
// helper's /run/omarchy-fan/status.json and omarchy-fan-set modes,
// /proc/stat per-core deltas, /proc/meminfo) and its system_monitor_stats.py
// label handling. Functions below are ports of that logic to JS.

var HISTORY = 30            // samples kept per sparkline: 30 x 2 s = 60 s
var SAMPLE_MS = 2000

function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v }
function num(v) { var n = Number(v); return isFinite(n) ? n : 0 }

// ----------------------------------------------------------------- CPU
// /proc/stat -> { all: [idle, total], cores: { "0": [idle, total], ... } }
function parseCpuStat(text) {
  var out = { all: null, cores: {} }
  var lines = String(text || "").split("\n")
  for (var i = 0; i < lines.length; i++) {
    var m = /^(cpu\d*)\s+(.*)$/.exec(lines[i])
    if (!m) continue
    var f = m[2].trim().split(/\s+/).map(Number)
    if (f.length < 4 || f.some(function (x) { return !isFinite(x) })) continue
    var idle = f[3] + (f[4] || 0)                       // idle + iowait
    var total = 0
    for (var k = 0; k < Math.min(f.length, 8); k++) total += f[k]   // user..steal
    if (m[1] === "cpu") out.all = [idle, total]
    else out.cores[m[1].slice(3)] = [idle, total]
  }
  return out
}

// Percent busy between two parseCpuStat results for a set of cpu ids (all if
// `ids` is null). Null when there is nothing to compare.
function cpuUsage(prev, cur, ids) {
  if (!prev || !cur) return null
  var list = ids
  if (!list) {
    var a = prev.all, b = cur.all
    if (!a || !b) return null
    var dt = b[1] - a[1]
    return dt > 0 ? clamp(Math.round(100 * (1 - (b[0] - a[0]) / dt)), 0, 100) : null
  }
  var idle = 0, total = 0, seen = 0
  for (var i = 0; i < list.length; i++) {
    var p = prev.cores[String(list[i])], c = cur.cores[String(list[i])]
    if (!p || !c) continue
    idle += c[0] - p[0]
    total += c[1] - p[1]
    seen++
  }
  return seen > 0 && total > 0 ? clamp(Math.round(100 * (1 - idle / total)), 0, 100) : null
}

// "0-1", "2-5", "0 1 2" -> [0, 1, ...]
function parseCpuList(text) {
  var out = []
  String(text || "").trim().split(/[\s,]+/).forEach(function (tok) {
    var m = /^(\d+)(?:-(\d+))?$/.exec(tok)
    if (!m) return
    var a = Number(m[1]), b = m[2] === undefined ? a : Number(m[2])
    for (var i = a; i <= b && out.length < 512; i++) out.push(i)
  })
  return out
}

// cpufreq policies -> clusters. `policies` = [{ cpus: "0-1", khz: "2064000" }].
// The lowest-numbered policy is the efficiency cluster on Apple Silicon; the
// rest are performance clusters, merged into one "P" entry.
function buildClusters(policies) {
  var list = (policies || []).map(function (p) { return { cpus: parseCpuList(p.cpus), khz: num(p.khz) } })
    .filter(function (p) { return p.cpus.length > 0 })
    .sort(function (a, b) { return a.cpus[0] - b.cpus[0] })
  if (list.length === 0) return { e: null, p: null }
  if (list.length === 1) return { e: null, p: list[0] }
  var perf = list.slice(1)
  var cpus = []
  var khz = 0
  perf.forEach(function (p) { cpus = cpus.concat(p.cpus); khz += p.khz })
  return { e: list[0], p: { cpus: cpus, khz: Math.round(khz / perf.length) } }
}

// `grep -H .` over cpufreq policy dirs -> [{ cpus: "0-1", khz: "2064000" }]
function parsePolicies(text) {
  var by = {}
  String(text || "").split("\n").forEach(function (line) {
    var m = /^\/sys\/devices\/system\/cpu\/cpufreq\/policy(\d+)\/(related_cpus|scaling_cur_freq):(.*)$/.exec(line)
    if (!m) return
    if (!by[m[1]]) by[m[1]] = {}
    by[m[1]][m[2] === "related_cpus" ? "cpus" : "khz"] = m[3].trim()
  })
  return Object.keys(by).map(function (k) { return by[k] }).filter(function (p) { return p.cpus })
}

function fmtGHz(khz) {
  var k = num(khz)
  if (k <= 0) return "--"
  return (k / 1000000).toFixed(2) + " GHz"
}

// ----------------------------------------------------------------- RAM
function parseMeminfo(text) {
  var kb = {}
  String(text || "").split("\n").forEach(function (line) {
    var m = /^(\w+):\s+(\d+)/.exec(line)
    if (m) kb[m[1]] = Number(m[2])
  })
  var total = kb.MemTotal || 0
  var avail = kb.MemAvailable !== undefined ? kb.MemAvailable : (kb.MemFree || 0) + (kb.Buffers || 0) + (kb.Cached || 0)
  var used = Math.max(0, total - avail)
  var swapTotal = kb.SwapTotal || 0
  var swapUsed = Math.max(0, swapTotal - (kb.SwapFree || 0))
  return {
    ok: total > 0,
    totalKb: total, usedKb: used, availKb: avail,
    pct: total > 0 ? clamp(Math.round(100 * used / total), 0, 100) : 0,
    swapTotalKb: swapTotal, swapUsedKb: swapUsed,
    swapPct: swapTotal > 0 ? clamp(Math.round(100 * swapUsed / swapTotal), 0, 100) : 0
  }
}

function fmtGiB(kb) {
  var g = num(kb) / 1048576
  return (g >= 10 ? g.toFixed(0) : g.toFixed(1)) + " GB"
}

// ------------------------------------------------------ hwmon / temps / fans
// The collector prints `grep -H . <hwmon files>`, so every line is
// `/sys/class/hwmon/hwmonN/<file>:<value>`. Group by hwmon dir and keep the
// one named macsmc_hwmon (Apple SMC) or, failing that, any with temps/fans.
function groupHwmon(text) {
  var dirs = {}
  String(text || "").split("\n").forEach(function (line) {
    var m = /^\/sys\/class\/hwmon\/(hwmon\d+)\/([A-Za-z0-9_]+):(.*)$/.exec(line)
    if (!m) return
    if (!dirs[m[1]]) dirs[m[1]] = {}
    dirs[m[1]][m[2]] = m[3].trim()
  })
  return dirs
}

// Short, useful names for SMC / generic sensor labels. Order matters.
var TEMP_RULES = [
  [/\b(cpu|core|package|tdie|tctl)\b/i, "CPU"],
  [/\b(gpu)\b/i, "GPU"],
  [/\b(soc|die)\b/i, "SoC"],
  [/battery/i, "Battery"],
  [/ambient|airflow|inlet/i, "Ambient"],
  [/nand|nvme|ssd|flash/i, "SSD"],
  [/wifi|wi-fi|bt\b|wlan/i, "WiFi"],
  [/charge|regulator|vrm/i, "Charger"],
  [/palm|skin|case/i, "Case"]
]

function tempName(label) {
  var s = String(label || "")
  for (var i = 0; i < TEMP_RULES.length; i++) if (TEMP_RULES[i][0].test(s)) return TEMP_RULES[i][1]
  return s.replace(/\s*temp(erature)?\b/i, "").trim().slice(0, 10) || "Temp"
}

function powerName(label) {
  var s = String(label || "")
  if (/total system/i.test(s)) return "System"
  if (/heatpipe/i.test(s)) return "Heatpipe"
  if (/ac input/i.test(s)) return "AC in"
  if (/rail/i.test(s)) return "3.8 V rail"
  return s.slice(0, 12)
}

function parseHwmon(text) {
  var dirs = groupHwmon(text)
  var pick = null
  Object.keys(dirs).forEach(function (d) {
    if (dirs[d].name === "macsmc_hwmon") pick = d
  })
  if (!pick) {
    Object.keys(dirs).forEach(function (d) {
      if (pick) return
      var keys = Object.keys(dirs[d])
      if (keys.some(function (k) { return /^(temp|fan)\d+_input$/.test(k) })) pick = d
    })
  }
  var out = { ok: false, name: "", temps: [], fans: [], powers: [], hottest: null }
  if (!pick) return out
  var h = dirs[pick]
  out.ok = true
  out.name = h.name || pick
  for (var i = 1; i <= 16; i++) {
    var t = h["temp" + i + "_input"]
    if (t !== undefined && isFinite(Number(t))) {
      var c = Number(t) / 1000
      if (c > -40 && c < 150) out.temps.push({ id: "temp" + i, label: h["temp" + i + "_label"] || ("temp" + i), name: tempName(h["temp" + i + "_label"]), c: Math.round(c * 10) / 10 })
    }
    var f = h["fan" + i + "_input"]
    if (f !== undefined && isFinite(Number(f))) {
      out.fans.push({
        id: "fan" + i, label: h["fan" + i + "_label"] || ("Fan " + i),
        rpm: Math.round(Number(f)),
        target: h["fan" + i + "_target"] !== undefined ? Math.round(num(h["fan" + i + "_target"])) : null,
        min: h["fan" + i + "_min"] !== undefined ? Math.round(num(h["fan" + i + "_min"])) : 0,
        max: h["fan" + i + "_max"] !== undefined ? Math.round(num(h["fan" + i + "_max"])) : 0
      })
    }
    var p = h["power" + i + "_input"]
    if (p !== undefined && isFinite(Number(p)))
      out.powers.push({ id: "power" + i, label: h["power" + i + "_label"] || ("power" + i), name: powerName(h["power" + i + "_label"]), w: Math.round(Number(p) / 1000) / 1000 })
  }
  out.temps.forEach(function (t) { if (!out.hottest || t.c > out.hottest.c) out.hottest = t })
  return out
}

// Fan fill 0..1 against its max (falls back to 8000 rpm when max is unknown).
function fanFraction(fan) {
  if (!fan) return 0
  var max = fan.max > 0 ? fan.max : 8000
  return clamp(fan.rpm / max, 0, 1)
}

function fmtRpm(r) { return r > 0 ? String(Math.round(r)) : "0" }

function totalPower(powers) {
  var list = powers || []
  for (var i = 0; i < list.length; i++) if (list[i].name === "System") return list[i].w
  return null
}

// /run/omarchy-fan/status.json (written by omarchy-fan-helper):
//   { controllable, hw, mode, version }
function parseFanHelper(text) {
  var out = { present: false, controllable: false, mode: "", version: "" }
  var d = null
  try { d = JSON.parse(String(text || "")) } catch (e) { d = null }
  if (!d || typeof d !== "object") return out
  out.present = true
  out.controllable = d.controllable === true
  out.mode = typeof d.mode === "string" ? d.mode.trim().slice(0, 24) : ""
  out.version = typeof d.version === "string" ? d.version.slice(0, 24) : ""
  return out
}

// UI mode labels -> the argument omarchy-fan-set (the fan plugin's writer)
// accepts. Same path the fan plugin takes; the root daemon does the work.
var FAN_MODES = [
  { id: "auto", title: "Auto" },
  { id: "low", title: "Quiet" },
  { id: "med", title: "Med" },
  { id: "high", title: "Max" }
]

function fanModeArg(id) {
  for (var i = 0; i < FAN_MODES.length; i++) if (FAN_MODES[i].id === id) return id
  return null
}

function fanModeTitle(id) {
  for (var i = 0; i < FAN_MODES.length; i++) if (FAN_MODES[i].id === id) return FAN_MODES[i].title
  return id || "Auto"
}

// GPU kind from hwmon name dump + optional DRM vendor ids. Utilization is
// not wired for any vendor here (Asahi AGX has no userspace counter).
function detectGpu(hwmonText, drmVendorText) {
  var blob = (String(hwmonText || "") + " " + String(drmVendorText || "")).toLowerCase()
  if (/macsmc|asahi|agx/.test(blob)) return { kind: "asahi-agx", label: "Asahi AGX", util: false, note: "no util counter" }
  if (/nvidia|10de/.test(blob)) return { kind: "nvidia", label: "NVIDIA", util: false, note: "util not wired" }
  if (/amdgpu|radeon|1002/.test(blob)) return { kind: "amd", label: "AMD", util: false, note: "util not wired" }
  if (/i915|\bxe\b|8086/.test(blob)) return { kind: "intel", label: "Intel", util: false, note: "util not wired" }
  return { kind: "none", label: "GPU", util: false, note: "n/a" }
}

function detectNpu(aneStatsText, accelPresent) {
  if (aneStatsText && parseAneStats(aneStatsText).ok) return { kind: "ane", label: "ANE", present: true }
  if (accelPresent) return { kind: "accel", label: "NPU", present: true }
  return { kind: "none", label: "NPU", present: false }
}

// ----------------------------------------------------------------- Neural Engine
// /sys/class/accel/accel0/device/ane_stats: "busy_ns N\njobs N\n<pmp state>"
function parseAneStats(text) {
  var out = { ok: false, busyNs: 0, jobs: 0, pmp: "" }
  String(text || "").split("\n").forEach(function (line) {
    var m = /^busy_ns\s+(\d+)/.exec(line)
    if (m) { out.busyNs = Number(m[1]); out.ok = true }
    m = /^jobs\s+(\d+)/.exec(line)
    if (m) out.jobs = Number(m[1])
    if (/^pmp/.test(line)) out.pmp = line.trim()
  })
  return out
}

// Percent busy between two parseAneStats results taken dtMs apart.
function aneUtil(prev, cur, dtMs) {
  if (!prev || !cur || !prev.ok || !cur.ok || !(dtMs > 0)) return null
  var d = cur.busyNs - prev.busyNs
  if (d < 0) return null
  return clamp(Math.round(100 * d / (dtMs * 1e6)), 0, 100)
}

// `omarchy-ane-check` output -> { ready, version, bound, note }.
function parseAneCheck(text) {
  var s = String(text || "")
  var out = { ready: false, version: "", bound: false, device: false, state: "unknown" }
  if (!s.trim()) return out
  var v = /ane is loaded \(version ([^)]+)\)/.exec(s)
  if (v) out.version = v[1].trim()
  out.bound = /ane is bound to/.test(s)
  out.device = /\/dev\/accel\/accel0 present/.test(s)
  out.ready = /omarchy-ane-check:\s*ready\s*$/m.test(s)
  out.state = out.ready ? "ready" : (/\bFAIL\b|\bfail\b|not loaded|missing/.test(s) ? "not ready" : "unknown")
  return out
}

// `fuser /dev/accel/accel0` prints pids on stdout (own uid without root).
function parseFuserPids(text) {
  var out = []
  String(text || "").split(/\s+/).forEach(function (t) {
    var m = /^(\d+)[a-z]*$/.exec(t)
    if (m) out.push(Number(m[1]))
  })
  return out
}

// ----------------------------------------------------------------- MLX
// `pgrep -af` lines -> running MLX model servers.
function parseMlxProcs(text) {
  var out = []
  String(text || "").split("\n").forEach(function (line) {
    var m = /^(\d+)\s+(.*)$/.exec(line.trim())
    if (!m) return
    var cmd = m[2]
    if (/pgrep|\bsh -c\b|bash -c/.test(cmd)) return
    if (!/(_mlxlm_server|mlx_lm\.server|omlx\.server|mlx_omarchy_[a-z0-9]+\.server)/.test(cmd)) return
    var model = /--model\s+(\S+)/.exec(cmd)
    var port = /--port\s+(\d+)/.exec(cmd)
    var name = model ? model[1].replace(/\/+$/, "").split("/").slice(-2).join("/") : ""
    out.push({ pid: Number(m[1]), model: name.slice(0, 48), port: port ? Number(port[1]) : 8080 })
  })
  return out
}

// ~/.local/share/mlx-omarchy/reservations.json -> { count, bytes, gib, notes }
function parseReservations(text) {
  var out = { count: 0, bytes: 0, gib: 0, notes: [] }
  var d = null
  try { d = JSON.parse(String(text || "")) } catch (e) { d = null }
  if (!d || typeof d !== "object") return out
  Object.keys(d).forEach(function (k) {
    var r = d[k]
    if (!r || typeof r !== "object" || !(Number(r.bytes) > 0)) return
    out.count++
    out.bytes += Number(r.bytes)
    if (typeof r.note === "string") out.notes.push(r.note.slice(0, 60))
  })
  out.gib = Math.round(out.bytes / 1073741824 * 10) / 10
  return out
}

// Output of the slow scan script: "==ane" pids, "==comm" "pid name" lines,
// "==ss" `ss -ltnp` lines, then "==mlx" pgrep lines.
function parseScan(text) {
  var sec = { ane: "", comm: "", ss: "", mlx: "" }, cur = ""
  String(text || "").split("\n").forEach(function (line) {
    var m = /^==(ane|comm|ss|mlx)\s*$/.exec(line)
    if (m) { cur = m[1]; return }
    if (cur) sec[cur] += line + "\n"
  })
  var mlx = parseMlxProcs(sec.mlx)
  var ports = mlxListenPorts(sec.ss, mlx.map(function (p) { return p.pid }))
  return { anePids: parseFuserPids(sec.ane), aneProcs: parseAneProcs(sec.comm), mlx: mlx, mlxPorts: ports }
}

// "pid name" lines (from /proc/PID/comm) -> deduped process names, in order.
function parseAneProcs(text) {
  var seen = {}, out = []
  String(text || "").split("\n").forEach(function (line) {
    var m = /^(\d+)\s+(.+)$/.exec(line.trim())
    if (!m) return
    var name = m[2].trim().slice(0, 24)
    if (!name || seen[name]) return
    seen[name] = true
    out.push(name)
  })
  return out
}

// `ss -ltnp` -> sorted unique localhost ports whose listener pid is in pids.
// Only loopback / wildcard listeners count; anything else is never queried.
function mlxListenPorts(text, pids) {
  var want = {}, seen = {}, out = []
  ;(pids || []).forEach(function (p) { want[p] = true })
  String(text || "").split("\n").forEach(function (line) {
    var a = /^LISTEN\s+\d+\s+\d+\s+(\S+):(\d+)\s/.exec(line.trim())
    if (!a) return
    if (!/^(127\.0\.0\.1|0\.0\.0\.0|\*|\[::1\]|\[::\])$/.test(a[1])) return
    var re = /pid=(\d+)/g, m, hit = false
    while ((m = re.exec(line))) if (want[Number(m[1])]) hit = true
    var port = Number(a[2])
    if (hit && port > 0 && port < 65536 && !seen[port]) { seen[port] = true; out.push(port) }
  })
  return out.sort(function (x, y) { return x - y }).slice(0, 4)
}

// Shell command that asks each (validated numeric) localhost port for /v1/models.
function modelsCommand(ports) {
  var ps = (ports || []).map(Number).filter(function (p) { return p > 0 && p < 65536 && Math.floor(p) === p })
  if (!ps.length) return ""
  return ps.map(function (p) {
    return "echo '==port " + p + "'; /usr/bin/curl -s -m 1 http://127.0.0.1:" + p + "/v1/models 2>/dev/null; echo"
  }).join("; ")
}

// Output of modelsCommand -> sorted unique model ids (max 6).
function parseModelIds(text) {
  var seen = {}, out = []
  String(text || "").split(/^==port \d+\s*$/m).forEach(function (chunk) {
    var d = null
    try { d = JSON.parse(chunk.trim()) } catch (e) { d = null }
    if (!d || !Array.isArray(d.data)) return
    d.data.forEach(function (m) {
      if (!m || typeof m.id !== "string" || !m.id) return
      var id = m.id.replace(/\/+$/, "").split("/").slice(-2).join("/").slice(0, 48)
      if (!seen[id]) { seen[id] = true; out.push(id) }
    })
  })
  return out.slice(0, 6)
}

// ANE runtime PM: "active" -> Active, "suspended" -> Asleep.
function aneState(text) {
  var t = String(text || "").trim()
  if (t === "active") return "Active"
  if (t === "suspended") return "Asleep"
  return t ? t.slice(0, 12) : "unknown"
}

// Sliding window of {t, jobs} samples (last windowMs), oldest first.
function pushJobs(buf, t, jobs, windowMs) {
  var w = windowMs > 0 ? windowMs : 60000
  var out = (Array.isArray(buf) ? buf : []).filter(function (s) { return t - s.t <= w })
  out.push({ t: t, jobs: jobs })
  return out
}

// Jobs per minute across the window; null when not computable.
function jobsPerMin(buf) {
  var b = Array.isArray(buf) ? buf : []
  if (b.length < 2) return null
  var a = b[0], z = b[b.length - 1]
  var dt = z.t - a.t, dj = z.jobs - a.jobs
  if (!(dt > 0) || dj < 0) return null
  return Math.round(dj * 60000 / dt * 10) / 10
}

// Timestamp of the last time jobs increased (carried forward otherwise).
function aneLastUsed(prevJobs, curJobs, nowMs, prevLast) {
  if (prevJobs !== null && prevJobs !== undefined && curJobs > prevJobs) return nowMs
  return prevLast || 0
}

// "12s ago" / "4m ago" / "2h ago" / "never".
function fmtAgo(ms, nowMs) {
  if (!(ms > 0)) return "never"
  var s = Math.max(0, Math.round((nowMs - ms) / 1000))
  if (s < 60) return s + "s ago"
  if (s < 3600) return Math.floor(s / 60) + "m ago"
  if (s < 86400) return Math.floor(s / 3600) + "h ago"
  return Math.floor(s / 86400) + "d ago"
}

var MLX_COMMAND = "mlx-omarchy-serve recommend"

// ----------------------------------------------------------------- sparkline buffer
// Fixed-size ring of the latest samples (oldest first). Null samples
// ("no reading") are kept as gaps so the line stays time-aligned.
function pushSample(buf, value, max) {
  var cap = max > 0 ? max : HISTORY
  var out = (Array.isArray(buf) ? buf : []).slice(-(cap - 1))
  out.push(value === null || value === undefined || !isFinite(Number(value)) ? null : Number(value))
  return out
}

function lastValue(buf) {
  var b = Array.isArray(buf) ? buf : []
  for (var i = b.length - 1; i >= 0; i--) if (b[i] !== null) return b[i]
  return null
}

function hasData(buf) {
  return (Array.isArray(buf) ? buf : []).some(function (v) { return v !== null })
}

if (typeof module !== "undefined") {
  module.exports = {
    HISTORY: HISTORY, SAMPLE_MS: SAMPLE_MS, FAN_MODES: FAN_MODES, MLX_COMMAND: MLX_COMMAND,
    parseCpuStat: parseCpuStat, cpuUsage: cpuUsage, parseCpuList: parseCpuList, parsePolicies: parsePolicies, parseScan: parseScan, buildClusters: buildClusters, fmtGHz: fmtGHz,
    parseMeminfo: parseMeminfo, fmtGiB: fmtGiB,
    groupHwmon: groupHwmon, tempName: tempName, powerName: powerName, parseHwmon: parseHwmon,
    fanFraction: fanFraction, fmtRpm: fmtRpm, totalPower: totalPower,
    parseFanHelper: parseFanHelper, fanModeArg: fanModeArg, fanModeTitle: fanModeTitle,
    detectGpu: detectGpu, detectNpu: detectNpu,
    parseAneStats: parseAneStats, aneUtil: aneUtil, parseAneCheck: parseAneCheck, parseFuserPids: parseFuserPids,
    parseMlxProcs: parseMlxProcs, parseAneProcs: parseAneProcs, mlxListenPorts: mlxListenPorts,
    modelsCommand: modelsCommand, parseModelIds: parseModelIds, aneState: aneState, pushJobs: pushJobs,
    jobsPerMin: jobsPerMin, aneLastUsed: aneLastUsed, fmtAgo: fmtAgo, parseReservations: parseReservations,
    pushSample: pushSample, lastValue: lastValue, hasData: hasData
  }
}
