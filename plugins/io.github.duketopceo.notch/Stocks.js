// Pure logic for the Stocks tab: palette, settings, series parsing, chart
// scaling, axis ticks, candle aggregation, crosshair lookup, formatting. No
// Qt types, so tests run it with node.
//
// Series come from bin/notch-data in the cache under `series`:
//   series[SYMBOL][RANGE] = { t:[unix s], o:[], h:[], l:[], c:[], v:[], prev, fetchedAt, interval }

// Up/down colors are defined here once: muted, TradingView-like.
var COLORS = {
  up: "#4fae7b",
  down: "#d2585d",
  flat: "#8b8f98",
  upFill: "#4fae7b",
  downFill: "#d2585d",
  grid: "#ffffff",         // drawn at low alpha
  card: "#ffffff",         // card fill at low alpha
  cardSelected: "#ffffff",
  crosshair: "#ffffff"
}

var RANGES = [
  { key: "1D", label: "1D", seconds: 86400, interval: "5m" },
  { key: "5D", label: "5D", seconds: 5 * 86400, interval: "30m" },
  { key: "1M", label: "1M", seconds: 30 * 86400, interval: "1d" },
  { key: "6M", label: "6M", seconds: 182 * 86400, interval: "1d" },
  { key: "1Y", label: "1Y", seconds: 365 * 86400, interval: "1wk" }
]

var DEFAULTS = { range: "1M", style: "line", prepost: false, cards: 6 }
var MAX_WATCH = 12
var CARD_CHOICES = [4, 5, 6]

// ------------------------------------------------------------ ranges

function rangeSpec(key) {
  for (var i = 0; i < RANGES.length; i++) if (RANGES[i].key === key) return RANGES[i]
  return null
}

function validRange(key, fallback) {
  return rangeSpec(key) ? key : (fallback || DEFAULTS.range)
}

// Request file the tab writes so notch-data fetches the ranges in use.
function requestJson(ranges, nowSeconds) {
  var out = []
  var list = Array.isArray(ranges) ? ranges : []
  for (var i = 0; i < list.length; i++) if (rangeSpec(list[i]) && out.indexOf(list[i]) < 0) out.push(list[i])
  return JSON.stringify({ ranges: out, at: Math.floor(Number(nowSeconds) || 0) })
}

// ------------------------------------------------------------ settings

function normalizeSymbol(s) {
  var t = String(s === undefined || s === null ? "" : s).trim().toUpperCase()
  return /^[A-Z0-9.\-=^]{1,12}$/.test(t) ? t : ""
}

function cleanList(list) {
  var out = []
  var src = Array.isArray(list) ? list : []
  for (var i = 0; i < src.length && out.length < MAX_WATCH; i++) {
    var s = normalizeSymbol(src[i])
    if (s && out.indexOf(s) < 0) out.push(s)
  }
  return out
}

// Watchlist: the notch's own `stocks.watchlist`, else finance.json's.
function watchlist(entry, financeText) {
  var own = cleanList(entry ? entry["stocks.watchlist"] : null)
  if (own.length) return own
  var fin = null
  try { fin = JSON.parse(String(financeText || "")) } catch (e) { fin = null }
  return cleanList(fin ? fin.watchlist : null)
}

function addSymbol(list, sym) {
  var s = normalizeSymbol(sym)
  var cur = cleanList(list)
  if (!s || cur.indexOf(s) >= 0 || cur.length >= MAX_WATCH) return cur
  cur.push(s)
  return cur
}

function removeSymbol(list, sym) {
  var cur = cleanList(list)
  var i = cur.indexOf(String(sym))
  if (i >= 0) cur.splice(i, 1)
  return cur
}

