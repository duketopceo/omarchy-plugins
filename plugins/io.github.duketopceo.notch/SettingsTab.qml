import QtQuick
import qs.Commons as Commons
import "Settings.js" as Settings
import "Capabilities.js" as Caps

// Settings tab: first-run / optional-module setup strip, then prefs grid.
// Setup offers Enable for capabilities `bin/notch-probe` found on this host.
// Prefs never require sibling plugins or private shell config.
Item {
  id: tab

  property var notch: null

  readonly property color textColor: notch ? notch.textColor : Tk.white
  readonly property color dimColor: notch ? notch.dimColor : "gray"
  readonly property string family: notch ? notch.fontFamily : ""
  readonly property var settings: notch ? notch.settings : Settings.resolve(null)
  readonly property var probe: notch && notch.capabilities ? notch.capabilities : Caps.emptyProbe()
  readonly property var rows: Caps.setupRows(probe, settings)
  readonly property var offers: Caps.offers(probe, settings)
  readonly property bool showSetup: Caps.needsSetup(settings) || offers.length > 0
  readonly property var prefs: Settings.prefFields()

  function change(key, dir) {
    if (notch) notch.setSetting(key, Settings.next(settings, key, dir))
  }
  function enableModule(setting) {
    if (notch) notch.setSetting(setting, true)
  }
  function finishSetup() {
    if (notch) notch.setSetting("setupDone", true)
  }

  readonly property int gutter: 16
  readonly property int headerH: 28
  readonly property int setupH: showSetup ? Math.min(160, 36 + offers.length * 28 + (Caps.needsSetup(settings) ? 32 : 0)) : 0
  readonly property int rowH: Math.max(36, Math.min(56, Math.floor((height - headerH - setupH - 8) / Math.max(1, Math.ceil(prefs.length / 2)))))

  Text {
    id: head
    textFormat: Text.PlainText
    text: "Notch settings"
    color: tab.textColor
    font.family: tab.family
    font.pixelSize: Commons.Style.font.title
    font.weight: Font.DemiBold
    height: tab.headerH
    verticalAlignment: Text.AlignVCenter
  }

  // ---- optional setup strip
  Item {
    id: setupBox
    anchors.top: head.bottom
    anchors.left: parent.left
    anchors.right: parent.right
    height: tab.setupH
    visible: tab.showSetup
    clip: true

    Rectangle {
      anchors.fill: parent
      anchors.bottomMargin: 6
      radius: Tk.r(10)
      color: Tk.tint(0.06)
    }

    Column {
      id: setupCol
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: 10
      spacing: 4

      Text {
        width: parent.width
        textFormat: Text.PlainText
        wrapMode: Text.WordWrap
        text: Caps.needsSetup(tab.settings)
              ? "Optional additions detected — enable what you want. Built-in tabs work without these."
              : "Optional modules (detected on this host)"
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: Tk.fs.caption
      }

      Repeater {
        model: tab.offers
        delegate: Item {
          required property var modelData
          width: setupCol.width
          height: 26
          Text {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: enableBtn.left
            anchors.rightMargin: 8
            textFormat: Text.PlainText
            elide: Text.ElideRight
            text: modelData.label
            color: tab.textColor
            font.family: tab.family
            font.pixelSize: Tk.fs.bodySmall
          }
          Rectangle {
            id: enableBtn
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: 64; height: 22; radius: Tk.r(11)
            color: enHit.containsMouse ? Tk.tint(0.22) : Tk.tint(0.12)
            Text {
              anchors.centerIn: parent
              textFormat: Text.PlainText
              text: "Enable"
              color: Tk.accent
              font.family: tab.family
              font.pixelSize: Tk.fs.caption
            }
            MouseArea {
              id: enHit
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: tab.enableModule(modelData.setting)
            }
          }
        }
      }

      Text {
        visible: tab.offers.length === 0 && Caps.needsSetup(tab.settings)
        width: parent.width
        textFormat: Text.PlainText
        wrapMode: Text.WordWrap
        text: "No optional backends found. You can enable modules later if you install them."
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: Tk.fs.caption
      }

      Rectangle {
        visible: Caps.needsSetup(tab.settings)
        width: 88; height: 24; radius: Tk.r(12)
        color: doneHit.containsMouse ? Tk.tint(0.22) : Tk.tint(0.12)
        Text {
          anchors.centerIn: parent
          textFormat: Text.PlainText
          text: "Done"
          color: tab.textColor
          font.family: tab.family
          font.pixelSize: Tk.fs.bodySmall
        }
        MouseArea {
          id: doneHit
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: tab.finishSetup()
        }
      }
    }
  }

  NotchScroll {
    anchors.top: setupBox.visible ? setupBox.bottom : head.bottom
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    rowHeight: tab.rowH
    contentHeight: flow.height
    contentWidth: width

  Flow {
    id: flow
    width: parent.width
    spacing: 0

    Repeater {
      model: tab.prefs

      Item {
        id: row
        required property var modelData
        required property int index
        readonly property int padL: index % 2 === 1 ? tab.gutter / 2 : 0
        readonly property int padR: index % 2 === 0 ? tab.gutter / 2 : 0
        readonly property bool isInt: row.modelData.type === "int"
        width: Math.floor(tab.width / 2)
        height: tab.rowH

        Rectangle { anchors.bottom: parent.bottom; x: row.padL; width: parent.width - row.padL - row.padR; height: Tk.bw(1); color: Tk.tint(0.07) }

        Text {
          textFormat: Text.PlainText
          anchors.left: parent.left
          anchors.leftMargin: row.padL
          anchors.verticalCenter: parent.verticalCenter
          text: row.modelData.label
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: Tk.fs.body
        }

        Row {
          anchors.right: parent.right
          anchors.rightMargin: row.padR
          anchors.verticalCenter: parent.verticalCenter
          spacing: 4

          Rectangle {
            visible: row.isInt
            width: 26; height: 26; radius: Tk.r(13)
            color: minus.containsMouse ? Tk.tint(0.22) : Tk.tint(0.1)
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: "−"
              color: tab.textColor
              font.family: tab.family
              font.pixelSize: Commons.Style.font.title
            }
            MouseArea { id: minus; anchors.fill: parent; hoverEnabled: true; onClicked: tab.change(row.modelData.key, -1) }
          }

          Rectangle {
            id: pill
            width: row.isInt ? 72 : Math.max(56, pillText.implicitWidth + 16)
            height: 26; radius: Tk.r(13)
            readonly property bool on: row.modelData.type === "bool" && tab.settings[row.modelData.key] === true
            color: on ? (Tk.pxl ? Tk.edge : Tk.alpha(Tk.accent, 0.3)) : (pillHit.containsMouse && !row.isInt ? Tk.tint(0.22) : Tk.tint(0.1))
            Text {
              id: pillText
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: Settings.format(row.modelData, tab.settings[row.modelData.key])
              color: pill.on && Tk.pxl ? Tk.accent : tab.textColor
              font.family: tab.family
              font.pixelSize: Tk.fs.body
            }
            MouseArea {
              id: pillHit
              anchors.fill: parent
              hoverEnabled: true
              enabled: !row.isInt
              cursorShape: row.isInt ? Qt.ArrowCursor : Qt.PointingHandCursor
              onClicked: tab.change(row.modelData.key, 1)
            }
          }

          Rectangle {
            visible: row.isInt
            width: 26; height: 26; radius: Tk.r(13)
            color: plus.containsMouse ? Tk.tint(0.22) : Tk.tint(0.1)
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: "+"
              color: tab.textColor
              font.family: tab.family
              font.pixelSize: Commons.Style.font.title
            }
            MouseArea { id: plus; anchors.fill: parent; hoverEnabled: true; onClicked: tab.change(row.modelData.key, 1) }
          }
        }
      }
    }
  }
  }
}
