// Wisp Dashboard: the omarchy-max lock screen.
// A Lock Screen Explorer custom design. Install with scripts/install-lock-design.sh,
// which copies it to ~/.config/omarchy/lock-designs/ (the import below is
// resolved relative to that folder, so keep it as is).
//
// Privacy: the lock screen shows counts and glyphs only. Notifications are
// counted from history file names; no notification text, calendar title or
// Wisp state is ever read here.
import QtQuick
import Qt.labs.folderlistmodel
import Quickshell
import qs.Commons
import qs.Commons as Commons
import "../plugins/io.github.sirjul1337.lock-explorer/designs"

DesignBase {
  id: lock
  inputItem: field.input

  readonly property color ink: Commons.Color.lock.text
  readonly property color accent: Commons.Color.lock.borderActive
  readonly property color panel: lock.withAlpha(Commons.Color.lock.background, 0.62)
  readonly property color hairline: lock.withAlpha(Commons.Color.lock.text, 0.1)

  // When this lock began, so only notifications that arrived since count.
  readonly property real lockedAtMs: Date.now()

  LiveWeather { id: weather; lock: lock }
  LiveMedia { id: media }
  LiveBattery { id: battery }
  LiveSystem { id: system }

  // History files are named <epoch-ms>-<n>.json; only the names are read.
  // Omarchy caps history at 10 files, so a full folder swaps its oldest file
  // for each new one and the count never changes: recount on every insert.
  FolderListModel {
    id: history
    folder: "file://" + Quickshell.env("HOME") + "/.local/state/omarchy/notifications/history"
    nameFilters: ["*.json"]
    showDirs: false
  }
  property int missed: 0
  function countMissed() {
    var n = 0
    for (var i = 0; i < history.count; i++) {
      var ts = parseInt(String(history.get(i, "fileName")).split("-")[0])
      if (ts > lock.lockedAtMs) n++
    }
    lock.missed = n
  }
  Connections {
    target: history
    function onRowsInserted() { lock.countMissed() }
    function onCountChanged() { lock.countMissed() }
  }

  Wallpaper { anchors.fill: parent; lock: lock; blur: 0.9; dim: 0.35 }

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    onClicked: { lock.wakeRequested(); lock.forcePasswordFocus() }
    onPositionChanged: lock.wakeRequested()
  }

  component Tile: Rectangle {
    property string icon: ""
    property string label: ""
    property string value: ""
    property string sub: ""
    property real fill: -1
    width: 196
    height: 104
    radius: 16
    color: lock.panel
    border.width: 1
    border.color: lock.hairline
    Column {
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: 16
      spacing: 4
      Row {
        spacing: 8
        Text { text: icon; textFormat: Text.PlainText; color: lock.accent; font.family: Style.font.family; font.pixelSize: Style.font.title }
        Text {
          anchors.verticalCenter: parent.verticalCenter
          text: label.toUpperCase()
          textFormat: Text.PlainText
          color: lock.withAlpha(lock.ink, 0.55)
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          font.letterSpacing: 2
        }
      }
      Text {
        width: parent.width
        text: value
        textFormat: Text.PlainText
        elide: Text.ElideRight
        color: lock.ink
        font.family: Style.font.family
        font.pixelSize: Style.font.heading
        font.weight: Font.DemiBold
      }
      Text {
        width: parent.width
        visible: sub.length > 0
        text: sub
        textFormat: Text.PlainText
        elide: Text.ElideRight
        color: lock.withAlpha(lock.ink, 0.55)
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
      }
    }
    Rectangle {
      visible: fill >= 0
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      anchors.margins: 12
      height: 3
      radius: 2
      color: lock.withAlpha(lock.ink, 0.14)
      Rectangle { width: parent.width * Math.max(0, Math.min(1, fill)); height: parent.height; radius: 2; color: lock.accent }
    }
  }

  // The Wisp orb: decoration only. A soft ember that breathes, with two rings
  // drifting out of it. It reads nothing and takes no input; it shivers once
  // after a wrong password and rests while the screen is asleep.
  component WispOrb: Item {
    id: orb
    width: 132
    height: 132
    property real breath: 0
    property real drift: 0
    property real shake: 0

    SequentialAnimation on breath {
      running: lock.animating
      loops: Animation.Infinite
      NumberAnimation { from: 0; to: 1; duration: 2600; easing.type: Easing.InOutSine }
      NumberAnimation { from: 1; to: 0; duration: 2600; easing.type: Easing.InOutSine }
    }
    NumberAnimation on drift {
      running: lock.animating
      loops: Animation.Infinite
      from: 0; to: 1; duration: 4200
    }
    SequentialAnimation {
      id: shiver
      NumberAnimation { target: orb; property: "shake"; to: 1; duration: 60 }
      NumberAnimation { target: orb; property: "shake"; to: -1; duration: 90 }
      NumberAnimation { target: orb; property: "shake"; to: 0.5; duration: 80 }
      NumberAnimation { target: orb; property: "shake"; to: 0; duration: 120 }
    }
    Connections {
      target: lock
      function onFailedAttemptsChanged() { if (lock.failedAttempts > 0) shiver.restart() }
    }

    Repeater {
      model: 2
      Rectangle {
        readonly property real t: (orb.drift + index * 0.5) % 1
        anchors.centerIn: parent
        width: 44 + t * 84
        height: width
        radius: width / 2
        color: "transparent"
        border.width: 1.5
        border.color: lock.withAlpha(lock.accent, 0.45 * (1 - t))
      }
    }
    Rectangle {
      anchors.centerIn: parent
      anchors.horizontalCenterOffset: orb.shake * 6
      width: 46 + orb.breath * 8
      height: width
      radius: width / 2
      color: lock.withAlpha(lock.accent, 0.22 + orb.breath * 0.12)
      Rectangle {
        anchors.centerIn: parent
        width: parent.width * 0.52
        height: width
        radius: width / 2
        color: lock.withAlpha(lock.accent, 0.85)
      }
    }
  }

  // Clock and date, top left.
  Column {
    anchors.left: parent.left
    anchors.top: parent.top
    anchors.leftMargin: Math.round(parent.width * 0.06)
    anchors.topMargin: Math.round(parent.height * 0.08)
    spacing: 0
    Text {
      text: lock.clock("HH:mm")
      textFormat: Text.PlainText
      color: lock.ink
      font.family: Style.font.family
      font.pixelSize: Math.round(Style.font.baseSize * 9)
      font.weight: Font.DemiBold
      font.letterSpacing: -3
    }
    Text {
      text: lock.date("dddd, d MMMM")
      textFormat: Text.PlainText
      color: lock.withAlpha(lock.ink, 0.7)
      font.family: Style.font.family
      font.pixelSize: Style.font.title
    }
  }

  // Orb, greeting and password, centered.
  Column {
    anchors.centerIn: parent
    spacing: 18

    WispOrb { anchors.horizontalCenter: parent.horizontalCenter }

    Text {
      anchors.horizontalCenter: parent.horizontalCenter
      text: lock.displayName
      textFormat: Text.PlainText
      color: lock.withAlpha(lock.ink, 0.8)
      font.family: Style.font.family
      font.pixelSize: Style.font.subtitle
    }

    PasswordField {
      id: field
      lock: lock
      anchors.horizontalCenter: parent.horizontalCenter
      width: 400
      height: 54
      placeholder: lock.tr("Password")
    }

    Text {
      anchors.horizontalCenter: parent.horizontalCenter
      visible: lock.failedAttempts > 0
      text: lock.failedAttempts === 1 ? lock.tr("1 failed attempt") : lock.tr("%1 failed attempts").arg(lock.failedAttempts)
      textFormat: Text.PlainText
      color: Commons.Color.lock.textError
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
    }
  }

  // Dashboard tiles along the bottom. Music only shows while something plays.
  Row {
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: Math.round(parent.height * 0.07)
    spacing: 14

    Tile {
      icon: weather.glyph
      label: lock.tr("Weather")
      value: weather.failed || !weather.current ? "—" : weather.tempC
      sub: weather.failed ? lock.tr("Offline") : [weather.condition, weather.place].filter(function(s) { return s && s.length }).join(" · ")
    }
    Tile {
      visible: media.hasMedia
      icon: media.playing ? "󰐊" : "󰏤"
      label: lock.tr("Now playing")
      value: media.title
      sub: media.artist
    }
    Tile {
      icon: battery.hasBattery ? battery.glyph : "󰚥"
      label: lock.tr("Battery")
      value: battery.hasBattery ? battery.percent + "%" : "AC"
      sub: battery.hasBattery ? (battery.charging ? lock.tr("Charging") : lock.tr("On battery")) : ""
      fill: battery.hasBattery ? battery.percent / 100 : -1
    }
    Tile {
      icon: "󰍛"
      label: lock.tr("System")
      value: system.memoryPercent + "% " + lock.tr("memory")
      sub: system.uptime.length ? lock.tr("up") + " " + system.uptime : ""
      fill: system.memoryPercent / 100
    }
    Tile {
      icon: lock.missed > 0 ? "󰂚" : "󰂜"
      label: lock.tr("Notifications")
      value: lock.missed > 0 ? String(lock.missed) : lock.tr("None")
      sub: lock.missed > 0 ? lock.tr("since you locked") : ""
    }
  }
}
