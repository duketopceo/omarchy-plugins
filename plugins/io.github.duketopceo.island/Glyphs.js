// Card controls for each activity: which control a row shows, and the label
// each control draws. ES5, no Qt types; node tests load it with require().
//
// Actions are the strings the root's act(id, action) accepts (KTD11).

function cp(n) {
  n -= 0x10000
  return String.fromCharCode(0xD800 + (n >> 10), 0xDC00 + (n & 0x3FF))
}

// Nerd Font Material Design glyphs (plane 15).
var GLYPHS = {
  stop: cp(0xF04DB),      // nf-md-stop
  play: cp(0xF040A),      // nf-md-play
  pause: cp(0xF03E4),     // nf-md-pause
  next: cp(0xF04AD),      // nf-md-skip_next
  previous: cp(0xF04AE),  // nf-md-skip_previous
  cancel: cp(0xF0156),    // nf-md-close
  music: cp(0xF075A),     // nf-md-music
  // Pages: ring and chip icons, the launcher grid, the profile control.
  battery: cp(0xF0079),   // nf-md-battery
  charging: cp(0xF0084),  // nf-md-battery_charging
  bolt: cp(0xF0241),      // nf-md-flash
  cpu: cp(0xF061A),       // nf-md-chip
  memory: cp(0xF035B),    // nf-md-memory
  wifi: cp(0xF05A9),      // nf-md-wifi
  ethernet: cp(0xF0200),  // nf-md-ethernet
  vpn: cp(0xF0582),       // nf-md-vpn
  fan: cp(0xF0210),       // nf-md-fan
  message: cp(0xF0369),   // nf-md-message_text
  clock: cp(0xF0150),     // nf-md-clock_outline
  camera: cp(0xF0100),    // nf-md-camera
  settings: cp(0xF0493),  // nf-md-cog
  check: cp(0xF012C),     // nf-md-check
  person: cp(0xF0009),    // nf-md-account_circle
  leaf: cp(0xF032A),      // nf-md-leaf
  balance: cp(0xF05D1),   // nf-md-scale_balance
  speed: cp(0xF04C5),     // nf-md-speedometer
  open: cp(0xF03CC),      // nf-md-open_in_new
  // Omacontrol shortcuts.
  bluetooth: cp(0xF00AF), // nf-md-bluetooth
  sound: cp(0xF057E),     // nf-md-volume_high
  display: cp(0xF0379),   // nf-md-monitor
  power: cp(0xF0425),     // nf-md-power
  keyboard: cp(0xF030C),  // nf-md-keyboard
  theme: cp(0xF03D8),     // nf-md-palette
  tune: cp(0xF062E)       // nf-md-tune
}

// The icon a page shows in the More launcher.
var PAGE_GLYPH = { messages: "message", dayflow: "clock", shots: "camera", settings: "settings", omacontrol: "tune" }
// A glyph by name; the open-in-new glyph for an unknown name.
function glyph(name) { return GLYPHS[name] || GLYPHS.open }
function pageGlyph(id) { return GLYPHS[PAGE_GLYPH[id]] || GLYPHS.open }

// The icon of a power profile segment.
var PROFILE_GLYPH = { "power-saver": "leaf", balanced: "balance", performance: "speed" }
function profileGlyph(name) { return GLYPHS[PROFILE_GLYPH[name]] || GLYPHS.balance }

// The one control a card row shows for an activity, or "" for none.
function primaryControl(a) {
  if (!a || a.active !== true) return ""
  if (a.id === "dictation") return a.state === "recording" ? "stop" : ""
  if (a.id === "screenrec") return a.state === "recording" ? "stop" : ""
  if (a.id === "media") return a.canTogglePlaying ? "toggle" : ""
  if (a.id === "timer") {
    if (a.state === "running") return "pause"
    if (a.state === "paused") return "resume"
    return ""
  }
  if (a.id === "calendar") return typeof a.url === "string" && a.url !== "" ? "join" : ""
  return ""
}

// Every control a Home row shows: the primary one, plus the timer's +1 min
// and cancel (the full set it had on the 0.3 Now page).
function rowControls(a) {
  var first = primaryControl(a)
  if (a && a.id === "timer" && first !== "") return [first, "add", "cancel"]
  return first !== "" ? [first] : []
}

// Label for a control button; media's toggle shows what a press will do.
function controlLabel(action, a) {
  switch (action) {
    case "stop": return GLYPHS.stop
    case "toggle": return a && a.playing ? GLYPHS.pause : GLYPHS.play
    case "pause": return GLYPHS.pause
    case "resume": return GLYPHS.play
    case "next": return GLYPHS.next
    case "previous": return GLYPHS.previous
    case "cancel": return GLYPHS.cancel
    case "add": return "+1 min"
    case "join": return "Join"
    default: return ""
  }
}

// The hint a control shows on hover: what a press will do.
function controlHint(action, a) {
  switch (action) {
    case "stop":
      return a && a.id === "screenrec" ? "Stop recording" : (a && a.id === "dictation" ? "Stop dictation" : "Stop")
    case "toggle": return a && a.playing ? "Pause" : "Play"
    case "pause": return "Pause timer"
    case "resume": return "Resume timer"
    case "next": return "Next track"
    case "previous": return "Previous track"
    case "cancel": return "Cancel timer"
    case "add": return "Add one minute"
    case "join": return "Join meeting"
    default: return ""
  }
}

if (typeof module !== "undefined") module.exports = {
  GLYPHS: GLYPHS, primaryControl: primaryControl, rowControls: rowControls, controlLabel: controlLabel,
  controlHint: controlHint, pageGlyph: pageGlyph, glyph: glyph, profileGlyph: profileGlyph
}
