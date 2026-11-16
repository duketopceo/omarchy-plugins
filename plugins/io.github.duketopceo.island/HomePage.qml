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

  // The shared type scale (Txt.qml): body and caption only on this page.
  component Label: Txt {}
  component Caption: Txt { kind: "caption" }

  // Transport and Join are small glyph or word buttons.
  readonly property int keyH: Commons.Style.space(28)
  readonly property int linkH: Math.ceil(Commons.Style.font.bodySmall * 1.9)

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
      onOpenPage: function(id) { page.openPage(id) }
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

        // The tile above the transport row opens Music. The transport keys
        // sit below it, so the two never overlap.
        HoverButton {
          id: nowOpen
          passive: page.media === null
          hint: "Open in Music"
          width: parent.width
          height: parent.height - page.keyH - Commons.Style.spacing.sm
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
          spacing: Commons.Style.spacing.lg

          Repeater {
            model: [
              { action: "previous", flag: "canGoPrevious" },
              { action: "toggle", flag: "canTogglePlaying" },
              { action: "next", flag: "canGoNext" }
            ]
            HoverButton {
              id: transport
              required property var modelData
              enabled: page.media !== null && page.media[transport.modelData.flag] === true
              hint: Glyphs.controlHint(transport.modelData.action, page.media)
              width: page.keyH
              height: page.keyH
              radius: height / 2
              onClicked: page.act("media", transport.modelData.action)

              Label {
                anchors.centerIn: parent
                width: implicitWidth
                kind: "heading"
                font.bold: false
                text: Glyphs.controlLabel(transport.modelData.action, page.media)
              }
            }
          }
        }

        EmptyNote {
          visible: page.media === null
          anchors.fill: parent
          text: "Nothing playing"
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
              height: Math.max(evTime.implicitHeight, join.visible ? join.height : 0)

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
              HoverButton {
                id: join
                visible: ev.modelData.url !== ""
                hint: "Join meeting"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: joinText.implicitWidth + Commons.Style.spacing.lg
                height: page.linkH
                radius: height / 2
                onClicked: page.island.joinMeeting(ev.modelData.url)

                Label {
                  id: joinText
                  anchors.centerIn: parent
                  width: implicitWidth
                  text: "Join"
                  color: Commons.Color.accent
                }
              }
            }
          }
        }

        EmptyNote {
          visible: nextTile.items.length === 0
          anchors.fill: parent
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

          HoverButton {
            visible: glanceTile.agents !== ""
            hint: "Open Agents"
            width: parent.width
            height: agentsLabel.implicitHeight + 2
            hitPad: 3
            onClicked: page.openPage("agents")

            Caption { id: agentsLabel; anchors.verticalCenter: parent.verticalCenter; width: implicitWidth; text: "Agents" }
            Caption {
              anchors.right: parent.right
              anchors.left: agentsLabel.right
              anchors.leftMargin: Commons.Style.spacing.sm
              anchors.verticalCenter: parent.verticalCenter
              horizontalAlignment: Text.AlignRight
              opacity: 1
              text: glanceTile.agents
            }
          }
        }

        EmptyNote {
          visible: glanceTile.rows.length === 0
          anchors.fill: parent
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
        hint: page.island !== null && page.island.dndOn === true ? "Turn off Do Not Disturb" : "Turn on Do Not Disturb"
        emphasized: page.island !== null && page.island.dndOn === true
        onClicked: page.island.toggleDnd()
      }
      ActivityButton {
        visible: page.island !== null && page.island.micMuteAvailable === true
        label: page.island !== null && page.island.micMuted ? "Mic muted" : "Mic on"
        hint: page.island !== null && page.island.micMuted ? "Unmute the microphone" : "Mute the microphone"
        emphasized: page.island !== null && page.island.micMuted === true
        onClicked: page.island.toggleMicMute()
      }
      ActivityButton {
        visible: page.island !== null
        label: "5 min timer"
        hint: "Start a 5 minute timer"
        onClicked: page.island.startTimer("5m")
      }
    }
  }
}
