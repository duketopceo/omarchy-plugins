import QtQuick 6.11

// A page's empty state: one muted caption line centered in the area the
// parent gives it. Every page uses this, so empty reads the same everywhere.
Item {
  id: note

  property string text: ""

  Txt {
    anchors.centerIn: parent
    width: Math.min(implicitWidth, parent.width)
    horizontalAlignment: Text.AlignHCenter
    kind: "caption"
    text: note.text
  }
}
