import QtQuick
import "Motion.js" as Motion

// A number that chases `target` with real spring physics (frame-rate
// independent): duration + bounce as in Motion.js. `instant` snaps (reduce
// motion). Retargeting mid-flight keeps the current velocity.
QtObject {
  id: sv

  property real target: 0
  property real value: target
  property real duration: Motion.OPEN.duration
  property real bounce: Motion.OPEN.bounce
  property bool instant: false
  property real epsilon: 0.25
  property real velocity: 0
  // Pxl: snap to the target in a few whole-pixel frames instead of springing.
  property bool stepped: false
  property int frames: 3
  property int frameMs: 45
  property real from: 0
  property int frame: 0

  onTargetChanged: {
    if (instant) { value = target; velocity = 0; return }
    if (stepped) { from = value; frame = 0; anim.running = false; stepTimer.restart(); return }
    anim.running = true
  }
  onInstantChanged: if (instant) { value = target; velocity = 0; anim.running = false }

  property Timer stepTimer: Timer {
    interval: sv.frameMs
    repeat: true
    onTriggered: {
      sv.frame += 1
      if (sv.frame >= sv.frames) { sv.value = Math.round(sv.target); stop(); return }
      sv.value = Math.round(sv.from + (sv.target - sv.from) * sv.frame / sv.frames)
    }
  }

  property FrameAnimation anim: FrameAnimation {
    running: false
    onTriggered: {
      var w = 2 * Math.PI / Math.max(0.01, sv.duration)
      var z = Math.max(0.05, 1 - sv.bounce)
      var dt = Math.min(frameTime, 0.05)
      var steps = 4
      var h = dt / steps
      for (var i = 0; i < steps; i++) {
        var a = -w * w * (sv.value - sv.target) - 2 * z * w * sv.velocity
        sv.velocity += a * h
        sv.value += sv.velocity * h
      }
      if (Math.abs(sv.value - sv.target) < sv.epsilon && Math.abs(sv.velocity) < sv.epsilon * 4) {
        sv.value = sv.target
        sv.velocity = 0
        running = false
      }
    }
  }
}
