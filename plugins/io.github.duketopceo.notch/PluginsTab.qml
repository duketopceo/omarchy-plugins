import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import "Plugins.js" as Plugins
import "Tabs.js" as Tabs

// Plugins tab: the hub for the plugin estate (plan U1 / R1-R6). Every tray
// plugin plus the confirmed right-side set, grouped into Tray / System / Agent
// and shown as large tiles. A tile whose UI already lives in the notch opens
// that tab in place (notch.openTab); anything else runs the launcher chain
// (Plugins.openChain, through notch.openPlugin). The end row opens Settings.
Item {
  id: tab

  property var notch: null

  readonly property color textColor: notch ? notch.textColor : Tk.white
  readonly property color dimColor: notch ? notch.dimColor : "gray"
  readonly property color faintColor: notch && notch.faintColor ? notch.faintColor : dimColor
  readonly property color accentColor: notch && notch.accentColor ? notch.accentColor : textColor
  readonly property color goodColor: notch && notch.goodColor ? notch.goodColor : accentColor
  readonly property string family: notch ? notch.fontFamily : ""
  readonly property string home: Quickshell.env("HOME")
  readonly property int gap: Plugins.HUB_GAP
  readonly property int radius: Tk.r(notch && notch.cardRadius ? notch.cardRadius : 12)

  // Tabs this panel can actually show. An embedded tile only opens in place
  // when its tab is shipped and visible; otherwise it degrades to the chain.
  readonly property var tabIds: Tabs.visibleIds(notch ? notch.settings : null)

  // Installed plugins from the shell registry, when it exposes them. Unknown
  // (null) means "do not filter" so the hub still works if the API moves.
  readonly property var installed: {
    try {
      var reg = notch && notch.shell && notch.shell.pluginRegistry ? notch.shell.pluginRegistry.installedPlugins : null
      if (!reg) return null
      var out = []
      for (var k in reg) out.push(String(k))
      return out.length ? out : null
    } catch (e) { return null }
  }

  readonly property var tray: Plugins.trayIds(notch ? notch.shellConfig : null)
  readonly property var groups: Plugins.hub(notch ? notch.shellConfig : null, installed, null)
  readonly property var statusCtx: ({
    failed: notch ? notch.openFailed : "",
    tabs: tabIds,
    tray: tray,
    right: Plugins.RIGHT_IDS,
    // Live figures the hub repeats from the bar: AI usage percent, Blip unread.
    usage: notch ? notch.usage : null,
    messages: notch ? notch.messages : null
  })

  // Tone for a tile's live detail: severity words from usage, Blip's states.
  function toneColor(tone) {
    if (tone === "critical") return notch && notch.urgentColor ? notch.urgentColor : Tk.urgent
    if (tone === "high" || tone === "warn") return notch && notch.warnColor ? notch.warnColor : tab.accentColor
    if (tone === "mid") return tab.accentColor
    if (tone === "low" || tone === "info") return tab.goodColor
    return tab.faintColor
  }

  // R2/R6: embedded tabs open in place, everything else through the chain.
  function openTile(id) {
    if (!notch) return
    var a = Plugins.action(String(id), tabIds)
    if (a.kind === "tab") openTab(a.id)
    else notch.openPlugin(String(id))   // notch.openPlugin runs Plugins.openChain
  }

  function openTab(id) {
    if (!notch) return
    if (typeof notch.openTab === "function") notch.openTab(id)
    else notch.openTabRequested(id, "")
  }

  function openConfigure() { openTab(Plugins.configure().id) }

  Text {
    textFormat: Text.PlainText
    anchors.centerIn: parent
    visible: tab.groups.length === 0
    text: "No plugins to show"
    color: tab.faintColor
    font.family: tab.family
    font.pixelSize: Tk.fs.bodySmall
  }

  NotchScroll {
    anchors.fill: parent
    rowHeight: Plugins.TILE_H + tab.gap
    rowsPerNotch: 1   // one tile row per wheel notch; three would fly past
    contentHeight: col.height
    contentWidth: width

    Column {
      id: col
      width: parent.width
      spacing: 14

      Repeater {
        model: tab.groups

        Column {
          id: section
          required property var modelData
          width: col.width
          spacing: tab.gap

          Text {
            textFormat: Text.PlainText
            text: section.modelData.title.toUpperCase()
            color: tab.faintColor
            font.family: tab.family
            font.pixelSize: Tk.fs.caption
            font.letterSpacing: 1.2
            font.bold: true
          }

          Flow {
            width: parent.width
            spacing: tab.gap

            Repeater {
              model: section.modelData.tiles

              Rectangle {
                id: slot
                required property string modelData
                // Name/icon from the manifest; the id's last segment and a
                // generic glyph stand in when it cannot be read (R9).
                property var info: Plugins.slotInfo(slot.modelData, "", tab.home)
                property bool imageOk: false

                readonly property var st: Plugins.status(slot.modelData, tab.statusCtx)
                readonly property string hint: Plugins.launchHint(slot.modelData, tab.tabIds)

                width: Plugins.tileWidth(tab.width)
                height: Plugins.TILE_H
                radius: Tk.r(tab.radius)
                color: hit.containsMouse ? Tk.tint(0.16) : Tk.tint(0.07)
                border.width: slot.st.on ? 0 : 1
                border.color: Tk.tint(0.10)

                FileView {
                  path: slot.info.image
                  printErrors: false
                  onLoaded: slot.imageOk = true
                  onLoadFailed: slot.imageOk = false
                }
                FileView {
                  path: Plugins.manifestPath(tab.home, slot.modelData)
                  blockLoading: true
                  printErrors: false
                  onLoaded: slot.info = Plugins.slotInfo(slot.modelData, text(), tab.home)
                  onLoadFailed: slot.info = Plugins.slotInfo(slot.modelData, "", tab.home)
                }

                Column {
                  anchors.centerIn: parent
                  width: parent.width - 24
                  spacing: 3

                  Item {
                    width: parent.width
                    height: 32
                    Image {
                      id: iconImg
                      anchors.centerIn: parent
                      width: 30; height: 30
                      visible: slot.imageOk && status === Image.Ready
                      source: slot.imageOk ? "file://" + slot.info.image : ""
                      sourceSize: Qt.size(120, 120)
                      fillMode: Image.PreserveAspectFit
                      asynchronous: true
                    }
                    Text {
                      textFormat: Text.PlainText
                      anchors.centerIn: parent
                      visible: !slot.imageOk || iconImg.status !== Image.Ready
                      text: slot.info.glyph
                      color: tab.textColor
                      font.family: tab.family
                      font.pixelSize: 22
                    }
                  }

                  Text {
                    textFormat: Text.PlainText
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    text: slot.info.name
                    color: tab.textColor
                    font.family: tab.family
                    font.pixelSize: Tk.fs.body
                  }

                  // Live figure where one exists: the AI usage percent next to
                  // the bar icon, or Blip's unread count (R8).
                  Text {
                    textFormat: Text.PlainText
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: slot.st.detail !== ""
                    text: slot.st.detail
                    color: tab.toneColor(slot.st.tone)
                    font.family: tab.family
                    font.pixelSize: Tk.fs.body
                    font.bold: true
                  }

                  // R3: pill when the UI is in the notch, dot for on/off bar.
                  Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    height: 16
                    width: Math.min(chip.implicitWidth + 14, parent.width)
                    radius: Tk.r(height / 2)
                    color: slot.st.on ? Tk.tint(0.10) : "transparent"
                    border.width: slot.st.on ? 0 : 1
                    border.color: Tk.tint(0.14)

                    Row {
                      id: chip
                      anchors.centerIn: parent
                      spacing: 6
                      Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 7; height: 7; radius: Tk.r(3.5)
                        color: slot.st.on ? tab.goodColor : tab.faintColor
                      }
                      Text {
                        textFormat: Text.PlainText
                        anchors.verticalCenter: parent.verticalCenter
                        text: slot.hint !== "" ? slot.hint : slot.st.text
                        color: slot.st.on ? tab.textColor : tab.faintColor
                        font.family: tab.family
                        font.pixelSize: Tk.fs.caption
                      }
                    }
                  }
                }

                MouseArea {
                  id: hit
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: tab.openTile(slot.modelData)
                }
              }
            }
          }
        }
      }

      // R6: the end row. "Configure" opens the Settings tab.
      Rectangle {
        id: configure
        width: col.width
        height: 52
        radius: Tk.r(tab.radius)
        color: cfgHit.containsMouse ? Tk.tint(0.16) : Tk.tint(0.07)

        Text {
          textFormat: Text.PlainText
          anchors.left: parent.left
          anchors.leftMargin: 16
          anchors.verticalCenter: parent.verticalCenter
          text: Plugins.CONFIGURE.title
          color: tab.textColor
          font.family: tab.family
          font.pixelSize: Tk.fs.body
        }
        Row {
          anchors.right: parent.right
          anchors.rightMargin: 16
          anchors.verticalCenter: parent.verticalCenter
          spacing: 8
          Text {
            textFormat: Text.PlainText
            anchors.verticalCenter: parent.verticalCenter
            text: Plugins.CONFIGURE.label
            color: tab.accentColor
            font.family: tab.family
            font.pixelSize: Tk.fs.bodySmall
          }
          Text {
            textFormat: Text.PlainText
            anchors.verticalCenter: parent.verticalCenter
            text: "\u{F0142}"
            color: tab.accentColor
            font.family: tab.family
            font.pixelSize: Tk.fs.bodySmall
          }
        }

        MouseArea {
          id: cfgHit
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: tab.openConfigure()
        }
      }
    }
  }
}
