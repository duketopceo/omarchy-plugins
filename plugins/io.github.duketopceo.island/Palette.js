// Dominant colors from raw pixels, for the Island's artwork tint. ES5, no Qt
// types. ArtTint.qml reads a small canvas and hands the RGBA bytes here; the
// result feeds Tint.pick(). Quickshell's ColorQuantizer reads only local
// files, so it could not tint remote or data: art.

var LEVELS = 4          // buckets per channel (the top 2 bits)
var MIN_SHARE = 0.02    // a bucket under 2% of the opaque pixels is noise
var MAX_COLORS = 6

// data: RGBA bytes (array or Uint8ClampedArray). Returns [{r, g, b}] in 0..1,
// most common first; the mean of each bucket's pixels.
function dominant(data, opts) {
  var max = opts && opts.max > 0 ? Math.floor(opts.max) : MAX_COLORS
  if (!data || typeof data.length !== "number") return []
  var buckets = {}
  var total = 0
  for (var i = 0; i + 3 < data.length; i += 4) {
    if (!(data[i + 3] >= 128)) continue
    var r = data[i] | 0, g = data[i + 1] | 0, b = data[i + 2] | 0
    var key = ((r >> 6) * LEVELS + (g >> 6)) * LEVELS + (b >> 6)
    var e = buckets[key]
    if (!e) e = buckets[key] = { n: 0, r: 0, g: 0, b: 0 }
    e.n++
    e.r += r
    e.g += g
    e.b += b
    total++
  }
  var list = []
  for (var k in buckets) if (buckets[k].n / total >= MIN_SHARE) list.push(buckets[k])
  list.sort(function (x, y) { return y.n - x.n })
  var out = []
  for (var j = 0; j < list.length && j < max; j++) {
    out.push({ r: list[j].r / list[j].n / 255, g: list[j].g / list[j].n / 255, b: list[j].b / list[j].n / 255 })
  }
  return out
}

if (typeof module !== "undefined") module.exports = { dominant: dominant, MIN_SHARE: MIN_SHARE, MAX_COLORS: MAX_COLORS }
