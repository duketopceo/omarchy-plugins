// Pure next-calendar-event logic for the Island. ES5, no Qt types; node tests
// load it with require().
//
// Input: the events bin/island-calendar prints ({ title, start, end, url },
// epoch ms, timed events only). activity() picks the next event that has not
// ended and builds the Island activity:
//   - starts within 10 minutes: ear countdown "in 8m"
//   - started less than 10 minutes ago (and not ended): ear "now"
//   - otherwise: a card-only row, "Title · 09:30"
// `url` is kept only for an https Zoom, Google Meet or Microsoft Teams link;
// the helper already filters, and this repeats the check because the root
// opens it with xdg-open.

var PRIORITY = 40
var SOON_MS = 10 * 60 * 1000
var MAX_TITLE = 80
// Keep both lists in step with MEETING_HOSTS / SUFFIX_HOSTS in
// bin/island-calendar. SUFFIX_HOSTS also allow subdomains (us02web.zoom.us).
var HOSTS = ["meet.google.com", "teams.microsoft.com", "teams.live.com", "zoom.us"]
var SUFFIX_HOSTS = ["zoom.us"]

function _cp(code) {
  var c = code - 0x10000
  return String.fromCharCode(0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF))
}
var GLYPHS = {
  calendar: _cp(0xF00ED)  // nf-md-calendar
}

// The URL when it is an allowlisted https meeting link, else "".
function meetingUrl(url) {
  if (typeof url !== "string") return ""
  var m = /^https:\/\/([^\/?#]+)(?:[\/?#]|$)/i.exec(url)
  // The authority must be a plain hostname (and optional port): no userinfo,
  // no backslash (browsers read "a\.zoom.us" as host "a"), no escapes.
  if (!m || /[\s\\]/.test(url)) return ""
  var authority = m[1].toLowerCase()
  if (!/^[a-z0-9.-]+(:[0-9]+)?$/.test(authority)) return ""
  var host = authority.replace(/:\d+$/, "")
  for (var i = 0; i < HOSTS.length; i++) if (host === HOSTS[i]) return url
  for (var j = 0; j < SUFFIX_HOSTS.length; j++) {
    var s = "." + SUFFIX_HOSTS[j]
    if (host.length > s.length && host.slice(host.length - s.length) === s) return url
  }
  return ""
}

function _pad(n) {
  return n < 10 ? "0" + n : String(n)
}

// Local HH:MM for an epoch-ms time.
function clock(ms) {
  var d = new Date(ms)
  return _pad(d.getHours()) + ":" + _pad(d.getMinutes())
}

function _title(t) {
  var s = String(t === undefined || t === null ? "" : t).replace(/\s+/g, " ").trim()
  if (s === "") s = "Event"
  return s.length > MAX_TITLE ? s.slice(0, MAX_TITLE - 1) + "…" : s
}

// The event to show: the earliest one that starts in the future or started
// less than 10 minutes ago, so a long block already under way never hides
// the next meeting. Only when there is none, the earliest event still under
// way. null when nothing has an end after `now`.
function next(events, now) {
  if (!Array.isArray(events)) return null
  var fresh = null
  var running = null
  for (var i = 0; i < events.length; i++) {
    var e = events[i]
    if (!e || typeof e.start !== "number" || typeof e.end !== "number") continue
    if (!(e.end > now)) continue
    if (now - e.start < SOON_MS) {
      if (fresh === null || e.start < fresh.start) fresh = e
    } else if (running === null || e.start < running.start) {
      running = e
    }
  }
  return fresh !== null ? fresh : running
}

function activity(events, now) {
  var e = next(events, now)
  if (!e) return { id: "calendar", active: false, priority: PRIORITY, text: "", glyph: "", card: "", url: "" }
  var until = e.start - now
  var ear = ""
  if (until > 0 && until <= SOON_MS) ear = "in " + Math.ceil(until / 60000) + "m"
  else if (until <= 0 && -until < SOON_MS) ear = "now"
  var a = {
    id: "calendar", active: true, priority: PRIORITY,
    text: ear !== "" ? ear : (until <= 0 ? "now" : clock(e.start)),
    glyph: GLYPHS.calendar,
    card: _title(e.title) + " · " + clock(e.start),
    url: meetingUrl(e.url)
  }
  if (ear === "") a.cardOnly = true
  return a
}

if (typeof module !== "undefined") module.exports = {
  PRIORITY: PRIORITY, GLYPHS: GLYPHS, HOSTS: HOSTS, SUFFIX_HOSTS: SUFFIX_HOSTS,
  meetingUrl: meetingUrl, clock: clock, next: next, activity: activity
}
