import QtQuick

// Segmented choice: a short row of options, one selected. Use for choices of
// two to five values (a stepper is for open-ended numbers). Emits
// `picked(value)`; the owner stores it and passes it back in as `current`.
// Press selects (no overlay); hover is instant and only on the segment under
// the pointer.
Rectangle {
  id: seg
  property var options: []        // [{ value, label }]
  property var current: null
  signal picked(var value)

  implicitHeight: 26
  height: implicitHeight
  implicitWidth: row.width + 4
  width: implicitWidth
  radius: Tk.r(height / 2)
  color: Tk.tint(0.08)
  border.width: Tk.pxl ? Tk.bw(1) : 0
  border.color: Tk.edge

  Row {
    id: row
    x: 2
    anchors.verticalCenter: parent.verticalCenter
    spacing: 0
    Repeater {
      model: seg.options
      Rectangle {
        id: cell
        required property var modelData
        readonly property bool selected: seg.current === cell.modelData.value
        width: Math.max(40, lbl.implicitWidth + 20)
        height: seg.height - 4
        radius: Tk.r(height / 2)
        color: selected ? (Tk.pxl ? Tk.edge : Tk.alpha(Tk.accent, 0.3)) : (hit.containsMouse ? Tk.tint(0.14) : "transparent")
        Text {
          id: lbl
          anchors.centerIn: parent
          textFormat: Text.PlainText
          text: cell.modelData.label
          color: cell.selected && Tk.pxl ? Tk.accent : Tk.text
          font.family: Tk.family
          font.pixelSize: Tk.fs.bodySmall
        }
        MouseArea {
          id: hit
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onPressed: seg.picked(cell.modelData.value)
        }
      }
    }
  }
}
