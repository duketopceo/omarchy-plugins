import QtQuick 6.11
import Quickshell
import Quickshell.Bluetooth
import "Bluetooth.js" as BluetoothModel

// Connected Bluetooth audio devices for the Island (KTD13): a card-only
// activity with the device's name and battery, and a connect edge for the
// alert. Read-only; the reader lives in a Loader so BlueZ is only touched
// while the setting is on.
Scope {
  id: src

  property bool enabled: false

  property var list: []
  property var model: BluetoothModel.initial()
  readonly property var activity: BluetoothModel.activity(src.list)

  // One per newly connected audio device: { address, name, battery }.
  signal connected(var edge)

  onEnabledChanged: if (!src.enabled) { src.list = []; src.model = BluetoothModel.initial() }

  function ingest(devices) {
    var audio = BluetoothModel.audio(devices)
    src.list = audio
    var r = BluetoothModel.step(src.model, audio)
    if (r.model !== src.model) src.model = r.model
    for (var i = 0; i < r.edges.length; i++) src.connected(r.edges[i])
  }

  Loader {
    active: src.enabled

    sourceComponent: Item {
      id: reader

      // Reading each device's fields inside the binding re-evaluates it when
      // a device connects, disconnects or reports a new battery level.
      readonly property var records: {
        var values = Bluetooth.devices ? Bluetooth.devices.values : []
        var out = []
        for (var i = 0; i < values.length; i++) {
          var d = values[i]
          if (!d) continue
          out.push({
            address: String(d.address || ""), name: String(d.name || d.deviceName || ""),
            icon: String(d.icon || ""), connected: d.connected === true,
            batteryAvailable: d.batteryAvailable === true, battery: Number(d.battery) || 0
          })
        }
        return out
      }
      onRecordsChanged: src.ingest(reader.records)
      Component.onCompleted: src.ingest(reader.records)
    }
  }
}
