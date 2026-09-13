import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

BarWidget {
    id: root
    moduleName: "lukedaduke.connections"
    implicitWidth: rowLayout.implicitWidth
    implicitHeight: root.bar ? root.bar.barSize : Style.bar.sizeHorizontal

    function injectPanels() {
        if (btLoader.item) {
            if ("bar" in btLoader.item) btLoader.item.bar = root.bar;
            if ("anchorItem" in btLoader.item) btLoader.item.anchorItem = btButton;
            if ("hostWidget" in btLoader.item) btLoader.item.hostWidget = root;
        }
        if (wifiLoader.item) {
            if ("bar" in wifiLoader.item) wifiLoader.item.bar = root.bar;
            if ("anchorItem" in wifiLoader.item) wifiLoader.item.anchorItem = wifiButton;
            if ("hostWidget" in wifiLoader.item) wifiLoader.item.hostWidget = root;
        }
    }

    onBarChanged: injectPanels()

    Loader {
        id: btLoader
        active: true
        source: "file:///usr/share/omarchy/shell/plugins/panels/bluetooth/Panel.qml"
        visible: false
        onLoaded: {
            root.injectPanels();
            Qt.callLater(root.injectPanels);
        }
    }

    Loader {
        id: wifiLoader
        active: true
        source: "file:///usr/share/omarchy/shell/plugins/panels/network/Panel.qml"
        visible: false
        onLoaded: {
            root.injectPanels();
            Qt.callLater(root.injectPanels);
        }
    }

    Row {
        id: rowLayout
        anchors.verticalCenter: parent.verticalCenter
        spacing: 0

        BarIconButton {
            id: btButton
            bar: root.bar
            text: btLoader.item && btLoader.item.icon ? btLoader.item.icon : "󰂯"
            dimmed: btLoader.item && "bluetoothEnabled" in btLoader.item ? !btLoader.item.bluetoothEnabled : false
            tooltipText: "Bluetooth · Left: panel · Right: toggle radio"
            onPressed: function(b) {
                if (!btLoader.item) return;
                if (b === Qt.RightButton && typeof btLoader.item.toggleBluetooth === "function")
                    btLoader.item.toggleBluetooth();
                else if (typeof btLoader.item.toggle === "function")
                    btLoader.item.toggle();
            }
        }

        BarIconButton {
            id: wifiButton
            bar: root.bar
            text: wifiLoader.item && wifiLoader.item.icon ? wifiLoader.item.icon : "󰤨"
            dimmed: wifiLoader.item && "wifiEnabled" in wifiLoader.item ? !wifiLoader.item.wifiEnabled : false
            tooltipText: "Wi-Fi · Left: panel · Right: toggle radio"
            onPressed: function(b) {
                if (!wifiLoader.item) return;
                if (b === Qt.RightButton && typeof wifiLoader.item.toggleNetwork === "function")
                    wifiLoader.item.toggleNetwork();
                else if (typeof wifiLoader.item.toggle === "function")
                    wifiLoader.item.toggle();
            }
        }
    }
}
