import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "lukedaduke.ticker"
  ipcTarget: "lukedaduke.ticker"

  property string barSummary: "GOLD · TECH · ENERGY"
  property string lastUpdated: ""
  property var marketItems: []
  property bool isFetching: false
  property string fetchError: ""
  property int selectedIndex: 0

  readonly property color fg: bar ? bar.foreground : Color.foreground
  readonly property color urgent: Color.urgent
  readonly property color accent: Color.accent
  readonly property color muted: Color.muted
  readonly property string pluginRoot: {
    var p = Qt.resolvedUrl(".").toString()
    if (p.indexOf("file://") === 0)
      p = p.substring(7)
    if (p.length > 1 && p.charAt(p.length - 1) === "/")
      p = p.substring(0, p.length - 1)
    return p
  }

  function refresh() {
    if (!statsProc.running) {
      isFetching = true
      statsProc.running = true
    }
  }

  function launchTradingView(tvSym) {
    var target = tvSym || "OANDA:XAUUSD"
    Quickshell.execDetached(["xdg-open", "https://www.tradingview.com/chart/?symbol=" + target])
    root.close()
  }

  function activateSelected() {
    if (root.marketItems[root.selectedIndex])
      root.launchTradingView(root.marketItems[root.selectedIndex].tv_sym)
  }

  function chipFill(positive) {
    var c = positive ? root.accent : root.urgent
    return Qt.rgba(c.r, c.g, c.b, 0.22)
  }

  function chipText(positive) {
    return positive ? root.accent : root.urgent
  }

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Process {
    id: statsProc
    command: ["python3", root.pluginRoot + "/bin/market_stats.py"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.isFetching = false
        try {
          var d = JSON.parse(text)
          if (d.summary)
            root.barSummary = d.summary
          if (d.items && d.items.length)
            root.marketItems = d.items
          if (d.updated_str)
            root.lastUpdated = d.updated_str
          if (d.ok === false)
            root.fetchError = d.error || "quotes failed"
          else
            root.fetchError = d.error || ""
          if (root.selectedIndex >= root.marketItems.length)
            root.selectedIndex = Math.max(0, root.marketItems.length - 1)
        } catch (e) {
          root.fetchError = "bad quotes json"
        }
      }
    }
    onExited: function (code) {
      root.isFetching = false
      if (code !== 0 && root.fetchError.length === 0)
        root.fetchError = "quotes helper exited " + code
    }
  }

  Timer {
    interval: 60000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    slotSize: Style.bar.iconSlot
    text: "󰠘"
    active: root.opened
    tooltipText: "Markets (" + root.barSummary + ")"
    onPressed: function (b) {
      if (b === Qt.RightButton)
        root.launchTradingView("OANDA:XAUUSD")
      else {
        root.refresh()
        root.toggle()
      }
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: panel.fittedContentWidth(Style.space(480))
    contentHeight: panel.fittedContentHeight(mainCol.implicitHeight)
    Keys.onPressed: function (event) {
      if (event.key === Qt.Key_J) {
        root.selectedIndex = Math.min(root.marketItems.length - 1, root.selectedIndex + 1)
        event.accepted = true
      } else if (event.key === Qt.Key_K) {
        root.selectedIndex = Math.max(0, root.selectedIndex - 1)
        event.accepted = true
      } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
        root.activateSelected()
        event.accepted = true
      }
    }

    Column {
      id: mainCol
      width: parent.width
      spacing: Style.space(8)
      padding: Style.space(12)

      RowLayout {
        width: parent.width
        Text {
          text: "Market watchlist"
          color: root.fg
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.bodySmall
          font.bold: true
        }
        Item {
          Layout.fillWidth: true
        }
        Rectangle {
          height: Style.space(20)
          width: statusLabel.implicitWidth + 16
          radius: Style.space(4)
          color: root.isFetching ? root.accent : Color.popups.background
          border.color: root.fg
          border.width: 1
          Text {
            id: statusLabel
            anchors.centerIn: parent
            text: root.isFetching ? "syncing" : (root.lastUpdated ? root.lastUpdated : "idle")
            color: root.isFetching ? Color.background : root.fg
            font.pixelSize: Style.font.bodySmall
            font.bold: true
          }
          MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: root.refresh()
          }
        }
      }

      Text {
        visible: root.fetchError.length > 0
        width: parent.width
        text: root.fetchError
        color: root.urgent
        font.pixelSize: Style.font.bodySmall
        wrapMode: Text.WordWrap
      }

      Text {
        visible: root.marketItems.length === 0 && !root.isFetching
        text: "No quotes yet"
        color: root.muted
        font.pixelSize: Style.font.bodySmall
      }

      Rectangle {
        width: parent.width
        height: 1
        color: root.fg
        opacity: 0.15
      }

      Grid {
        id: gridTable
        width: parent.width
        columns: 2
        columnSpacing: Style.space(8)
        rowSpacing: Style.space(4)
        Repeater {
          model: root.marketItems
          delegate: Rectangle {
            required property var modelData
            required property int index
            width: (gridTable.width - gridTable.columnSpacing) / 2
            height: Style.space(28)
            radius: Style.space(4)
            color: index === root.selectedIndex ? Style.selectedFillFor(root.fg, Color.accent) : "transparent"
            border.color: root.fg
            border.width: 1
            opacity: 0.9
            RowLayout {
              anchors.fill: parent
              anchors.leftMargin: Style.space(6)
              anchors.rightMargin: Style.space(6)
              spacing: Style.space(4)
              Text {
                text: modelData.symbol
                color: root.fg
                font.bold: true
                font.pixelSize: Style.font.bodySmall
                Layout.preferredWidth: Style.space(55)
              }
              Text {
                text: modelData.price
                color: root.fg
                font.bold: true
                font.pixelSize: Style.font.bodySmall
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignRight
              }
              Rectangle {
                height: Style.space(18)
                width: Style.space(58)
                radius: Style.space(3)
                color: root.chipFill(modelData.positive)
                Text {
                  anchors.centerIn: parent
                  text: modelData.change
                  color: root.chipText(modelData.positive)
                  font.bold: true
                  font.pixelSize: Style.font.bodySmall
                }
              }
            }
            MouseArea {
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onEntered: root.selectedIndex = index
              onClicked: root.launchTradingView(modelData.tv_sym)
            }
          }
        }
      }

      Text {
        anchors.horizontalCenter: parent.horizontalCenter
        text: "Enter or click opens TradingView"
        color: root.muted
        font.pixelSize: Style.font.bodySmall
      }
    }
  }
}
