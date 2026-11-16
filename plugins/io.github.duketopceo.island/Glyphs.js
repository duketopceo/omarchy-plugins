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
  music: cp(0xF075A)      // nf-md-music
}

// The one control a card row shows for an activity, or "" for none.
function primaryControl(a) {
  if (!a || a.active !== true) return ""
  if (a.id === "dictation") return a.state === "recording" ? "stop" : ""
  if (a.id === "media") return a.canTogglePlaying ? "toggle" : ""
  if (a.id === "timer") {
    if (a.state === "running") return "pause"
    if (a.state === "paused") return "resume"
    return ""
  }
  return ""
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
    default: return ""
  }
}

if (typeof module !== "undefined") module.exports = {
  GLYPHS: GLYPHS, primaryControl: primaryControl, controlLabel: controlLabel
}
