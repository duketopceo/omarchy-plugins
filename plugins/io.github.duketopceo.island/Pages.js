// The expanded card's pages: which chips show, what More lists, and page ids.
// ES5, no Qt types; node tests load it with require().
//
// avail = { music, agents, shots, messages, dayflow }: the page's backend is
//   detected and its setting is on. Home, System, More and Settings always exist.
// live  = { shots, messages, dayflow }: the page has something live now
//   (an unseen screenshot, an unread message, Dayflow recording or paused).

var PAGE_IDS = ["home", "music", "agents", "system", "more", "shots", "messages", "dayflow", "settings"]
var LABELS = {
  home: "Home", music: "Music", agents: "Agents", system: "System", more: "More",
  shots: "Shots", messages: "Messages", dayflow: "Dayflow", settings: "Settings"
}
var BASE = ["home", "music", "agents", "system"]
var ALWAYS = { home: true, system: true, more: true, settings: true }
// Fixed order on the More page, and the order live pages are promoted in.
var MORE_ORDER = ["shots", "messages", "dayflow"]
var PROMOTE_ORDER = ["messages", "shots", "dayflow"]
var MAX_CHIPS = 6

function exists(id, avail) {
  if (ALWAYS[id] === true) return true
  return !!avail && avail[id] === true
}

// Page id, with the 0.3 "now" page as an alias for Home; "" when unknown.
function normalize(id) {
  var s = String(id === null || id === undefined ? "" : id)
  if (s === "now") return "home"
  return PAGE_IDS.indexOf(s) >= 0 ? s : ""
}

function label(id) { return LABELS[id] || "" }

// -> { chips: [id], more: [id] }. `current` is the page the card is showing:
// a promoted page keeps its chip while open even after it stops being live
// (opening Shots marks its screenshot seen), so the chip under the pointer
// does not vanish at the next commit.
function chips(avail, live, current) {
  var out = []
  for (var i = 0; i < BASE.length; i++) if (exists(BASE[i], avail)) out.push(BASE[i])
  // Promoted pages go before More; More always takes the last slot.
  // Candidates keep PROMOTE_ORDER, so opening one never reorders the row;
  // when the row is full the open page keeps its slot over a later one.
  var cur = normalize(current)
  var promos = []
  for (var j = 0; j < PROMOTE_ORDER.length; j++) {
    var id = PROMOTE_ORDER[j]
    if (exists(id, avail) && (id === cur || (live && live[id] === true))) promos.push(id)
  }
  var room = MAX_CHIPS - 1 - out.length
  var others = room - (promos.indexOf(cur) >= 0 ? 1 : 0)
  for (var k = 0; k < promos.length; k++) {
    if (promos[k] === cur) out.push(cur)
    else if (others > 0) { out.push(promos[k]); others-- }
  }
  out.push("more")
  var more = []
  for (var k = 0; k < MORE_ORDER.length; k++) if (exists(MORE_ORDER[k], avail)) more.push(MORE_ORDER[k])
  more.push("settings")
  return { chips: out, more: more }
}

// The page to show for a request: the page when it exists, else Home.
function reachable(id, avail) {
  var p = normalize(id)
  return p !== "" && exists(p, avail) ? p : "home"
}

if (typeof module !== "undefined") module.exports = {
  PAGE_IDS: PAGE_IDS, MAX_CHIPS: MAX_CHIPS,
  normalize: normalize, label: label, chips: chips, reachable: reachable, exists: exists
}
