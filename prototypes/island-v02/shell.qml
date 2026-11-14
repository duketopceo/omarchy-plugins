import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Mpris

// Standalone IslandCN-inspired desktop prototype. No Notch plugin dependency.
ShellRoot {
  Variants {
    model: Quickshell.screens
    PanelWindow {
      id: window
      required property var modelData
      screen: modelData
      anchors.top: true
      implicitWidth: 400
      implicitHeight: Math.ceil(island.height)
      color: "transparent"
      WlrLayershell.namespace: "islandcn-native-v02"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: island.expanded ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
      exclusionMode: ExclusionMode.Ignore
      mask: Region { item: island }

      readonly property var players: Mpris.players ? Mpris.players.values : []
      readonly property var player: {
        for (var i = 0; i < players.length; i++) if (players[i].isPlaying) return players[i]
        return players.length ? players[0] : null
      }
      readonly property bool playing: !!player && player.isPlaying
      readonly property int sensorWidth: modelData.name === "eDP-1" ? 186 : 95
      property date now: new Date()
      Timer { interval: 1000; running: true; repeat: true; onTriggered: { window.now = new Date(); if (island.expanded && window.player) window.player.positionChanged() } }

      Rectangle {
        id: island
        property bool expanded: false
        anchors.horizontalCenter: parent.horizontalCenter
        width: expanded ? 374 : Math.max(250, window.sensorWidth + 120)
        height: expanded ? 180 : 37
        radius: expanded ? 46 : 18.5
        color: "#050505"
        clip: true
        Behavior on width { NumberAnimation { duration: 390; easing.type: Easing.OutBack; easing.overshoot: 0.45 } }
        Behavior on height { NumberAnimation { duration: 390; easing.type: Easing.OutBack; easing.overshoot: 0.3 } }
        Behavior on radius { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        Shortcut { sequence: "Escape"; enabled: island.expanded; onActivated: island.expanded = false }

        Item {
          anchors.fill: parent
          opacity: island.expanded ? 0 : 1
          visible: opacity > 0
          Behavior on opacity { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
          Text {
            anchors.verticalCenter: parent.verticalCenter
            x: 8
            width: Math.max(0, (parent.width - window.sensorWidth) / 2 - 14)
            horizontalAlignment: Text.AlignRight
            text: Qt.formatTime(window.now, "h:mm")
            textFormat: Text.PlainText; elide: Text.ElideRight
            color: "#f8f8f8"; font.family: "Noto Sans"; font.pixelSize: 13; font.weight: Font.DemiBold
          }
          Text {
            anchors.verticalCenter: parent.verticalCenter
            x: (parent.width + window.sensorWidth) / 2 + 6
            width: Math.max(0, parent.width - x - 8)
            text: window.playing ? "♫ " + (window.player.trackTitle || window.player.identity) : Qt.formatDate(window.now, "MMM d")
            textFormat: Text.PlainText; elide: Text.ElideRight
            color: "#e6e6e6"; font.family: "Noto Sans"; font.pixelSize: 12
          }
          TapHandler { enabled: !island.expanded; onTapped: island.expanded = true }
        }

        Item {
          anchors.fill: parent
          opacity: island.expanded ? 1 : 0
          visible: opacity > 0
          Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

          Rectangle {
            id: artwork
            x: 22; y: 41; width: 60; height: 60; radius: 13
            color: "#282828"
            Image {
              anchors.fill: parent
              source: window.player && window.player.trackArtUrl ? window.player.trackArtUrl : ""
              fillMode: Image.PreserveAspectCrop
              asynchronous: true
              visible: status === Image.Ready
            }
            Text { anchors.centerIn: parent; visible: !window.player || !window.player.trackArtUrl; text: "♫"; textFormat: Text.PlainText; color: "#a6a6a6"; font.pixelSize: 25 }
          }

          Text {
            x: 98; y: 44; width: parent.width - x - 26
            text: window.player ? (window.player.trackTitle || window.player.identity) : Qt.formatDate(window.now, "dddd, MMMM d")
            textFormat: Text.PlainText; elide: Text.ElideRight
            color: "#ffffff"; font.family: "Noto Sans"; font.pixelSize: 15; font.weight: Font.DemiBold
          }
          Text {
            x: 98; y: 66; width: parent.width - x - 26
            text: window.player ? (window.player.trackArtist || window.player.identity) : Qt.formatTime(window.now, "h:mm AP")
            textFormat: Text.PlainText; elide: Text.ElideRight
            color: "#a4a4a4"; font.family: "Noto Sans"; font.pixelSize: 13
          }
          Rectangle {
            x: 23; y: 112; width: parent.width - 46; height: 4; radius: 2; color: "#393939"
            visible: !!window.player && window.player.length > 0
            Rectangle { width: parent.width * Math.max(0, Math.min(1, window.player ? window.player.position / window.player.length : 0)); height: parent.height; radius: 2; color: "#f1f1f1" }
          }
          Row {
            anchors.horizontalCenter: parent.horizontalCenter
            y: 129; spacing: 38
            visible: !!window.player
            Repeater {
              model: ["previous", "toggle", "next"]
              Item {
                required property string modelData
                width: 42; height: 38
                Text {
                  anchors.centerIn: parent
                  text: modelData === "previous" ? "⏮" : modelData === "next" ? "⏭" : window.playing ? "Ⅱ" : "▶"
                  textFormat: Text.PlainText; color: "#fafafa"; font.pixelSize: modelData === "toggle" ? 25 : 18
                }
                TapHandler { onTapped: { if (!window.player) return; if (modelData === "previous") window.player.previous(); else if (modelData === "next") window.player.next(); else window.player.togglePlaying() } }
              }
            }
          }
          Text {
            anchors.right: parent.right; anchors.rightMargin: 24; y: 17
            text: "×"; textFormat: Text.PlainText; color: "#8f8f8f"; font.pixelSize: 21
            TapHandler { onTapped: island.expanded = false }
          }
        }
      }
    }
  }
}
