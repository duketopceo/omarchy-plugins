import QtQuick
import qs.Commons
import qs.Ui

// Retired plugin: shows one dimmed icon whose tooltip names the replacement.
// No helpers, no polling, no processes.
BarWidget {
  id: root
  moduleName: "lukedaduke.ticker"
  implicitWidth: notice.implicitWidth
  implicitHeight: root.bar ? root.bar.barSize : Style.bar.sizeHorizontal

  BarIconButton {
    id: notice
    anchors.verticalCenter: parent.verticalCenter
    bar: root.bar
    text: "󰀦"
    dimmed: true
    tooltipText: "Market Watchlist is retired. Use mohamedmansour.finance instead (see the plugin README)."
  }
}
