import QtQuick 6.11
import qs.Commons as Commons
import "Privacy.js" as Privacy
import "Dnd.js" as Dnd

// The compact pill's content: the time in the left ear (with the Do Not
// Disturb glyph beside it when on); in the right ear the top live activity
// (glyph, or a moving equalizer for playing media, plus its short ear text),
// or the short date when nothing is live. The second activity is not drawn
// here: it is the window's detached bubble (KTD6). Mic and camera dots sit in
// a reserved slot at the right ear's inner edge, beside the camera (R8). Every
// label is single-line and elides; `wantEar` reports the natural width the
// ears would like so the window can size the pill to its content (KTD5).
Item {
  id: pill

  property date now: new Date()
  property int earWidth: 56
  // Width the right ear's label may use (the ear minus the dot slot).
  property int textWidth: 56
  property int dotSlot: 0
  property int cameraWidth: 160
  property color textColor: Commons.Color.popups.text
  // Media accent from local album art, or the theme accent.
  property color tint: Commons.Color.accent
  // From Activity.layout(): the top live activity, or null.
  property var topActivity: null
  property bool dnd: false
  property bool micInUse: false
  property bool cameraInUse: false

  readonly property int pad: Commons.Style.spacing.lg
  readonly property bool mediaPlaying: pill.topActivity !== null && pill.topActivity.id === "media" && pill.topActivity.playing === true
  readonly property string earText: pill.topActivity
    ? (pill.mediaPlaying ? pill.topActivity.text : pill.topActivity.glyph + " " + pill.topActivity.text)
    : Qt.formatDate(pill.now, "MMM d")
  // Natural width of the wider ear, padding included.
  readonly property int wantEar: Math.ceil(Math.max(
    timeText.implicitWidth + (dndGlyph.visible ? dndGlyph.implicitWidth + Commons.Style.spacing.sm : 0),
    earLabel.implicitWidth + (pill.mediaPlaying ? eq.width + Commons.Style.spacing.sm : 0)) + pill.pad * 1.5)

  Text {
    id: timeText
    textFormat: Text.PlainText
    text: Qt.formatTime(pill.now, Qt.locale().timeFormat(Locale.ShortFormat))
    color: pill.textColor
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.bodySmall
    font.features: { "tnum": 1 }
    maximumLineCount: 1
    elide: Text.ElideRight
    width: Math.min(implicitWidth, Math.max(0, pill.earWidth - pill.pad - (dndGlyph.visible ? dndGlyph.implicitWidth + Commons.Style.spacing.sm : 0)))
    anchors.left: parent.left
    anchors.leftMargin: pill.pad
    anchors.verticalCenter: parent.verticalCenter
  }

  Text {
    id: dndGlyph
    visible: pill.dnd
    textFormat: Text.PlainText
    text: Dnd.GLYPH
    color: pill.textColor
    opacity: 0.8
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.bodySmall
    anchors.left: timeText.right
    anchors.leftMargin: Commons.Style.spacing.sm
    anchors.verticalCenter: parent.verticalCenter
  }

  // ---- privacy dots: camera then mic, beside the camera cutout ----
  Row {
    id: dots
    visible: pill.dotSlot > 0
    spacing: 4
    x: pill.width / 2 + pill.cameraWidth / 2 + 6
    anchors.verticalCenter: parent.verticalCenter

    readonly property var base: ({ h: Commons.Color.urgent.hslHue, s: Commons.Color.urgent.hslSaturation, l: Commons.Color.urgent.hslLightness })

    Rectangle {
      visible: pill.cameraInUse
      width: 8; height: 8; radius: 4
      readonly property var hsl: Privacy.dotColor("camera", dots.base)
      color: Qt.hsla(hsl.h, hsl.s, hsl.l, 1)
    }
    Rectangle {
      visible: pill.micInUse
      width: 8; height: 8; radius: 4
      readonly property var hsl: Privacy.dotColor("mic", dots.base)
      color: Qt.hsla(hsl.h, hsl.s, hsl.l, 1)
    }
  }

  // ---- right ear ----
  Text {
    id: earLabel
    textFormat: Text.PlainText
    text: pill.earText
    color: pill.textColor
    opacity: pill.topActivity ? 1 : 0.8
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.bodySmall
    font.features: { "tnum": 1 }
    maximumLineCount: 1
    elide: Text.ElideRight
    width: Math.min(implicitWidth, Math.max(0, pill.textWidth - pill.pad - (pill.mediaPlaying ? eq.width + Commons.Style.spacing.sm : 0)))
    horizontalAlignment: Text.AlignRight
    anchors.right: parent.right
    anchors.rightMargin: pill.pad
    anchors.verticalCenter: parent.verticalCenter
  }

  Equalizer {
    id: eq
    visible: pill.mediaPlaying
    playing: pill.mediaPlaying
    color: pill.tint
    width: 12
    height: 11
    anchors.right: earLabel.left
    anchors.rightMargin: Commons.Style.spacing.sm
    anchors.verticalCenter: parent.verticalCenter
  }
}