// Resolve `stocks.*` values from the plugin entry plus unsaved overrides.
function settings(entry, pending, financeText) {
  var merged = {}
  var k
  for (k in (entry || {})) merged[k] = entry[k]
  for (k in (pending || {})) merged[k] = pending[k]
  var cards = Math.round(Number(merged["stocks.cards"]))
  return {
    watchlist: watchlist(merged, financeText),
    range: validRange(merged["stocks.range"], DEFAULTS.range),
    style: merged["stocks.style"] === "candle" ? "candle" : "line",
    prepost: merged["stocks.prepost"] === true,
    cards: cards >= 4 && cards <= 6 ? cards : DEFAULTS.cards
  }
}

// ------------------------------------------------------------ series

function isNum(x) { return typeof x === "number" && isFinite(x) }

// Series for `symbol`/`range` from cache text or object: { points:[{t,o,h,l,c,v}], prev, interval }
// (t in ms). Rows with a bad time or close are dropped; returns null when empty.
function parseSeries(cache, symbol, range) {
  var d = cache
  if (typeof cache === "string") {
    try { d = JSON.parse(cache) } catch (e) { return null }
  }
  var e = d && d.series && d.series[symbol] ? d.series[symbol][range] : null
  if (!e || !Array.isArray(e.t) || !Array.isArray(e.c)) return null
  var pts = []
  for (var i = 0; i < e.t.length; i++) {
    var t = e.t[i], c = e.c[i]
    if (!isNum(t) || !isNum(c)) continue
    var o = e.o && isNum(e.o[i]) ? e.o[i] : c
    var h = e.h && isNum(e.h[i]) ? e.h[i] : Math.max(o, c)
    var l = e.l && isNum(e.l[i]) ? e.l[i] : Math.min(o, c)
    pts.push({ t: t * 1000, o: o, h: Math.max(h, o, c), l: Math.min(l, o, c), c: c, v: e.v && isNum(e.v[i]) ? e.v[i] : 0 })
  }
  if (!pts.length) return null
  return { points: pts, prev: isNum(e.prev) ? e.prev : null, interval: e.interval || "" }
}

// Change over the series: from the previous close on 1D, else from the first
// Today's change %: the quote's changePercent (vs the previous close) when it
// is a number, else the 1D series change, else NaN. Never the range change.
function todayPercent(quote, dayChange) {
  var q = quote ? Number(quote.changePercent) : NaN
  if (quote && quote.changePercent !== null && quote.changePercent !== undefined && isFinite(q)) return q
  return dayChange && isFinite(dayChange.percent) ? dayChange.percent : NaN
}

// close. { value, percent, last } or null.
function seriesChange(series, range) {
  if (!series || !series.points.length) return null
  var last = series.points[series.points.length - 1].c
  var base = range === "1D" && isNum(series.prev) && series.prev !== 0 ? series.prev : series.points[0].c
  if (!base) return null
  return { value: last - base, percent: (last - base) / base * 100, last: last }
}

function direction(pct) {
  var p = Number(pct)
  if (!isFinite(p) || Math.round(Math.abs(p) * 100) === 0) return "flat"
  return p > 0 ? "up" : "down"
}

function toneColor(pct) {
  var d = direction(pct)
  return d === "up" ? COLORS.up : (d === "down" ? COLORS.down : COLORS.flat)
}

// ------------------------------------------------------------ scaling

// Nice axis ticks covering [min, max]: about `count` steps of 1/2/5 x 10^n.
// Returns { ticks:[...], min, max } with min/max the first/last tick.
function niceTicks(min, max, count) {
  var lo = Number(min), hi = Number(max)
  if (!isFinite(lo) || !isFinite(hi)) return { ticks: [], min: 0, max: 1 }
  if (hi < lo) { var tmp = lo; lo = hi; hi = tmp }
  if (hi === lo) { var pad = Math.abs(lo) * 0.01 || 1; lo -= pad; hi += pad }
  var n = Math.max(2, Math.round(Number(count) || 5))
  var raw = (hi - lo) / (n - 1)
  var mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10))
  var f = raw / mag
  var step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * mag
  var start = Math.floor(lo / step + 1e-9) * step
  var ticks = []
  var decimals = Math.max(0, -Math.floor(Math.log(step) / Math.LN10 + 1e-9))
  for (var v = start; v < hi + step * 0.999; v += step) {
    ticks.push(Number(v.toFixed(Math.min(10, decimals))))
    if (ticks.length > 50) break
  }
  return { ticks: ticks, min: ticks[0], max: ticks[ticks.length - 1] }
}

