import QtQuick 6.11
import qs.Commons as Commons
import "Glyphs.js" as Glyphs

// Dayflow: a hero row (a recording indicator, the state word, the one action
// that fits the state, and Open Dayflow when its panel is installed) over
// three stat tiles: frames today, last frame as relative time, and storage.
// Blocks pending shows only when there are some. `More.dayflowView` shapes
// the data; the buttons run `dayflow pause|resume` through the root.
Item {
  id: page

  property var island: null
  property int maxRows: 0

  readonly property var view: page.island ? page.island.dayflowView : null
  readonly property int gap: Commons.Style.spacing.lg
  readonly property int heroH: Commons.Style.space(72)
  readonly property int statH: Commons.Style.space(92)
  readonly property int rowH: Commons.Style.spacing.controlHeight

  function count() { return page.view ? 1 : 0 }
  function heightFor(n) { return n <= 0 ? page.rowH : page.heroH + page.gap + page.statH }

  // A tile: one big value over a short caption.
  component Stat: Item {
    id: stat
    property string value: ""
    property string caption: ""

    Plate {
      anchors.fill: parent
    }
    Column {
      anchors.centerIn: parent
      width: parent.width - Commons.Style.spacing.xxl * 2
      spacing: Commons.Style.spacing.md

      Txt {
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        kind: "display"
        numeric: true
        text: stat.value
      }
      Txt {
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        kind: "caption"
        text: stat.caption
      }
    }
  }

  // A glyph-and-word button on the hero row.
  component Action: HoverButton {
    id: action
    property string glyph: ""
    property string label: ""
    outlined: true
    radius: height / 2
    width: actionRow.implicitWidth + Commons.Style.spacing.huge * 2
    height: page.rowH

    Row {
      id: actionRow
      anchors.centerIn: parent
      spacing: Commons.Style.spacing.lg

      Txt {
        icon: true
        anchors.verticalCenter: parent.verticalCenter
        text: action.glyph
      }
      Txt {
        anchors.verticalCenter: parent.verticalCenter
        text: action.label
      }
    }
  }

  EmptyNote {
    visible: page.view === null
    width: parent.width
    height: page.rowH
    text: "Dayflow did not answer"
  }

  Column {
    width: parent.width
    spacing: page.gap
    visible: page.view !== null

    // ---- hero ----
    Item {
      id: hero
      width: parent.width
      height: page.heroH

      Plate {
        anchors.fill: parent
        strong: true
      }

      // The indicator: a pulsing dot while recording, a pause glyph while paused.
      Item {
        id: lamp
        width: Commons.Style.space(44)
        height: width
        x: Commons.Style.spacing.huge
        anchors.verticalCenter: parent.verticalCenter
        readonly property bool recording: page.view !== null && page.view.state === "recording"
        readonly property bool paused: page.view !== null && page.view.state === "paused"

        Rectangle {
          id: halo
          anchors.centerIn: parent
          width: parent.width
          height: width
          radius: width / 2
          color: Commons.Color.accent
          opacity: 0
          visible: lamp.recording

          ParallelAnimation {
            running: lamp.recording && page.visible && Commons.Style.duration(1400) > 0
            loops: Animation.Infinite
            NumberAnimation { target: halo; property: "scale"; from: 0.45; to: 1; duration: Commons.Style.duration(1400); easing.type: Easing.OutCubic }
            NumberAnimation { target: halo; property: "opacity"; from: 0.45; to: 0; duration: Commons.Style.duration(1400); easing.type: Easing.OutCubic }
          }
        }
        Rectangle {
          anchors.centerIn: parent
          width: Commons.Style.space(16)
          height: width
          radius: width / 2
          visible: !lamp.paused
          color: lamp.recording ? Commons.Color.accent : Qt.alpha(Commons.Color.popups.text, 0.3)
        }
        Txt {
          icon: true
          visible: lamp.paused
          anchors.centerIn: parent
          width: implicitWidth
          font.pixelSize: Commons.Style.font.heading + Commons.Style.spacing.xl
          text: Glyphs.GLYPHS.pause
        }
      }

      Column {
        anchors.left: lamp.right
        anchors.leftMargin: Commons.Style.spacing.xxl
        anchors.verticalCenter: parent.verticalCenter
        spacing: Commons.Style.spacing.md

        Txt {
          kind: "heading"
          font.pixelSize: Commons.Style.font.heading + Commons.Style.spacing.md
          text: page.view ? page.view.title : ""
        }
        Tag {
          visible: page.view !== null && page.view.pending > 0
          dim: true
          tone: Qt.alpha(Commons.Color.popups.text, 0.5)
          text: page.view ? page.view.pending + (page.view.pending === 1 ? " block pending" : " blocks pending") : ""
        }
      }

      Row {
        anchors.right: parent.right
        anchors.rightMargin: Commons.Style.spacing.huge
        anchors.verticalCenter: parent.verticalCenter
        spacing: Commons.Style.spacing.lg

        Action {
          visible: page.view !== null && page.view.panel
          glyph: Glyphs.GLYPHS.open
          label: "Open Dayflow"
          hint: "Open the Dayflow panel"
          onClicked: if (page.island) page.island.openDayflowPanel()
        }
        Action {
          visible: page.view !== null && page.view.action !== ""
          glyph: page.view && page.view.action === "resume" ? Glyphs.GLYPHS.play : Glyphs.GLYPHS.pause
          label: page.view && page.view.action === "resume" ? "Resume" : "Pause"
          hint: page.view && page.view.action === "resume" ? "Resume screen capture" : "Pause screen capture"
          onClicked: if (page.island && page.view) page.island.dayflowAction(page.view.action)
        }
      }
    }

    // ---- stats ----
    Row {
      id: stats
      width: parent.width
      spacing: page.gap
      readonly property int tileW: Math.floor((width - spacing * 2) / 3)

      Stat {
        width: stats.tileW
        height: page.statH
        value: page.view ? page.view.frames : ""
        caption: "frames today"
      }
      Stat {
        width: stats.tileW
        height: page.statH
        value: page.view ? page.view.last : ""
        caption: "last frame"
      }
      Stat {
        width: stats.tileW
        height: page.statH
        value: page.view ? (page.view.storage || "none") : ""
        caption: "storage"
      }
    }
  }
}
