import QtQuick 6.11
import qs.Commons as Commons
import qs.Ui

// P1 settings: both hover delays. Edits save once per commit (one spin step or
// one finished text entry) into this plugin's own shell.json entry, through
// the root's saveSettings(). Nothing is scrolled: the page fits the card.
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

  Column {
    anchors.fill: parent
    spacing: Commons.Style.spacing.xxl

    Text {
      textFormat: Text.PlainText
      text: "Settings"
      color: Commons.Color.popups.text
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.heading
      font.bold: true
    }

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
