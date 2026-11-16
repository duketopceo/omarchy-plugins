import QtQuick 6.11
import qs.Commons as Commons
import "Dnd.js" as Dnd
import "Presentation.js" as Presentation
import "Privacy.js" as Privacy

// The expanded card's content: the active page, and a compact row with the Now
// and Settings chips plus the Do Not Disturb and pin controls. The Now page
// shows the top activity's block and up to two rows (KTD9), or the clock and
// date when nothing is live. Media on top gets the Now Playing block and a
// card as short as that block needs; every other page and activity keeps the
// full card height. The window asks heightFor() once when the card opens or the
// page changes and holds that size while open (KTD2). It clips this content to
// the morphing shape.
Item {
  id: card

  property date now: new Date()
  property string page: "now"
  property bool pinned: false
  // The Island root, handed to the Settings page.
  property var island: null
  // Activity.layout() for this window: { top, second, rows, held }.
  property var layout: null
  // Media accent from the album art, or the theme accent.
  property color tint: Commons.Color.accent
  // The pill row above the card and the tallest the card may be, from the window.
  property int band: 28
  property int maxHeight: 380
  // Rows shown below the top block: the count the window committed to.
  property int maxRows: 2

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
  readonly property var shownRowIds: card.rowIds.slice(0, card.maxRows)
  function rowFor(id) {
    for (var i = 0; i < card.rows.length; i++) if (String(card.rows[i].id) === id) return card.rows[i]
    return null
  }

  readonly property int pad: Commons.Style.spacing.huge
  readonly property int rowHeight: Commons.Style.space(24)
  readonly property color textColor: Commons.Color.popups.text
  readonly property var pages: [{ id: "now", label: "Now" }, { id: "settings", label: "Settings" }]

  // The card height for `rowCount` rows under the current page and top block.
  function heightFor(rowCount) {
    return Presentation.cardHeight({
      page: card.page,
      kind: card.topActivity ? String(card.topActivity.id) : "",
      band: card.band,
      pad: card.pad,
      content: mediaBlock.implicitHeight + header.implicitHeight + Commons.Style.spacing.lg,
      rows: rowCount,
      rowH: Commons.Style.spacing.controlHeight,
      gap: Commons.Style.spacing.lg,
      pageRowH: card.rowHeight,
      max: card.maxHeight
    })
  }

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

      // Time and date (and the indicators the pill shows) above the media block.
      Row {
        id: header
        visible: card.topActivity !== null && card.topActivity.id === "media"
        width: parent.width
        height: visible ? implicitHeight : 0
        spacing: Commons.Style.spacing.lg

        Text {
          textFormat: Text.PlainText
          text: Qt.formatTime(card.now, Qt.locale().timeFormat(Locale.ShortFormat)) + "  \u00b7  " + Qt.formatDate(card.now, "ddd MMM d")
          color: card.textColor
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.body
          font.features: { "tnum": 1 }
        }
        Text {
          visible: card.island !== null && card.island.dndOn === true
          textFormat: Text.PlainText
          text: Dnd.GLYPH
          color: card.textColor
          opacity: 0.8
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.body
        }
        Rectangle {
          visible: card.island !== null && card.island.cameraInUse === true
          width: Presentation.DOT_SIZE; height: Presentation.DOT_SIZE; radius: Presentation.DOT_SIZE / 2
          anchors.verticalCenter: parent.verticalCenter
          readonly property var hsl: Privacy.dotColor("camera", { h: Commons.Color.urgent.hslHue, s: Commons.Color.urgent.hslSaturation, l: Commons.Color.urgent.hslLightness })
          color: Qt.hsla(hsl.h, hsl.s, hsl.l, 1)
        }
        Rectangle {
          visible: card.island !== null && card.island.micInUse === true
          width: Presentation.DOT_SIZE; height: Presentation.DOT_SIZE; radius: Presentation.DOT_SIZE / 2
          anchors.verticalCenter: parent.verticalCenter
          readonly property var hsl: Privacy.dotColor("mic", { h: Commons.Color.urgent.hslHue, s: Commons.Color.urgent.hslSaturation, l: Commons.Color.urgent.hslLightness })
          color: Qt.hsla(hsl.h, hsl.s, hsl.l, 1)
        }
      }

      MediaBlock {
        id: mediaBlock
        visible: card.topActivity !== null && card.topActivity.id === "media"
        width: parent.width
        height: visible ? implicitHeight : 0
        activity: visible ? card.topActivity : null
        tint: card.tint
        onAct: function(id, action, value) { card.act(id, action, value) }
        onHoldStart: card.holdStart()
        onHoldEnd: card.holdEnd()
      }

      ActivityBlock {
        visible: card.topActivity !== null && card.topActivity.id !== "media"
        width: parent.width
        height: visible ? implicitHeight : 0
        activity: visible ? card.topActivity : null
        onAct: function(id, action, value) { card.act(id, action, value) }
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
        model: card.shownRowIds

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
          width: chipText.implicitWidth + Commons.Style.spacing.huge * 1.5
          height: card.rowHeight
          radius: height / 2
          color: chip.selected ? Commons.Color.menu.selectedBackground : "transparent"

          Text {
            id: chipText
            textFormat: Text.PlainText
            text: chip.modelData.label
            color: chip.selected ? Commons.Color.menu.selectedText : card.textColor
            opacity: chip.selected ? 1 : 0.75
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
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
      width: dndText.implicitWidth + Commons.Style.spacing.huge * 1.5
      height: card.rowHeight
      radius: height / 2
      color: dndToggle.on ? Commons.Color.menu.selectedBackground : "transparent"

      Text {
        id: dndText
        textFormat: Text.PlainText
        text: Dnd.GLYPH + "  Do Not Disturb"
        color: dndToggle.on ? Commons.Color.accent : card.textColor
        opacity: dndToggle.on ? 1 : 0.75
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.bodySmall
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
      width: pinText.implicitWidth + Commons.Style.spacing.huge * 1.5
      height: card.rowHeight
      radius: height / 2
      color: card.pinned ? Commons.Color.menu.selectedBackground : "transparent"

      Text {
        id: pinText
        textFormat: Text.PlainText
        text: card.pinned ? "Pinned" : "Pin"
        color: card.pinned ? Commons.Color.accent : card.textColor
        opacity: card.pinned ? 1 : 0.75
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.bodySmall
        anchors.centerIn: parent
      }

      MouseArea {
        anchors.fill: parent
        onClicked: card.pinClicked()
      }
    }
  }
}
