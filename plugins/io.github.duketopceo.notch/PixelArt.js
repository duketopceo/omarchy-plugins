// Pixel-art weather icons for the notch island. Pure data and logic, no Qt
// types, so tests can run it with node. Kinds match Model.weatherKind().
// ---------------------------------------------------------------- sprites
// Tiny pixel-art weather icons: SPRITE_SIZE x SPRITE_SIZE cells, 2-4 frames
// each, drawn by the panel with a Canvas. A cell is one char: "." is empty,
// any other char is a key into SPRITE_COLORS. The island is black, so these
// are fixed warm/cool tints rather than theme colors.
var SPRITE_SIZE = 14
var SPRITE_COLORS = {
  Y: "#ffd23f", // sun
  O: "#ff9f1c", // sun rays
  M: "#dfe6f2", // moon
  T: "#fff3b0", // star
  W: "#e6edf7", // cloud
  G: "#9aa8bd", // cloud shade
  B: "#4cc9f0", // rain
  S: "#ffffff", // snow
  L: "#ffe14d", // lightning
  F: "#b8c4d6"  // fog
}

function spriteBlank() {
  var line = ""
  for (var x = 0; x < SPRITE_SIZE; x++) line += "."
  var rows = []
  for (var y = 0; y < SPRITE_SIZE; y++) rows.push(line)
  return rows
}

// Copy `art` (array of strings) onto `rows` at (x, y); "." leaves the cell alone.
function spriteStamp(rows, art, x, y) {
  var out = rows.slice()
  for (var r = 0; r < art.length; r++) {
    var yy = y + r
    if (yy < 0 || yy >= SPRITE_SIZE) continue
    var line = out[yy].split("")
    for (var c = 0; c < art[r].length; c++) {
      var xx = x + c
      if (xx < 0 || xx >= SPRITE_SIZE || art[r].charAt(c) === ".") continue
      line[xx] = art[r].charAt(c)
    }
    out[yy] = line.join("")
  }
  return out
}

function spriteDots(rows, key, points) {
  var out = rows
  for (var i = 0; i < points.length; i++) out = spriteStamp(out, [key], points[i][0], points[i][1])
  return out
}

var ART = {
  sun: [
    "..YYYY..",
    ".YYYYYY.",
    "YYYYYYYY",
    "YYYYYYYY",
    "YYYYYYYY",
    "YYYYYYYY",
    ".YYYYYY.",
    "..YYYY.."
  ],
  moon: [
    "..MMMM...",
    ".MMM.....",
    "MMM......",
    "MMM......",
    "MMM......",
    "MMMM....M",
    ".MMMMMMMM",
    "..MMMMMM."
  ],
  cloud: [
    "...WWWW.....",
    "..WWWWWW.WW.",
    ".WWWWWWWWWWW",
    "WWWWWWWWWWWW",
    "WWWWWWWWWWWW",
    ".GGGGGGGGGG."
  ],
  smallCloud: [
    "..WWWW....",
    ".WWWWWW.WW",
    "WWWWWWWWWW",
    "WWWWWWWWWW",
    ".GGGGGGGG."
  ]
}

