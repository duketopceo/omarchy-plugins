import QtQuick 6.11
import qs.Commons as Commons
import "Dnd.js" as Dnd

// Home, the page every open starts on: the header (time, date, weather,
// status dots, Do Not Disturb bell, mic and camera dots), then the live
// activities as compact rows with their primary control (the next calendar
// event first, with Join), then the Do Not Disturb and mic-mute toggles. The
// media row opens Music. Rows past the count committed at open are left out
// until the card reopens, so the height never changes while open (KTD2).
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

  readonly property int maxStrip: 3
  readonly property int rowH: Commons.Style.spacing.controlHeight
  readonly property int gap: Commons.Style.spacing.lg

  readonly property var live: {
    var out = []
    if (page.layout && page.layout.top) out.push(page.layout.top)
    var rows = page.layout && page.layout.rows ? page.layout.rows : []
    for (var i = 0; i < rows.length; i++) out.push(rows[i])
    // The next calendar event leads the strip.
    out.sort(function (a, b) { return (a.id === "calendar" ? 0 : 1) - (b.id === "calendar" ? 0 : 1) })
    return out
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

  readonly property bool hasToggles: page.island !== null && (page.island.dndAvailable === true || page.island.micMuteAvailable === true)

  function count() { return Math.min(page.maxStrip, page.liveIds.length) }
  function heightFor(n) {
    return header.implicitHeight + n * (page.rowH + page.gap) + (page.hasToggles ? page.gap + page.rowH : 0)
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

    Repeater {
      model: page.liveIds.slice(0, page.maxRows)

      Item {
        id: slot
        required property string modelData
        readonly property var activity: page.activityFor(modelData)
        width: parent.width
        height: page.rowH

        // Under the row, so the row's own button still takes its clicks.
        MouseArea {
          anchors.fill: parent
          enabled: slot.modelData === "media"
          cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
          onClicked: page.openPage("music")
        }

        ActivityRow {
          anchors.fill: parent
          activity: slot.activity
          onAct: function(id, action) { page.act(id, action) }
        }
      }
    }

    Row {
      visible: page.hasToggles
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
    }
  }
}
