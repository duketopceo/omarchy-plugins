import QtQuick 6.11
import qs.Commons as Commons
import qs.Ui

// Settings: both hover delays and one toggle per live-activity integration
// (KTD12). Edits save once per commit (one spin step, one finished text entry
// or one toggle) into this plugin's own shell.json entry, through the root's
// saveSettings(). Nothing is scrolled: the page fits the card.
Item {
  id: page

  // The Island root: settings, entryExists and saveSettings(edit).
  property var island: null
  // "saved" | "unchanged" | "noentry" from the last commit.
  property string lastResult: ""

  signal holdStart()
  signal holdEnd()

  readonly property int openDelay: island && island.settings ? island.settings.openDelay : 140
  readonly property int closeDelay: island && island.settings ? island.settings.closeDelay : 450
  readonly property bool needsEntry: (island && !island.entryExists) || page.lastResult === "noentry"
  readonly property var toggles: [
    { key: "dictation", label: "Dictation" },
    { key: "media", label: "Media" },
    { key: "charging", label: "Charging" },
    { key: "hud", label: "Volume level" },
    { key: "screenRecording", label: "Recording" },
    { key: "privacy", label: "Mic, camera" },
    { key: "dnd", label: "Do Not Disturb" },
    { key: "bluetooth", label: "Bluetooth" },
    { key: "alerts", label: "Alerts" }
  ]
  // The HUD only shows once the owner has turned off Omarchy's own OSD.
  readonly property bool hudWaiting: island && island.settings && island.settings.hud === true && !island.hudEffective

  // A text field with focus keeps the card open (R10).
  readonly property bool editing: openField.field.activeFocus || closeField.field.activeFocus
  property bool holding: false
  onEditingChanged: page.syncHold()
  Component.onDestruction: if (page.holding) page.holdEnd()

  function syncHold() {
    if (page.editing === page.holding) return
    page.holding = page.editing
    if (page.holding) page.holdStart()
    else page.holdEnd()
  }

  function commit(edit) {
    if (!page.island) return
    page.lastResult = page.island.saveSettings(edit)
  }

  // No heading: the selected Settings chip already names the page, and the
  // nine toggles need the room.
  Column {
    anchors.fill: parent
    spacing: Commons.Style.spacing.lg

    Row {
      spacing: Commons.Style.spacing.huge * 2

      NumberField {
        id: openField
        label: "Open delay (ms)"
        from: 0
        to: 600
        stepSize: 10
        value: page.openDelay
        foreground: Commons.Color.popups.text
        onModified: function(newValue) { page.commit({ openDelay: newValue }) }
      }

      NumberField {
        id: closeField
        label: "Close delay (ms)"
        from: 150
        to: 1500
        stepSize: 50
        value: page.closeDelay
        foreground: Commons.Color.popups.text
        onModified: function(newValue) { page.commit({ closeDelay: newValue }) }
      }
    }

    Grid {
      columns: 3
      columnSpacing: Commons.Style.spacing.huge * 2
      rowSpacing: Commons.Style.spacing.sm

      Repeater {
        model: page.toggles

        Toggle {
          required property var modelData
          width: (page.width - Commons.Style.spacing.huge * 4) / 3
          label: modelData.label
          titleSize: Commons.Style.font.body
          checked: page.island && page.island.settings ? page.island.settings[modelData.key] === true : true
          foreground: Commons.Color.popups.text
          onClicked: {
            var edit = {}
            edit[modelData.key] = !checked
            page.commit(edit)
          }
        }
      }
    }

    Text {
      textFormat: Text.PlainText
      visible: page.hudWaiting
      text: "The volume and brightness level shows here only after Omarchy's OSD is turned off (omarchy-plugin-disable omarchy.osd)."
      color: Commons.Color.popups.text
      opacity: 0.7
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.bodySmall
      wrapMode: Text.WordWrap
      width: page.width
    }

    Text {
      textFormat: Text.PlainText
      visible: page.needsEntry
      text: "Enable the Island plugin first: there is no settings entry to save to yet."
      color: Commons.Color.popups.text
      opacity: 0.7
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.bodySmall
      wrapMode: Text.WordWrap
      width: page.width
    }
  }
}