function spriteFrames(kind) {
  var b = spriteBlank()
  var out = []
  var i
  if (kind === "clear") {
    var core = spriteStamp(b, ART.sun, 3, 3)
    var plus = [[6, 0], [7, 0], [6, 13], [7, 13], [0, 6], [0, 7], [13, 6], [13, 7]]
    var diag = [[1, 1], [12, 1], [1, 12], [12, 12], [2, 2], [11, 2], [2, 11], [11, 11]]
    out.push(spriteDots(core, "O", plus), spriteDots(core, "O", diag))
  } else if (kind === "night") {
    var m = spriteStamp(b, ART.moon, 2, 3)
    out.push(spriteDots(m, "T", [[11, 2], [12, 7]]), spriteDots(m, "T", [[11, 2], [1, 1], [12, 8]]), spriteDots(m, "T", [[1, 1], [12, 7]]))
  } else if (kind === "partly") {
    var sun = spriteStamp(b, ART.sun, 0, 0)
    var sunRays = [spriteDots(sun, "O", [[4, 9], [10, 2]]), spriteDots(sun, "O", [[9, 0], [10, 4]])]
    for (i = 0; i < 2; i++) out.push(spriteStamp(sunRays[i], ART.cloud, 2, 6 + i))
  } else if (kind === "night-cloudy") {
    var mn = spriteStamp(b, ART.moon, 0, 0)
    for (i = 0; i < 2; i++) out.push(spriteStamp(spriteDots(mn, "T", i ? [[11, 1], [12, 5]] : [[12, 1], [11, 5]]), ART.cloud, 2, 6 + i))
  } else if (kind === "cloudy") {
    var back = spriteStamp(b, ART.smallCloud, 4, 1)
    for (i = 0; i < 3; i++) out.push(spriteStamp(spriteStamp(back, ART.smallCloud, 0, 1), ART.cloud, 1 + (i === 1 ? 1 : 0), 6 + (i === 2 ? 1 : 0)))
  } else if (kind === "fog") {
    var top = spriteStamp(b, ART.smallCloud, 2, 1)
    for (i = 0; i < 3; i++) {
      var f = top
      f = spriteStamp(f, ["FFFFFFFFFFF"], 1 + i, 7)
      f = spriteStamp(f, ["FFFFFFFFFFF"], 2 - i + 1, 9)
      f = spriteStamp(f, ["FFFFFFFFFFF"], 1 + (i === 1 ? 2 : 0), 11)
      out.push(f)
    }
  } else if (kind === "rain") {
    var rc = spriteStamp(b, ART.cloud, 1, 1)
    for (i = 0; i < 3; i++) out.push(spriteDots(rc, "B", [[3 + i, 8 + i], [7 + i, 8 + i], [11 + i - 3, 9 + i], [4 + ((i + 1) % 3), 11 + (i % 2)], [9 + ((i + 2) % 3), 11 + (i % 2)]]))
  } else if (kind === "snow") {
    var sc = spriteStamp(b, ART.cloud, 1, 1)
    for (i = 0; i < 4; i++) out.push(spriteDots(sc, "S", [[3 + (i % 2), 8 + i], [7 - (i % 2), 9 + ((i + 1) % 4)], [10 + (i % 2), 8 + ((i + 2) % 4)], [5, 12 - ((i + 1) % 3)]]))
  } else if (kind === "storm") {
    var tc = spriteStamp(b, ART.cloud, 1, 0)
    var bolt = ["..LL", ".LL.", "LLLL", "..LL", ".L.."]
    var bolt2 = ["..LL", ".LL.", ".LLL", "..L.", "..L."]
    out.push(spriteStamp(tc, bolt, 5, 7), spriteDots(tc, "B", [[3, 9], [10, 10], [4, 12]]),
      spriteStamp(tc, bolt2, 5, 7), spriteDots(tc, "B", [[4, 10], [9, 9], [11, 12]]))
  }
  return out
}

var SPRITE_KINDS = ["clear", "night", "partly", "night-cloudy", "cloudy", "fog", "rain", "snow", "storm"]
var SPRITES = {}
for (var sk = 0; sk < SPRITE_KINDS.length; sk++) SPRITES[SPRITE_KINDS[sk]] = spriteFrames(SPRITE_KINDS[sk])

// Frames for a weather kind; unknown kinds fall back to cloudy.
function weatherSprite(kind) {
  return SPRITES[kind] || SPRITES["cloudy"]
}

// Frame to show at `ms` with `frameMs` per frame.
function spriteFrame(kind, ms, frameMs) {
  var frames = weatherSprite(kind)
  var step = Math.max(1, Number(frameMs) || 600)
  return Math.floor(Math.max(0, Number(ms) || 0) / step) % frames.length
}

if (typeof module !== "undefined") {
  module.exports = {
    SPRITE_SIZE: SPRITE_SIZE,
    SPRITE_COLORS: SPRITE_COLORS,
    SPRITE_KINDS: SPRITE_KINDS,
    weatherSprite: weatherSprite,
    spriteFrame: spriteFrame
  }
}
