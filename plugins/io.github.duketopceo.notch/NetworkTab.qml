import QtQuick
import qs.Commons as Commons
import "Network.js" as Network
import "Settings.js" as Settings

// Network tab (about 428x164 usable): two cards.
//   Tailscale: state pill + switch, this device's IP and MagicDNS name (click
//   to copy), a filter box, an exit-node picker (only when the operator is
//   set, else read-only) and the peers, online first (click to copy an IP).
//   NordVPN: state pill + switch, server/location/IP/uptime, favorite country
//   chips, a country dropdown and connect / disconnect.
// Polling lives in NetworkOps and runs only while this tab is visible. The
// idle-dot state in the root's NetworkState is untouched.
Item {
  id: tab

  property var notch: null

  readonly property color textColor: notch ? notch.textColor : Commons.Color.foreground
  readonly property color dimColor: notch ? notch.dimColor : Commons.Color.muted
  readonly property string family: notch ? notch.fontFamily : Commons.Style.font.family
  readonly property string pluginId: notch && notch.pluginId ? notch.pluginId : "io.github.duketopceo.notch"
  readonly property color good: "#6fbf73"
  readonly property color warn: "#e0b050"
  readonly property color bad: "#d9695f"
  readonly property color card: Qt.rgba(1, 1, 1, 0.05)
  readonly property color chip: Qt.rgba(1, 1, 1, 0.08)
  readonly property color chipHover: Qt.rgba(1, 1, 1, 0.16)

  implicitWidth: 428
  implicitHeight: 164

  // ------------------------------------------------------------- state
  property string toast: ""
  property string filter: ""
  property bool exitOpen: false
  property bool countryOpen: false
  readonly property var shown: Network.filterPeers(ops.ts.running ? ops.ts.peers : [], filter)

  function copy(text, what) {
    if (!text) return
    ops.copy(text)
    toast = what
    toastTimer.restart()
  }
  Timer { id: toastTimer; interval: 1600; onTriggered: { tab.toast = ""; toastTimer.interval = 1600 } }

  NetworkOps {
    id: ops
    active: tab.visible
    favoritesSetting: {
      var e = tab.notch ? Settings.pluginEntry(tab.notch.shellConfig, tab.pluginId) : null
      if (tab.pendingFavorites !== null) return tab.pendingFavorites
      return e ? e["network.nordFavorites"] : null
    }
    onFavoritesWanted: function(list) {
      tab.pendingFavorites = list
      if (tab.notch) tab.notch.setSetting("network.nordFavorites", list)
    }
  }
  property var pendingFavorites: null

  onVisibleChanged: if (!visible) { exitOpen = false; countryOpen = false }

  // Small helpers -------------------------------------------------------
  component Pill: Rectangle {
    id: pill
    property string label: ""
    property color tone: tab.dimColor
    height: 16
    width: pillText.implicitWidth + 14
    radius: 8
    color: Qt.rgba(tone.r, tone.g, tone.b, 0.18)
    Text {
      id: pillText
      textFormat: Text.PlainText
      anchors.centerIn: parent
      text: pill.label
      color: pill.tone
      font.family: tab.family
      font.pixelSize: 9
      font.weight: Font.DemiBold
    }
  }

  component Chip: Rectangle {
    id: chipBox
    property string label: ""
    property bool selected: false
    property bool enabledChip: true
    property color labelColor: tab.textColor
    signal clicked()
    signal rightClicked()
    height: 18
    width: chipText.implicitWidth + 14
    radius: 9
    opacity: enabledChip ? 1 : 0.4
    color: selected ? Qt.rgba(0.44, 0.75, 0.45, 0.28) : (chipHit.containsMouse && enabledChip ? tab.chipHover : tab.chip)
    Text {
      id: chipText
      textFormat: Text.PlainText
      anchors.centerIn: parent
      text: chipBox.label
      color: chipBox.labelColor
      font.family: tab.family
      font.pixelSize: 10
    }
    MouseArea {
      id: chipHit
      anchors.fill: parent
      enabled: chipBox.enabledChip
      hoverEnabled: true
      acceptedButtons: Qt.LeftButton | Qt.RightButton
      cursorShape: Qt.PointingHandCursor
      onClicked: function(m) { if (m.button === Qt.RightButton) chipBox.rightClicked(); else chipBox.clicked() }
    }
  }

  component IconBadge: Rectangle {
    property string glyph: ""
    property color tone: tab.good
    width: 20; height: 20; radius: 6
    color: Qt.rgba(tone.r, tone.g, tone.b, 0.2)
    Text {
      textFormat: Text.PlainText
      anchors.centerIn: parent
      text: parent.glyph
      color: parent.tone
      font.family: tab.family
      font.pixelSize: 12
    }
  }

  // ============================================================ Tailscale
  Rectangle {
    id: tsCard
    anchors.left: parent.left
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    width: Math.round(parent.width * 0.57)
    radius: 8
    color: tab.card

    readonly property string pillLabel: !ops.tsLoaded ? "..." : ops.ts.needsLogin ? "Sign in" : !ops.ts.ok ? "Unavailable" : ops.tsBusy ? (ops.tsOn ? "Connecting" : "Stopping") : ops.tsOn ? "Connected" : "Disconnected"
    readonly property color pillTone: ops.tsBusy ? tab.warn : ops.tsOn && ops.ts.ok ? tab.good : ops.ts.needsLogin ? tab.warn : tab.dimColor

    Item {
      id: tsInner
      anchors.fill: parent
      anchors.margins: 6

      Item {
        id: tsHead
        width: parent.width
        height: 20
        IconBadge { id: tsIcon; glyph: "\u{F0AC}"; tone: tsCard.pillTone }
        Text {
          id: tsTitle
          textFormat: Text.PlainText
          anchors.left: tsIcon.right
          anchors.leftMargin: 6
          anchors.verticalCenter: parent.verticalCenter
          text: "Tailscale"
          color: tab.textColor
          font.family: tab.family
          font.pixelSize: 12
          font.weight: Font.DemiBold
        }
        Pill {
          anchors.left: tsTitle.right
          anchors.leftMargin: 6
          anchors.verticalCenter: parent.verticalCenter
          label: tsCard.pillLabel
          tone: tsCard.pillTone
        }
        PillSwitch {
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          on: ops.tsOn
          busy: ops.tsBusy
          enabledSwitch: Network.tailscaleToggleCommand(ops.ts) !== null
          onToggled: ops.toggleTailscale()
        }
      }

      // This device: MagicDNS name and tailnet IP, each click-to-copy.
      Row {
        id: selfRow
        anchors.top: tsHead.bottom
        anchors.topMargin: 4
        width: parent.width
        height: 20
        spacing: 4
        visible: ops.ts.selfIp !== ""

        Rectangle {
          id: selfIpBox
          height: parent.height
          width: selfIpText.implicitWidth + 14
          radius: 6
          color: ipHit.containsMouse ? tab.chipHover : tab.chip
          Text {
            id: selfIpText
            textFormat: Text.PlainText
            anchors.centerIn: parent
            text: ops.ts.selfIp
            color: tab.textColor
            font.family: tab.family
            font.pixelSize: 10
            font.weight: Font.DemiBold
          }
          MouseArea { id: ipHit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: tab.copy(ops.ts.selfIp, "Copied " + ops.ts.selfIp) }
        }
        Rectangle {
          height: parent.height
          width: parent.width - selfIpBox.width - parent.spacing
          radius: 6
          color: dnsHit.containsMouse ? tab.chipHover : tab.chip
          Text {
            textFormat: Text.PlainText
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 7
            anchors.right: parent.right
            anchors.rightMargin: 7
            elide: Text.ElideMiddle
            text: ops.ts.selfDns !== "" ? ops.ts.selfDns : ops.ts.selfName
            color: tab.dimColor
            font.family: tab.family
            font.pixelSize: 10
          }
          MouseArea { id: dnsHit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: tab.copy(ops.ts.selfDns !== "" ? ops.ts.selfDns : ops.ts.selfName, "Copied name") }
        }
      }

      // Filter box and exit-node button.
      Row {
        id: filterRow
        anchors.top: selfRow.visible ? selfRow.bottom : tsHead.bottom
        anchors.topMargin: 4
        width: parent.width
        height: 20
        spacing: 4
        visible: ops.ts.running

        Rectangle {
          id: filterBox
          height: parent.height
          width: parent.width - exitBtn.width - parent.spacing
          radius: 6
          color: tab.chip
          border.width: filterInput.activeFocus ? 1 : 0
          border.color: Qt.rgba(1, 1, 1, 0.3)
          TextInput {
            id: filterInput
            anchors.fill: parent
            anchors.leftMargin: 7
            anchors.rightMargin: 7
            verticalAlignment: TextInput.AlignVCenter
            color: tab.textColor
            selectionColor: Qt.rgba(1, 1, 1, 0.3)
            font.family: tab.family
            font.pixelSize: 10
            clip: true
            onTextChanged: tab.filter = text
            Keys.onEscapePressed: { text = ""; focus = false }
          }
          Text {
            textFormat: Text.PlainText
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 7
            visible: filterInput.text === "" && !filterInput.activeFocus
            text: "Filter " + ops.ts.peerCount + " peers"
            color: tab.dimColor
            font.family: tab.family
            font.pixelSize: 10
          }
          MouseArea { anchors.fill: parent; cursorShape: Qt.IBeamCursor; onPressed: function(m) { filterInput.forceActiveFocus(); m.accepted = false } }
        }
        Rectangle {
          id: exitBtn
          height: parent.height
          width: 92
          radius: 6
          color: exitHit.containsMouse ? tab.chipHover : tab.chip
          border.width: ops.exitName !== "" ? 1 : 0
          border.color: Qt.rgba(0.44, 0.75, 0.45, 0.6)
          Text {
            textFormat: Text.PlainText
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 7
            anchors.right: parent.right
            anchors.rightMargin: 7
            elide: Text.ElideRight
            text: "Exit: " + (ops.exitName !== "" ? ops.exitName : "none") + (ops.exitFeasible ? "  ▾" : "")
            color: ops.exitName !== "" ? tab.good : tab.textColor
            font.family: tab.family
            font.pixelSize: 10
          }
          MouseArea {
            id: exitHit
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: ops.exitFeasible ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: if (ops.exitFeasible) { tab.countryOpen = false; tab.exitOpen = !tab.exitOpen } else { tab.toast = Network.exitNodeNote(false); toastTimer.interval = 4000; toastTimer.restart() }
          }
        }
      }

      // Peers, online first.
      NotchScroll {
        id: peerScroll
        anchors.top: filterRow.visible ? filterRow.bottom : (selfRow.visible ? selfRow.bottom : tsHead.bottom)
        anchors.topMargin: 4
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        rowHeight: 20
        rowsPerNotch: 3
        contentWidth: width
        contentHeight: peerCol.height

        Column {
          id: peerCol
          width: peerScroll.width
          Repeater {
            model: tab.shown
            delegate: Item {
              id: peer
              required property var modelData
              width: peerCol.width
              height: 20
              readonly property string status: Network.peerStatus(modelData, ops.now)
              Rectangle {
                anchors.fill: parent
                radius: 5
                color: peerHit.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : "transparent"
              }
              Text {
                id: osGlyph
                textFormat: Text.PlainText
                anchors.left: parent.left
                anchors.leftMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                width: 14
                horizontalAlignment: Text.AlignHCenter
                text: Network.osIcon(peer.modelData.os).glyph
                color: peer.modelData.online ? tab.textColor : tab.dimColor
                font.family: tab.family
                font.pixelSize: 11
              }
              Text {
                textFormat: Text.PlainText
                anchors.left: osGlyph.right
                anchors.leftMargin: 5
                anchors.right: peerIp.left
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
                text: peer.modelData.name + (peer.modelData.exitNode ? "  (exit)" : "")
                color: peer.modelData.online ? tab.textColor : tab.dimColor
                font.family: tab.family
                font.pixelSize: 10
              }
              Text {
                id: peerIp
                textFormat: Text.PlainText
                anchors.right: dotMark.left
                anchors.rightMargin: 5
                anchors.verticalCenter: parent.verticalCenter
                text: peer.modelData.online ? peer.modelData.ip : peer.status
                color: tab.dimColor
                font.family: tab.family
                font.pixelSize: 9
              }
              Rectangle {
                id: dotMark
                width: 6; height: 6; radius: 3
                anchors.right: parent.right
                anchors.rightMargin: 5
                anchors.verticalCenter: parent.verticalCenter
                color: peer.modelData.online ? tab.good : "#555a60"
              }
              MouseArea {
                id: peerHit
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: tab.copy(peer.modelData.ip, "Copied " + peer.modelData.ip)
              }
            }
          }
        }
      }

      Text {
        textFormat: Text.PlainText
        anchors.centerIn: peerScroll
        width: peerScroll.width - 12
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        visible: !ops.ts.running || tab.shown.length === 0
        text: !ops.tsLoaded ? "" : ops.ts.running ? (tab.filter !== "" ? "No match" : "No peers") : (ops.ts.needsLogin ? "Sign in with tailscale up" : "Tailscale is off")
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: 10
      }
    }

    // Exit-node picker (only reachable when the operator is set).
    Rectangle {
      id: exitMenu
      visible: tab.exitOpen && ops.exitFeasible
      z: 5
      x: tsInner.x + tsInner.width - width
      y: tsInner.y + filterRow.y + filterRow.height + 2
      width: 150
      height: Math.min(exitCol.height + 8, tsCard.height - y - 4)
      radius: 8
      color: Qt.rgba(0.1, 0.1, 0.12, 0.97)
      border.width: 1
      border.color: Qt.rgba(1, 1, 1, 0.14)
      NotchScroll {
        id: exitScroll
        anchors.fill: parent
        anchors.margins: 4
        rowHeight: 20
        contentWidth: width
        contentHeight: exitCol.height
        Column {
          id: exitCol
          width: exitScroll.width
          Repeater {
            model: [{ name: "None (direct)", ip: "" }].concat(ops.ts.exitOptions)
            delegate: Item {
              id: opt
              required property var modelData
              width: exitCol.width
              height: 20
              readonly property bool current: modelData.ip === "" ? ops.exitName === "" : ops.exitName === modelData.name
              Rectangle { anchors.fill: parent; radius: 5; color: optHit.containsMouse ? Qt.rgba(1, 1, 1, 0.12) : "transparent" }
              Text {
                textFormat: Text.PlainText
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 6
                anchors.right: parent.right
                anchors.rightMargin: 6
                elide: Text.ElideRight
                text: (opt.current ? "✓ " : "") + opt.modelData.name
                color: opt.current ? tab.good : tab.textColor
                font.family: tab.family
                font.pixelSize: 10
              }
              MouseArea {
                id: optHit
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: { tab.exitOpen = false; ops.setExitNode(opt.modelData.ip) }
              }
            }
          }
        }
      }
    }
  }

  // ============================================================== NordVPN
  Rectangle {
    id: nordCard
    anchors.left: tsCard.right
    anchors.leftMargin: 6
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    radius: 8
    color: tab.card

    readonly property bool connected: ops.nord.state === "connected"
    readonly property string pillLabel: !ops.nordLoaded ? "..." : !ops.nord.ok ? "Unavailable" : ops.nordBusy ? (ops.nordOn ? "Connecting" : "Stopping") : ops.nord.state === "connecting" ? "Connecting" : connected ? "Connected" : "Disconnected"
    readonly property color pillTone: ops.nordBusy || ops.nord.state === "connecting" ? tab.warn : connected ? tab.good : tab.dimColor
    readonly property string currentCountryId: ops.nord.country.replace(/ /g, "_")

    Item {
      id: nordInner
      anchors.fill: parent
      anchors.margins: 6

      Item {
        id: nordHead
        width: parent.width
        height: 20
        IconBadge { id: nordIcon; glyph: "\u{F132}"; tone: nordCard.pillTone }
        Pill {
          anchors.left: nordIcon.right
          anchors.leftMargin: 6
          anchors.verticalCenter: parent.verticalCenter
          label: nordCard.pillLabel
          tone: nordCard.pillTone
        }
        PillSwitch {
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          on: ops.nordOn
          busy: ops.nordBusy
          enabledSwitch: ops.nord.ok
          onToggled: ops.toggleNord()
        }
      }

      // Server, location, IP and uptime.
      Column {
        id: nordInfo
        anchors.top: nordHead.bottom
        anchors.topMargin: 5
        width: parent.width
        spacing: 1

        Text {
          textFormat: Text.PlainText
          width: parent.width
          elide: Text.ElideRight
          text: !ops.nord.ok ? "NordVPN CLI not available or not logged in"
            : ops.nordBusy && ops.nordOn ? "Connecting to " + (ops.nordTarget !== "" ? ops.nordTarget.replace(/_/g, " ") : "the best server")
            : nordCard.connected ? [ops.nord.country, ops.nord.city].filter(function (s) { return s !== "" }).join(", ")
            : "Not connected"
          color: nordCard.connected ? tab.textColor : tab.dimColor
          font.family: tab.family
          font.pixelSize: 11
          font.weight: nordCard.connected ? Font.DemiBold : Font.Normal
        }
        Text {
          textFormat: Text.PlainText
          visible: !nordCard.connected && ops.nord.ok && !ops.nordBusy
          width: parent.width
          wrapMode: Text.WordWrap
          text: "Pick a country, or Connect for the fastest server"
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: 10
        }
        Text {
          textFormat: Text.PlainText
          visible: nordCard.connected
          width: parent.width
          elide: Text.ElideRight
          text: ops.nord.hostname !== "" ? ops.nord.hostname : ops.nord.server
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: 10
        }
        Item {
          visible: nordCard.connected
          width: parent.width
          height: 13
          Text {
            id: nordIpText
            textFormat: Text.PlainText
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: tab.toast === "Copied IP" ? "copied" : ops.nord.ip
            color: tab.toast === "Copied IP" ? tab.good : tab.dimColor
            font.family: tab.family
            font.pixelSize: 10
          }
          Text {
            textFormat: Text.PlainText
            anchors.left: nordIpText.right
            anchors.leftMargin: 6
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            elide: Text.ElideRight
            text: ops.nord.uptime !== "" ? "up " + ops.nord.uptime : ""
            color: tab.dimColor
            font.family: tab.family
            font.pixelSize: 10
          }
          MouseArea { anchors.fill: nordIpText; cursorShape: Qt.PointingHandCursor; onClicked: tab.copy(ops.nord.ip, "Copied IP") }
        }
      }

      // Quick picks: favorites (left click connects, right click removes) + star.
      Flow {
        id: favRow
        anchors.bottom: dropRow.top
        anchors.bottomMargin: 4
        width: parent.width
        spacing: 4
        Repeater {
          model: ops.favorites
          delegate: Chip {
            required property string modelData
            label: Network.favoriteLabel(modelData)
            selected: nordCard.connected && nordCard.currentCountryId === modelData
            enabledChip: ops.nord.ok && !ops.nordBusy
            onClicked: ops.connectNord(modelData)
            onRightClicked: ops.toggleFavorite(modelData)
          }
        }
        Chip {
          visible: nordCard.connected && nordCard.currentCountryId !== ""
          label: ops.favorites.indexOf(nordCard.currentCountryId) >= 0 ? "★" : "☆"
          labelColor: ops.favorites.indexOf(nordCard.currentCountryId) >= 0 ? tab.warn : tab.dimColor
          onClicked: ops.toggleFavorite(nordCard.currentCountryId)
        }
      }

      // Country dropdown and connect / disconnect.
      Row {
        id: dropRow
        anchors.bottom: parent.bottom
        width: parent.width
        height: 20
        spacing: 4

        Rectangle {
          id: dropBtn
          height: parent.height
          width: parent.width - actBtn.width - parent.spacing
          radius: 6
          color: dropHit.containsMouse ? tab.chipHover : tab.chip
          Text {
            textFormat: Text.PlainText
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 7
            anchors.right: parent.right
            anchors.rightMargin: 7
            elide: Text.ElideRight
            text: "Country  ▾"
            color: tab.textColor
            font.family: tab.family
            font.pixelSize: 10
          }
          MouseArea {
            id: dropHit
            anchors.fill: parent
            hoverEnabled: true
            enabled: ops.nord.ok && ops.countries.length > 0
            cursorShape: Qt.PointingHandCursor
            onClicked: { tab.exitOpen = false; tab.countryOpen = !tab.countryOpen }
          }
        }
        Rectangle {
          id: actBtn
          height: parent.height
          width: 66
          radius: 6
          opacity: ops.nord.ok && !ops.nordBusy ? 1 : 0.4
          color: nordCard.connected ? (actHit.containsMouse ? Qt.rgba(0.85, 0.41, 0.37, 0.45) : Qt.rgba(0.85, 0.41, 0.37, 0.28))
                                    : (actHit.containsMouse ? Qt.rgba(0.44, 0.75, 0.45, 0.45) : Qt.rgba(0.44, 0.75, 0.45, 0.28))
          Text {
            textFormat: Text.PlainText
            anchors.centerIn: parent
            text: nordCard.connected ? "Disconnect" : "Connect"
            color: tab.textColor
            font.family: tab.family
            font.pixelSize: 10
          }
          MouseArea {
            id: actHit
            anchors.fill: parent
            hoverEnabled: true
            enabled: ops.nord.ok && !ops.nordBusy
            cursorShape: Qt.PointingHandCursor
            onClicked: if (nordCard.connected) ops.disconnectNord(); else ops.connectNord("")
          }
        }
      }
    }

    // Country dropdown list (opens upward over the card).
    Rectangle {
      id: countryMenu
      visible: tab.countryOpen && ops.countries.length > 0
      z: 5
      x: nordInner.x
      width: nordInner.width
      height: Math.min(nordCard.height - 36, 120)
      y: nordInner.y + dropRow.y - height - 2
      radius: 8
      color: Qt.rgba(0.1, 0.1, 0.12, 0.97)
      border.width: 1
      border.color: Qt.rgba(1, 1, 1, 0.14)
      NotchScroll {
        id: countryScroll
        anchors.fill: parent
        anchors.margins: 4
        rowHeight: 20
        contentWidth: width
        contentHeight: countryCol.height
        Column {
          id: countryCol
          width: countryScroll.width
          Repeater {
            model: ops.countries
            delegate: Item {
              id: ctry
              required property var modelData
              width: countryCol.width
              height: 20
              Rectangle { anchors.fill: parent; radius: 5; color: ctryHit.containsMouse ? Qt.rgba(1, 1, 1, 0.12) : "transparent" }
              Text {
                textFormat: Text.PlainText
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 6
                anchors.right: parent.right
                anchors.rightMargin: 6
                elide: Text.ElideRight
                text: (nordCard.currentCountryId === ctry.modelData.id && nordCard.connected ? "✓ " : "") + ctry.modelData.label
                color: tab.textColor
                font.family: tab.family
                font.pixelSize: 10
              }
              MouseArea {
                id: ctryHit
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: { tab.countryOpen = false; ops.connectNord(ctry.modelData.id) }
              }
            }
          }
        }
      }
    }
  }

  Rectangle {
    id: toastBox
    z: 10
    anchors.horizontalCenter: tsCard.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: 8
    height: 20
    width: toastText.implicitWidth + 20
    radius: 10
    color: Qt.rgba(0.05, 0.05, 0.07, 0.94)
    border.width: 1
    border.color: Qt.rgba(0.44, 0.75, 0.45, 0.5)
    opacity: tab.toast !== "" ? 1 : 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 140 } }
    Text {
      id: toastText
      textFormat: Text.PlainText
      anchors.centerIn: parent
      text: tab.toast
      color: tab.good
      font.family: tab.family
      font.pixelSize: 10
    }
  }
}
