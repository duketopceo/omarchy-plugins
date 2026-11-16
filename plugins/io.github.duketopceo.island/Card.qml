import QtQuick 6.11
import qs.Commons as Commons
import "Dnd.js" as Dnd
import "Pages.js" as Pages
import "More.js" as More
import "Presentation.js" as Presentation
import "Controls.js" as Controls

// The expanded card's content: the active page, and a compact row with the
// page chips (Pages.js, frozen by the window while open), a Do Not Disturb
// bell and the pin control. Every page is as tall as its content: the window
// asks countFor() and heightFor() once when the card opens or the page
// changes and holds that size while open (KTD2). It clips this content to the
// morphing shape.
Item {
  id: card

  property date now: new Date()
  property string page: "home"
  // The chip row and the More list, from the window's commit.
  property var chips: ["home", "system", "more"]
  property var moreList: ["settings"]
  property bool pinned: false
  // The Island root: sources, settings, actions.
  property var island: null
  // Activity.layout() for this window: { top, second, rows, held }.
  property var layout: null
  // Media accent from the album art, or the theme accent.
  property color tint: Commons.Color.accent
  // The pill row above the card and the tallest the card may be, from the window.
  property int band: 28
  property int maxHeight: 380
  // Rows the active page shows: the count the window committed to.
  property int maxRows: 0

  signal pageSelected(string id)
  signal pinClicked()
  signal cardClicked()
  signal holdStart()
  signal holdEnd()
  signal act(string id, string action, real value)

  readonly property int pad: Commons.Style.spacing.huge
  readonly property int rowHeight: Commons.Style.space(24)
  readonly property color textColor: Commons.Color.popups.text

  function pageItem(id) {
    switch (id) {
      case "home": return homePage
      case "music": return musicPage
      case "agents": return agentsPage
      case "system": return systemPage
      case "more": return morePage
      case "shots": return shotsPage
      case "messages": return messagesPage
      case "dayflow": return dayflowPage
      case "settings": return settingsPage
      default: return null
    }
  }

  // The rows a page would show now, for the window's commit.
  function countFor(id) {
    var p = card.pageItem(id)
    return p ? p.count() : 0
  }

  // The card height for `rows` rows of page `id`.
  function heightFor(id, rows) {
    var p = card.pageItem(id)
    return Presentation.cardHeight({
      band: card.band,
      pad: card.pad,
      content: p ? p.heightFor(rows) : 0,
      gap: Commons.Style.spacing.lg,
      pageRowH: card.rowHeight,
      max: card.maxHeight,
      // A floor of two control rows, so a short page still reads as a card.
      min: card.band + card.pad * 2 + Commons.Style.spacing.lg + card.rowHeight + Commons.Style.spacing.controlHeight * 2
    })
  }

  // The pin control's center in window coordinates, for the live hover check.
  function pinCenter() {
    var p = pin.mapToItem(null, pin.width / 2, pin.height / 2)
    return { x: p.x, y: p.y }
  }

  function open(id) {
    card.pageSelected(id)
    card.cardClicked()
  }

  // A click anywhere on the card raises keyboard focus; controls inside still
  // get their own clicks.
  TapHandler { onTapped: card.cardClicked() }

  // ---- hover hints: HoverButton finds this host by walking up its parents ----
  readonly property bool hintHost: true
  property var hintOwner: null
  function showHint(text, item) {
    if (!item || text === "") { card.hideHint(card.hintOwner); return }
    card.hintOwner = item
    hintBubble.text = text
    var p = item.mapToItem(card, 0, 0)
    var at = Controls.hintPos({ x: p.x, y: p.y, w: item.width, h: item.height },
                              { w: hintBubble.width, h: hintBubble.height },
                              { w: card.width, h: card.height }, Commons.Style.spacing.sm)
    hintBubble.x = at.x
    hintBubble.y = at.y
    hintBubble.visible = true
  }
  function hideHint(item) {
    if (item !== card.hintOwner) return
    card.hintOwner = null
    hintBubble.visible = false
  }
  onPageChanged: { card.hintOwner = null; hintBubble.visible = false }
  onVisibleChanged: if (!card.visible) { card.hintOwner = null; hintBubble.visible = false }

  HintBubble {
    id: hintBubble
    z: 100
    visible: false
    maxWidth: card.width - Commons.Style.spacing.lg * 2
  }

  Item {
    id: pageArea
    x: card.pad
    y: card.pad
    width: card.width - card.pad * 2
    height: pageRow.y - y - Commons.Style.spacing.lg
    clip: true

    HomePage {
      id: homePage
      visible: card.page === "home"
      width: parent.width
      height: parent.height
      island: card.island
      now: card.now
      layout: card.layout
      maxRows: card.maxRows
      onAct: function(id, action) { card.act(id, action, 0) }
      onOpenPage: function(id) { card.open(id) }
    }

    MusicPage {
      id: musicPage
      visible: card.page === "music"
      width: parent.width
      height: parent.height
      island: card.island
      now: card.now
      tint: card.tint
      onAct: function(id, action, value) { card.act(id, action, value) }
      onHoldStart: card.holdStart()
      onHoldEnd: card.holdEnd()
    }

    AgentsPage {
      id: agentsPage
      visible: card.page === "agents"
      width: parent.width
      height: parent.height
      island: card.island
      maxRows: card.maxRows
    }

    SystemPage {
      id: systemPage
      visible: card.page === "system"
      width: parent.width
      height: parent.height
      island: card.island
      maxRows: card.maxRows
    }

    MorePage {
      id: morePage
      visible: card.page === "more"
      width: parent.width
      height: parent.height
      island: card.island
      entries: card.moreList
      onOpenPage: function(id) { card.open(id) }
    }

    ListPage {
      id: shotsPage
      visible: card.page === "shots"
      width: parent.width
      height: parent.height
      maxRows: card.maxRows
      summary: card.island && card.island.shots ? card.island.shots.total + " captioned screenshots" : ""
      emptyText: "No captioned screenshots yet"
      rowHint: "Open this screenshot"
      rows: card.island ? card.island.shotRows : []
      onActivated: function(row) { if (card.island) card.island.openShot(row.name) }
    }

    ListPage {
      id: messagesPage
      visible: card.page === "messages"
      width: parent.width
      height: parent.height
      maxRows: card.maxRows
      summary: More.unreadText(card.island ? card.island.messages.unread : 0)
      emptyText: "All caught up"
      actionLabel: "Open Blip"
      actionHint: "Open Blip"
      rowHint: "Open this chat in Blip"
      rows: card.island ? card.island.messages.rows : []
      onAction: if (card.island) card.island.openBlip()
      onActivated: function(row) { if (card.island) card.island.openBlipChat(row.chat) }
    }

    ListPage {
      id: dayflowPage
      visible: card.page === "dayflow"
      width: parent.width
      height: parent.height
      maxRows: card.maxRows
      summary: "Dayflow"
      emptyText: "Dayflow did not answer"
      rows: card.island ? card.island.dayflowRows : []
    }

    SettingsPage {
      id: settingsPage
      visible: card.page === "settings"
      width: parent.width
      height: parent.height
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
      spacing: Commons.Style.spacing.md

      Repeater {
        model: card.chips

        // Idle chips are dimmed text on nothing; hover adds a fill; the
        // selected chip is the filled one with the selected text color.
        HoverButton {
          id: chip
          required property string modelData
          // More stays lit while one of its pages is open from the list.
          readonly property bool lit: card.page === chip.modelData
            || (chip.modelData === "more" && card.chips.indexOf(card.page) < 0)
          selected: chip.lit
          hint: chip.lit ? "" : (chip.modelData === "more" ? "More pages" : "Open " + Pages.label(chip.modelData))
          width: chipText.implicitWidth + Commons.Style.spacing.huge * 1.2
          height: card.rowHeight
          radius: height / 2
          onClicked: card.open(chip.modelData)

          Txt {
            id: chipText
            kind: "caption"
            text: Pages.label(chip.modelData)
            color: chip.lit ? Commons.Color.menu.selectedText : card.textColor
            opacity: chip.lit || chip.hovered ? 1 : 0.75
            anchors.centerIn: parent
          }
        }
      }
    }

    // Omarchy's Do Not Disturb, toggled through Omarchy's own command (R10).
    // A bell only, so six chips fit; Home has the labelled toggle.
    HoverButton {
      id: dndToggle
      visible: card.island !== null && card.island.dndAvailable === true
      readonly property bool on: card.island !== null && card.island.dndOn === true
      selected: dndToggle.on
      hint: dndToggle.on ? "Turn off Do Not Disturb" : "Turn on Do Not Disturb"
      anchors.right: pin.left
      anchors.rightMargin: Commons.Style.spacing.md
      width: card.rowHeight + Commons.Style.spacing.lg
      height: card.rowHeight
      radius: height / 2
      onClicked: if (card.island) card.island.toggleDnd()

      Txt {
        kind: "caption"
        text: Dnd.GLYPH
        color: dndToggle.on ? Commons.Color.accent : card.textColor
        opacity: dndToggle.on || dndToggle.hovered ? 1 : 0.75
        anchors.centerIn: parent
      }
    }

    // The only control that pins; the pinned state is drawn filled.
    HoverButton {
      id: pin
      selected: card.pinned
      hint: card.pinned ? "Unpin the card" : "Keep the card open"
      anchors.right: parent.right
      width: pinText.implicitWidth + Commons.Style.spacing.huge * 1.2
      height: card.rowHeight
      radius: height / 2
      onClicked: card.pinClicked()

      Txt {
        id: pinText
        kind: "caption"
        text: card.pinned ? "Pinned" : "Pin"
        color: card.pinned ? Commons.Color.accent : card.textColor
        opacity: card.pinned || pin.hovered ? 1 : 0.75
        anchors.centerIn: parent
      }
    }
  }
}
