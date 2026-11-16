import QtQuick 6.11
import Quickshell
import Quickshell.Widgets
import qs.Commons as Commons
import "Glyphs.js" as Glyphs
import "Media.js" as Media

// The expanded Now Playing block, laid out like macOS Now Playing: rounded
// album art, the player's own icon and name, title, artist (or show), a tinted
// progress bar with elapsed and remaining time, and large borderless transport
// glyphs. It has one height (`implicitHeight`); the card sizes itself from it.
// Controls call act("media", action, value) and never raise keyboard focus
// (KTD4). A scrub drag holds the card open (R10).
Item {
  id: block

  property var activity: null
  // Accent from the art, or the theme accent. The pill row above the card
  // already carries the equalizer.
  property color tint: Commons.Color.accent
  signal act(string id, string action, real value)
  signal holdStart()
  signal holdEnd()

  readonly property color textColor: Commons.Color.popups.text
  readonly property int artSize: Commons.Style.space(84)
  readonly property int scrubHeight: Commons.Style.space(16)
  readonly property int controlsHeight: Commons.Style.space(44)
  readonly property int gap: Commons.Style.spacing.xl
  implicitHeight: block.artSize + block.gap + block.scrubHeight + Commons.Style.spacing.sm + block.controlsHeight

  readonly property bool scrubbable: block.activity !== null && block.activity.canSeek === true && block.activity.length > 0
  readonly property bool hasLength: block.activity !== null && block.activity.length > 0
  // While dragging, the bar shows the drag position instead of the player's.
  property real dragFraction: -1
  property bool dragging: false

  // The player's icon from its desktop entry, else a themed icon of the same
  // name; empty when neither resolves, and the name then stands alone.
  readonly property string iconName: {
    var id = block.activity ? String(block.activity.desktopEntry || "") : ""
    if (id === "") return ""
    var entry = DesktopEntries.heuristicLookup(id)
    return Quickshell.iconPath(entry && entry.icon ? entry.icon : id, true)
  }

  function send(action, value) { block.act("media", action, value === undefined ? 0 : value) }

  // ---- header ----
  ArtImage {
    id: art
    width: block.artSize
    height: block.artSize
    radius: Math.round(block.artSize * 0.14)
    source: block.activity ? String(block.activity.art || "") : ""
    glyphSize: Commons.Style.font.displayLarge
  }

  Item {
    id: identity
    anchors.left: art.right
    anchors.leftMargin: Commons.Style.spacing.huge
    anchors.right: parent.right
    anchors.top: art.top
    height: Commons.Style.space(18)

    IconImage {
      id: appIcon
      visible: block.iconName !== ""
      source: block.iconName
      implicitSize: Commons.Style.space(14)
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
    }

    Text {
      textFormat: Text.PlainText
      text: block.activity ? String(block.activity.identity || "") : ""
      color: block.textColor
      opacity: 0.7
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.bodySmall
      elide: Text.ElideRight
      maximumLineCount: 1
      anchors.left: appIcon.visible ? appIcon.right : parent.left
      anchors.leftMargin: appIcon.visible ? Commons.Style.spacing.md : 0
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
    }
  }

  Column {
    anchors.left: identity.left
    anchors.right: parent.right
    anchors.bottom: art.bottom
    spacing: Commons.Style.spacing.xs

    Text {
      width: parent.width
      textFormat: Text.PlainText
      text: block.activity ? String(block.activity.card || "") : ""
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
      text: block.activity ? String(block.activity.subtitle || "") : ""
      color: block.textColor
      opacity: 0.75
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.body
      elide: Text.ElideRight
      maximumLineCount: 1
    }
  }

  // ---- progress ----
  Item {
    id: scrub
    anchors.top: art.bottom
    anchors.topMargin: block.gap
    anchors.left: parent.left
    anchors.right: parent.right
    height: block.scrubHeight

    readonly property real fraction: block.dragging ? block.dragFraction
      : (block.hasLength ? Math.max(0, Math.min(1, block.activity.position / block.activity.length)) : 0)

    Text {
      id: posText
      textFormat: Text.PlainText
      text: block.hasLength ? Media.fmt(scrub.fraction * block.activity.length) : ""
      color: block.textColor
      opacity: 0.7
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.bodySmall
      font.features: { "tnum": 1 }
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
    }
    Text {
      id: leftText
      textFormat: Text.PlainText
      text: block.hasLength ? Media.fmtRemaining(scrub.fraction * block.activity.length, block.activity.length) : ""
      color: block.textColor
      opacity: 0.7
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.bodySmall
      font.features: { "tnum": 1 }
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
    }

    Rectangle {
      id: track
      visible: block.hasLength
      anchors.left: posText.right
      anchors.right: leftText.left
      anchors.leftMargin: Commons.Style.spacing.xl
      anchors.rightMargin: Commons.Style.spacing.xl
      anchors.verticalCenter: parent.verticalCenter
      // The bar thickens under the pointer so a scrubbable bar reads as one.
      height: Commons.Style.space(seek.containsMouse && block.scrubbable ? 7 : 5)
      radius: height / 2
      color: Qt.alpha(block.textColor, 0.18)

      Rectangle {
        width: track.width * scrub.fraction
        height: parent.height
        radius: parent.radius
        color: block.tint
      }
    }

    MouseArea {
      id: seek
      enabled: block.scrubbable
      hoverEnabled: true
      cursorShape: block.scrubbable ? Qt.PointingHandCursor : Qt.ArrowCursor
      anchors.fill: track
      anchors.topMargin: -Commons.Style.spacing.lg
      anchors.bottomMargin: -Commons.Style.spacing.lg
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

  // ---- transport: borderless glyphs, the play control largest ----
  Row {
    id: controls
    anchors.top: scrub.bottom
    anchors.topMargin: Commons.Style.spacing.sm
    anchors.horizontalCenter: parent.horizontalCenter
    height: block.controlsHeight
    spacing: Commons.Style.spacing.huge * 2

    Repeater {
      model: [
        { action: "previous", flag: "canGoPrevious", size: 1.0 },
        { action: "toggle", flag: "canTogglePlaying", size: 1.45 },
        { action: "next", flag: "canGoNext", size: 1.0 }
      ]

      HoverButton {
        id: key
        required property var modelData
        enabled: block.activity !== null && block.activity[key.modelData.flag] === true
        hint: Glyphs.controlHint(key.modelData.action, block.activity)
        width: block.controlsHeight
        height: block.controlsHeight
        radius: height / 2
        onClicked: block.send(key.modelData.action)

        Text {
          textFormat: Text.PlainText
          text: Glyphs.controlLabel(key.modelData.action, block.activity)
          color: block.textColor
          opacity: key.hovered ? 1 : 0.85
          font.family: Commons.Style.font.family
          font.pixelSize: Math.round(Commons.Style.font.displayLarge * key.modelData.size)
          anchors.centerIn: parent
        }
      }
    }
  }
}
