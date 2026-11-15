import QtQuick
import Quickshell
import Quickshell.Services.Mpris
import qs.Commons as Commons
import "Media.js" as Media

// Media tab of the expanded panel (688 x ~298). Loaded with `notch` set to
// the root Notch item, which exposes `mediaActivity` (MediaActivity.qml).
Item {
  id: tab
  property var notch: null
  readonly property var media: notch ? notch.mediaActivity : null
  readonly property var player: media ? media.player : null
  readonly property color textColor: notch ? notch.textColor : Tk.text
  readonly property color dimColor: notch ? notch.dimColor : Tk.dim
  readonly property string family: notch ? notch.fontFamily : Commons.Style.font.family
  readonly property bool fp: !!media && media.isFastpotify && media.cliReady
  property bool dragging: false
  property real dragFrac: 0

  implicitWidth: 688
  implicitHeight: 298

  // Position only ticks while this tab is on screen.
  onVisibleChanged: if (media) media.tracking = visible
  Component.onCompleted: if (media) media.tracking = visible
  Component.onDestruction: if (media) media.tracking = false

  readonly property real frac: dragging ? dragFrac : Media.fraction(media ? media.position : 0, media ? media.length : 0)

  component Caption: Text {
    textFormat: Text.PlainText
    color: tab.dimColor
    font.family: tab.family
    font.pixelSize: Tk.fs.caption
    font.letterSpacing: 0.8
    font.capitalization: Font.AllUppercase
  }

  component Btn: Rectangle {
    id: b
    property string glyph: ""
    property bool on: false
    property bool dim: false
    signal clicked()
    width: 44; height: 32; radius: Tk.r(16)
    color: ma.containsMouse ? Tk.tint(0.22) : Tk.tint(b.on ? 0.18 : 0.08)
    opacity: b.dim ? 0.35 : 1
    Text {
      anchors.centerIn: parent
      textFormat: Text.PlainText
      text: b.glyph
      color: b.on ? Tk.accent : tab.textColor
      font.family: tab.family
      font.pixelSize: Commons.Style.font.icon
    }
    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; enabled: !b.dim; onClicked: b.clicked() }
  }

  readonly property int artSize: height - 28 - 14

  Rectangle {
    id: art
    width: tab.artSize; height: tab.artSize; radius: Tk.r(14)
    color: Tk.tint(0.08)
    clip: true
    Image {
      anchors.fill: parent
      source: media ? media.artUrl : ""
      fillMode: Image.PreserveAspectCrop
      asynchronous: true
      visible: status === Image.Ready
    }
    Text {
      anchors.centerIn: parent
      visible: !media || media.artUrl === ""
      textFormat: Text.PlainText
      text: Media.MUSIC_GLYPH
      color: tab.dimColor
      font.family: tab.family
      font.pixelSize: Commons.Style.font.display
    }
  }

  Column {
    anchors.left: art.right
    anchors.leftMargin: 20
    anchors.right: parent.right
    anchors.top: art.top
    anchors.bottom: art.bottom
    spacing: 4

    Caption { text: tab.player && tab.player.identity ? String(tab.player.identity) : "Media" }
    Text {
      width: parent.width
      textFormat: Text.PlainText
      elide: Text.ElideRight
      text: tab.player ? String(tab.player.trackTitle || tab.player.identity || "") : "Nothing playing"
      color: tab.player ? tab.textColor : tab.dimColor
      font.family: tab.family
      font.pixelSize: Commons.Style.font.displayLarge
      font.weight: Font.DemiBold
    }
    Text {
      width: parent.width
      textFormat: Text.PlainText
      elide: Text.ElideRight
      text: tab.player ? String(tab.player.trackArtist || "") : ""
      color: tab.dimColor
      font.family: tab.family
      font.pixelSize: Commons.Style.font.heading
    }
  }

  // Transport pinned to the art's lower half: progress, times, buttons.
  Column {
    anchors.left: art.right
    anchors.leftMargin: 20
    anchors.right: parent.right
    anchors.bottom: art.bottom
    spacing: 6

    // Seekable progress bar.
    Item {
      width: parent.width
      height: 16
      SegBar { id: track; anchors.verticalCenter: parent.verticalCenter; width: parent.width; value: tab.frac; track: Tk.tint(0.15) }
      MouseArea {
        anchors.fill: parent
        enabled: !!tab.player
        onPressed: function(e) { tab.dragging = true; tab.dragFrac = Math.max(0, Math.min(1, e.x / width)) }
        onPositionChanged: function(e) { if (pressed) tab.dragFrac = Math.max(0, Math.min(1, e.x / width)) }
        onReleased: { tab.dragging = false; if (tab.media) tab.media.seekTo(tab.dragFrac * tab.media.length) }
        onCanceled: tab.dragging = false
      }
    }
    Item {
      width: parent.width
      height: 14
      Text {
        textFormat: Text.PlainText
        text: Media.formatTime(tab.frac * (media ? media.length : 0))
        color: tab.dimColor; font.family: tab.family; font.pixelSize: Tk.fs.bodySmall
      }
      Text {
        anchors.right: parent.right
        textFormat: Text.PlainText
        text: Media.formatTime(media ? media.length : 0)
        color: tab.dimColor; font.family: tab.family; font.pixelSize: Tk.fs.bodySmall
      }
    }
    Row {
      spacing: 8
      Btn { glyph: "\u{F049D}"; visible: tab.fp; on: !!media && media.shuffleOn; onClicked: media.toggleShuffle() }
      Btn { glyph: "\u{F04AE}"; dim: !tab.player; onClicked: tab.player.previous() }
      Btn { glyph: tab.player && tab.player.isPlaying ? "\u{F03E4}" : "\u{F040A}"; dim: !tab.player; onClicked: tab.player.togglePlaying() }
      Btn { glyph: "\u{F04AD}"; dim: !tab.player; onClicked: tab.player.next() }
      Btn { glyph: !!media && media.repeatMode === "track" ? "\u{F0457}" : "\u{F0456}"; visible: tab.fp; on: !!media && media.repeatMode !== "off"; onClicked: media.cycleRepeat() }
      Btn { glyph: !!media && media.liked ? "\u{F02D1}" : "\u{F02D5}"; visible: tab.fp; on: !!media && media.liked; onClicked: media.like() }
    }
  }

  // Source picker (one chip per MPRIS player) and the fastpotify launcher.
  Row {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    spacing: 6
    Repeater {
      model: media ? media.players : []
      Rectangle {
        id: chip
        required property var modelData
        readonly property bool current: !!tab.player && !!chip.modelData && tab.player.dbusName === chip.modelData.dbusName
        height: 24; width: Math.min(130, chipText.implicitWidth + 16); radius: Tk.r(12)
        color: current ? Tk.tint(0.2) : Tk.tint(0.07)
        Text {
          id: chipText
          anchors.centerIn: parent
          width: parent.width - 12
          horizontalAlignment: Text.AlignHCenter
          textFormat: Text.PlainText
          elide: Text.ElideRight
          text: chip.modelData ? String(chip.modelData.identity || "") : ""
          color: tab.textColor; font.family: tab.family; font.pixelSize: Tk.fs.caption
        }
        MouseArea { anchors.fill: parent; onClicked: tab.media.preferred = chip.modelData.dbusName }
      }
    }
    Item { width: 1; height: 1 }
    Rectangle {
      visible: !!media && media.cliReady
      height: 24; width: openText.implicitWidth + 16; radius: Tk.r(12)
      color: openHit.containsMouse ? Tk.tint(0.22) : Tk.tint(0.1)
      Text {
        id: openText
        anchors.centerIn: parent
        textFormat: Text.PlainText
        text: "Open fastpotify"
        color: tab.textColor; font.family: tab.family; font.pixelSize: Tk.fs.caption
      }
      MouseArea { id: openHit; anchors.fill: parent; hoverEnabled: true; onClicked: tab.media.openApp() }
    }
  }
}
