import QtQuick 6.11
import qs.Commons as Commons
import "Dnd.js" as Dnd

// The expanded card's content at its one fixed size: the active page, and a
// row with the Now and Settings chips plus the pin control. The Now page shows
// the top activity's block and up to two rows (KTD9), or the clock and date
// when nothing is live. The window clips it to the morphing shape.
Item {
  id: card

  property date now: new Date()
  property string page: "now"
  property bool pinned: false
  // The Island root, handed to the Settings page.
  property var island: null
  // Activity.layout() for this window: { top, second, rows, held }.
  property var layout: null
  // Media accent from local album art, or the theme accent.
  property color tint: Commons.Color.accent

  signal pageSelected(string id)
  signal pinClicked()
  signal cardClicked()
  signal holdStart()
  signal holdEnd()
  signal act(string id, string action, real value)

  readonly property var topActivity: card.layout ? card.layout.top : null
  readonly property var rows: card.layout && card.layout.rows ? card.layout.rows : []
  // The row Repeater is keyed on ids, reassigned only when the set or order
  // changes: `rows` is a new array on every tick (a running timer redraws
  // each second), and a new model would destroy each row and its button
  // mid-click. Each row looks its activity up by id, so text still updates.
  property var rowIds: []
  onRowsChanged: {
    var ids = []
    for (var i = 0; i < card.rows.length; i++) ids.push(String(card.rows[i].id))
    if (ids.join(",") !== card.rowIds.join(",")) card.rowIds = ids
  }
  function rowFor(id) {
    for (var i = 0; i < card.rows.length; i++) if (String(card.rows[i].id) === id) return card.rows[i]
    return null
  }

  readonly property int pad: Commons.Style.spacing.huge
  readonly property int rowHeight: Math.max(Commons.Style.space(30), Commons.Style.spacing.controlHeight)
  readonly property color textColor: Commons.Color.popups.text
  readonly property var pages: [{ id: "now", label: "Now" }, { id: "settings", label: "Settings" }]

  // The pin control's center in window coordinates, for the live hover check.
  function pinCenter() {
    var p = pin.mapToItem(null, pin.width / 2, pin.height / 2)
    return { x: p.x, y: p.y }
  }

  // A click anywhere on the card raises keyboard focus; controls inside still
  // get their own clicks.
  TapHandler { onTapped: card.cardClicked() }

  Item {
    id: pageArea
    x: card.pad
    y: card.pad
    width: card.width - card.pad * 2
    height: pageRow.y - y - Commons.Style.spacing.lg

    // The top activity's block, or the clock and date when no activity may
    // take the top (nothing live, or only card-only ones such as Bluetooth
    // audio), then up to two rows (KTD9, KTD13).
    Column {
      visible: card.page === "now"
      width: parent.width
      spacing: Commons.Style.spacing.lg

      ActivityBlock {
        visible: card.topActivity !== null
        width: parent.width
        height: visible ? implicitHeight : 0
        activity: card.topActivity
        tint: card.tint
        onAct: function(id, action, value) { card.act(id, action, value) }
        onHoldStart: card.holdStart()
        onHoldEnd: card.holdEnd()
      }

      Column {
        visible: card.topActivity === null
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Commons.Style.spacing.md
        topPadding: card.rowIds.length > 0 ? 0 : Math.max(0, (pageArea.height - implicitHeight) / 2 - Commons.Style.spacing.lg)

        Text {
          textFormat: Text.PlainText
          text: Qt.formatTime(card.now, Qt.locale().timeFormat(Locale.ShortFormat))
          color: card.textColor
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.displayLarge * 2
          font.bold: true
          anchors.horizontalCenter: parent.horizontalCenter
        }

        Text {
          textFormat: Text.PlainText
          text: Qt.formatDate(card.now, "dddd, MMMM d")
          color: card.textColor
          opacity: 0.8
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.heading
          anchors.horizontalCenter: parent.horizontalCenter
        }
      }

      Repeater {
        model: card.rowIds

        ActivityRow {
          required property string modelData
          width: parent.width
          height: Commons.Style.spacing.controlHeight
          activity: card.rowFor(modelData)
          onAct: function(id, action) { card.act(id, action, 0) }
        }
      }
    }

    SettingsPage {
      visible: card.page === "settings"
      anchors.fill: parent
      island: card.island
      onHoldStart: card.holdStart()
      onHoldEnd: card.holdEnd()
    }
  }

  Item {
    id: pageRow
    x: card.pad
    y: card.height - card.pad - card.rowHeight
    width: card.width - card.pad * 2
    height: card.rowHeight

    Row {
      spacing: Commons.Style.spacing.lg

      Repeater {
        model: card.pages

        Rectangle {
          id: chip
          required property var modelData
          readonly property bool selected: card.page === chip.modelData.id
          width: chipText.implicitWidth + Commons.Style.spacing.huge * 2
          height: card.rowHeight
          radius: Commons.Style.cornerRadius
          color: chip.selected ? Commons.Color.menu.selectedBackground : "transparent"
          border.width: Commons.Style.normalBorderWidth
          border.color: chip.selected ? Commons.Color.menu.selectedText : Commons.Color.menu.border

          Text {
            id: chipText
            textFormat: Text.PlainText
            text: chip.modelData.label
            color: chip.selected ? Commons.Color.menu.selectedText : card.textColor
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.body
            anchors.centerIn: parent
          }

          MouseArea {
            anchors.fill: parent
            onClicked: {
              card.pageSelected(chip.modelData.id)
              card.cardClicked()
            }
          }
        }
      }
    }

    // Omarchy's Do Not Disturb, toggled through Omarchy's own command (R10).
    Rectangle {
      id: dndToggle
      visible: card.island !== null && card.island.dndAvailable === true
      readonly property bool on: card.island !== null && card.island.dndOn === true
      anchors.right: pin.left
      anchors.rightMargin: Commons.Style.spacing.lg
      width: dndText.implicitWidth + Commons.Style.spacing.huge * 2
      height: card.rowHeight
      radius: Commons.Style.cornerRadius
      color: dndToggle.on ? Commons.Color.menu.selectedBackground : "transparent"
      border.width: Commons.Style.normalBorderWidth
      border.color: dndToggle.on ? Commons.Color.accent : Commons.Color.menu.border

      Text {
        id: dndText
        textFormat: Text.PlainText
        text: Dnd.GLYPH + "  Do Not Disturb"
        color: dndToggle.on ? Commons.Color.accent : card.textColor
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.body
        anchors.centerIn: parent
      }

      MouseArea {
        anchors.fill: parent
        onClicked: if (card.island) card.island.toggleDnd()
      }
    }

    // The only control that pins; the pinned state is drawn filled.
    Rectangle {
      id: pin
      anchors.right: parent.right
      width: pinText.implicitWidth + Commons.Style.spacing.huge * 2
      height: card.rowHeight
      radius: Commons.Style.cornerRadius
      color: card.pinned ? Commons.Color.menu.selectedBackground : "transparent"
      border.width: Commons.Style.normalBorderWidth
      border.color: card.pinned ? Commons.Color.accent : Commons.Color.menu.border

      Text {
        id: pinText
        textFormat: Text.PlainText
        text: card.pinned ? "Pinned" : "Pin"
        color: card.pinned ? Commons.Color.accent : card.textColor
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.body
        anchors.centerIn: parent
      }

      MouseArea {
        anchors.fill: parent
        onClicked: card.pinClicked()
      }
    }
  }
}
