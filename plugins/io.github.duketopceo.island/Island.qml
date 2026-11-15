import QtQuick

// Placeholder root so the manifest entry point exists; replaced by the
// window, hover and card units.
Item {
  id: root

  property var shell: null
  property var manifest: null
  property bool opened: false

  function open(payload) {}
  function close() {}
  function toggle() {}
}
