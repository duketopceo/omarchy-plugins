import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Widgets
import qs.Commons as Commons
import "Messages.js" as Messages

// Messages tab for the expanded panel (about 428x164 usable). `notch` is the
// root Notch item; its `messages` object is the MessagesActivity. Header: unread
// count, search, "Read" (mark all read) and "Open Blip". Rows are 44 px: avatar
// (Blip's cached photo, else initials on a hashed colour), name, one-line
// preview, relative time and an unread dot. Clicking a row opens that thread in
// Blip's panel. Nothing here sends a message; Blip's `compose` acts on whatever
// thread its panel has open, so a per-thread quick reply is deliberately absent.
Item {
  id: tab

  property var notch: null
  readonly property color textColor: notch && notch.textColor ? notch.textColor : Commons.Color.foreground
  readonly property color dimColor: notch && notch.dimColor ? notch.dimColor : Commons.Color.muted
  readonly property string family: notch && notch.fontFamily ? notch.fontFamily : Commons.Style.font.family

  implicitWidth: 428
  implicitHeight: 164

  readonly property var feed: notch ? notch.messages : null
  readonly property bool offline: !feed || !feed.online
  readonly property string banner: Messages.offlineLabel(!!feed && feed.running, !!feed && feed.online)
  readonly property var allRows: feed && feed.rows ? feed.rows : []
  readonly property var shown: Messages.filterRows(allRows, search.text)
  readonly property int unreadCount: feed ? feed.unread : Messages.totalUnread(allRows)

  property real now: Date.now()
  property var avatarSet: ({})
  readonly property string avatarDir: Quickshell.env("HOME") + "/.cache/blip/avatars"

  // Thread list and avatar index (both read-only) only while the tab is on screen.
  function load() {
    now = Date.now()
    if (feed && feed.online) feed.fetchThreads()
    if (!avatarProc.running) avatarProc.running = true
  }
  onVisibleChanged: if (visible) load()
  onFeedChanged: if (visible) load()
  Component.onCompleted: if (visible) load()
  Timer { interval: 15000; running: tab.visible; repeat: true; onTriggered: tab.load() }

  Process {
    id: avatarProc
    command: ["ls", "-1", tab.avatarDir]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: tab.avatarSet = Messages.parseAvatarList(text)
    }
  }

  // ---------------------------------------------------------------- header
  Item {
    id: head
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    height: 22

    Row {
      id: titleRow
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      spacing: 6
      Text {
        textFormat: Text.PlainText
        anchors.verticalCenter: parent.verticalCenter
        text: "Messages"
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: 11
        font.bold: true
      }
      Rectangle {
        visible: tab.unreadCount > 0
        anchors.verticalCenter: parent.verticalCenter
        height: 15
        width: Math.max(15, countLabel.implicitWidth + 8)
        radius: 8
        color: "#4aa3ff"
        Text {
          id: countLabel
          textFormat: Text.PlainText
          anchors.centerIn: parent
          text: tab.feed ? tab.feed.badge || String(tab.unreadCount) : String(tab.unreadCount)
          color: "#06121f"
          font.family: tab.family
          font.pixelSize: 9
          font.bold: true
        }
      }
    }

    Rectangle {
      id: openBtn
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      width: openLabel.implicitWidth + 16
      height: 20
      radius: 10
      color: openHit.containsMouse ? Qt.rgba(1, 1, 1, 0.24) : Qt.rgba(1, 1, 1, 0.1)
      Text {
        id: openLabel
        textFormat: Text.PlainText
        anchors.centerIn: parent
        text: "Open Blip"
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: 10
      }
      MouseArea {
        id: openHit
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: if (tab.feed) tab.feed.openBlip()
      }
    }

    Rectangle {
      id: readBtn
      visible: tab.unreadCount > 0
      anchors.right: openBtn.left
      anchors.rightMargin: 4
      anchors.verticalCenter: parent.verticalCenter
      width: readLabel.implicitWidth + 16
      height: 20
      radius: 10
      color: readHit.containsMouse ? Qt.rgba(1, 1, 1, 0.24) : Qt.rgba(1, 1, 1, 0.1)
      Text {
        id: readLabel
        textFormat: Text.PlainText
        anchors.centerIn: parent
        text: "Read all"
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: 10
      }
      MouseArea {
        id: readHit
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: if (tab.feed) tab.feed.markAllRead()
      }
    }

    Rectangle {
      anchors.left: titleRow.right
      anchors.leftMargin: 10
      anchors.right: readBtn.visible ? readBtn.left : openBtn.left
      anchors.rightMargin: 6
      anchors.verticalCenter: parent.verticalCenter
      height: 20
      radius: 10
      color: Qt.rgba(1, 1, 1, 0.07)
      border.width: search.activeFocus ? 1 : 0
      border.color: Qt.rgba(1, 1, 1, 0.3)
      TextInput {
        id: search
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        verticalAlignment: TextInput.AlignVCenter
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: 10
        clip: true
        selectByMouse: true
        Text {
          textFormat: Text.PlainText
          visible: search.text === "" && !search.activeFocus
          anchors.verticalCenter: parent.verticalCenter
          text: "Search"
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: 10
        }
      }
    }
  }

  // ---------------------------------------------------------------- banner
  Rectangle {
    id: banner
    visible: tab.banner !== ""
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: head.bottom
    anchors.topMargin: 4
    height: visible ? 16 : 0
    radius: 8
    color: Qt.rgba(1, 1, 1, 0.06)
    opacity: 0.7
    Text {
      textFormat: Text.PlainText
      anchors.centerIn: parent
      text: tab.banner
      color: tab.dimColor
      font.family: tab.family
      font.pixelSize: 10
    }
  }

  // ---------------------------------------------------------------- list
  Item {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: banner.visible ? banner.bottom : head.bottom
    anchors.topMargin: 4
    anchors.bottom: parent.bottom
    opacity: tab.offline ? 0.45 : 1

    Text {
      textFormat: Text.PlainText
      visible: tab.shown.length === 0
      anchors.centerIn: parent
      text: search.text !== "" ? "No matches" : tab.offline ? "Nothing to show while offline" : "No conversations yet"
      color: tab.dimColor
      font.family: tab.family
      font.pixelSize: 11
    }

    NotchScroll {
      anchors.fill: parent
      rowHeight: 44
      contentHeight: list.height
      contentWidth: width

      Column {
        id: list
        width: parent.width

        Repeater {
          model: tab.shown
          Rectangle {
            id: row
            required property var modelData
            readonly property bool hasPhoto: !!tab.avatarSet[modelData.avatar]
            width: list.width
            height: 44
            radius: 8
            color: rowHit.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : "transparent"

            Item {
              id: avatar
              width: 32; height: 32
              anchors.left: parent.left
              anchors.leftMargin: 6
              anchors.verticalCenter: parent.verticalCenter

              Rectangle {
                anchors.fill: parent
                radius: 16
                color: row.modelData.color
                Text {
                  textFormat: Text.PlainText
                  anchors.centerIn: parent
                  text: row.modelData.initials
                  color: "#f2f2f4"
                  font.family: tab.family
                  font.pixelSize: 12
                  font.bold: true
                }
              }
              ClippingRectangle {
                anchors.fill: parent
                radius: 16
                color: "transparent"
                visible: photo.status === Image.Ready
                Image {
                  id: photo
                  anchors.fill: parent
                  source: row.hasPhoto ? "file://" + tab.avatarDir + "/" + row.modelData.avatar + ".jpg" : ""
                  sourceSize.width: 64
                  sourceSize.height: 64
                  fillMode: Image.PreserveAspectCrop
                  asynchronous: true
                }
              }
            }

            Text {
              id: when
              textFormat: Text.PlainText
              anchors.right: parent.right
              anchors.rightMargin: 8
              anchors.top: parent.top
              anchors.topMargin: 7
              text: Messages.relTime(row.modelData.ts, tab.now)
              color: row.modelData.unread > 0 ? "#4aa3ff" : tab.dimColor
              font.family: tab.family
              font.pixelSize: 10
            }
            Text {
              textFormat: Text.PlainText
              anchors.left: avatar.right
              anchors.leftMargin: 9
              anchors.right: when.left
              anchors.rightMargin: 8
              anchors.top: parent.top
              anchors.topMargin: 6
              elide: Text.ElideRight
              maximumLineCount: 1
              text: row.modelData.name
              color: tab.textColor
              font.family: tab.family
              font.pixelSize: 12
              font.bold: true
            }
            Text {
              textFormat: Text.PlainText
              anchors.left: avatar.right
              anchors.leftMargin: 9
              anchors.right: dot.visible ? dot.left : parent.right
              anchors.rightMargin: 8
              anchors.bottom: parent.bottom
              anchors.bottomMargin: 6
              elide: Text.ElideRight
              maximumLineCount: 1
              text: row.modelData.preview
              color: row.modelData.unread > 0 ? tab.textColor : tab.dimColor
              font.family: tab.family
              font.pixelSize: 11
            }
            Rectangle {
              id: dot
              visible: row.modelData.unread > 0
              width: 8; height: 8; radius: 4
              anchors.right: parent.right
              anchors.rightMargin: 10
              anchors.bottom: parent.bottom
              anchors.bottomMargin: 8
              color: "#4aa3ff"
            }
            MouseArea {
              id: rowHit
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: if (tab.feed) tab.feed.openThread(row.modelData.chat)
            }
          }
        }
      }
    }
  }
}
