import QtQuick
import qs.Commons as Commons
import "Watchlist.js" as Watchlist

// Stock watchlist slide. Notched screens: one symbol in the right ear
// (symbol and change over price, to fit 96 px). Virtual notch: two symbols
// side by side, each "SYM price change".
Item {
  id: slide

  property var quotes: []         // [{symbol, price, changePercent}]
  property int index: 0           // which slide of the rotation to show
  property bool notched: true
  property int maxWidth: 88
  property string family: ""

  // Up color follows the notch theme (Notch.qml passes root.goodColor);
  // the default keeps this slide usable standalone.
  property color upColor: Tk.good

  readonly property int perSlide: Watchlist.perSlide(notched, 2)
  readonly property var shown: Watchlist.slide(quotes, index, perSlide)
  readonly property int slides: Watchlist.slideCount(quotes.length, perSlide)

  // Up uses the theme's good color (upColor); down is the theme's urgent
  // color; flat is muted.
  function tint(pct) {
    var d = Watchlist.direction(pct)
    return d === "up" ? upColor : (d === "down" ? Tk.urgent : Tk.dim)
  }

  implicitWidth: Math.min(maxWidth, row.implicitWidth)
  implicitHeight: row.implicitHeight
  width: implicitWidth
  height: implicitHeight

  Row {
    id: row
    spacing: 10
    Repeater {
      model: slide.shown
      delegate: Item {
        id: entry
        required property var modelData
        readonly property real share: (slide.maxWidth - (slide.shown.length - 1) * row.spacing) / Math.max(1, slide.shown.length)
        implicitWidth: Math.min(share, notchedCol.visible ? notchedCol.implicitWidth : flat.implicitWidth)
        implicitHeight: notchedCol.visible ? notchedCol.implicitHeight : flat.implicitHeight
        width: implicitWidth
        height: implicitHeight

        // Ear: the ticker tall on the left, price over change on the right.
        Row {
          id: notchedCol
          visible: slide.notched
          spacing: 5
          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: entry.modelData.symbol
            textFormat: Text.PlainText
            color: Tk.text
            font.family: slide.family
            font.pixelSize: Tk.pxl ? 14 : 15
            font.weight: Font.DemiBold
          }
          Column {
            anchors.verticalCenter: parent.verticalCenter
            spacing: Tk.pxl ? -1 : 0
            Text {
              text: Watchlist.formatPrice(entry.modelData.price)
              textFormat: Text.PlainText
              color: Tk.dim
              font.family: slide.family
              font.pixelSize: Tk.pxl ? 9 : 10
            }
            Text {
              text: Watchlist.formatChange(entry.modelData.changePercent)
              textFormat: Text.PlainText
              color: slide.tint(entry.modelData.changePercent)
              font.family: slide.family
              font.pixelSize: Tk.pxl ? 9 : 10
            }
          }
        }

        // Virtual notch: one line, "SYM price change".
        Row {
          id: flat
          visible: !slide.notched
          spacing: 4
          Text {
            text: entry.modelData.symbol
            textFormat: Text.PlainText
            color: Tk.text
            font.family: slide.family
            font.pixelSize: 11
            font.weight: Font.DemiBold
          }
          Text {
            text: Watchlist.formatPrice(entry.modelData.price)
            textFormat: Text.PlainText
            color: Tk.dim
            font.family: slide.family
            font.pixelSize: 11
          }
          Text {
            text: Watchlist.formatChange(entry.modelData.changePercent)
            textFormat: Text.PlainText
            color: slide.tint(entry.modelData.changePercent)
            font.family: slide.family
            font.pixelSize: 11
          }
        }
      }
    }
  }
}
