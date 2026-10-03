import QtQuick

// Freshness and backoff bookkeeping for one polled source (plan R8).
// Data is stale after 3 refresh intervals without a good result; repeated
// failures back off exponentially to at most one attempt per 60 s.
QtObject {
  id: root

  property int intervalMs: 5000
  property double lastGoodMs: 0
  property int failures: 0
  property double nowMs: Date.now()   // callers bump this from their own tick

  readonly property bool stale: root.lastGoodMs > 0
                                && (root.nowMs - root.lastGoodMs) > 3 * root.intervalMs
  readonly property string ageText: {
    if (root.lastGoodMs <= 0) return ""
    var s = Math.max(0, Math.round((root.nowMs - root.lastGoodMs) / 1000))
    if (s < 90) return s + "s ago"
    if (s < 5400) return Math.round(s / 60) + "m ago"
    return Math.round(s / 3600) + "h ago"
  }
  // Delay before the next helper attempt.
  readonly property int nextDelayMs: root.failures <= 0
    ? root.intervalMs
    : Math.min(60000, root.intervalMs * Math.pow(2, Math.min(root.failures, 10)))

  function markGood() { root.lastGoodMs = Date.now(); root.nowMs = root.lastGoodMs; root.failures = 0 }
  function markFailed() { root.failures = root.failures + 1; root.nowMs = Date.now() }
}
