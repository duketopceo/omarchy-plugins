import QtQuick
import qs.Commons as Commons
import "Expand.js" as Expand

// Small month calendar: month title, weekday letters, day grid with today lit.
Item {
  id: cal

  property date today: new Date()
  property int firstDay: 0   // 0 = Sunday, 1 = Monday
  property color textColor: Commons.Color.foreground
  property color dimColor: Commons.Color.muted
  property color accentColor: Commons.Color.accent
  property string family: Commons.Style.font.family

  readonly property var rows: Expand.monthGrid(today.getFullYear(), today.getMonth(), firstDay)
  readonly property var labels: Expand.weekdayLabels(firstDay)
  readonly property int cellW: Math.floor(width / 7)
  readonly property int cellH: 14

  implicitWidth: 7 * 22
  implicitHeight: 16 + cellH * (rows.length + 1)

  Text {
    textFormat: Text.PlainText
    id: title
    text: Qt.formatDate(cal.today, "MMMM yyyy")
    color: cal.textColor
    font.family: cal.family
    font.pixelSize: 11
    font.weight: Font.DemiBold
  }

  Grid {
    anchors.top: title.bottom
    anchors.topMargin: 4
    columns: 7

    Repeater {
      model: cal.labels
      Text {
        textFormat: Text.PlainText
        required property string modelData
        width: cal.cellW
        height: cal.cellH
        horizontalAlignment: Text.AlignHCenter
        text: modelData
        color: cal.dimColor
        font.family: cal.family
        font.pixelSize: 9
      }
    }

    Repeater {
      model: [].concat.apply([], cal.rows)
      Item {
        id: cell
        required property int modelData
        readonly property bool isToday: modelData === cal.today.getDate()
        width: cal.cellW
        height: cal.cellH

        Rectangle {
          anchors.centerIn: parent
          width: 14
          height: 14
          radius: 7
          visible: cell.isToday
          color: cal.accentColor
        }
        Text {
          textFormat: Text.PlainText
          anchors.centerIn: parent
          text: cell.modelData > 0 ? String(cell.modelData) : ""
          color: cell.isToday ? "black" : cal.textColor
          font.family: cal.family
          font.pixelSize: 9
          font.weight: cell.isToday ? Font.Bold : Font.Normal
        }
      }
    }
  }
}
