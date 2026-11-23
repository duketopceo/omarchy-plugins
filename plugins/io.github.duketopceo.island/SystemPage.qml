import QtQuick 6.11
import qs.Commons as Commons
import "Glyphs.js" as Glyphs

// System: three rings (Battery, CPU, Memory) with the percentage in the
// middle and a one-word caption, a row of chips (network, Tailscale, fan) and
// the power-profile segmented control. Status.system() turns the helper's
// data into rings, chips and profiles; the root samples them only while a
// System page is open. The fan chip opens the Resource & Fan panel when that
// plugin is installed. The card's height comes from heightFor() and does not
// move while it is open (KTD2).
Item {
  id: page

  property var island: null
  property int maxRows: 0

  readonly property var view: page.island ? page.island.systemView : null
  readonly property var rings: page.view ? page.view.rings : []
  readonly property var chips: page.view ? page.view.chips : []
  readonly property var profiles: page.view ? page.view.profiles : null

  readonly property int gap: Commons.Style.spacing.lg
  readonly property int rowH: Commons.Style.spacing.controlHeight
  readonly property int ringTileH: Commons.Style.space(128)
  readonly property int ringSize: Commons.Style.space(80)

  function count() { return page.rings.length > 0 ? 1 : 0 }
  function heightFor(n) {
    // No rings yet: reserve the full layout, because the card does not
    // re-measure when the first reading arrives.
    return page.ringTileH + page.gap + page.rowH + (page.profilesOn ? page.gap + page.rowH : 0)
  }
  // The profile control exists only while power-profiles-daemon answers:
  // a dead control would be a fake button.
  readonly property bool profilesOn: page.profiles !== null && page.profiles.available

  // ---- one ring tile ----
  component RingTile: Item {
    id: tile
    required property var modelData

    Plate {
      anchors.fill: parent
    }
    Ring {
      id: ring
      width: page.ringSize
      height: width
      anchors.horizontalCenter: parent.horizontalCenter
      anchors.top: parent.top
      anchors.topMargin: Commons.Style.spacing.xl
      level: tile.modelData.level
      tone: tile.modelData.tone === "urgent" ? Commons.Color.urgent : Commons.Color.accent

      Txt {
        icon: true
        visible: tile.modelData.charging
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.16
        width: implicitWidth
        opacity: 1
        color: Commons.Color.accent
        text: Glyphs.GLYPHS.bolt
      }
      Txt {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: tile.modelData.charging ? Commons.Style.spacing.md : 0
        width: implicitWidth
        kind: "display"
        font.pixelSize: Commons.Style.font.title + Commons.Style.spacing.md
        numeric: true
        text: tile.modelData.pct + "%"
      }
    }
    Txt {
      anchors.horizontalCenter: parent.horizontalCenter
      anchors.top: ring.bottom
      anchors.topMargin: Commons.Style.spacing.md
      width: Math.min(implicitWidth, parent.width)
      kind: "caption"
      text: tile.modelData.caption
    }
  }

  // ---- one chip: a glyph and a short word ----
  component Chip: Item {
    id: chip
    required property var modelData
    readonly property bool clickable: chip.modelData.action === "fan" && page.island !== null && page.island.fanPanel
    implicitWidth: chipRow.implicitWidth + Commons.Style.spacing.xxl * 2
    height: page.rowH

    Plate {
      anchors.fill: parent
      radius: height / 2
    }
    // Only the fan chip is a button; the others are display-only.
    HoverButton {
      anchors.fill: parent
      z: 1
      radius: height / 2
      visible: chip.clickable
      hint: "Open the fan panel"
      onClicked: page.island.openFanPanel()
    }
    Item {
      anchors.fill: parent

      Row {
        id: chipRow
        anchors.centerIn: parent
        spacing: Commons.Style.spacing.lg

        Txt {
          icon: true
          anchors.verticalCenter: parent.verticalCenter
          opacity: chip.modelData.on ? 1 : 0.45
          text: Glyphs.GLYPHS[chip.modelData.icon]
        }
        Txt {
          anchors.verticalCenter: parent.verticalCenter
          width: Math.min(implicitWidth, Commons.Style.space(190))
          opacity: chip.modelData.on ? 1 : 0.55
          text: chip.modelData.text
        }
      }
    }
  }

  EmptyNote {
    visible: page.rings.length === 0
    width: parent.width
    height: page.rowH
    text: "Reading system state"
  }

  Column {
    width: parent.width
    spacing: page.gap
    visible: page.rings.length > 0

    Row {
      id: ringRow
      width: parent.width
      spacing: page.gap
      readonly property int tileW: Math.floor((width - spacing * 2) / 3)

      Repeater {
        model: page.rings

        RingTile {
          width: ringRow.tileW
          height: page.ringTileH
        }
      }
    }

    Row {
      id: chipRow2
      height: page.rowH
      spacing: page.gap

      Repeater {
        model: page.chips

        Chip {}
      }
    }

    // The power profile: a segmented control. Hidden when the daemon is not
    // running (nothing to set); the active profile is the filled segment.
    Item {
      id: seg
      width: parent.width
      height: page.rowH
      visible: page.profilesOn
      readonly property var names: page.profiles ? page.profiles.names : []
      readonly property bool available: page.profiles !== null && page.profiles.available
      readonly property string active: page.profiles ? page.profiles.active : ""

      Plate {
        anchors.fill: parent
        radius: height / 2
      }
      Row {
        anchors.fill: parent

        Repeater {
          model: seg.names

          HoverButton {
            id: segment
            required property var modelData
            enabled: seg.available
            selected: seg.active === segment.modelData.name
            hint: segment.selected ? "" : "Power profile: " + segment.modelData.hint
            width: seg.width / Math.max(1, seg.names.length)
            height: seg.height
            radius: height / 2
            onClicked: if (page.island) page.island.setProfile(segment.modelData.name)

            Row {
              anchors.centerIn: parent
              spacing: Commons.Style.spacing.lg

              Txt {
                icon: true
                anchors.verticalCenter: parent.verticalCenter
                color: segment.selected ? Commons.Color.menu.selectedText : Commons.Color.popups.text
                text: Glyphs.profileGlyph(segment.modelData.name)
              }
              Txt {
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(implicitWidth, segment.width - Commons.Style.spacing.huge * 3)
                color: segment.selected ? Commons.Color.menu.selectedText : Commons.Color.popups.text
                text: segment.modelData.label
              }
            }
          }
        }
      }
    }
  }
}
