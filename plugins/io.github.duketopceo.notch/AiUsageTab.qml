import QtQuick
import Quickshell
import qs.Commons as Commons
import "Agents.js" as Agents

// AI usage tab: the same quota data the bar's AI Usage widget draws, one card
// per provider, one row per window (session, weekly, extras). The bar icon and
// this tab read the same `ai-usagebar usage --json` report; Notch shares one
// fetch and rate-limits it to 5 minutes, so opening the tab refreshes at most
// once per visit. The Plugins hub's AI tile opens this tab in place.
Item {
  id: tab

  property var notch: null

  readonly property color textColor: notch && notch.textColor ? notch.textColor : Tk.text
  readonly property color dimColor: notch && notch.dimColor ? notch.dimColor : Tk.dim
  readonly property color accentColor: notch && notch.accentColor ? notch.accentColor : Tk.accent
  readonly property color urgentColor: notch && notch.urgentColor ? notch.urgentColor : Tk.urgent
  readonly property color warnColor: notch && notch.warnColor ? notch.warnColor : Tk.warn
  readonly property color goodColor: notch && notch.goodColor ? notch.goodColor : Tk.good
  readonly property string family: notch && notch.fontFamily ? notch.fontFamily : Commons.Style.font.family
  readonly property int cardRadius: notch && notch.cardRadius ? notch.cardRadius : 8

  readonly property var usage: notch && notch.usage ? notch.usage : ({ ok: false, providers: [] })
  readonly property var providers: usage && Array.isArray(usage.providers) ? usage.providers : []

  property real nowMs: Date.now()
  property real updatedAt: 0

  function refresh() {
    nowMs = Date.now()
    if (!notch || typeof notch.refreshUsage !== "function") return
    notch.refreshUsage()
    updatedAt = Date.now()
  }
  onVisibleChanged: if (visible) refresh()
  onNotchChanged: if (visible) refresh()
  Component.onCompleted: if (visible) refresh()
  Timer { interval: 60000; running: tab.visible; repeat: true; onTriggered: tab.refresh() }

  function sevColor(sev) {
    return sev === "critical" ? urgentColor
      : sev === "high" ? warnColor
      : sev === "mid" ? accentColor
      : goodColor
  }

  // Busiest window of a provider, for the card's headline percent.
  function topRow(p) {
    var best = null
    for (var i = 0; i < p.rows.length; i++) if (best === null || p.rows[i].percent > best.percent) best = p.rows[i]
    return best
  }

  // ---------------------------------------------------------------- content
  Item {
    anchors.fill: parent

    // header: title + refresh
    Item {
      id: head
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: parent.top
      height: 22

      Text {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        textFormat: Text.PlainText
        text: "AI usage"
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: 11
        font.bold: true
      }

      Rectangle {
        id: refreshBtn
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: refreshLabel.implicitWidth + 16
        height: 20
        radius: Tk.r(10)
        color: refreshHit.containsMouse ? Tk.tint(0.24) : Tk.tint(0.1)
        Text {
          id: refreshLabel
          anchors.centerIn: parent
          textFormat: Text.PlainText
          text: "Refresh"
          color: tab.textColor
          font.family: tab.family
          font.pixelSize: 10
        }
        MouseArea {
          id: refreshHit
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: tab.refresh()
        }
      }

      Text {
        anchors.right: refreshBtn.left
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        textFormat: Text.PlainText
        text: "Resets count down live"
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: 10
        opacity: 0.8
      }
    }

    Text {
      visible: tab.providers.length === 0
      anchors.centerIn: parent
      textFormat: Text.PlainText
      text: "No usage data yet"
      color: tab.dimColor
      font.family: tab.family
      font.pixelSize: 11
    }

    NotchScroll {
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: head.bottom
      anchors.topMargin: 4
      anchors.bottom: parent.bottom
      rowHeight: 116
      contentHeight: cards.height
      contentWidth: width

      Column {
        id: cards
        width: parent.width
        spacing: 8

        Repeater {
          model: tab.providers

          Rectangle {
            id: card
            required property var modelData
            readonly property var best: tab.topRow(modelData)

            width: cards.width
            height: cardHead.height + 4 + rowsCol.height + 10
            radius: Tk.r(tab.cardRadius)
            color: Tk.tint(0.06)

            Item {
              id: cardHead
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.top: parent.top
              anchors.leftMargin: 10
              anchors.rightMargin: 10
              anchors.topMargin: 7
              height: 18

              Text {
                id: cardName
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                textFormat: Text.PlainText
                text: card.modelData.name
                color: tab.textColor
                font.family: tab.family
                font.pixelSize: 12
                font.bold: true
              }
              Text {
                id: cardPlan
                anchors.left: cardName.right
                anchors.leftMargin: 8
                anchors.right: cardPercent.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                textFormat: Text.PlainText
                text: card.modelData.plan
                color: tab.dimColor
                font.family: tab.family
                font.pixelSize: 10
                elide: Text.ElideRight
              }
              Text {
                id: cardPercent
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                textFormat: Text.PlainText
                text: card.best ? card.best.percent + "%" : ""
                color: card.best ? tab.sevColor(card.best.severity) : tab.dimColor
                font.family: tab.family
                font.pixelSize: 15
                font.bold: true
              }
            }

            Column {
              id: rowsCol
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.top: cardHead.bottom
              anchors.leftMargin: 10
              anchors.rightMargin: 10
              anchors.topMargin: 4
              spacing: 3

              Repeater {
                model: card.modelData.rows

                Item {
                  id: row
                  required property var modelData
                  width: rowsCol.width
                  height: 22

                  Text {
                    id: label
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: 110
                    textFormat: Text.PlainText
                    text: row.modelData.label
                    color: tab.dimColor
                    font.family: tab.family
                    font.pixelSize: 10
                    elide: Text.ElideRight
                  }

                  Text {
                    id: reset
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    width: 96
                    horizontalAlignment: Text.AlignRight
                    textFormat: Text.PlainText
                    text: {
                      if (!row.modelData.resetAt) return ""
                      var left = Agents.resetShort(row.modelData.resetAt, tab.nowMs)
                      return left === "" ? "" : left === "now" ? "resets now" : "resets in " + left
                    }
                    color: tab.dimColor
                    font.family: tab.family
                    font.pixelSize: 9
                    elide: Text.ElideRight
                  }

                  Text {
                    id: pct
                    anchors.right: reset.left
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    width: 38
                    horizontalAlignment: Text.AlignRight
                    textFormat: Text.PlainText
                    text: row.modelData.percent + "%"
                    color: tab.sevColor(row.modelData.severity)
                    font.family: tab.family
                    font.pixelSize: 10
                    font.bold: true
                  }

                  SegBar {
                    id: track
                    anchors.left: label.right
                    anchors.leftMargin: 6
                    anchors.right: pct.left
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    swiftHeight: 5
                    track: Tk.tint(0.12)
                    value: row.modelData.percent / 100
                    fill: tab.sevColor(row.modelData.severity)
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
