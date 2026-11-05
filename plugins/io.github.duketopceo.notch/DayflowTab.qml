import QtQuick
import Quickshell
import qs.Commons as Commons
import "Dayflow.js" as Dayflow

// Dayflow tab (local customization, optional: Settings > Dayflow). Reads the
// shared DayflowState on the root Notch item (`notch.dayflow`); while visible
// it asks for the throttled heavy reads (agents, briefing, forecast).
//   header:  recording state, frames, last frame | pause / resume
//   strip:   today's blocks coloured by category, current block outlined
//   col 1:   now (current block title, category, time), focus share, forecast
//   col 2:   top apps with minute bars
//   col 3:   agent sessions today (count, by tool, latest), workstreams
// Block titles are shown here only; the collapsed notch never shows them.
Item {
  id: tab

  property var notch: null
  readonly property var df: notch ? notch.dayflow : null
  readonly property var status: df ? df.status : Dayflow.parseStatus("")
  readonly property var today: df ? df.today : Dayflow.emptyToday()
  readonly property var agents: df ? df.agents : Dayflow.parseAgents("")
  readonly property var briefing: df ? df.briefing : Dayflow.parseBriefing("")
  readonly property var forecast: df ? df.forecast : Dayflow.parseForecast("")
  readonly property date now: notch ? notch.now : new Date()
  readonly property color textColor: notch ? notch.textColor : "white"
  readonly property color dimColor: notch ? notch.dimColor : "gray"
  readonly property string family: notch ? notch.fontFamily : ""

  readonly property var stripModel: {
    var d0 = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    return Dayflow.strip(today, Math.floor(now.getTime() / 1000), Math.floor(d0.getTime() / 1000))
  }

  function ask() { if (visible && df) { df.requestDetails(); df.pollStatus() } }
  onVisibleChanged: ask()
  onDfChanged: ask()
  Component.onCompleted: ask()

  readonly property int gap: 16
  readonly property int colW: Math.floor((width - 2 * gap) / 3)
  readonly property int bodyTop: 104
  implicitWidth: 688
  implicitHeight: 298

  component Caption: Text {
    textFormat: Text.PlainText
    color: tab.dimColor
    font.family: tab.family
    font.pixelSize: Commons.Style.font.caption
    font.letterSpacing: 0.8
    font.capitalization: Font.AllUppercase
  }
  component Line: Text {
    textFormat: Text.PlainText
    width: parent ? parent.width : 0
    elide: Text.ElideRight
    color: tab.textColor
    font.family: tab.family
    font.pixelSize: Commons.Style.font.bodySmall
  }
  component Divider: Rectangle {
    width: 1
    color: Qt.rgba(1, 1, 1, 0.07)
  }

  // ------------------------------------------------------------ header
  Item {
    id: header
    width: parent.width
    height: 28

    Rectangle {
      id: recDot
      width: 10; height: 10; radius: 5
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      color: tab.status.paused ? Commons.Color.urgent : tab.status.recording ? "#f53d3d" : tab.dimColor
      SequentialAnimation on opacity {
        running: tab.visible && tab.status.recording && !(tab.notch && tab.notch.reduceMotion)
        loops: Animation.Infinite
        onRunningChanged: if (!running) recDot.opacity = 1
        NumberAnimation { to: 0.35; duration: 900; easing.type: Easing.InOutSine }
        NumberAnimation { to: 1; duration: 900; easing.type: Easing.InOutSine }
      }
    }
    Text {
      id: stateLabel
      textFormat: Text.PlainText
      anchors.left: recDot.right
      anchors.leftMargin: 8
      anchors.verticalCenter: parent.verticalCenter
      text: Dayflow.stateText(tab.status)
      color: tab.status.paused ? Commons.Color.urgent : tab.textColor
      font.family: tab.family
      font.pixelSize: Commons.Style.font.body
      font.weight: Font.DemiBold
    }
    Text {
      textFormat: Text.PlainText
      anchors.left: stateLabel.right
      anchors.leftMargin: 10
      anchors.right: toggleBtn.left
      anchors.rightMargin: 10
      anchors.verticalCenter: parent.verticalCenter
      elide: Text.ElideRight
      visible: tab.status.ok
      text: tab.status.frames + " frames" + (tab.status.lastFrame ? "  ·  last " + tab.status.lastFrame : "")
        + "  ·  " + tab.status.blocksDone + " blocks" + (tab.status.blocksPending > 0 ? " (" + tab.status.blocksPending + " pending)" : "")
        + (tab.status.storage ? "  ·  " + tab.status.storage : "")
      color: tab.dimColor
      font.family: tab.family
      font.pixelSize: Commons.Style.font.bodySmall
    }

    Rectangle {
      id: toggleBtn
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      width: toggleLabel.implicitWidth + 24
      height: 24
      radius: 12
      opacity: tab.status.ok && !(tab.df && tab.df.toggling) ? 1 : 0.4
      color: tab.status.paused ? (toggleHit.containsMouse ? Qt.lighter(Commons.Color.accent, 1.15) : Commons.Color.accent)
                               : (toggleHit.containsMouse ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(1, 1, 1, 0.1))
      Text {
        id: toggleLabel
        textFormat: Text.PlainText
        anchors.centerIn: parent
        text: tab.status.paused ? "Resume capture" : "Pause"
        color: tab.status.paused ? Commons.Color.background : tab.textColor
        font.family: tab.family
        font.pixelSize: Commons.Style.font.bodySmall
        font.weight: Font.DemiBold
      }
      MouseArea {
        id: toggleHit
        anchors.fill: parent
        hoverEnabled: true
        enabled: tab.status.ok
        cursorShape: Qt.PointingHandCursor
        onClicked: if (tab.df) tab.df.toggle()
      }
    }
  }

  // ------------------------------------------------------------ timeline strip
  Item {
    id: stripBox
    y: header.height + 10
    width: parent.width
    height: 20

    Rectangle { anchors.fill: parent; radius: 5; color: Qt.rgba(1, 1, 1, 0.06) }
    Repeater {
      model: tab.stripModel.segments
      Rectangle {
        required property var modelData
        x: Math.round(modelData.x * stripBox.width)
        width: Math.max(2, Math.round(modelData.w * stripBox.width) - 1)
        height: stripBox.height
        radius: 3
        color: modelData.color
        opacity: modelData.current ? 1 : 0.6
        border.width: modelData.current ? 2 : 0
        border.color: tab.textColor
      }
    }
    // Now marker.
    Rectangle {
      x: Math.round(tab.stripModel.now * stripBox.width) - 1
      y: -3
      width: 2
      height: stripBox.height + 6
      radius: 1
      color: tab.textColor
      opacity: 0.8
    }
  }
  Item {
    id: ticks
    anchors.top: stripBox.bottom
    anchors.topMargin: 4
    width: parent.width
    height: 14
    Repeater {
      model: {
        var out = []
        var from = tab.stripModel.from, to = tab.stripModel.to
        var hours = Math.max(1, Math.round((to - from) / 3600))
        var step = hours > 12 ? 4 : hours > 6 ? 2 : 1
        for (var t = from; t <= to; t += step * 3600) out.push({ t: t, x: (t - from) / Math.max(1, to - from) })
        return out
      }
      Text {
        required property var modelData
        textFormat: Text.PlainText
        x: Math.max(0, Math.min(ticks.width - implicitWidth, Math.round(modelData.x * ticks.width - implicitWidth / 2)))
        text: Qt.formatTime(new Date(modelData.t * 1000), "h AP")
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: Commons.Style.font.caption
      }
    }
  }
  Rectangle { y: tab.bodyTop - 8; width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.07) }

  // ------------------------------------------------------------ col 1: now, focus, forecast
  Item {
    id: col1
    x: 0
    y: tab.bodyTop
    width: tab.colW
    height: tab.height - tab.bodyTop

    Column {
      width: parent.width
      spacing: 3
      Caption { text: "Now" }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.WordWrap
        maximumLineCount: 2
        elide: Text.ElideRight
        text: tab.today.current ? tab.today.current.title : (tab.today.ok ? "No current block" : "No timeline yet")
        color: tab.today.current ? tab.textColor : tab.dimColor
        font.family: tab.family
        font.pixelSize: Commons.Style.font.body
        font.weight: Font.DemiBold
      }
      Row {
        visible: tab.today.current !== null
        spacing: 6
        Rectangle { width: 8; height: 8; radius: 4; anchors.verticalCenter: parent.verticalCenter; color: tab.today.current ? Dayflow.categoryColor(tab.today.current.category) : "transparent" }
        Text {
          textFormat: Text.PlainText
          text: tab.today.current ? Dayflow.categoryLabel(tab.today.current.category) + "  ·  " + tab.today.current.startLabel + " – " + tab.today.current.endLabel + (tab.today.current.app ? "  ·  " + tab.today.current.app : "") : ""
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: Commons.Style.font.bodySmall
        }
      }
    }

    Column {
      anchors.bottom: parent.bottom
      width: parent.width
      spacing: 2
      Caption { text: "Focus today" }
      Row {
        spacing: 8
        Text {
          id: focusPct
          textFormat: Text.PlainText
          text: tab.today.focusPct >= 0 ? tab.today.focusPct + "%" : "–"
          color: tab.today.focusPct >= 60 ? Commons.Color.accent : tab.textColor
          font.family: tab.family
          font.pixelSize: Commons.Style.font.display
          font.weight: Font.DemiBold
          font.features: ({ "tnum": 1 })
        }
        Text {
          textFormat: Text.PlainText
          anchors.baseline: focusPct.baseline
          text: tab.today.trackedMin > 0 ? Dayflow.duration(tab.today.productiveMin) + " of " + Dayflow.duration(tab.today.trackedMin) : ""
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: Commons.Style.font.bodySmall
        }
      }
      // Category mix as one thin bar.
      Row {
        width: parent.width
        height: 4
        Repeater {
          model: tab.today.categories
          Rectangle {
            required property var modelData
            width: tab.today.trackedMin > 0 ? Math.floor(col1.width * modelData.minutes / tab.today.trackedMin) : 0
            height: 4
            color: Dayflow.categoryColor(modelData.name)
          }
        }
      }
      Item { width: 1; height: 4 }
      Line { text: tab.forecast.line; color: tab.dimColor; visible: tab.forecast.line !== "" }
    }
  }
  Divider { x: tab.colW + tab.gap / 2; y: tab.bodyTop; height: tab.height - tab.bodyTop }

  // ------------------------------------------------------------ col 2: top apps
  Column {
    id: col2
    x: tab.colW + tab.gap
    y: tab.bodyTop
    width: tab.colW
    spacing: 6
    Caption { text: "Top apps" }
    Line { visible: tab.today.topApps.length === 0; text: "Nothing tracked yet"; color: tab.dimColor }
    Repeater {
      model: tab.today.topApps
      Column {
        id: appRow
        required property var modelData
        required property int index
        width: col2.width
        spacing: 3
        Row {
          width: parent.width
          Text { textFormat: Text.PlainText; width: parent.width - mins.implicitWidth; elide: Text.ElideRight; text: appRow.modelData.name; color: tab.textColor; font.family: tab.family; font.pixelSize: Commons.Style.font.bodySmall }
          Text { id: mins; textFormat: Text.PlainText; text: Dayflow.duration(appRow.modelData.minutes); color: tab.dimColor; font.family: tab.family; font.pixelSize: Commons.Style.font.bodySmall; font.features: ({ "tnum": 1 }) }
        }
        Rectangle {
          width: parent.width; height: 3; radius: 2
          color: Qt.rgba(1, 1, 1, 0.08)
          Rectangle {
            width: tab.today.topApps.length ? parent.width * appRow.modelData.minutes / Math.max(1, tab.today.topApps[0].minutes) : 0
            height: parent.height; radius: 2
            color: Commons.Color.accent
            opacity: appRow.index === 0 ? 1 : 0.6
          }
        }
      }
    }
  }
  Divider { x: 2 * tab.colW + tab.gap * 1.5; y: tab.bodyTop; height: tab.height - tab.bodyTop }

  // ------------------------------------------------------------ col 3: agents + workstreams
  Column {
    id: col3
    x: 2 * (tab.colW + tab.gap)
    y: tab.bodyTop
    width: tab.colW
    spacing: 3

    Row {
      width: parent.width
      Caption { text: "Agent sessions"; width: parent.width - agentCount.implicitWidth }
      Text {
        id: agentCount
        textFormat: Text.PlainText
        text: tab.agents.ok ? String(tab.agents.count) : "…"
        color: tab.agents.count > 0 ? Commons.Color.accent : tab.dimColor
        font.family: tab.family
        font.pixelSize: Commons.Style.font.bodySmall
        font.weight: Font.DemiBold
        font.features: ({ "tnum": 1 })
      }
    }
    Line {
      text: tab.agents.ok ? tab.agents.bySource.map(function (s) { return s.source + " " + s.count }).join("  ·  ") : "Loading…"
      color: tab.dimColor
    }
    Repeater {
      model: tab.agents.latest
      Line {
        required property var modelData
        text: modelData.source + "  " + (modelData.title || modelData.project)
      }
    }
    Item { width: 1; height: 6 }
    Caption { text: "Workstreams" }
    Line { visible: !tab.briefing.ok; text: "Loading…"; color: tab.dimColor }
    Repeater {
      model: tab.briefing.workstreams
      Row {
        id: wsRow
        required property var modelData
        width: col3.width
        Text { textFormat: Text.PlainText; width: parent.width - wsCount.implicitWidth; elide: Text.ElideRight; text: wsRow.modelData.name; color: tab.textColor; font.family: tab.family; font.pixelSize: Commons.Style.font.bodySmall }
        Text { id: wsCount; textFormat: Text.PlainText; text: String(wsRow.modelData.threads); color: tab.dimColor; font.family: tab.family; font.pixelSize: Commons.Style.font.bodySmall; font.features: ({ "tnum": 1 }) }
      }
    }
  }
}