// Value range of a points list (candles use high/low), with a little headroom.
function valueRange(points, candles) {
  var lo = Infinity, hi = -Infinity
  for (var i = 0; i < points.length; i++) {
    var p = points[i]
    var a = candles ? p.l : p.c, b = candles ? p.h : p.c
    if (a < lo) lo = a
    if (b > hi) hi = b
  }
  if (!isFinite(lo)) return { min: 0, max: 1 }
  var pad = (hi - lo) * 0.06
  if (pad === 0) pad = Math.abs(lo) * 0.01 || 1
  return { min: lo - pad, max: hi + pad }
}

// Map points to chart coordinates. box = { w, h, left, right, top, bottom }.
// x spreads points evenly (market gaps are not drawn), y is linear in
// [min, max] with larger values higher. Returns { xs, ys, x(i), y(v), plot }.
function scalePoints(points, box, min, max) {
  var left = box.left || 0, right = box.right || 0, top = box.top || 0, bottom = box.bottom || 0
  var pw = Math.max(1, box.w - left - right), ph = Math.max(1, box.h - top - bottom)
  var n = points.length
  var span = max - min || 1
  function x(i) { return n <= 1 ? left + pw / 2 : left + pw * i / (n - 1) }
  function y(v) { return top + ph * (1 - (v - min) / span) }
  var xs = [], ys = []
  for (var i = 0; i < n; i++) { xs.push(x(i)); ys.push(y(points[i].c)) }
  return { xs: xs, ys: ys, x: x, y: y, plot: { left: left, top: top, width: pw, height: ph } }
}

// Aggregate points into at most `maxCandles` OHLC candles (equal-size groups,
// the remainder spread over the first groups). Keeps each group's last time.
function aggregate(points, maxCandles) {
  var n = points.length
  var m = Math.max(1, Math.floor(Number(maxCandles) || n))
  if (n <= m) return points.map(function (p) { return { t: p.t, o: p.o, h: p.h, l: p.l, c: p.c, v: p.v } })
  var out = []
  var base = Math.floor(n / m), extra = n % m
  var idx = 0
  for (var g = 0; g < m; g++) {
    var size = base + (g < extra ? 1 : 0)
    var first = points[idx], lastP = points[idx + size - 1]
    var hi = -Infinity, lo = Infinity, vol = 0
    for (var j = idx; j < idx + size; j++) {
      if (points[j].h > hi) hi = points[j].h
      if (points[j].l < lo) lo = points[j].l
      vol += points[j].v
    }
    out.push({ t: lastP.t, o: first.o, h: hi, l: lo, c: lastP.c, v: vol })
    idx += size
  }
  return out
}

// Index of the entry in `xs` (ascending) nearest to `x`; -1 when empty.
function nearest(xs, x) {
  var n = xs ? xs.length : 0
  if (!n) return -1
  var lo = 0, hi = n - 1
  while (hi - lo > 1) {
    var mid = (lo + hi) >> 1
    if (xs[mid] <= x) lo = mid; else hi = mid
  }
  return Math.abs(xs[lo] - x) <= Math.abs(xs[hi] - x) ? lo : hi
}

// ------------------------------------------------------------ cards / scroll

// Card grid geometry: `columns` per row; rows needed for `count` cards.
function gridRows(count, columns) {
  return Math.ceil(Math.max(0, Number(count) || 0) / Math.max(1, Number(columns) || 1))
}

// Wheel handling: one notch (angleDelta.y 120) moves 3 rows. Returns the new
// scroll offset in px, clamped to [0, max(0, rows*rowH - viewH)].
function scrollTarget(current, angleDeltaY, rowH, rows, viewH) {
  var maxScroll = Math.max(0, rows * rowH - viewH)
  var next = Number(current) - (Number(angleDeltaY) / 120) * 3 * rowH
  return Math.max(0, Math.min(maxScroll, isFinite(next) ? next : 0))
}

