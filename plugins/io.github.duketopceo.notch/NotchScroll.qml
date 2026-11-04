import QtQuick

// Flickable with a wheel step that feels right in the small panel: each wheel
// notch scrolls `rowsPerNotch` rows (default 3) with a short ease, instead of
// Qt's slow default. Drag still flicks. Put the content inside as children.
Flickable {
  id: sc

  property real rowHeight: 26
  property real rowsPerNotch: 3

  clip: true
  boundsBehavior: Flickable.StopAtBounds
  flickableDirection: Flickable.VerticalFlick
  maximumFlickVelocity: 2400
  flickDeceleration: 4200

  readonly property real maxY: Math.max(0, contentHeight - height)

  NumberAnimation { id: ease; target: sc; property: "contentY"; duration: 110; easing.type: Easing.OutQuad }

  WheelHandler {
    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
    onWheel: function(event) {
      // angleDelta is 120 per notch; touchpads send many small ones.
      var dy = -event.angleDelta.y / 120 * sc.rowsPerNotch * sc.rowHeight
      var base = ease.running ? ease.to : sc.contentY
      ease.stop()
      ease.to = Math.max(0, Math.min(sc.maxY, base + dy))
      ease.from = sc.contentY
      ease.start()
    }
  }
}
