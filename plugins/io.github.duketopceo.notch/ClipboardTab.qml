import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import "Clipboard.js" as Clip

// Clipboard tab (R7): the last dozen copies from cliphist. Click a row to put
// it back on the clipboard (wl-copy); links get Open, file paths get Folder.
// Entries that look like credentials show "Hidden" instead of their text; a
// click still copies them. Hidden by the capability probe without cliphist.
// Nothing here logs or stores clipboard text: previews live in `entries`
// while the tab is visible and are dropped when it closes.
Item {
  id: tab

  property var notch: null
  // Test hook: a cliphist-format string used instead of running cliphist.
  readonly property string fixture: notch && notch.clipFixture ? String(notch.clipFixture) : ""

  readonly property color textColor: notch ? notch.textColor : Tk.white
  readonly property color dimColor: notch ? notch.dimColor : "gray"
  readonly property string family: notch ? notch.fontFamily : ""

  property var fetched: []
  readonly property var entries: fixture !== "" ? Clip.parseList(fixture) : fetched
  property bool fetchedOnce: false
  readonly property bool loaded: fixture !== "" || fetchedOnce
  property string flash: ""    // "Copied" for a moment after a click

  function refresh() {
    if (fixture !== "" || !visible || lister.running) return
    lister.running = true
  }
  onVisibleChanged: { if (visible) refresh(); else fetched = [] }
  Component.onCompleted: refresh()

  Process {
    id: lister
    command: Clip.listArgs(Clip.MAX_ENTRIES)
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: { if (text.length < 200000) tab.fetched = Clip.parseList(text); tab.fetchedOnce = true }
    }
  }
  Timer { interval: 4000; running: tab.visible && tab.fixture === ""; repeat: true; onTriggered: tab.refresh() }

  Timer { id: flashOff; interval: 1400; onTriggered: tab.flash = "" }
  function run(argv, say) {
    if (!argv) return
    Quickshell.execDetached(argv)
    if (say) { flash = say; flashOff.restart() }
  }

  readonly property var kindGlyph: ({ text: "\u{F09A8}", link: "\u{F0337}", path: "\u{F024B}", image: "\u{F02E9}" })

  Item {
    id: head
    width: parent.width
    height: 30
    Text {
      anchors.verticalCenter: parent.verticalCenter
      textFormat: Text.PlainText
      text: "Clipboard"
      color: tab.textColor
      font.family: tab.family
      font.pixelSize: Commons.Style.font.title
      font.weight: Font.DemiBold
    }
    Text {
      anchors.verticalCenter: parent.verticalCenter
      anchors.right: parent.right
      textFormat: Text.PlainText
      text: tab.flash !== "" ? tab.flash : "Click an entry to copy it"
      color: tab.flash !== "" ? Tk.accent : tab.dimColor
      font.family: tab.family
      font.pixelSize: Tk.fs.caption
    }
  }

  Text {
    visible: tab.loaded && tab.entries.length === 0
    anchors.centerIn: parent
    textFormat: Text.PlainText
    text: "Nothing copied yet"
    color: tab.dimColor
    font.family: tab.family
    font.pixelSize: Tk.fs.body
  }

  NotchScroll {
    id: list
    anchors.top: head.bottom
    anchors.topMargin: 6
    anchors.bottom: parent.bottom
    anchors.left: parent.left
    anchors.right: parent.right
    rowHeight: 34
    contentHeight: col.height
    contentWidth: width

    Column {
      id: col
      width: list.width
      Repeater {
        model: tab.entries
        delegate: Item {
          id: row
          required property var modelData
          width: col.width
          height: 34

          Rectangle { anchors.fill: parent; anchors.topMargin: 1; anchors.bottomMargin: 1; radius: Tk.r(8); color: Tk.tint(0.08); visible: rowHit.containsMouse }
          Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: Tk.bw(1); color: Tk.tint(0.07) }

          MouseArea {
            id: rowHit
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onPressed: tab.run(Clip.copyArgs(row.modelData.id), "Copied")
          }

          Text {
            id: glyph
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            textFormat: Text.PlainText
            text: row.modelData.secret ? "\u{F033E}" : tab.kindGlyph[row.modelData.kind]
            color: row.modelData.secret ? Tk.amber : tab.dimColor
            font.family: tab.family
            font.pixelSize: Tk.fs.body
          }
          Text {
            anchors.left: glyph.right
            anchors.leftMargin: 10
            anchors.right: act.left
            anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            textFormat: Text.PlainText
            elide: Text.ElideRight
            text: row.modelData.text
            color: row.modelData.secret ? tab.dimColor : tab.textColor
            font.family: tab.family
            font.pixelSize: Tk.fs.bodySmall
            font.italic: row.modelData.secret
          }
          Rectangle {
            id: act
            visible: row.modelData.canOpen || row.modelData.canFolder
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            width: 64; height: 22; radius: Tk.r(11)
            color: actHit.containsMouse ? Tk.tint(0.22) : Tk.tint(0.12)
            Text {
              anchors.centerIn: parent
              textFormat: Text.PlainText
              text: row.modelData.canOpen ? "Open" : "Folder"
              color: Tk.accent
              font.family: tab.family
              font.pixelSize: Tk.fs.caption
            }
            MouseArea {
              id: actHit
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onPressed: tab.run(row.modelData.canOpen ? Clip.openArgs(row.modelData.id) : Clip.folderArgs(row.modelData.id), "")
            }
          }
        }
      }
    }
  }
}
