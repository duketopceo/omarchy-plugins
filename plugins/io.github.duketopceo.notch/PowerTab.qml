import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import "Power.js" as Power

// Power tab: battery hero (icon with fill, percent, state, time), power flow in
// watts with a direction animation, health (cycles, design vs full capacity,
// charge limit), sparklines of the last hours, and a power-profile picker.
// Reads /sys/class/power_supply/macsmc-* (one `tail` exec), the Omarchy
// battery status line and the power plugin's history log; nothing is written
// except the profile, via omarchy-powerprofiles-set (no sudo).
Item {
  id: tab

  property var notch: null
  readonly property color textColor: notch ? notch.textColor : Tk.text
  readonly property color dimColor: notch ? notch.dimColor : Tk.dim
  readonly property string family: notch ? notch.fontFamily : Commons.Style.font.family
  readonly property string home: Quickshell.env("HOME")

  // Live readings
  property var fields: ({})
  property var status: Power.parseStatus("")
  property var samples: []                 // in-memory, used when no history log
  property string historyText: ""
  property real nowSeconds: Date.now() / 1000
  property var profileNames: []
  property string activeProfile: ""
  property string pendingProfile: ""

  readonly property var ac: Power.acOnline(fields)
  readonly property real percent: {
    var p = status.ok ? status.percent : Number(fields.capacity)
    return isFinite(p) ? p : -1
  }
  readonly property string kind: Power.chargeState(fields.status, percent, ac, status.thresholdHigh !== null ? status.thresholdHigh : Power.chargeLimit(fields, status).high)
  readonly property var flow: Power.wattsFromSysfs(fields, fields.status)
  readonly property var limit: Power.chargeLimit(fields, status)
  readonly property var hl: Power.health(fields)
  readonly property real adapterW: Power.adapterLimitW(fields) === null ? -1 : Power.adapterLimitW(fields)
  readonly property real timeSecs: {
    if (status.timeSeconds !== null) return status.timeSeconds
    var s = Number(kind === "charging" ? fields.time_to_full_now : fields.time_to_empty_now)
    return isFinite(s) ? s : 0
  }
  readonly property bool onBattery: kind === "discharging"
  readonly property var history: {
    var h = Power.historySeries(historyText, nowSeconds, 6, 90)
    if (h.count >= 2 && nowSeconds - h.lastTime < 1800) return h
    return Power.historySeries(samples, nowSeconds, 6, 90)
  }

  readonly property color tone: {
    var t = notch && notch.themeObj ? notch.themeObj : null
    if (kind === "charging") return t ? t.good : Tk.good
    if (kind === "full") return t ? t.good : Tk.good
    if (kind === "hold") return t ? t.hold : Tk.hold
    if (percent >= 0 && percent <= 15) return notch && notch.urgentColor ? notch.urgentColor : Tk.urgent
    if (percent >= 0 && percent <= 30) return t ? t.warn : Tk.warn
    return textColor
  }

  function refreshNow() {
    nowSeconds = Date.now() / 1000
    if (!sysProc.running) { sysProc.command = Power.sysfsArgs(); sysProc.running = true }
  }
  function refreshSlow() {
    if (!statusProc.running) statusProc.running = true
    if (!profProc.running) profProc.running = true
  }
  function setProfile(name) {
    if (name === activeProfile || setProc.running) return
    pendingProfile = name
    setProc.command = Power.profileSetArgs(name, onBattery)
    setProc.running = true
  }

  Component.onCompleted: { refreshNow(); refreshSlow() }

  Timer {
    interval: 4000
    running: tab.visible
    repeat: true
    onTriggered: tab.refreshNow()
  }
  Timer {
    interval: 20000
    running: tab.visible
    repeat: true
    onTriggered: tab.refreshSlow()
  }
  // 60 s in-memory sampling while the tab is open (fallback history).
  Timer {
    interval: 60000
    running: tab.visible
    repeat: true
    triggeredOnStart: true
    onTriggered: {
      if (tab.percent < 0) return
      tab.samples = Power.addSample(tab.samples, Date.now() / 1000, tab.percent, Power.signedWatts(tab.flow), 360)
    }
  }
  onVisibleChanged: if (visible) { refreshNow(); refreshSlow() }

  Process {
    id: sysProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 20000) tab.fields = Power.parseSysfsDump(text)
    }
  }
  Process {
    id: statusProc
    command: ["/usr/bin/omarchy-battery-status", "--shell"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 4000) tab.status = Power.parseStatus(text)
    }
  }
  Process {
    id: profProc
    command: ["/usr/bin/omarchy-powerprofiles-list", "--active-state"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var r = Power.parseProfiles(text)
        tab.profileNames = Power.orderedProfiles(r.profiles)
        if (tab.pendingProfile === "") tab.activeProfile = r.active
      }
    }
  }
  Process {
    id: setProc
    onExited: {
      tab.activeProfile = tab.pendingProfile
      tab.pendingProfile = ""
      profProc.running = true
    }
  }
  FileView {
    path: tab.home + "/.local/state/omarchy/battery_history.json"
    watchChanges: true
    printErrors: false
    onLoaded: { var t = text(); tab.historyText = t.length < 2000000 ? t : "" }
    onLoadFailed: tab.historyText = ""
    onFileChanged: reload()
  }

  // ------------------------------------------------------------- hero
  Item {
    id: hero
    anchors.left: parent.left
    anchors.top: parent.top
    anchors.bottom: profileRow.top
    anchors.bottomMargin: 6
    width: 134

    // Battery icon: body outline, fill by percent, nub, bolt while charging.
    Item {
      id: batt
      anchors.horizontalCenter: parent.horizontalCenter
      anchors.top: parent.top
      anchors.topMargin: 2
      width: 96
      height: 46

      Rectangle {
        id: body
        width: 90
        height: 46
        radius: Tk.r(10)
        color: Tk.tint(0.06)
        border.width: Tk.bw(2)
        border.color: Tk.alpha(tab.tone, 0.85)

        Rectangle {
          id: fill
          x: 4
          y: 4
          height: parent.height - 8
          width: Math.max(0, (parent.width - 8) * Math.max(0, Math.min(100, tab.percent)) / 100)
          radius: Tk.r(6)
          color: tab.tone
          opacity: 0.9
          Behavior on width { NumberAnimation { duration: Tk.ms(400); easing.type: Easing.OutCubic } }
          // Soft pulse while charging.
          SequentialAnimation on opacity {
            running: tab.kind === "charging" && tab.visible
            loops: Animation.Infinite
            NumberAnimation { to: 0.6; duration: 900; easing.type: Easing.InOutSine }
            NumberAnimation { to: 0.95; duration: 900; easing.type: Easing.InOutSine }
          }
        }
        // Limit marker: where the charge cap sits on the icon.
        Rectangle {
          visible: tab.limit.high !== null && tab.limit.high < 100
          x: 4 + (body.width - 8) * (tab.limit.high === null ? 0 : tab.limit.high) / 100 - 1
          y: 2
          width: 2
          height: body.height - 4
          radius: Tk.r(1)
          color: Tk.tint(0.55)
        }
      }
      Rectangle {
        x: 91
        anchors.verticalCenter: body.verticalCenter
        width: 5
        height: 18
        radius: Tk.r(2)
        color: Tk.alpha(tab.tone, 0.85)
      }
    }

    Text {
      id: pctText
      textFormat: Text.PlainText
      anchors.horizontalCenter: parent.horizontalCenter
      anchors.top: batt.bottom
      anchors.topMargin: 6
      text: tab.percent >= 0 ? Math.round(tab.percent) + "%" : Power.DASH
      color: tab.textColor
      font.family: tab.family
      font.pixelSize: 32
      font.weight: Font.DemiBold
    }
    Text {
      id: stateText
      textFormat: Text.PlainText
      anchors.horizontalCenter: parent.horizontalCenter
      anchors.top: pctText.bottom
      width: parent.width
      horizontalAlignment: Text.AlignHCenter
      elide: Text.ElideRight
      text: Power.stateLabel(tab.kind)
      color: tab.tone
      font.family: tab.family
      font.pixelSize: 11
      font.weight: Font.Medium
    }
    Text {
      textFormat: Text.PlainText
      anchors.horizontalCenter: parent.horizontalCenter
      anchors.top: stateText.bottom
      anchors.topMargin: 1
      width: parent.width
      horizontalAlignment: Text.AlignHCenter
      elide: Text.ElideRight
      text: Power.timeText(tab.kind, tab.timeSecs)
      color: tab.dimColor
      font.family: tab.family
      font.pixelSize: 10
    }
  }

  // ------------------------------------------------------------- right column
  Item {
    id: right
    anchors.left: hero.right
    anchors.leftMargin: 14
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.bottom: profileRow.top
    anchors.bottomMargin: 6

    // Power flow card
    Rectangle {
      id: flowCard
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: parent.top
      height: 38
      radius: Tk.r(8)
      color: Tk.tint(0.06)

      Row {
        id: arrows
        anchors.left: parent.left
        anchors.leftMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        spacing: 1
        property int phase: 0
        readonly property bool moving: tab.flow.flow !== "idle"
        Timer {
          interval: 260
          running: arrows.moving && tab.visible
          repeat: true
          onTriggered: arrows.phase = (arrows.phase + 1) % 3
        }
        Repeater {
          model: 3
          Text {
            textFormat: Text.PlainText
            // "in" flows toward the battery (right), "out" away from it (left).
            readonly property int slot: tab.flow.flow === "out" ? 2 - index : index
            text: tab.flow.flow === "out" ? "‹" : "›"
            color: tab.flow.flow === "out" ? (tab.notch && tab.notch.themeObj ? tab.notch.themeObj.warn : Tk.warn) : (tab.notch && tab.notch.themeObj ? tab.notch.themeObj.good : Tk.good)
            opacity: arrows.moving ? (arrows.phase === slot ? 1.0 : 0.25) : 0.2
            font.family: tab.family
            font.pixelSize: 22
            font.weight: Font.Bold
            Behavior on opacity { NumberAnimation { duration: Tk.ms(180) } }
          }
        }
      }
      Text {
        id: wattsText
        textFormat: Text.PlainText
        anchors.left: arrows.right
        anchors.leftMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        text: tab.flow.watts === null ? Power.DASH : Power.fmtWatts(tab.flow.watts)
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: 20
        font.weight: Font.DemiBold
      }
      Column {
        anchors.right: parent.right
        anchors.rightMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        Text {
          textFormat: Text.PlainText
          anchors.right: parent.right
          text: tab.flow.flow === "in" ? "from adapter" : tab.flow.flow === "out" ? "system draw" : (tab.ac ? "adapter idle" : "idle")
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: 10
        }
        Text {
          textFormat: Text.PlainText
          anchors.right: parent.right
          visible: tab.adapterW > 0 && tab.ac === true
          text: Math.round(tab.adapterW) + " W adapter"
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: 10
        }
      }
    }

    // Health row
    Row {
      id: healthRow
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: flowCard.bottom
      anchors.topMargin: 8
      spacing: 6
      readonly property real cell: (width - spacing * 2) / 3

      Stat { width: healthRow.cell; label: "Cycles"; value: tab.status.cycles !== null ? String(tab.status.cycles) : (isFinite(Number(tab.fields.cycle_count)) ? String(Number(tab.fields.cycle_count)) : Power.DASH) }
      Stat {
        width: healthRow.cell
        label: tab.hl.fullWh !== null ? "Health " + tab.hl.fullWh.toFixed(0) + "/" + tab.hl.designWh.toFixed(0) + " Wh" : "Health"
        value: tab.hl.percent !== null ? tab.hl.percent + "%" : Power.DASH
      }
      Stat { width: healthRow.cell; label: "Charge limit"; value: tab.limit.text }
    }

    // Sparklines
    Row {
      id: sparks
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: healthRow.bottom
      anchors.topMargin: 8
      anchors.bottom: parent.bottom
      spacing: 8
      readonly property real cell: (width - spacing) / 2

      Item {
        width: sparks.cell
        height: sparks.height
        Text {
          id: capCap
          textFormat: Text.PlainText
          text: "Charge" + (Power.fmtSpan(tab.history.spanSeconds) !== "" ? " · " + Power.fmtSpan(tab.history.spanSeconds) : "")
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: 9
        }
        SparkChart {
          anchors.top: capCap.bottom
          anchors.topMargin: 1
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.bottom: parent.bottom
          values: tab.history.cap
          tone: tab.tone
        }
        Text {
          textFormat: Text.PlainText
          anchors.centerIn: parent
          visible: tab.history.count < 2
          text: "collecting"
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: 9
        }
      }
      Item {
        width: sparks.cell
        height: sparks.height
        Text {
          id: wCap
          textFormat: Text.PlainText
          text: "Watts (+in / −out)"
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: 9
        }
        SparkChart {
          anchors.top: wCap.bottom
          anchors.topMargin: 1
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.bottom: parent.bottom
          values: tab.history.watts
          tone: tab.notch && tab.notch.themeObj ? tab.notch.themeObj.warn : Tk.warn
        }
        Text {
          textFormat: Text.PlainText
          anchors.centerIn: parent
          visible: tab.history.count < 2
          text: "collecting"
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: 9
        }
      }
    }
  }

  // ------------------------------------------------------------- profiles
  Row {
    id: profileRow
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    height: 26
    spacing: 6
    visible: tab.profileNames.length > 0
    readonly property int count: Math.max(1, tab.profileNames.length)
    readonly property real cell: (width - spacing * (count - 1)) / count

    Repeater {
      model: tab.profileNames
      Rectangle {
        id: pill
        required property string modelData
        readonly property bool active: modelData === (tab.pendingProfile !== "" ? tab.pendingProfile : tab.activeProfile)
        width: profileRow.cell
        height: profileRow.height
        radius: Tk.r(8)
        color: active ? Tk.alpha(tab.tone, 0.22) : (hit.containsMouse ? Tk.tint(0.12) : Tk.tint(0.06))
        border.width: active ? 1 : 0
        border.color: Tk.alpha(tab.tone, 0.7)
        Text {
          textFormat: Text.PlainText
          anchors.centerIn: parent
          text: Power.profileTitle(pill.modelData)
          color: pill.active ? tab.textColor : tab.dimColor
          font.family: tab.family
          font.pixelSize: 11
          font.weight: pill.active ? Font.DemiBold : Font.Normal
        }
        MouseArea {
          id: hit
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: tab.setProfile(pill.modelData)
        }
      }
    }
  }

  // Small label/value stat tile.
  component Stat: Rectangle {
    property string label: ""
    property string value: ""
    height: 34
    radius: Tk.r(8)
    color: Tk.tint(0.06)
    Column {
      anchors.centerIn: parent
      width: parent.width - 8
      Text {
        textFormat: Text.PlainText
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: value
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: 13
        font.weight: Font.DemiBold
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: label
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: 9
      }
    }
  }
}
