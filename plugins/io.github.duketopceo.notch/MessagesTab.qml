import QtQuick
import Quickshell
import qs.Commons as Commons

// Messages tab for the expanded panel. `notch` is the root Notch item; its
// `messages` object is the MessagesActivity. Clicking a thread opens it in
// Blip's own panel; "Mark all read" is a deliberate click, never automatic.
Item {
  id: tab

  property var notch: null
  property color textColor: Commons.Color.foreground
  property color dimColor: Commons.Color.muted
  property string family: Commons.Style.font.family

  readonly property var feed: notch ? notch.messages : null
  readonly property bool offline: !feed || !feed.online
  readonly property var rows: feed ? feed.rows : []

  opacity: offline ? 0.45 : 1

  Text {
    id: head
    textFormat: Text.PlainText
    anchors.left: parent.left
    anchors.top: parent.top
    text: tab.offline ? "Messages · Mac offline" : "Messages"
    color: tab.dimColor
    font.family: tab.family
    font.pixelSize: 10
  }

  Rectangle {
    id: markAll
    anchors.right: parent.right
    anchors.verticalCenter: head.verticalCenter
    width: markLabel.implicitWidth + 14
    height: 18
    radius: 9
    visible: !!tab.feed && tab.feed.unread > 0
    color: markHit.containsMouse ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(1, 1, 1, 0.1)
    Text {
      id: markLabel
      textFormat: Text.PlainText
      anchors.centerIn: parent
      text: "Mark all read"
      color: tab.textColor
      font.family: tab.family
      font.pixelSize: 10
    }
    MouseArea {
      id: markHit
      anchors.fill: parent
      hoverEnabled: true
      onClicked: if (tab.feed) tab.feed.markAllRead()
    }
  }

  Column {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: head.bottom
    anchors.topMargin: 6
    spacing: 2

    Text {
      textFormat: Text.PlainText
      visible: tab.rows.length === 0
      text: tab.offline ? "Blip is not reachable" : "No unread messages"
      color: tab.dimColor
      font.family: tab.family
      font.pixelSize: 11
    }

    Repeater {
      model: tab.rows
      Rectangle {
        id: row
        required property var modelData
        width: parent.width
        height: 22
        radius: 6
        color: rowHit.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : "transparent"

        Rectangle {
          id: dot
          width: 7; height: 7; radius: 4
          anchors.left: parent.left
          anchors.leftMargin: 4
          anchors.verticalCenter: parent.verticalCenter
          visible: row.modelData.unread > 0
          color: "#4aa3ff"
        }
        Text {
          id: who
          textFormat: Text.PlainText
          anchors.left: dot.right
          anchors.leftMargin: 6
          anchors.verticalCenter: parent.verticalCenter
          width: Math.min(implicitWidth, parent.width * 0.4)
          elide: Text.ElideRight
          text: row.modelData.name
          color: tab.textColor
          font.family: tab.family
          font.pixelSize: 11
          font.bold: row.modelData.unread > 0
        }
        Text {
          textFormat: Text.PlainText
          anchors.left: who.right
          anchors.leftMargin: 6
          anchors.right: parent.right
          anchors.rightMargin: 4
          anchors.verticalCenter: parent.verticalCenter
          elide: Text.ElideRight
          text: row.modelData.preview
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: 10
        }
        MouseArea {
          id: rowHit
          anchors.fill: parent
          hoverEnabled: true
          onClicked: if (tab.feed) tab.feed.openThread(row.modelData.chat)
        }
      }
    }
  }
}
