import QtQuick
import qs.Commons as Commons
import "Settings.js" as Settings
import "Capabilities.js" as Caps
import "Tabs.js" as Tabs
import "Actions.js" as Actions

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
  readonly property var secs: Settings.sections(Tabs.TABS, Tabs.PINNED)
  property string section: "look"
  readonly property var secRows: { for (var i = 0; i < secs.length; i++) if (secs[i].id === section) return secs[i].rows; return [] }

  function change(key, dir) {
    if (notch) notch.setSetting(key, Settings.next(settings, key, dir))
  }
  // Set one registry row (a setting, or a built-in tab's shown/hidden switch).
  function setRow(row, value) {
    if (!notch) return
    var patch = Settings.rowPatch(settings, row, value)
    for (var k in patch) notch.setSetting(k, patch[k])
  }
  function options(row) {
    var f = Settings.field(row.key)   // not row.field: the Repeater model flattens nested arrays
    if (f.type === "choice") return f.options
    return Settings.choicesFor(f, settings[row.key]).map(function (v) { return { value: v, label: Settings.format(f, v) } })
  }
  // ---- quick actions editor: every edit rewrites the whole list through the sanitiser
  readonly property var actionList: settings.quickActions || []
  readonly property var actionItems: notch && notch.actionsState ? notch.actionsState.items : []
  readonly property var iconKeys: Object.keys(Settings.ACTION_ICONS)
  function saveActions(list) { if (notch) notch.setSetting("quickActions", Settings.sanitizeActions(list)) }
  function editAction(id, patch) { saveActions(Actions.update(actionList, id, patch)) }
  function missing(id) {
    for (var i = 0; i < actionItems.length; i++) if (actionItems[i].id === id) return actionItems[i].enabled ? "" : actionItems[i].reason
    return ""
  }
  function enableModule(setting) {
    if (notch) notch.setSetting(setting, true)
  }
  function finishSetup() {
    if (notch) notch.setSetting("setupDone", true)
  }

  readonly property int gutter: 16
  readonly property int headerH: 28
  readonly property var setupLay: Settings.setupLayout(offers.length, Caps.needsSetup(settings), height - headerH - 8)
  readonly property int setupH: showSetup ? setupLay.height : 0

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

  // ---- optional setup card: intro, a scrolling module list, Done pinned below
  // the list (Settings.setupLayout keeps Done inside the card at any count).
  Item {
    id: setupBox
    anchors.top: head.bottom
    anchors.left: parent.left
    anchors.right: parent.right
    height: tab.setupH
    visible: tab.showSetup

    Rectangle {
      anchors.fill: parent
      anchors.bottomMargin: Settings.SETUP.gap
      radius: Tk.r(10)
      color: Tk.tint(0.06)
    }

    Text {
      id: setupIntro
      anchors.top: parent.top
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.margins: 10
      height: Settings.SETUP.intro - 10
      textFormat: Text.PlainText
      wrapMode: Text.WordWrap
      elide: Text.ElideRight
      maximumLineCount: 2
      text: Caps.needsSetup(tab.settings)
            ? "Optional additions detected. Enable what you want; built-in tabs work without these."
            : "Optional modules detected on this host"
      color: tab.dimColor
      font.family: tab.family
      font.pixelSize: Tk.fs.caption
    }

    NotchScroll {
      id: setupList
      anchors.top: setupIntro.bottom
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.leftMargin: 10
      anchors.rightMargin: 10
      height: tab.setupLay.listH
      rowHeight: Settings.SETUP.row
      contentHeight: setupCol.height
      contentWidth: width

      Column {
        id: setupCol
        width: setupList.width

        Repeater {
          model: tab.offers
          delegate: Item {
            required property var modelData
            width: setupCol.width
            height: Settings.SETUP.row
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
          visible: tab.offers.length === 0
          width: parent.width
          height: Settings.SETUP.row
          verticalAlignment: Text.AlignVCenter
          textFormat: Text.PlainText
          elide: Text.ElideRight
          text: "No optional backends found. You can enable modules later if you install them."
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: Tk.fs.caption
        }
      }
    }

    // Done lives outside the scrolling list so it is always reachable.
    Rectangle {
      visible: Caps.needsSetup(tab.settings)
      anchors.right: parent.right
      anchors.rightMargin: 10
      anchors.bottom: parent.bottom
      anchors.bottomMargin: Settings.SETUP.gap + 8
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

  // ---- sections: a rail on the left, one scrolling list of rows on the right
  Item {
    id: main
    visible: height > 80
    anchors.top: setupBox.visible ? setupBox.bottom : head.bottom
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom

    Column {
      id: rail
      width: 150
      spacing: 2
      Repeater {
        model: tab.secs
        Rectangle {
          id: railItem
          required property var modelData
          readonly property bool selected: tab.section === railItem.modelData.id
          width: rail.width
          height: 30
          radius: Tk.r(15)
          color: selected ? Tk.tint(0.16) : (railHit.containsMouse ? Tk.tint(0.08) : "transparent")
          Text {
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 12
            anchors.right: parent.right
            anchors.rightMargin: 6
            textFormat: Text.PlainText
            elide: Text.ElideRight
            text: railItem.modelData.title
            color: railItem.selected ? tab.textColor : tab.dimColor
            font.family: tab.family
            font.pixelSize: Tk.fs.body
          }
          MouseArea {
            id: railHit
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onPressed: tab.section = railItem.modelData.id
          }
        }
      }
    }

    NotchScroll {
      id: list
      anchors.top: parent.top
      anchors.bottom: parent.bottom
      anchors.left: rail.right
      anchors.leftMargin: 14
      anchors.right: parent.right
      rowHeight: 40
      contentHeight: col.height
      contentWidth: width

      Column {
        id: col
        width: list.width

        Repeater {
          model: tab.secRows

          Item {
            id: row
            required property var modelData
            readonly property bool isSwitch: row.modelData.type === "bool"
            readonly property bool isSeg: row.modelData.type === "choice" || (row.modelData.type === "int" && !!Settings.field(row.modelData.key).choices)
            readonly property bool isActions: row.modelData.type === "actions"
            readonly property bool isStep: row.modelData.type === "int" && !row.isSeg
            readonly property var value: Settings.rowValue(tab.settings, row.modelData)
            width: col.width
            readonly property bool showDetail: row.modelData.detail !== "" && row.value === row.modelData.detailWhen
            height: row.isActions ? labelCol.height + actionsBox.height + 24 : (showDetail ? 76 : (row.modelData.hint !== "" ? 52 : 38))

            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: Tk.bw(1); color: Tk.tint(0.07) }

            Column {
              id: labelCol
              anchors.left: parent.left
              anchors.right: ctl.left
              anchors.rightMargin: 12
              anchors.top: row.isActions ? parent.top : undefined
              anchors.topMargin: row.isActions ? 8 : 0
              anchors.verticalCenter: row.isActions ? undefined : parent.verticalCenter
              spacing: 1
              Text {
                width: parent.width
                textFormat: Text.PlainText
                elide: Text.ElideRight
                text: row.modelData.label
                color: tab.textColor
                font.family: tab.family
                font.pixelSize: Tk.fs.body
              }
              Text {
                visible: row.modelData.hint !== ""
                width: parent.width
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                text: row.modelData.hint
                color: tab.dimColor
                font.family: tab.family
                font.pixelSize: Tk.fs.caption
              }
              Text {
                visible: row.showDetail
                width: parent.width
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                text: row.modelData.detail
                color: Tk.amber
                font.family: tab.family
                font.pixelSize: Tk.fs.caption
              }
            }

            // Quick-actions editor (R8): one line per action under the hint.
            Column {
              id: actionsBox
              visible: row.isActions
              anchors.top: labelCol.bottom
              anchors.topMargin: 8
              anchors.left: parent.left
              anchors.right: parent.right
              spacing: 6

              Repeater {
                model: row.isActions ? tab.actionList : []
                delegate: Column {
                  id: ar
                  required property var modelData
                  width: actionsBox.width
                  spacing: 2
                  Row {
                    spacing: 6
                    height: 28
                    Rectangle {
                      width: 28; height: 28; radius: Tk.r(14)
                      color: icHit.containsMouse ? Tk.tint(0.22) : Tk.tint(0.1)
                      Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: Settings.ACTION_ICONS[ar.modelData.icon] || ""; color: tab.textColor; font.family: tab.family; font.pixelSize: Tk.fs.body }
                      MouseArea { id: icHit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onPressed: tab.editAction(ar.modelData.id, { icon: Actions.nextIcon(tab.iconKeys, ar.modelData.icon) }) }
                    }
                    Rectangle {
                      width: 104; height: 28; radius: Tk.r(8); color: Tk.tint(0.07)
                      border.width: lblIn.activeFocus ? 1 : 0; border.color: Tk.tint(0.3)
                      TextInput {
                        id: lblIn
                        anchors.fill: parent; anchors.leftMargin: 9; anchors.rightMargin: 9
                        verticalAlignment: TextInput.AlignVCenter
                        color: tab.textColor; font.family: tab.family; font.pixelSize: Tk.fs.caption
                        maximumLength: Settings.ACTION_LIMITS.label
                        clip: true
                        text: ar.modelData.label
                        onTextChanged: if (!activeFocus) cursorPosition = 0
                        onActiveFocusChanged: if (!activeFocus) cursorPosition = 0
                        onEditingFinished: if (text !== ar.modelData.label) tab.editAction(ar.modelData.id, { label: text })
                        MouseArea { anchors.fill: parent; onPressed: function (m) { lblIn.forceActiveFocus(); m.accepted = false } }
                      }
                    }
                    Segmented {
                      options: [{ value: "app", label: "App" }, { value: "command", label: "Cmd" }, { value: "toggle", label: "Toggle" }]
                      current: ar.modelData.kind
                      onPicked: function (v) { tab.editAction(ar.modelData.id, { kind: v }) }
                    }
                    Rectangle {
                      width: actionsBox.width - 28 - 104 - 150 - 3 * 24 - 5 * 6 - 8; height: 28; radius: Tk.r(8); color: Tk.tint(0.07)
                      border.width: tab.missing(ar.modelData.id) !== "" ? 1 : (cmdIn.activeFocus ? 1 : 0)
                      border.color: tab.missing(ar.modelData.id) !== "" ? Tk.urgent : Tk.tint(0.3)
                      TextInput {
                        id: cmdIn
                        anchors.fill: parent; anchors.leftMargin: 9; anchors.rightMargin: 9
                        verticalAlignment: TextInput.AlignVCenter
                        color: tab.textColor; font.family: tab.family; font.pixelSize: Tk.fs.caption
                        maximumLength: Settings.ACTION_LIMITS.cmd
                        clip: true
                        text: ar.modelData.cmd
                        onTextChanged: if (!activeFocus) cursorPosition = 0
                        onActiveFocusChanged: if (!activeFocus) cursorPosition = 0
                        onEditingFinished: if (text !== ar.modelData.cmd) tab.editAction(ar.modelData.id, { cmd: text })
                        MouseArea { anchors.fill: parent; onPressed: function (m) { cmdIn.forceActiveFocus(); m.accepted = false } }
                      }
                    }
                    Repeater {
                      model: [{ g: "\u2191", d: -1 }, { g: "\u2193", d: 1 }, { g: "\u00D7", d: 0 }]
                      delegate: Rectangle {
                        required property var modelData
                        width: 24; height: 28; radius: Tk.r(12)
                        color: btnHit.containsMouse ? Tk.tint(0.22) : Tk.tint(0.1)
                        Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: modelData.g; color: tab.textColor; font.family: tab.family; font.pixelSize: Tk.fs.body }
                        MouseArea {
                          id: btnHit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                          onPressed: tab.saveActions(modelData.d === 0 ? Actions.remove(tab.actionList, ar.modelData.id) : Actions.move(tab.actionList, ar.modelData.id, modelData.d))
                        }
                      }
                    }
                  }
                  Text {
                    visible: tab.missing(ar.modelData.id) !== ""
                    textFormat: Text.PlainText
                    text: "Disabled: " + tab.missing(ar.modelData.id)
                    color: Tk.urgent
                    font.family: tab.family
                    font.pixelSize: Tk.fs.caption
                  }
                }
              }
              Row {
                spacing: 8
                PillButton { text: "Add action"; enabledButton: tab.actionList.length < Settings.ACTION_LIMITS.max; onClicked: tab.saveActions(Actions.add(tab.actionList, Settings.ACTION_LIMITS.max)) }
                PillButton { text: "Reset"; onClicked: if (tab.notch) tab.notch.setSetting("quickActions", null) }
              }
            }

            Item {
              id: ctl
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              width: row.isActions ? 0 : (row.isSwitch ? sw.width : (row.isSeg ? segc.width : stepc.width))
              height: 26

              PillSwitch {
                id: sw
                visible: row.isSwitch
                anchors.verticalCenter: parent.verticalCenter
                on: row.value === true
                onToggled: tab.setRow(row.modelData, !(row.value === true))
              }
              Segmented {
                id: segc
                visible: row.isSeg
                options: row.isSeg ? tab.options(row.modelData) : []
                current: row.value
                onPicked: function (v) { tab.setRow(row.modelData, v) }
              }
              Row {
                id: stepc
                visible: row.isStep
                spacing: 4
                Rectangle {
                  width: 26; height: 26; radius: Tk.r(13)
                  color: minus.containsMouse ? Tk.tint(0.22) : Tk.tint(0.1)
                  Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: "\u2212"; color: tab.textColor; font.family: tab.family; font.pixelSize: Commons.Style.font.title }
                  MouseArea { id: minus; anchors.fill: parent; hoverEnabled: true; onPressed: tab.change(row.modelData.key, -1) }
                }
                Rectangle {
                  width: 72; height: 26; radius: Tk.r(13); color: Tk.tint(0.1)
                  Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: row.isStep ? Settings.format(Settings.field(row.modelData.key), row.value) : ""; color: tab.textColor; font.family: tab.family; font.pixelSize: Tk.fs.body }
                }
                Rectangle {
                  width: 26; height: 26; radius: Tk.r(13)
                  color: plus.containsMouse ? Tk.tint(0.22) : Tk.tint(0.1)
                  Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: "+"; color: tab.textColor; font.family: tab.family; font.pixelSize: Commons.Style.font.title }
                  MouseArea { id: plus; anchors.fill: parent; hoverEnabled: true; onPressed: tab.change(row.modelData.key, 1) }
                }
              }
            }
          }
        }
      }
    }
  }
}
