import QtQuick 6.11
import qs.Commons as Commons
import qs.Ui
import "Omacontrol.js" as Omacontrol
import "Glyphs.js" as Glyphs

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
  readonly property bool omacontrol: !!island && island.omacontrolAvailable === true
  readonly property bool needsEntry: (island && !island.entryExists) || page.lastResult === "noentry"
  readonly property var toggles: [
    { key: "dictation", label: "Dictation" },
    { key: "media", label: "Media" },
    { key: "charging", label: "Charging" },
    { key: "hud", label: "Volume" },
    { key: "screenRecording", label: "Recording" },
    { key: "privacy", label: "Mic, cam" },
    { key: "dnd", label: "DND" },
    { key: "bluetooth", label: "Bluetooth" },
    { key: "calendar", label: "Calendar" },
    { key: "alerts", label: "Alerts" },
    { key: "weather", label: "Weather" },
    { key: "sansFont", label: "Sans font" },
    { key: "agents", label: "Agents" },
    { key: "messages", label: "Messages" },
    { key: "dayflow", label: "Dayflow" },
    { key: "shots", label: "Shots" }
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

  // The card sizes this page from its content, like every page (KTD2).
  function count() { return 0 }
  function heightFor(n) { return settingsColumn.implicitHeight }

  // No heading: the More chip and list already name the page, and the
  // fifteen toggles need the room.
  Column {
    id: settingsColumn
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

      // Beside the delays, where the row has room for the full label.
      Toggle {
        width: page.width - openField.width - closeField.width - Commons.Style.spacing.huge * 4
        anchors.bottom: parent.bottom
        label: "Load album art from the web"
        titleSize: Commons.Style.font.body
        checked: page.island && page.island.settings ? page.island.settings.webArt === true : true
        foreground: Commons.Color.popups.text
        onClicked: page.commit({ webArt: !checked })
      }
    }

    Grid {
      columns: 4
      columnSpacing: Commons.Style.spacing.huge * 2
      rowSpacing: Commons.Style.spacing.sm

      Repeater {
        model: page.toggles

        Toggle {
          required property var modelData
          width: (page.width - Commons.Style.spacing.huge * 6) / 4
          // Sixteen toggles in four columns: shorter than the Ui default so
          // the page and the Omacontrol row fit the card without scrolling.
          height: Commons.Style.spacing.controlHeight + Commons.Style.spacing.lg
          label: modelData.label
          titleSize: Commons.Style.font.bodySmall
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

    // System settings: shortcuts into Omacontrol, drawn only while it is
    // available. Each opens its window on one page and closes the card.
    Row {
      id: shortcuts
      visible: page.omacontrol
      spacing: Commons.Style.spacing.sm
      readonly property real cellW: (page.width - Commons.Style.spacing.sm * (Omacontrol.SHORTCUTS.length - 1)) / Omacontrol.SHORTCUTS.length

      Repeater {
        model: Omacontrol.SHORTCUTS

        Item {
          id: shortcut
          required property var modelData
          width: shortcuts.cellW
          height: Commons.Style.space(48)

          Plate {
            anchors.fill: parent
          }

          HoverButton {
            anchors.fill: parent
            hint: Omacontrol.hint(shortcut.modelData.id)
            onClicked: page.island.openOmacontrol(shortcut.modelData.id)

            Txt {
              icon: true
              anchors.horizontalCenter: parent.horizontalCenter
              anchors.top: parent.top
              anchors.topMargin: Commons.Style.spacing.md
              width: implicitWidth
              font.pixelSize: Commons.Style.font.heading
              text: Glyphs.glyph(shortcut.modelData.glyph)
            }

            Txt {
              kind: "caption"
              anchors.horizontalCenter: parent.horizontalCenter
              anchors.bottom: parent.bottom
              anchors.bottomMargin: Commons.Style.spacing.sm
              width: Math.min(implicitWidth, parent.width - Commons.Style.spacing.md * 2)
              horizontalAlignment: Text.AlignHCenter
              text: shortcut.modelData.label
            }
          }
        }
      }
    }

    Txt {
      visible: page.hudWaiting
      kind: "caption"
      wrap: true
      text: "Volume shows here once Omarchy's OSD is off (omarchy-plugin-disable omarchy.osd)."
      width: page.width
    }

    Txt {
      visible: page.needsEntry
      kind: "caption"
      wrap: true
      text: "Enable the Island plugin first: there is no settings entry to save to yet."
      width: parent.width
    }
  }
}
