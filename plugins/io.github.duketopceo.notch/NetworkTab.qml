import QtQuick
import qs.Commons as Commons
import "Network.js" as Network

// Network tab: Tailscale (state, this device's tailnet IP, peers with
// online/offline dots, connect toggle, click an IP to copy it) and NordVPN
// (state, country/server, connect toggle). State lives in the root item's
// NetworkState (`notch.network`); this tab only draws it and, while visible,
// asks it to poll faster and fetch the peer list.
Item {
  id: tab

  property var notch: null
  readonly property var net: notch ? notch.network : null
  readonly property var ts: net ? net.ts : Network.parseTailscale("")
  readonly property var nord: net ? net.nord : Network.parseNord("")
  readonly property color textColor: notch ? notch.textColor : "white"
  readonly property color dimColor: notch ? notch.dimColor : "gray"
  readonly property string family: notch ? notch.fontFamily : ""

  property bool counted: false
  function sync() {
    var want = visible && !!net
    if (want === counted) return
    counted = want
    net.viewers += want ? 1 : -1
  }
  onVisibleChanged: sync()
  onNetChanged: sync()
  Component.onCompleted: sync()
  Component.onDestruction: if (counted && net) net.viewers -= 1

  function dot(kind) { return kind === "on" ? "#6fbf73" : kind === "busy" ? "#e0b050" : "#555a60" }

  // ------------------------------------------------------------ Tailscale
  Item {
    id: tsCard
    anchors.left: parent.left
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    width: Math.round(parent.width * 0.56)

    Row {
      id: tsHead
      spacing: 6
      height: 18
      Rectangle { width: 8; height: 8; radius: 4; color: tab.dot(tab.net ? tab.net.tsDot : "off"); anchors.verticalCenter: parent.verticalCenter }
      Text {
        textFormat: Text.PlainText
        text: "Tailscale"
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: 12
        font.weight: Font.DemiBold
        anchors.verticalCenter: parent.verticalCenter
      }
      Text {
        textFormat: Text.PlainText
        text: tab.net && tab.net.tsBusy !== "" ? (tab.net.tsBusy === "up" ? "connecting" : "disconnecting") : Network.tailscaleSummary(tab.ts)
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: 10
        anchors.verticalCenter: parent.verticalCenter
      }
    }

    PillSwitch {
      anchors.right: parent.right
      anchors.rightMargin: 12
      anchors.verticalCenter: tsHead.verticalCenter
      on: tab.ts.running
      busy: !!tab.net && tab.net.tsBusy !== ""
      enabledSwitch: !!tab.net && Network.tailscaleToggleCommand(tab.ts) !== null
      onToggled: tab.net.toggleTailscale()
    }

    // This device and its tailnet IP; click to copy.
    Rectangle {
      id: selfRow
      anchors.top: tsHead.bottom
      anchors.topMargin: 6
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.rightMargin: 12
      height: 24
      radius: 6
      color: selfHit.containsMouse ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.07)
      visible: tab.ts.selfIp !== ""
      Text {
        textFormat: Text.PlainText
        anchors.left: parent.left
        anchors.leftMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - ipText.width - 22
        elide: Text.ElideRight
        text: tab.ts.selfName
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: 11
      }
      Text {
        id: ipText
        textFormat: Text.PlainText
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        text: tab.net && tab.net.copied === tab.ts.selfIp ? "copied" : tab.ts.selfIp
        color: tab.net && tab.net.copied === tab.ts.selfIp ? "#6fbf73" : tab.dimColor
        font.family: tab.family
        font.pixelSize: 10
      }
      MouseArea {
        id: selfHit
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: if (tab.net) tab.net.copyIp(tab.ts.selfIp)
      }
    }

    ListView {
      id: peerList
      anchors.top: selfRow.visible ? selfRow.bottom : tsHead.bottom
      anchors.topMargin: 4
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.rightMargin: 12
      anchors.bottom: parent.bottom
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      model: tab.ts.running ? tab.ts.peers : []
      delegate: Item {
        id: peer
        required property var modelData
        width: peerList.width
        height: 20
        Rectangle { anchors.fill: parent; radius: 5; color: peerHit.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : "transparent" }
        Rectangle {
          id: pdot
          width: 6; height: 6; radius: 3
          x: 8
          anchors.verticalCenter: parent.verticalCenter
          color: peer.modelData.online ? "#6fbf73" : "#555a60"
        }
        Text {
          textFormat: Text.PlainText
          anchors.left: pdot.right
          anchors.leftMargin: 6
          anchors.right: peerIp.left
          anchors.rightMargin: 6
          anchors.verticalCenter: parent.verticalCenter
          elide: Text.ElideRight
          text: peer.modelData.name
          color: peer.modelData.online ? tab.textColor : tab.dimColor
          font.family: tab.family
          font.pixelSize: 10
        }
        Text {
          id: peerIp
          textFormat: Text.PlainText
          anchors.right: parent.right
          anchors.rightMargin: 8
          anchors.verticalCenter: parent.verticalCenter
          text: tab.net && tab.net.copied === peer.modelData.ip ? "copied" : peer.modelData.ip
          color: tab.net && tab.net.copied === peer.modelData.ip ? "#6fbf73" : tab.dimColor
          font.family: tab.family
          font.pixelSize: 9
        }
        MouseArea {
          id: peerHit
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: if (tab.net) tab.net.copyIp(peer.modelData.ip)
        }
      }
    }

    Text {
      textFormat: Text.PlainText
      anchors.centerIn: peerList
      visible: !tab.ts.running || tab.ts.peers.length === 0
      text: tab.ts.running ? "No peers" : (tab.ts.needsLogin ? "Sign in with tailscale up" : "Tailscale is off")
      color: tab.dimColor
      font.family: tab.family
      font.pixelSize: 10
    }
  }

  Rectangle {
    anchors.left: tsCard.right
    anchors.leftMargin: -6
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    width: 1
    color: Qt.rgba(1, 1, 1, 0.1)
  }

  // -------------------------------------------------------------- NordVPN
  Item {
    id: nordCard
    anchors.left: tsCard.right
    anchors.leftMargin: 6
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.bottom: parent.bottom

    Row {
      id: nordHead
      spacing: 6
      height: 18
      Rectangle { width: 8; height: 8; radius: 4; color: tab.dot(tab.net ? tab.net.nordDot : "off"); anchors.verticalCenter: parent.verticalCenter }
      Text {
        textFormat: Text.PlainText
        text: "NordVPN"
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: 12
        font.weight: Font.DemiBold
        anchors.verticalCenter: parent.verticalCenter
      }
    }

    PillSwitch {
      anchors.right: parent.right
      anchors.verticalCenter: nordHead.verticalCenter
      on: tab.nord.state === "connected" || tab.nord.state === "connecting"
      busy: !!tab.net && tab.net.nordBusy !== ""
      enabledSwitch: !!tab.net && Network.nordToggleVerb(tab.nord) !== null
      onToggled: tab.net.toggleNord()
    }

    Column {
      anchors.top: nordHead.bottom
      anchors.topMargin: 10
      anchors.left: parent.left
      anchors.right: parent.right
      spacing: 4

      Text {
        textFormat: Text.PlainText
        width: parent.width
        elide: Text.ElideRight
        text: tab.net && tab.net.nordBusy !== "" ? (tab.net.nordBusy === "connect" ? "Connecting" : "Disconnecting") : Network.nordSummary(tab.nord)
        color: tab.nord.state === "connected" ? tab.textColor : tab.dimColor
        font.family: tab.family
        font.pixelSize: 12
      }
      Text {
        textFormat: Text.PlainText
        visible: text !== ""
        width: parent.width
        elide: Text.ElideRight
        text: tab.nord.state === "connected" ? tab.nord.detail : ""
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: 11
      }
      Text {
        textFormat: Text.PlainText
        visible: text !== ""
        width: parent.width
        elide: Text.ElideRight
        text: tab.nord.state === "connected" ? tab.nord.server : (tab.nord.ok ? "Click the switch to connect to the recommended server" : "NordVPN CLI not available or not logged in")
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: 10
        wrapMode: Text.WordWrap
        maximumLineCount: 3
      }
    }
  }
}
