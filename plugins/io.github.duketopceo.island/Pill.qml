import QtQuick 6.11
import qs.Commons as Commons
import "Privacy.js" as Privacy
import "Dnd.js" as Dnd
import "Presentation.js" as Presentation

// The compact pill's content. Left ear: the time (with the Do Not Disturb
// glyph beside it when on). Right ear: the top live activity (glyph and short
// ear text), or the short date when nothing is live. The temperature sits
// beside the time in the left ear, so it stays visible while media plays. While media is the top
// activity the right ear takes the Dynamic Island look instead: a rounded
// album-art thumbnail and equalizer bars tinted from the art, with no title
// text (the title is on the card). The time always stays left. The second activity
// is not drawn here: it is the window's detached bubble (KTD6). Mic and camera
// dots sit in a reserved slot at the right ear's inner edge, beside the camera
// (R8). Every label is single-line and elides; `wantEar` reports the natural
// width the ears would like so the window can size the pill to its content (KTD5).
Item {
  id: pill

  property date now: new Date()
  property int earWidth: 56
  // Width the right ear's label may use (the ear minus the dot slot).
  property int textWidth: 56
  property int dotSlot: 0
  property int cameraWidth: 160
  property color textColor: Commons.Color.popups.text
  // Media accent from the album art, or the theme accent.
  property color tint: Commons.Color.accent
  // From Activity.layout(): the top live activity, or null.
  property var topActivity: null
  property bool dnd: false
  // Unmuted unread messages (Blip): one small accent dot beside the time.
  property bool unread: false
  // Short temperature ("41°") beside the time in the left ear; "" hides it.
  property string weather: ""
  property bool micInUse: false
  property bool cameraInUse: false

  readonly property int pad: Commons.Style.spacing.lg
  // Width beside the time in the left ear: the Do Not Disturb glyph and the
  // unread dot, each with its gap. The time itself never moves or goes away.
  readonly property int dotSize: Presentation.DOT_SIZE - 2
  readonly property int leftExtras: (weatherText.visible ? weatherText.implicitWidth + Commons.Style.spacing.sm : 0)
    + (dndGlyph.visible ? dndGlyph.implicitWidth + Commons.Style.spacing.sm : 0)
    + (pill.unread ? pill.dotSize + Commons.Style.spacing.sm : 0)
  readonly property bool mediaTop: pill.topActivity !== null && pill.topActivity.id === "media"
  readonly property int thumbSize: Math.max(16, pill.height - Commons.Style.spacing.lg)
  readonly property string earText: pill.topActivity
    ? pill.topActivity.glyph + " " + pill.topActivity.text
    : Qt.formatDate(pill.now, "MMM d")
  // Natural width of the wider ear, padding included.
  readonly property int wantEar: Math.ceil(Math.max(
    timeText.implicitWidth + pill.leftExtras,
    pill.mediaTop ? pill.thumbSize + Commons.Style.spacing.md + eq.width : earLabel.implicitWidth) + pill.pad * 1.5)

  Face {
    id: timeText
    textFormat: Text.PlainText
    text: Qt.formatTime(pill.now, Qt.locale().timeFormat(Locale.ShortFormat))
    color: pill.textColor
    font.pixelSize: Commons.Style.font.bodySmall
    font.features: { "tnum": 1 }
    maximumLineCount: 1
    elide: Text.ElideRight
    width: Math.min(implicitWidth, Math.max(0, pill.earWidth - pill.pad - pill.leftExtras))
    anchors.left: parent.left
    anchors.leftMargin: pill.pad
    anchors.verticalCenter: parent.verticalCenter
  }

  // The album art thumbnail, right ear while media is on top, left of the bars.
  ArtImage {
    id: thumb
    visible: pill.mediaTop
    width: pill.thumbSize
    height: pill.thumbSize
    radius: Math.round(pill.thumbSize * 0.24)
    ink: pill.textColor
    glyphSize: Commons.Style.font.bodySmall
    source: pill.mediaTop ? String(pill.topActivity.art || "") : ""
    anchors.right: eq.left
    anchors.rightMargin: Commons.Style.spacing.md
    anchors.verticalCenter: parent.verticalCenter
  }

  // Temperature beside the time, dimmer so the time stays the anchor.
  Face {
    id: weatherText
    visible: pill.weather !== ""
    textFormat: Text.PlainText
    text: pill.weather
    color: pill.textColor
    opacity: 0.7
    font.pixelSize: Commons.Style.font.bodySmall
    font.features: { "tnum": 1 }
    anchors.left: timeText.right
    anchors.leftMargin: Commons.Style.spacing.sm
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
    anchors.left: weatherText.visible ? weatherText.right : timeText.right
    anchors.leftMargin: Commons.Style.spacing.sm
    anchors.verticalCenter: parent.verticalCenter
  }

  Rectangle {
    id: unreadDot
    visible: pill.unread
    width: pill.dotSize
    height: pill.dotSize
    radius: width / 2
    color: Commons.Color.accent
    anchors.left: dndGlyph.visible ? dndGlyph.right : (weatherText.visible ? weatherText.right : timeText.right)
    anchors.leftMargin: Commons.Style.spacing.sm
    anchors.verticalCenter: parent.verticalCenter
  }

  // ---- privacy dots: camera then mic, beside the camera cutout ----
  Row {
    id: dots
    visible: pill.dotSlot > 0
    spacing: Presentation.DOT_GAP
    x: pill.width / 2 + pill.cameraWidth / 2 + Presentation.DOT_PAD
    anchors.verticalCenter: parent.verticalCenter

    readonly property var base: ({ h: Commons.Color.urgent.hslHue, s: Commons.Color.urgent.hslSaturation, l: Commons.Color.urgent.hslLightness })

    Rectangle {
      visible: pill.cameraInUse
      width: Presentation.DOT_SIZE; height: Presentation.DOT_SIZE; radius: Presentation.DOT_SIZE / 2
      readonly property var hsl: Privacy.dotColor("camera", dots.base)
      color: Qt.hsla(hsl.h, hsl.s, hsl.l, 1)
    }
    Rectangle {
      visible: pill.micInUse
      width: Presentation.DOT_SIZE; height: Presentation.DOT_SIZE; radius: Presentation.DOT_SIZE / 2
      readonly property var hsl: Privacy.dotColor("mic", dots.base)
      color: Qt.hsla(hsl.h, hsl.s, hsl.l, 1)
    }
  }

  // ---- right ear ----
  Face {
    id: earLabel
    visible: !pill.mediaTop
    textFormat: Text.PlainText
    text: pill.earText
    color: pill.textColor
    opacity: pill.topActivity ? 1 : 0.8
    font.pixelSize: Commons.Style.font.bodySmall
    font.features: { "tnum": 1 }
    maximumLineCount: 1
    elide: Text.ElideRight
    width: Math.min(implicitWidth, Math.max(0, pill.textWidth - pill.pad))
    horizontalAlignment: Text.AlignRight
    anchors.right: parent.right
    anchors.rightMargin: pill.pad
    anchors.verticalCenter: parent.verticalCenter
  }

  // Playing: moving bars. Paused: the same bars, still and dimmed.
  Equalizer {
    id: eq
    visible: pill.mediaTop
    levels: [0.5, 0.9, 0.6, 1.0, 0.7]
    playing: pill.mediaTop && pill.topActivity.playing === true
    color: pill.tint
    opacity: eq.playing ? 1 : 0.5
    width: 18
    height: 14
    anchors.right: parent.right
    anchors.rightMargin: pill.pad
    anchors.verticalCenter: parent.verticalCenter
  }
}
