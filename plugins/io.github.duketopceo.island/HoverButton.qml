import QtQuick 6.11
import qs.Commons as Commons
import "Controls.js" as Controls

// The one clickable control of the Island card. Every button, chip, row and
// tile that reacts to the pointer is a HoverButton, so they all behave alike:
//   - hover: an instant fill (no fade, per the polish bar), or a border change
//     for `outlined` controls
//   - pressed: a darker fill and a 0.96 scale; the click is handled on release
//     and never waits on an animation
//   - the pointing-hand cursor, and a short `hint` drawn by the Card above or
//     below the control after a brief rest
//   - disabled (`enabled: false`): dimmed, no hover, no press, no hint
// Clicks never raise the card's keyboard focus (KTD4): this only emits
// `clicked`. Children go in the content area, positioned by the caller.
Item {
  id: btn

  property string hint: ""
  property bool selected: false
  property bool outlined: false
  // A row that only displays: no hover, no press, no cursor, not dimmed.
  property bool passive: false
  property real radius: Commons.Style.cornerRadius
  property color idleBorder: Commons.Color.menu.border
  property color selectedBorder: Commons.Color.menu.border
  // Grows the pointer target past the visible control (small glyph buttons).
  property real hitPad: 0
  default property alias content: body.data
  signal clicked()

  readonly property bool hovered: area.containsMouse
  readonly property bool pressed: area.pressed
  readonly property var look: Controls.look({ enabled: btn.enabled, hovered: area.containsMouse, pressed: area.pressed, selected: btn.selected })
  readonly property color ink: Commons.Color.popups.text

  opacity: btn.look.opacity

  // Only the visuals scale on press; the root and the MouseArea keep their
  // size, so a small pointer move while pressed never leaves the target.
  Item {
    id: visual
    anchors.fill: parent
    scale: btn.look.scale
    Behavior on scale { NumberAnimation { duration: Commons.Style.duration(70) } }

    Rectangle {
      id: plate
      anchors.fill: parent
      radius: btn.radius
      color: btn.look.fill === "pressed" ? Qt.alpha(btn.ink, 0.18)
           : (btn.look.fill === "selected" ? Commons.Color.menu.selectedBackground
           : (btn.look.fill === "hover" ? Qt.alpha(btn.ink, 0.10) : "transparent"))
      border.width: btn.outlined ? Commons.Style.normalBorderWidth : 0
      border.color: btn.selected ? btn.selectedBorder
                  : (btn.look.fill === "hover" || btn.look.fill === "pressed" ? Qt.alpha(btn.ink, 0.55) : btn.idleBorder)
    }

    Item {
      id: body
      anchors.fill: parent
    }
  }

  MouseArea {
    id: area
    anchors.fill: parent
    anchors.margins: -btn.hitPad
    hoverEnabled: true
    enabled: btn.enabled && !btn.passive
    cursorShape: btn.look.pointer && !btn.passive ? Qt.PointingHandCursor : Qt.ArrowCursor
    onClicked: btn.clicked()
  }

  // ---- hint: the Card owns the drawing so it is never clipped by a page ----
  property bool hintShown: false
  readonly property bool wantHint: btn.look.hint && btn.hint !== ""

  function host() {
    var p = btn.parent
    while (p) {
      if (p.hintHost === true) return p
      p = p.parent
    }
    return null
  }
  function hideHint() {
    hintTimer.stop()
    if (!btn.hintShown) return
    btn.hintShown = false
    var h = btn.host()
    if (h) h.hideHint(btn)
  }
  function showHint() {
    var h = btn.host()
    if (!h || btn.hint === "") return
    btn.hintShown = true
    h.showHint(btn.hint, btn)
  }

  onWantHintChanged: {
    if (btn.wantHint) hintTimer.restart()
    else btn.hideHint()
  }
  // A control whose hint changes under the pointer (Play becomes Pause).
  onHintChanged: if (btn.hintShown) btn.showHint()
  onVisibleChanged: if (!btn.visible) btn.hideHint()
  Component.onDestruction: btn.hideHint()

  Timer {
    id: hintTimer
    interval: Controls.HINT_DELAY_MS
    onTriggered: if (btn.wantHint) btn.showHint()
  }
}
