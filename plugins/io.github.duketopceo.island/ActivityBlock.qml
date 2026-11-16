import QtQuick 6.11
import qs.Commons as Commons
import "Glyphs.js" as Glyphs

// The top activity's controls on the Now page, at one fixed height (KTD9):
// a header (glyph, card text), then the activity's controls. The HUD adds a
// level bar. Media has its own block (MediaBlock). Controls call
// act(id, action, value) and never raise keyboard focus (KTD4).
Item {
  id: block

  property var activity: null
  signal act(string id, string action, real value)

  readonly property string kind: block.activity ? String(block.activity.id) : ""
  readonly property color textColor: Commons.Color.popups.text
  readonly property int artSize: Commons.Style.space(64)
  readonly property int levelHeight: Commons.Style.space(16)
  // One fixed height for every kind: header, level slot and control row (KTD9).
  implicitHeight: block.artSize + block.levelHeight + Commons.Style.spacing.controlHeight + Commons.Style.spacing.lg * 2
  // The timer's first control: what a press does now.
  readonly property string timerAction: block.kind === "timer" && block.activity.state === "paused" ? "resume" : "pause"
  function send(action, value) { block.act(block.kind, action, value === undefined ? 0 : value) }

  // ---- header ----
  Rectangle {
    id: art
    width: block.artSize
    height: block.artSize
    radius: Commons.Style.cornerRadius
    color: "transparent"
    border.width: Commons.Style.normalBorderWidth
    border.color: Commons.Color.menu.border
    clip: true

    Text {
      textFormat: Text.PlainText
      text: block.activity ? block.activity.glyph : ""
      color: block.textColor
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.displayLarge
      anchors.centerIn: parent
    }
  }

  Column {
    anchors.left: art.right
    anchors.leftMargin: Commons.Style.spacing.huge
    anchors.right: parent.right
    anchors.verticalCenter: art.verticalCenter
    spacing: Commons.Style.spacing.sm

    Text {
      width: parent.width
      textFormat: Text.PlainText
      text: block.activity ? block.activity.card : ""
      color: block.textColor
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.heading
      font.bold: true
      elide: Text.ElideRight
      maximumLineCount: 1
    }
  }

  // ---- HUD level bar ----
  Rectangle {
    id: level
    visible: block.kind === "hud"
    anchors.top: art.bottom
    anchors.topMargin: Commons.Style.spacing.xxl
    anchors.left: parent.left
    anchors.right: parent.right
    height: Commons.Style.space(6)
    radius: height / 2
    color: Commons.Color.menu.border

    Rectangle {
      width: level.width * (block.kind === "hud" ? Math.max(0, Math.min(1, Number(block.activity.level) || 0)) : 0)
      height: parent.height
      radius: parent.radius
      color: Commons.Color.accent
    }
  }

  // ---- controls ----
  Row {
    id: controls
    anchors.bottom: parent.bottom
    anchors.horizontalCenter: parent.horizontalCenter
    spacing: Commons.Style.spacing.lg

    // Dictation and screen recording: Stop
    ActivityButton {
      visible: (block.kind === "dictation" || block.kind === "screenrec") && block.activity.state === "recording"
      label: Glyphs.GLYPHS.stop + "  Stop"
      emphasized: true
      onClicked: block.send("stop")
    }

    // Calendar: Join the next meeting's link
    ActivityButton {
      visible: block.kind === "calendar" && Glyphs.primaryControl(block.activity) === "join"
      label: Glyphs.controlLabel("join", block.activity)
      emphasized: true
      onClicked: block.send("join")
    }

    // Timer
    ActivityButton {
      visible: block.kind === "timer" && block.activity.state !== "done"
      label: Glyphs.controlLabel(block.timerAction, block.activity)
      emphasized: true
      onClicked: block.send(block.timerAction)
    }
    ActivityButton {
      visible: block.kind === "timer" && block.activity.state !== "done"
      label: Glyphs.controlLabel("add", block.activity)
      onClicked: block.send("add")
    }
    ActivityButton {
      visible: block.kind === "timer" && block.activity.state !== "done"
      label: Glyphs.controlLabel("cancel", block.activity)
      onClicked: block.send("cancel")
    }
  }
}
