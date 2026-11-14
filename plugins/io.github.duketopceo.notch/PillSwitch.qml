import QtQuick

// Small on/off pill. Emits `toggled()`; the owner flips its own state.
Rectangle {
  id: sw
  property bool on: false
  property bool busy: false
  property bool enabledSwitch: true
  property color onColor: Tk.good
  signal toggled()

  width: 34
  height: 18
  radius: Tk.r(9)
  border.width: Tk.pxl ? Tk.bw(1) : 0
  border.color: Tk.edge
  color: on ? onColor : Tk.tint(0.16)
  opacity: enabledSwitch ? (busy ? 0.6 : 1) : 0.35
  Behavior on color { ColorAnimation { duration: Tk.ms(140) } }

  Rectangle {
    width: 14; height: 14; radius: Tk.r(7)
    anchors.verticalCenter: parent.verticalCenter
    x: Tk.px(sw.on ? sw.width - width - 2 : 2)
    color: Tk.white
    Behavior on x { NumberAnimation { duration: Tk.ms(140); easing.type: Easing.OutQuad } }
  }
  MouseArea {
    anchors.fill: parent
    enabled: sw.enabledSwitch && !sw.busy
    cursorShape: Qt.PointingHandCursor
    onClicked: sw.toggled()
  }
}
