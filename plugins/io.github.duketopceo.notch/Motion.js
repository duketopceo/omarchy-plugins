// Motion tokens for the notch: every duration, bounce and shift lives here so
// views carry no magic numbers. No Qt types, so tests run it with node.
//
// Springs are specified as duration (seconds, the time of one natural period)
// + bounce, the SwiftUI mapping: omega = 2 * PI / duration, zeta = 1 - bounce.
// SpringValue.qml integrates exactly that.

var OPEN = { duration: 0.35, bounce: 0.15 }    // island morph, notch -> panel
var CLOSE = { duration: 0.22, bounce: 0 }      // quicker than open, no overshoot
var STRIP = { duration: 0.3, bounce: 0.1 }     // tab-strip selection indicator

var FADE_IN_MS = 160       // content fades in once the shape is mostly open
var FADE_OUT_MS = 80       // ...and out first on close
var OPEN_GATE = 0.6        // shape progress (0..1) before the content starts fading in
var CONTENT_SLIDE = 6      // px the content rises while fading in on open

var TAB_OUT_MS = 80        // outgoing tab: fade + shift toward the side it came from
var TAB_IN_MS = 140        // incoming tab: slide in from the clicked tab's direction (total ~220)
var TAB_SHIFT_OUT = 8      // px
var TAB_SHIFT_IN = 24      // px

var REDUCED_FADE_MS = 120  // reduce motion: every transition is one quick fade

// Spring stiffness / damping for a duration + bounce pair.
function omega(spring) { return 2 * Math.PI / Math.max(0.01, spring.duration) }
function zeta(spring) { return Math.max(0.05, 1 - spring.bounce) }

// +1 when the new tab sits to the right of the old one, -1 when to the left.
function direction(fromIndex, toIndex) { return toIndex >= fromIndex ? 1 : -1 }

if (typeof module !== "undefined") {
  module.exports = { OPEN: OPEN, CLOSE: CLOSE, STRIP: STRIP, FADE_IN_MS: FADE_IN_MS, FADE_OUT_MS: FADE_OUT_MS, OPEN_GATE: OPEN_GATE, CONTENT_SLIDE: CONTENT_SLIDE, TAB_OUT_MS: TAB_OUT_MS, TAB_IN_MS: TAB_IN_MS, TAB_SHIFT_OUT: TAB_SHIFT_OUT, TAB_SHIFT_IN: TAB_SHIFT_IN, REDUCED_FADE_MS: REDUCED_FADE_MS, omega: omega, zeta: zeta, direction: direction }
}
