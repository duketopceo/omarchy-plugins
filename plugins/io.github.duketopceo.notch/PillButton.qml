import QtQuick

// Pill button. `primary` is the screen's one contrast action (white fill);
// everything else stays a quiet tinted pill. Acts on press; hover is instant.
Rectangle {
  id: btn
  property string text: ""
  property bool primary: false
  property bool enabledButton: true
  signal clicked()

  implicitWidth: Math.max(88, label.implicitWidth + 28)
  implicitHeight: 28
  width: implicitWidth
  height: implicitHeight
  radius: Tk.r(height / 2)
  opacity: enabledButton ? 1 : 0.4
  color: primary ? (hit.containsMouse ? Tk.alpha(Tk.text, 0.88) : Tk.text)
                 : (hit.containsMouse ? Tk.tint(0.22) : Tk.tint(0.12))
  border.width: Tk.pxl ? Tk.bw(1) : 0
  border.color: Tk.edge

  Text {
    id: label
    anchors.centerIn: parent
    textFormat: Text.PlainText
    text: btn.text
    color: btn.primary ? Tk.island : Tk.text
    font.family: Tk.family
    font.pixelSize: Tk.fs.body
    font.weight: btn.primary ? Font.DemiBold : Font.Normal
  }
  MouseArea {
    id: hit
    anchors.fill: parent
    hoverEnabled: true
    enabled: btn.enabledButton
    cursorShape: Qt.PointingHandCursor
    onPressed: btn.clicked()
  }
}