// Downsample closes to at most `max` values for a sparkline.
function sparkValues(points, max) {
  var n = points.length, m = Math.max(2, Math.floor(Number(max) || n))
  if (n <= m) return points.map(function (p) { return p.c })
  var out = []
  for (var i = 0; i < m; i++) out.push(points[Math.round(i * (n - 1) / (m - 1))].c)
  return out
}

// ------------------------------------------------------------ formatting

function formatPrice(price) {
  var p = Number(price)
  if (!isFinite(p)) return "--"
  var digits = Math.abs(p) >= 10000 ? 0 : (Math.abs(p) < 1 && p !== 0 ? 4 : 2)
  var parts = Math.abs(p).toFixed(digits).split(".")
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",")
  return (p < 0 ? "-" : "") + parts.join(".")
}

function formatChange(pct) {
  var p = Number(pct)
  if (!isFinite(p)) return "--"
  var r = Math.round(Math.abs(p) * 100) / 100
  if (r === 0) return "0.00%"
  return (p < 0 ? "-" : "+") + r.toFixed(2) + "%"
}

function formatDelta(v) {
  var p = Number(v)
  if (!isFinite(p)) return "--"
  var s = formatPrice(Math.abs(p))
  return (p < 0 ? "-" : (p > 0 ? "+" : "")) + s
}

function formatVolume(v) {
  var n = Number(v)
  if (!isFinite(n) || n <= 0) return "--"
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B"
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M"
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "K"
  return String(Math.round(n))
}

var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

function pad2(n) { return (n < 10 ? "0" : "") + n }

// Tooltip/axis time: intraday ranges "Nov 4 09:35" (axis: "09:35"), longer
// ranges "Nov 4" (1Y axis: "Nov 24"). Local time.
function formatTime(ms, range, axis) {
  var d = new Date(Number(ms))
  if (isNaN(d.getTime())) return "--"
  var hm = pad2(d.getHours()) + ":" + pad2(d.getMinutes())
  var md = MONTHS[d.getMonth()] + " " + d.getDate()
  if (range === "1D") return axis ? hm : md + " " + hm
  if (range === "5D") return axis ? md : md + " " + hm
  if (range === "1Y" && axis) return MONTHS[d.getMonth()] + " " + pad2(d.getFullYear() % 100)
  return md
}

// Evenly spaced x-axis label positions: indices of points to label.
function axisIndices(n, count) {
  var c = Math.max(2, Math.floor(Number(count) || 4))
  if (n <= 0) return []
  if (n <= c) { var all = []; for (var i = 0; i < n; i++) all.push(i); return all }
  var out = []
  for (var k = 0; k < c; k++) out.push(Math.round(k * (n - 1) / (c - 1)))
  return out
}

if (typeof module !== "undefined") {
  module.exports = {
    COLORS: COLORS, RANGES: RANGES, DEFAULTS: DEFAULTS, MAX_WATCH: MAX_WATCH, CARD_CHOICES: CARD_CHOICES,
    rangeSpec: rangeSpec, validRange: validRange, requestJson: requestJson,
    normalizeSymbol: normalizeSymbol, cleanList: cleanList, watchlist: watchlist,
    addSymbol: addSymbol, removeSymbol: removeSymbol, settings: settings,
    parseSeries: parseSeries, seriesChange: seriesChange, todayPercent: todayPercent, direction: direction, toneColor: toneColor,
    niceTicks: niceTicks, valueRange: valueRange, scalePoints: scalePoints, aggregate: aggregate,
    nearest: nearest, gridRows: gridRows, scrollTarget: scrollTarget, sparkValues: sparkValues,
    formatPrice: formatPrice, formatChange: formatChange, formatDelta: formatDelta,
    formatVolume: formatVolume, formatTime: formatTime, axisIndices: axisIndices
  }
}
