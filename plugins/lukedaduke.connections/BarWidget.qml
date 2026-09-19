import QtQuick
import Quickshell
import Quickshell.Bluetooth
import Quickshell.Networking
import qs.Commons
import qs.Ui

BarWidget {
    id: root
    moduleName: "lukedaduke.connections"
    implicitWidth: rowLayout.implicitWidth
    implicitHeight: root.bar ? root.bar.barSize : Style.bar.sizeHorizontal

    // The stock Panel base (Ui/Panel.qml) only accepts `bar` — its own
    // internal BarIconButton is what each KeyboardPanel anchors to, so the
    // Loaders below are filled to their visible buttons instead of trying to
    // inject anchor properties the Panel type doesn't declare.
    function injectPanels() {
        if (btLoader.item && "bar" in btLoader.item) btLoader.item.bar = root.bar;
        if (wifiLoader.item && "bar" in wifiLoader.item) wifiLoader.item.bar = root.bar;
    }

    onBarChanged: injectPanels()

    Row {
        id: rowLayout
        anchors.verticalCenter: parent.verticalCenter
        spacing: 0

        BarIconButton {
            id: btButton
            bar: root.bar
            text: btLoader.item && btLoader.item.icon ? btLoader.item.icon : "󰂯"
            // Same source the stock panel reads: Bluetooth.defaultAdapter.
            dimmed: !(Bluetooth.defaultAdapter && Bluetooth.defaultAdapter.enabled)
            tooltipText: "Bluetooth · Left: panel · Right: toggle radio"
            onPressed: function(b) {
                if (!btLoader.item) return;
                if (b === Qt.RightButton && typeof btLoader.item.toggleBluetooth === "function")
                    btLoader.item.toggleBluetooth();
                else if (typeof btLoader.item.toggle === "function")
                    btLoader.item.toggle();
            }

            // Filled to this button so the embedded panel's internal
            // BarIconButton — what its KeyboardPanel anchors to — sits
            // exactly under this icon and the popup opens in the right place.
            Loader {
                id: btLoader
                anchors.fill: parent
                active: true
                visible: false
                source: "file:///usr/share/omarchy/shell/plugins/panels/bluetooth/Panel.qml"
                onLoaded: {
                    root.injectPanels();
                    Qt.callLater(root.injectPanels);
                }
                onStatusChanged: {
                    if (status === Loader.Error)
                        console.warn("lukedaduke.connections: failed to load stock bluetooth panel: " + source);
                }
            }
        }

        BarIconButton {
            id: wifiButton
            bar: root.bar
            text: wifiLoader.item && wifiLoader.item.icon ? wifiLoader.item.icon : "󰤨"
            // Same source the stock panel reads: Networking.wifiEnabled.
            dimmed: !Networking.wifiEnabled
            tooltipText: "Wi-Fi · Left: panel · Right: toggle radio"
            onPressed: function(b) {
                if (!wifiLoader.item) return;
                if (b === Qt.RightButton && typeof wifiLoader.item.toggleNetwork === "function")
                    wifiLoader.item.toggleNetwork();
                else if (typeof wifiLoader.item.toggle === "function")
                    wifiLoader.item.toggle();
            }

            Loader {
                id: wifiLoader
                anchors.fill: parent
                active: true
                visible: false
                source: "file:///usr/share/omarchy/shell/plugins/panels/network/Panel.qml"
                onLoaded: {
                    root.injectPanels();
                    Qt.callLater(root.injectPanels);
                }
                onStatusChanged: {
                    if (status === Loader.Error)
                        console.warn("lukedaduke.connections: failed to load stock network panel: " + source);
                }
            }
        }
    }
}
