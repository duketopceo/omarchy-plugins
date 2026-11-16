import QtQuick 6.11
import qs.Commons as Commons
import "Glyphs.js" as Glyphs
import "Media.js" as Media

// The top activity's controls on the Now page, at one fixed height (KTD9):
// a header (art or glyph, card text, a subtitle), then the activity's
// controls. Media adds a scrub bar; the HUD adds a level bar. Controls call
// act(id, action, value) and never raise keyboard focus (KTD4). A scrub drag
// holds the card open (R10).
Item {
  id: block

  property var activity: null
  // Media accent from local album art, or the theme accent (R13).
  property color tint: Commons.Color.accent
  signal act(string id, string action, real value)
  signal holdStart()
  signal holdEnd()

  readonly property string kind: block.activity ? String(block.activity.id) : ""
  readonly property color textColor: Commons.Color.popups.text
  readonly property color accent: block.kind === "media" ? block.tint : Commons.Color.accent
  readonly property int artSize: Commons.Style.space(64)
  readonly property int scrubHeight: Commons.Style.space(16)
  // One fixed height for every kind, sized for the media layout: art, scrub
  // bar and transport row (KTD9). The card reads it from here.
  implicitHeight: block.artSize + block.scrubHeight + Commons.Style.spacing.controlHeight + Commons.Style.spacing.lg * 2
  readonly property bool scrubbable: block.kind === "media" && block.activity.canSeek === true && block.activity.length > 0
  // The timer's first control: what a press does now.
  readonly property string timerAction: block.kind === "timer" && block.activity.state === "paused" ? "resume" : "pause"
  // While dragging, the bar shows the drag position instead of the player's.
  property real dragFraction: -1
  property bool dragging: false

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

    Image {
      id: artImage
      anchors.fill: parent
      visible: block.kind === "media" && status === Image.Ready
      source: block.kind === "media" && block.activity.art ? block.activity.art : ""
      fillMode: Image.PreserveAspectCrop
      asynchronous: true
      sourceSize.width: block.artSize * 2
      sourceSize.height: block.artSize * 2
    }

    Text {
      visible: !artImage.visible
      textFormat: Text.PlainText
      text: block.kind === "media" ? Glyphs.GLYPHS.music : (block.activity ? block.activity.glyph : "")
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

    Text {
      width: parent.width
      visible: text !== ""
      textFormat: Text.PlainText
      text: block.kind === "media" ? String(block.activity.artist || "") : ""
      color: block.textColor
      opacity: 0.8
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.body
      elide: Text.ElideRight
      maximumLineCount: 1
    }
  }

  // ---- media scrub bar ----
  Item {
    id: scrub
    visible: block.scrubbable
    anchors.top: art.bottom
    anchors.topMargin: Commons.Style.spacing.lg
    anchors.left: parent.left
    anchors.right: parent.right
    height: block.scrubHeight

    readonly property real fraction: block.dragging ? block.dragFraction
      : (block.scrubbable ? Math.max(0, Math.min(1, block.activity.position / block.activity.length)) : 0)

    Text {
      id: posText
      textFormat: Text.PlainText
      text: block.scrubbable ? Media.fmt(scrub.fraction * block.activity.length) : ""
      color: block.textColor
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.bodySmall
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
    }
    Text {
      id: lenText
      textFormat: Text.PlainText
      text: block.scrubbable ? Media.fmt(block.activity.length) : ""
      color: block.textColor
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.bodySmall
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
    }

    Rectangle {
      id: track
      anchors.left: posText.right
      anchors.right: lenText.left
      anchors.leftMargin: Commons.Style.spacing.lg
      anchors.rightMargin: Commons.Style.spacing.lg
      anchors.verticalCenter: parent.verticalCenter
      height: Commons.Style.space(4)
      radius: height / 2
      color: Commons.Color.menu.border

      Rectangle {
        width: track.width * scrub.fraction
        height: parent.height
        radius: parent.radius
        color: block.accent
      }
    }

    MouseArea {
      anchors.fill: track
      anchors.topMargin: -Commons.Style.spacing.md
      anchors.bottomMargin: -Commons.Style.spacing.md
      preventStealing: true
      function at(x) { return Math.max(0, Math.min(1, x / Math.max(1, track.width))) }
      onPressed: function(mouse) {
        block.dragging = true
        block.dragFraction = at(mouse.x)
        block.holdStart()
      }
      onPositionChanged: function(mouse) { if (block.dragging) block.dragFraction = at(mouse.x) }
      onReleased: function(mouse) {
        block.send("seek", at(mouse.x))
        block.dragging = false
        block.holdEnd()
      }
      onCanceled: { block.dragging = false; block.holdEnd() }
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

    // Media
    ActivityButton {
      visible: block.kind === "media"
      label: Glyphs.controlLabel("previous", block.activity)
      available: block.kind === "media" && block.activity.canGoPrevious === true
      onClicked: block.send("previous")
    }
    ActivityButton {
      visible: block.kind === "media"
      label: Glyphs.controlLabel("toggle", block.activity)
      available: block.kind === "media" && block.activity.canTogglePlaying === true
      emphasized: true
      accent: block.accent
      onClicked: block.send("toggle")
    }
    ActivityButton {
      visible: block.kind === "media"
      label: Glyphs.controlLabel("next", block.activity)
      available: block.kind === "media" && block.activity.canGoNext === true
      onClicked: block.send("next")
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
