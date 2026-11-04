import QtQuick

// Small on/off pill. Emits `toggled()`; the owner flips its own state.
Rectangle {
  id: sw
  property bool on: false
  property bool busy: false
  property bool enabledSwitch: true
  property color onColor: "#6fbf73"
  signal toggled()

  width: 34
  height: 18
  radius: 9
  color: on ? onColor : Qt.rgba(1, 1, 1, 0.16)
  opacity: enabledSwitch ? (busy ? 0.6 : 1) : 0.35
  Behavior on color { ColorAnimation { duration: 140 } }

  Rectangle {
    width: 14; height: 14; radius: 7
    anchors.verticalCenter: parent.verticalCenter
    x: sw.on ? sw.width - width - 2 : 2
    color: "white"
    Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutQuad } }
  }
  MouseArea {
    anchors.fill: parent
    enabled: sw.enabledSwitch && !sw.busy
    cursorShape: Qt.PointingHandCursor
    onClicked: sw.toggled()
  }
}
