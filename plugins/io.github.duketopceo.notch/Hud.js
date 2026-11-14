// Pure logic for the volume / brightness HUD (R6). No Qt types.
//
// The HUD is an ordinary ear activity: HudActivity reads PipeWire's default
// sink (wpctl) and the internal backlight (brightnessctl), feeds each reading
// to step(), and shows a few seconds of "Volume 83%" / "Muted" / "Brightness
// 30%" plus a small meter when a value CHANGED. The first reading is only a
// baseline, so starting the shell never flashes a HUD.
//
// Who owns the popup is a setting (KTD4): "omarchy" (default, Omarchy's own
// OSD) or "notch". Only "notch" ever shows anything here, so nothing doubles.

var HUD_MS = 1600          // how long a change stays in the ear
var HUD_PRIORITY = 95      // above dictation (90): you just pressed a key
var OWNERS = ["omarchy", "notch"]

// One shell script, two tagged lines, so a single Process reads both.
// brightnessctl is asked for backlight-class devices only (the internal
// panel); with none, or no brightnessctl, the B line is simply absent.
function probeArgs() {
  var script =
    'PATH="$HOME/.local/bin:$PATH";' +
    'v=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null) && printf "V %s\\n" "$v";' +
    'b=$(brightnessctl -m -c backlight 2>/dev/null | head -n1) && [ -n "$b" ] && printf "B %s\\n" "$b";' +
    'exit 0'
  return ["sh", "-c", script]
}

// "Volume: 0.83" / "Volume: 0.00 [MUTED]" -> { volume: 0..150, muted } or null.
function parseVolume(text) {
  var m = /Volume:\s*([0-9]*\.?[0-9]+)(\s*\[MUTED\])?/.exec(String(text || ""))
  if (!m) return null
  var v = Math.round(Number(m[1]) * 100)
  if (!isFinite(v)) return null
  return { volume: Math.max(0, Math.min(150, v)), muted: !!m[2] }
}

// brightnessctl -m: "device,class,value,percent%,max" -> { percent, device } or null.
function parseBrightness(text) {
  var parts = String(text || "").trim().split(",")
  if (parts.length < 5 || parts[1] !== "backlight") return null
  var p = parseInt(String(parts[3]).replace("%", ""), 10)
  if (!isFinite(p)) return null
  return { percent: Math.max(0, Math.min(100, p)), device: parts[0] }
}

// The probe script's output -> { volume: {...}|null, brightness: {...}|null }.
function parseProbe(text) {
  var out = { volume: null, brightness: null }
  String(text || "").split("\n").forEach(function (line) {
    if (line.indexOf("V ") === 0) out.volume = parseVolume(line.slice(2))
    else if (line.indexOf("B ") === 0) out.brightness = parseBrightness(line.slice(2))
  })
  return out
}

function owner(settings) {
  var o = settings && settings.hudOwner
  return OWNERS.indexOf(o) >= 0 ? o : "omarchy"
}

function initial() {
  return { seen: false, volume: null, brightness: null, kind: "", text: "", level: 0, muted: false, until: 0 }
}

// Fold one reading into the model. Returns the same object when nothing
// changed, so callers can skip work.
function step(model, reading, now) {
  var m = model || initial()
  var r = reading || { volume: null, brightness: null }
  if (!m.seen) {
    return { seen: true, volume: r.volume, brightness: r.brightness, kind: "", text: "", level: 0, muted: false, until: 0 }
  }
  var next = null
  var v = r.volume, pv = m.volume
  if (v && pv && (v.volume !== pv.volume || v.muted !== pv.muted)) {
    next = { kind: "volume", text: v.muted ? "Muted" : "Volume " + v.volume + "%", level: v.muted ? 0 : Math.min(100, v.volume), muted: v.muted }
  }
  var b = r.brightness, pb = m.brightness
  if (!next && b && pb && b.percent !== pb.percent) {
    next = { kind: "brightness", text: "Brightness " + b.percent + "%", level: b.percent, muted: false }
  }
  var same = (!!v === !!pv) && (!v || (v.volume === pv.volume && v.muted === pv.muted)) &&
             (!!b === !!pb) && (!b || b.percent === pb.percent)
  if (!next && same) return m
  var out = { seen: true, volume: v || pv, brightness: b || pb, kind: m.kind, text: m.text, level: m.level, muted: m.muted, until: m.until }
  if (next) { out.kind = next.kind; out.text = next.text; out.level = next.level; out.muted = next.muted; out.until = now + HUD_MS }
  return out
}

function active(model, now, ownerName) {
  return ownerName === "notch" && !!model && model.until > now && model.text !== ""
}

if (typeof module !== "undefined") {
  module.exports = { HUD_MS: HUD_MS, HUD_PRIORITY: HUD_PRIORITY, OWNERS: OWNERS, probeArgs: probeArgs, parseVolume: parseVolume,
    parseBrightness: parseBrightness, parseProbe: parseProbe, owner: owner, initial: initial, step: step, active: active }
}
