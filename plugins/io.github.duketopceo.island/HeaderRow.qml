import QtQuick 6.11
import qs.Commons as Commons
import "Dnd.js" as Dnd
import "Presentation.js" as Presentation
import "Privacy.js" as Privacy

// The card's header line: time and date (and weather on Home) on the left;
// status dots (Home), the Do Not Disturb bell and the mic and camera dots on
// the right. The bell and dots are the ones the pill shows.
Item {
  id: header

  property var island: null
  property date now: new Date()
  property bool showWeather: false
  property bool showStatus: false
  // Music keeps the Now Playing header from 0.3: "time · date" in body size.
  property bool compact: false
  readonly property color textColor: Commons.Color.popups.text

  signal openPage(string id)

  implicitHeight: header.compact ? compactText.implicitHeight : Math.ceil(Commons.Style.font.heading * 1.5)

  Row {
    anchors.left: parent.left
    anchors.verticalCenter: parent.verticalCenter
    spacing: Commons.Style.spacing.lg

    Text {
      id: compactText
      visible: header.compact
      textFormat: Text.PlainText
      text: Qt.formatTime(header.now, Qt.locale().timeFormat(Locale.ShortFormat)) + "  \u00b7  " + Qt.formatDate(header.now, "ddd MMM d")
      color: header.textColor
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.body
      font.features: { "tnum": 1 }
      anchors.verticalCenter: parent.verticalCenter
    }
    Text {
      visible: !header.compact
      textFormat: Text.PlainText
      text: Qt.formatTime(header.now, Qt.locale().timeFormat(Locale.ShortFormat))
      color: header.textColor
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.heading
      font.bold: true
      font.features: { "tnum": 1 }
      anchors.verticalCenter: parent.verticalCenter
    }
    Text {
      visible: !header.compact
      textFormat: Text.PlainText
      text: Qt.formatDate(header.now, "ddd MMM d")
      color: header.textColor
      opacity: 0.8
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.body
      anchors.verticalCenter: parent.verticalCenter
    }
    Text {
      visible: header.showWeather && header.island !== null && header.island.weather !== null
      textFormat: Text.PlainText
      text: visible ? "·  " + header.island.weather.temp : ""
      color: header.textColor
      opacity: 0.8
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.body
      anchors.verticalCenter: parent.verticalCenter
    }
  }

  Row {
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    spacing: Commons.Style.spacing.lg

    // Unread messages (Home only; nothing at zero). Opens the Messages page.
    HoverButton {
      id: unreadBtn
      readonly property int unread: header.island !== null && header.island.messages ? header.island.messages.unread : 0
      visible: header.showStatus && unread > 0
      hint: "Open Messages"
      anchors.verticalCenter: parent.verticalCenter
      width: unreadText.implicitWidth + Commons.Style.spacing.huge
      height: Math.ceil(Commons.Style.font.bodySmall * 1.9)
      radius: height / 2
      onClicked: header.openPage("messages")

      Txt {
        id: unreadText
        anchors.centerIn: parent
        width: implicitWidth
        kind: "caption"
        color: Commons.Color.accent
        opacity: 1
        text: unreadBtn.unread + " unread"
      }
    }

    Repeater {
      model: header.showStatus && header.island ? header.island.homeDots : []

      Row {
        required property var modelData
        spacing: Commons.Style.spacing.sm
        anchors.verticalCenter: parent.verticalCenter
        Rectangle {
          width: Presentation.DOT_SIZE - 2; height: width; radius: width / 2
          anchors.verticalCenter: parent.verticalCenter
          color: modelData.on ? Commons.Color.accent : Commons.Color.muted
        }
        Text {
          textFormat: Text.PlainText
          text: modelData.text
          color: header.textColor
          opacity: modelData.on ? 0.9 : 0.55
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.bodySmall
          anchors.verticalCenter: parent.verticalCenter
        }
      }
    }

    Text {
      visible: header.island !== null && header.island.dndOn === true
      textFormat: Text.PlainText
      text: Dnd.GLYPH
      color: header.textColor
      opacity: 0.8
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.body
      anchors.verticalCenter: parent.verticalCenter
    }
    Rectangle {
      visible: header.island !== null && header.island.cameraInUse === true
      width: Presentation.DOT_SIZE; height: Presentation.DOT_SIZE; radius: Presentation.DOT_SIZE / 2
      anchors.verticalCenter: parent.verticalCenter
      readonly property var hsl: Privacy.dotColor("camera", { h: Commons.Color.urgent.hslHue, s: Commons.Color.urgent.hslSaturation, l: Commons.Color.urgent.hslLightness })
      color: Qt.hsla(hsl.h, hsl.s, hsl.l, 1)
    }
    Rectangle {
      visible: header.island !== null && header.island.micInUse === true
      width: Presentation.DOT_SIZE; height: Presentation.DOT_SIZE; radius: Presentation.DOT_SIZE / 2
      anchors.verticalCenter: parent.verticalCenter
      readonly property var hsl: Privacy.dotColor("mic", { h: Commons.Color.urgent.hslHue, s: Commons.Color.urgent.hslSaturation, l: Commons.Color.urgent.hslLightness })
      color: Qt.hsla(hsl.h, hsl.s, hsl.l, 1)
    }
  }
}
