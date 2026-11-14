import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import "Screenshots.js" as Screenshots

// Screenshots tab for snapdex: the last 8 captioned screenshots with their
// captions, the unprocessed count, "Process now" and the auto on/off switch.
// All work is snapdex's own `snapdex-ctl`; this tab only calls it. It polls
// (every 20 s) only while visible. Click a thumbnail to open it.
Item {
  id: tab

  property var notch: null
  readonly property color textColor: notch ? notch.textColor : Tk.white
  readonly property color dimColor: notch ? notch.dimColor : "gray"
  readonly property string family: notch ? notch.fontFamily : ""
  readonly property string home: Quickshell.env("HOME")

  property var snap: Screenshots.parsePanel("")
  property bool busy: false
  // Where shots are saved: snapdex's own destination, else the Omarchy 4.5 default.
  property bool libraryExists: false
  FileView {
    path: Screenshots.libraryIndexPath(tab.home)
    printErrors: false
    onLoaded: tab.libraryExists = true
    onLoadFailed: tab.libraryExists = false
  }
  readonly property var dirs: Screenshots.folders(snap, home, libraryExists)
  readonly property string folder: dirs.library
  property string busyLabel: ""

  function refresh() { if (!panelProc.running) { panelProc.command = Screenshots.ctlArgs(tab.home, ["panel"]); panelProc.running = true } }
  function control(args, label) {
    if (ctrlProc.running) return
    tab.busy = true
    tab.busyLabel = label
    ctrlProc.command = Screenshots.ctlArgs(tab.home, args)
    ctrlProc.running = true
  }
  onVisibleChanged: if (visible) refresh()
  Component.onCompleted: if (visible) refresh()
  Timer { interval: 20000; running: tab.visible; repeat: true; onTriggered: tab.refresh() }

  Process {
    id: panelProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 400000) tab.snap = Screenshots.parsePanel(text)
    }
  }
  Process {
    id: ctrlProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 400000) { var d = Screenshots.parsePanel(text); if (d.ok) tab.snap = d }
    }
    onExited: { tab.busy = false; tab.refresh() }
  }
  Process { id: openProc }

  // ------------------------------------------------------------ status row
  Item {
    id: bar
    anchors.top: parent.top
    anchors.left: parent.left
    anchors.right: parent.right
    height: 28

    Text {
      textFormat: Text.PlainText
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      text: tab.busy ? tab.busyLabel : (tab.snap.ok ? Screenshots.pendingText(tab.snap.pending) : "Snapdex unavailable")
      color: tab.snap.pending > 0 && !tab.busy ? Tk.accent : tab.dimColor
      font.family: tab.family
      font.pixelSize: Tk.fs.body
      font.weight: Font.DemiBold
    }

    Row {
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      spacing: 10

      Rectangle {
        id: folderBtn
        width: folderLabel.implicitWidth + 20
        height: 24
        radius: Tk.r(12)
        opacity: tab.folder !== "" ? 1 : 0.4
        color: folderHit.containsMouse ? Tk.tint(0.22) : Tk.tint(0.1)
        Text {
          id: folderLabel
          textFormat: Text.PlainText
          anchors.centerIn: parent
          text: "Open folder"
          color: tab.textColor
          font.family: tab.family
          font.pixelSize: Tk.fs.bodySmall
        }
        MouseArea {
          id: folderHit
          anchors.fill: parent
          hoverEnabled: true
          enabled: tab.folder !== ""
          cursorShape: Qt.PointingHandCursor
          onClicked: { openProc.command = ["/usr/bin/xdg-open", tab.folder]; openProc.running = true }
        }
      }

      Rectangle {
        id: processBtn
        width: processLabel.implicitWidth + 20
        height: 24
        radius: Tk.r(12)
        opacity: tab.snap.ok && !tab.busy ? 1 : 0.4
        color: processHit.containsMouse ? Tk.tint(0.22) : Tk.tint(0.1)
        Text {
          id: processLabel
          textFormat: Text.PlainText
          anchors.centerIn: parent
          text: "Process now"
          color: tab.textColor
          font.family: tab.family
          font.pixelSize: Tk.fs.bodySmall
        }
        MouseArea {
          id: processHit
          anchors.fill: parent
          hoverEnabled: true
          enabled: tab.snap.ok && !tab.busy
          cursorShape: Qt.PointingHandCursor
          onClicked: tab.control(["process"], "Processing")
        }
      }

      Row {
        spacing: 6
        anchors.verticalCenter: parent.verticalCenter
        Text {
          textFormat: Text.PlainText
          anchors.verticalCenter: parent.verticalCenter
          text: "Auto"
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: Tk.fs.bodySmall
        }
        PillSwitch {
          anchors.verticalCenter: parent.verticalCenter
          on: tab.snap.autoOn
          busy: tab.busy
          onColor: tab.notch && tab.notch.goodColor ? tab.notch.goodColor : Tk.good
          enabledSwitch: tab.snap.ok && tab.snap.autoKnown
          onToggled: tab.control(Screenshots.autoArgs(!tab.snap.autoOn), tab.snap.autoOn ? "Turning auto off" : "Turning auto on")
        }
      }
    }
  }

  Text {
    id: pathLine
    textFormat: Text.PlainText
    anchors.top: bar.bottom
    anchors.topMargin: 2
    anchors.left: parent.left
    anchors.right: parent.right
    elide: Text.ElideMiddle
    text: "Library " + Screenshots.shortPath(tab.dirs.library, tab.home) + (tab.dirs.separate ? "   Inbox " + Screenshots.shortPath(tab.dirs.inbox, tab.home) + " (" + tab.snap.pending + " pending)" : "  (renamed in place)")
    color: tab.dimColor
    font.family: tab.family
    font.pixelSize: Tk.fs.caption
  }

  // ------------------------------------------------------------ thumbnails
  Grid {
    id: grid
    anchors.top: pathLine.bottom
    anchors.topMargin: 8
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    columns: 4
    rowSpacing: 8
    columnSpacing: 8
    readonly property int cellW: Math.floor((width - 3 * columnSpacing) / 4)
    // Two rows share the full height; the caption sits under each thumbnail.
    readonly property int cellH: Math.floor((height - rowSpacing) / 2)

    Repeater {
      model: tab.snap.items
      Item {
        id: cell
        required property var modelData
        width: grid.cellW
        height: grid.cellH

        Rectangle {
          id: thumb
          width: parent.width
          height: cell.height - 20
          radius: Tk.r(8)
          color: Tk.tint(0.08)
          clip: true
          Image {
            anchors.fill: parent
            source: "file://" + cell.modelData.path
            sourceSize.width: 360
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            cache: false
          }
          Rectangle { anchors.fill: parent; radius: Tk.r(8); color: Tk.tint(hit.containsMouse ? 0.12 : 0) }
          MouseArea {
            id: hit
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: { openProc.command = ["/usr/bin/xdg-open", cell.modelData.path]; openProc.running = true }
          }
        }
        Text {
          textFormat: Text.PlainText
          anchors.top: thumb.bottom
          anchors.topMargin: 4
          width: parent.width
          elide: Text.ElideRight
          text: cell.modelData.caption
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: Tk.fs.caption
        }
      }
    }
  }

  Text {
    textFormat: Text.PlainText
    anchors.centerIn: grid
    visible: tab.snap.items.length === 0
    text: tab.snap.ok ? "No captioned screenshots yet" : ""
    color: tab.dimColor
    font.family: tab.family
    font.pixelSize: Tk.fs.bodySmall
  }
}
