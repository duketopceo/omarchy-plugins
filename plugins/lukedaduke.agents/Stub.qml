import QtQuick
import qs.Commons
import qs.Ui

// Retired plugin: shows one dimmed icon whose tooltip names the replacement.
// No helpers, no polling, no processes.
BarWidget {
  id: root
  moduleName: "lukedaduke.agents"
  implicitWidth: notice.implicitWidth
  implicitHeight: root.bar ? root.bar.barSize : Style.bar.sizeHorizontal

  BarIconButton {
    id: notice
    anchors.verticalCenter: parent.verticalCenter
    bar: root.bar
    text: "󰀦"
    dimmed: true
    tooltipText: "My Agents is retired. Use akitaonrails.ai-usagebar instead (see the plugin README)."
  }
}
