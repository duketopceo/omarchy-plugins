import QtQuick 6.11
import qs.Commons as Commons
import "Dnd.js" as Dnd
import "Glyphs.js" as Glyphs

// Home, the page every open starts on. It always has content:
//   - the header (time, date, weather, status dots, bell, mic and camera dots)
//   - three tiles: Now Playing (art, title, transport; the tile opens Music),
//     Up Next (the next three calendar events, Join on a meeting link) and a
//     glance (battery, CPU and memory meters, and the agents summary)
//   - the other live activities (timer, dictation, recording, ...) as compact
//     rows with their primary control
//   - quick actions: Do Not Disturb, mic mute and a 5 minute timer.
// Media and the calendar live in their tiles, so they are not repeated as
// rows. Rows past the count committed at open are left out until the card
// reopens, so the height never changes while open (KTD2).
Item {
  id: page

  property var island: null
  property date now: new Date()
  // Activity.layout() for this window: { top, rows, ... }.
  property var layout: null
  // Rows the window committed to when the card opened.
  property int maxRows: 0

  signal act(string id, string action)
  signal openPage(string id)

  readonly property int maxStrip: 2
  readonly property int rowH: Commons.Style.spacing.controlHeight
  readonly property int gap: Commons.Style.spacing.lg
  readonly property int tileH: Commons.Style.space(116)
  readonly property int tilePad: Commons.Style.spacing.lg
  readonly property color textColor: Commons.Color.popups.text
  readonly property color plate: Qt.alpha(Commons.Color.popups.text, 0.06)

  readonly property var media: page.island ? page.island.mediaActivity : null

  readonly property var live: {
    var out = []
    if (page.layout && page.layout.top) out.push(page.layout.top)
    var rows = page.layout && page.layout.rows ? page.layout.rows : []
    for (var i = 0; i < rows.length; i++) out.push(rows[i])
    return out.filter(function (a) { return a && a.id !== "media" && a.id !== "calendar" })
  }
  // Keyed on ids, reassigned only when the set or order changes, so a row and
  // its button are not rebuilt mid-click by a ticking timer.
  property var liveIds: []
  onLiveChanged: {
    var ids = []
    for (var i = 0; i < page.live.length; i++) ids.push(String(page.live[i].id))
    if (ids.join(",") !== page.liveIds.join(",")) page.liveIds = ids
  }
  function activityFor(id) {
    for (var i = 0; i < page.live.length; i++) if (String(page.live[i].id) === id) return page.live[i]
    return null
  }

  function count() { return Math.min(page.maxStrip, page.liveIds.length) }
  function heightFor(n) {
    return header.implicitHeight + page.gap + page.tileH + n * (page.rowH + page.gap) + page.gap + page.rowH
  }

  component Label: Text {
    textFormat: Text.PlainText
    color: page.textColor
    elide: Text.ElideRight
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.body
  }
  component Caption: Label {
    opacity: 0.6
    font.pixelSize: Commons.Style.font.bodySmall
  }

  Column {
    width: parent.width
    spacing: page.gap

    HeaderRow {
      id: header
      width: parent.width
      island: page.island
      now: page.now
      showWeather: true
      showStatus: true
    }

    Row {
      id: tiles
      width: parent.width
      height: page.tileH
      spacing: page.gap
      readonly property int tileW: Math.floor((width - spacing * 2) / 3)

      // ---- Now Playing ----
      Rectangle {
        id: nowTile
        width: tiles.tileW
        height: parent.height
        radius: Commons.Style.cornerRadius
        color: page.plate

        MouseArea {
          anchors.fill: parent
          enabled: page.media !== null
          cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
          onClicked: page.openPage("music")
        }

        Caption {
          id: nowCaption
          x: page.tilePad; y: page.tilePad
          width: parent.width - page.tilePad * 2
          text: page.media ? (page.media.identity || "Now Playing") : "Now Playing"
        }

        ArtImage {
          id: nowArt
          visible: page.media !== null
          x: page.tilePad
          anchors.top: nowCaption.bottom
          anchors.topMargin: Commons.Style.spacing.sm
          width: Commons.Style.space(44)
          height: width
          radius: Math.round(width * 0.18)
          source: page.media ? String(page.media.art || "") : ""
        }

        Column {
          visible: page.media !== null
          anchors.left: nowArt.right
          anchors.leftMargin: Commons.Style.spacing.lg
          anchors.right: parent.right
          anchors.rightMargin: page.tilePad
          anchors.verticalCenter: nowArt.verticalCenter
          Label { width: parent.width; text: page.media ? (page.media.card || page.media.text || "") : "" }
          Caption { width: parent.width; text: page.media ? (page.media.subtitle || "") : "" }
        }

        Row {
          visible: page.media !== null
          anchors.horizontalCenter: parent.horizontalCenter
          anchors.bottom: parent.bottom
          anchors.bottomMargin: Commons.Style.spacing.sm
          spacing: Commons.Style.spacing.huge

          Repeater {
            model: [
              { action: "previous", flag: "canGoPrevious" },
              { action: "toggle", flag: "canTogglePlaying" },
              { action: "next", flag: "canGoNext" }
            ]
            Text {
              id: transport
              required property var modelData
              readonly property bool ok: page.media !== null && page.media[transport.modelData.flag] === true
              textFormat: Text.PlainText
              text: transport.modelData.action === "toggle"
                ? (page.media && page.media.playing ? Glyphs.GLYPHS.pause : Glyphs.GLYPHS.play)
                : Glyphs.GLYPHS[transport.modelData.action]
              color: page.textColor
              opacity: transport.ok ? 1 : 0.35
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.heading
              MouseArea {
                anchors.fill: parent
                anchors.margins: -Commons.Style.spacing.sm
                enabled: transport.ok
                cursorShape: Qt.PointingHandCursor
                onClicked: page.act("media", transport.modelData.action)
              }
            }
          }
        }

        Column {
          visible: page.media === null
          anchors.centerIn: parent
          anchors.verticalCenterOffset: Commons.Style.spacing.sm
          spacing: Commons.Style.spacing.sm
          Label {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Glyphs.GLYPHS.music
            opacity: 0.5
            font.pixelSize: Commons.Style.font.heading
          }
          Caption { anchors.horizontalCenter: parent.horizontalCenter; text: "Nothing playing" }
        }
      }

      // ---- Up Next ----
      Rectangle {
        id: nextTile
        width: tiles.tileW
        height: parent.height
        radius: Commons.Style.cornerRadius
        color: page.plate
        readonly property var items: page.island ? page.island.agenda : []

        Caption {
          id: nextCaption
          x: page.tilePad; y: page.tilePad
          width: parent.width - page.tilePad * 2
          text: "Up next"
        }

        Column {
          anchors.top: nextCaption.bottom
          anchors.topMargin: Commons.Style.spacing.sm
          x: page.tilePad
          width: parent.width - page.tilePad * 2
          spacing: Commons.Style.spacing.sm

          Repeater {
            model: nextTile.items
            Item {
              id: ev
              required property var modelData
              width: parent.width
              height: Math.max(evTime.implicitHeight, join.visible ? join.implicitHeight : 0)

              Label {
                id: evTime
                width: Commons.Style.space(44)
                anchors.verticalCenter: parent.verticalCenter
                text: ev.modelData.time
                color: ev.modelData.live ? Commons.Color.accent : page.textColor
                font.features: { "tnum": 1 }
              }
              Label {
                anchors.left: evTime.right
                anchors.right: join.visible ? join.left : parent.right
                anchors.rightMargin: join.visible ? Commons.Style.spacing.sm : 0
                anchors.verticalCenter: parent.verticalCenter
                text: ev.modelData.title
              }
              Label {
                id: join
                visible: ev.modelData.url !== ""
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                text: "Join"
                color: Commons.Color.accent
                MouseArea {
                  anchors.fill: parent
                  anchors.margins: -Commons.Style.spacing.sm
                  cursorShape: Qt.PointingHandCursor
                  onClicked: page.island.joinMeeting(ev.modelData.url)
                }
              }
            }
          }
        }

        Caption {
          visible: nextTile.items.length === 0
          anchors.centerIn: parent
          anchors.verticalCenterOffset: Commons.Style.spacing.sm
          text: page.island && page.island.calendarOn ? "Nothing in the next 24 h" : "Calendar is off"
        }
      }

      // ---- Glance: battery, CPU, memory, agents ----
      Rectangle {
        id: glanceTile
        width: tiles.tileW
        height: parent.height
        radius: Commons.Style.cornerRadius
        color: page.plate
        readonly property var rows: page.island ? page.island.homeGlance : []
        readonly property string agents: page.island ? page.island.agentsSummary : ""

        Column {
          x: page.tilePad; y: page.tilePad
          width: parent.width - page.tilePad * 2
          spacing: Commons.Style.spacing.sm

          Repeater {
            model: glanceTile.rows
            Column {
              id: g
              required property var modelData
              width: parent.width
              spacing: 2
              Item {
                width: parent.width
                height: gLabel.implicitHeight
                Caption { id: gLabel; text: g.modelData.label }
                Label {
                  anchors.right: parent.right
                  anchors.verticalCenter: gLabel.verticalCenter
                  text: g.modelData.value
                  font.pixelSize: Commons.Style.font.bodySmall
                  font.features: { "tnum": 1 }
                }
              }
              Rectangle {
                width: parent.width
                height: 3
                radius: 1.5
                color: Commons.Color.menu.selectedBackground
                Rectangle {
                  height: parent.height
                  radius: parent.radius
                  width: Math.round(parent.width * Math.max(0, Math.min(1, g.modelData.level)))
                  color: Commons.Color.accent
                }
              }
            }
          }

          Item {
            visible: glanceTile.agents !== ""
            width: parent.width
            height: agentsLabel.implicitHeight
            Caption { id: agentsLabel; text: "Agents" }
            Label {
              anchors.right: parent.right
              anchors.left: agentsLabel.right
              anchors.leftMargin: Commons.Style.spacing.sm
              horizontalAlignment: Text.AlignRight
              text: glanceTile.agents
              font.pixelSize: Commons.Style.font.bodySmall
            }
            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: page.openPage("agents")
            }
          }
        }

        Caption {
          visible: glanceTile.rows.length === 0
          anchors.centerIn: parent
          text: "Reading system state"
        }
      }
    }

    Repeater {
      model: page.liveIds.slice(0, page.maxRows)

      ActivityRow {
        required property string modelData
        width: parent.width
        height: page.rowH
        activity: page.activityFor(modelData)
        onAct: function(id, action) { page.act(id, action) }
      }
    }

    Row {
      spacing: Commons.Style.spacing.lg

      ActivityButton {
        visible: page.island !== null && page.island.dndAvailable === true
        label: Dnd.GLYPH + "  Do Not Disturb"
        emphasized: page.island !== null && page.island.dndOn === true
        onClicked: page.island.toggleDnd()
      }
      ActivityButton {
        visible: page.island !== null && page.island.micMuteAvailable === true
        label: page.island !== null && page.island.micMuted ? "Mic muted" : "Mic on"
        emphasized: page.island !== null && page.island.micMuted === true
        onClicked: page.island.toggleMicMute()
      }
      ActivityButton {
        visible: page.island !== null
        label: "5 min timer"
        onClicked: page.island.startTimer("5m")
      }
    }
  }
}
