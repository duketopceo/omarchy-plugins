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
  readonly property color textColor: notch && notch.textColor ? notch.textColor : Tk.text
  readonly property color dimColor: notch && notch.dimColor ? notch.dimColor : Tk.dim
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
        font.pixelSize: Tk.fs.bodySmall
        font.bold: true
      }
      Rectangle {
        visible: tab.unreadCount > 0
        anchors.verticalCenter: parent.verticalCenter
        height: 15
        width: Math.max(15, countLabel.implicitWidth + 8)
        radius: Tk.r(8)
        color: tab.notch && tab.notch.themeObj ? tab.notch.themeObj.info : Tk.info
        Text {
          id: countLabel
          textFormat: Text.PlainText
          anchors.centerIn: parent
          text: tab.feed ? tab.feed.badge || String(tab.unreadCount) : String(tab.unreadCount)
          color: tab.notch && tab.notch.themeObj ? tab.notch.themeObj.bubbleText : Tk.bubbleText
          font.family: tab.family
          font.pixelSize: Tk.fs.caption
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
      radius: Tk.r(10)
      color: openHit.containsMouse ? Tk.tint(0.24) : Tk.tint(0.1)
      Text {
        id: openLabel
        textFormat: Text.PlainText
        anchors.centerIn: parent
        text: "Open Blip"
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: Tk.fs.caption
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
      radius: Tk.r(10)
      color: readHit.containsMouse ? Tk.tint(0.24) : Tk.tint(0.1)
      Text {
        id: readLabel
        textFormat: Text.PlainText
        anchors.centerIn: parent
        text: "Read all"
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: Tk.fs.caption
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
      radius: Tk.r(10)
      color: Tk.tint(0.07)
      border.width: search.activeFocus ? 1 : 0
      border.color: Tk.tint(0.3)
      TextInput {
        id: search
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        verticalAlignment: TextInput.AlignVCenter
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: Tk.fs.caption
        clip: true
        selectByMouse: true
        Text {
          textFormat: Text.PlainText
          visible: search.text === "" && !search.activeFocus
          anchors.verticalCenter: parent.verticalCenter
          text: "Search"
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: Tk.fs.caption
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
    radius: Tk.r(8)
    color: Tk.tint(0.06)
    opacity: 0.7
    Text {
      textFormat: Text.PlainText
      anchors.centerIn: parent
      text: tab.banner
      color: tab.dimColor
      font.family: tab.family
      font.pixelSize: Tk.fs.caption
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
      text: search.text !== "" ? "No matches" : tab.offline ? "Conversations return once Blip is reachable" : "No conversations yet"
      color: tab.dimColor
      font.family: tab.family
      font.pixelSize: Tk.fs.bodySmall
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
            radius: Tk.r(8)
            color: rowHit.containsMouse ? Tk.tint(0.1) : "transparent"

            Item {
              id: avatar
              width: 32; height: 32
              anchors.left: parent.left
              anchors.leftMargin: 6
              anchors.verticalCenter: parent.verticalCenter

              Rectangle {
                anchors.fill: parent
                radius: Tk.r(16)
                color: row.modelData.color
                Text {
                  textFormat: Text.PlainText
                  anchors.centerIn: parent
                  text: row.modelData.initials
                  color: tab.notch && tab.notch.themeObj ? tab.notch.themeObj.bubble : Tk.bubble
                  font.family: tab.family
                  font.pixelSize: Tk.fs.body
                  font.bold: true
                }
              }
              ClippingRectangle {
                anchors.fill: parent
                radius: Tk.r(16)
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
              color: row.modelData.unread > 0 ? (tab.notch && tab.notch.themeObj ? tab.notch.themeObj.info : Tk.info) : tab.dimColor
              font.family: tab.family
              font.pixelSize: Tk.fs.caption
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
              font.pixelSize: Tk.fs.body
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
              font.pixelSize: Tk.fs.bodySmall
            }
            Rectangle {
              id: dot
              visible: row.modelData.unread > 0
              width: 8; height: 8; radius: Tk.r(4)
              anchors.right: parent.right
              anchors.rightMargin: 10
              anchors.bottom: parent.bottom
              anchors.bottomMargin: 8
              color: tab.notch && tab.notch.themeObj ? tab.notch.themeObj.info : Tk.info
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
