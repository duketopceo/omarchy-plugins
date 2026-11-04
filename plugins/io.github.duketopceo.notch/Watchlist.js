// Pure logic for the notch watchlist slide: parse cached quotes, format price
// and change, decide up/down, rotate symbols. No Qt types, testable with node.

// The `quotes` block of the cache (bin/notch-data) to [{symbol, price,
// changePercent}], or [] when missing or malformed.
function parseQuotes(text) {
  var d
  try {
    d = JSON.parse(String(text || ""))
  } catch (error) {
    return []
  }
  var items = d && d.quotes && Array.isArray(d.quotes.items) ? d.quotes.items : []
  var out = []
  for (var i = 0; i < items.length; i++) {
    var q = items[i] || {}
    var price = Number(q.price), pct = Number(q.changePercent)
    if (typeof q.symbol !== "string" || q.symbol === "") continue
    if (q.price === null || q.changePercent === null || !isFinite(price) || !isFinite(pct)) continue
    out.push({ symbol: q.symbol, price: price, changePercent: pct })
  }
  return out
}

// 1234.5 -> "1,234.50"; large prices lose decimals; tiny ones gain them.
function formatPrice(price) {
  var p = Number(price)
  if (!isFinite(p)) return "--"
  var digits = Math.abs(p) >= 10000 ? 0 : (Math.abs(p) < 1 ? 4 : 2)
  var s = Math.abs(p).toFixed(digits)
  var parts = s.split(".")
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",")
  return (p < 0 ? "-" : "") + parts.join(".")
}

// 2.291 -> "+2.3%", -0.04 -> "0.0%" (no sign on a rounded zero).
function formatChange(pct) {
  var p = Number(pct)
  if (!isFinite(p)) return "--"
  var r = Math.round(Math.abs(p) * 10) / 10
  if (r === 0) return "0.0%"
  return (p < 0 ? "-" : "+") + r.toFixed(1) + "%"
}

// "up", "down" or "flat" (flat when the change rounds to 0.0%).
function direction(pct) {
  var p = Number(pct)
  if (!isFinite(p) || Math.round(Math.abs(p) * 10) === 0) return "flat"
  return p > 0 ? "up" : "down"
}

// Symbols shown per slide: 1 in a notch ear (narrow), 2 on the virtual
// notch, but never more than `max`.
function perSlide(notched, max) {
  return Math.max(1, Math.min(notched ? 1 : 2, Number(max) || 2))
}

// Number of slides for `count` quotes at `size` per slide.
function slideCount(count, size) {
  return Math.ceil(Math.max(0, Number(count) || 0) / Math.max(1, Number(size) || 1))
}

// The quotes on slide number `index` (wraps around), `size` at a time.
function slide(quotes, index, size) {
  var list = Array.isArray(quotes) ? quotes : []
  var n = Math.max(1, Number(size) || 1)
  var count = slideCount(list.length, n)
  if (count === 0) return []
  var start = (((Math.floor(Number(index) || 0)) % count) + count) % count * n
  return list.slice(start, start + n)
}

if (typeof module !== "undefined") {
  module.exports = {
    parseQuotes: parseQuotes,
    formatPrice: formatPrice,
    formatChange: formatChange,
    direction: direction,
    perSlide: perSlide,
    slideCount: slideCount,
    slide: slide
  }
}
