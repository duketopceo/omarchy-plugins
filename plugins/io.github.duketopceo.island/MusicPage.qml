import QtQuick 6.11
import qs.Commons as Commons

// Music: the Now Playing view from 0.3.1 (header line, then the media block
// with art, scrubber and controls), unchanged except that it is its own page.
Item {
  id: page

  property var island: null
  property date now: new Date()
  property color tint: Commons.Color.accent

  signal act(string id, string action, real value)
  signal holdStart()
  signal holdEnd()

  readonly property var activity: page.island ? page.island.mediaActivity : null

  function count() { return 0 }
  function heightFor(n) {
    // Media can start while the page is open, so its block always has room.
    return header.implicitHeight + Commons.Style.spacing.lg + mediaBlock.implicitHeight
  }

  Column {
    width: parent.width
    spacing: Commons.Style.spacing.lg

    HeaderRow {
      id: header
      width: parent.width
      island: page.island
      now: page.now
      compact: true
    }

    MediaBlock {
      id: mediaBlock
      visible: page.activity !== null
      width: parent.width
      height: visible ? implicitHeight : 0
      activity: page.activity
      tint: page.tint
      onAct: function(id, action, value) { page.act(id, action, value) }
      onHoldStart: page.holdStart()
      onHoldEnd: page.holdEnd()
    }

    // The block's own height is held so the card never changes size (KTD2).
    EmptyNote {
      visible: page.activity === null
      width: parent.width
      height: mediaBlock.implicitHeight
      text: "Nothing playing"
    }
  }
}
