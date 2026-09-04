import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons

Item {
  id: root

  property var shell: null
  property var manifest: null
  property bool opened: false

  property bool redTint: true
  property bool lowBrightness: true
  property bool caffeine: false

  property var currentTime: new Date()
  property var weatherData: ({})
  property string weatherError: ""

  function open(payload) {
    root.opened = true;
    refreshData();
  }

  function close() {
    root.opened = false;
  }

  function toggle() {
    root.opened ? root.close() : root.open("");
  }

  function dismiss() {
    root.close();
    if (root.shell && typeof root.shell.hide === "function") {
      root.shell.hide((root.manifest && root.manifest.id) || "lukedaduke.standby");
    }
  }

  function refreshData() {
    weatherProc.running = false;
    weatherProc.running = true;
  }

  function toggleCaffeine() {
    var path = Quickshell.env("HOME") + "/.local/state/omarchy/indicators/stay-awake";
    if (root.caffeine) {
      Quickshell.execDetached(["rm", "-f", path]);
    } else {
      Quickshell.execDetached(["bash", "-c", "mkdir -p ~/.local/state/omarchy/indicators && touch '" + path + "'"]);
    }
  }

  function toggleRedTint() { root.redTint = !root.redTint; }
  function toggleLowBrightness() { root.lowBrightness = !root.lowBrightness; }

  Timer {
    id: clockTimer
    interval: 1000
    repeat: true
    running: root.opened
    onTriggered: root.currentTime = new Date()
  }

  Timer {
    id: weatherTimer
    interval: 5 * 60 * 1000
    repeat: true
    running: root.opened
    onTriggered: root.refreshData()
  }

  FileView {
    id: caffeineFile
    path: Quickshell.env("HOME") + "/.local/state/omarchy/indicators/stay-awake"
    watchChanges: true
    printErrors: false
    onLoaded: root.caffeine = text().length > 0
    onLoadFailed: root.caffeine = false
    onFileChanged: root.caffeine = text().length > 0
  }

  Process {
    id: weatherProc
    command: [Quickshell.env("HOME") + "/.config/omarchy/plugins/lukedaduke.standby/bin/standby-data"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var raw = String(text || "").trim();
        if (!raw) {
          root.weatherError = "weather unavailable";
          return;
        }
        try {
          root.weatherData = JSON.parse(raw);
          root.weatherError = "";
        } catch (e) {
          root.weatherError = "weather parse error";
        }
      }
    }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "lukedaduke.standby"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    exclusionMode: ExclusionMode.Ignore

    onVisibleChanged: {
      if (visible) {
        root.refreshData();
        Qt.callLater(function() { keyCatcher.forceActiveFocus(); });
      }
    }

    Rectangle {
      anchors.fill: parent
      color: Color.background
    }

    Rectangle {
      anchors.fill: parent
      color: Color.urgent
      opacity: root.redTint ? 0.12 : 0
    }

    Rectangle {
      anchors.fill: parent
      color: "black"
      opacity: root.lowBrightness ? 0.55 : 0
    }

    MouseArea {
      anchors.fill: parent
      onClicked: root.dismiss()
    }

    Item {
      id: keyCatcher
      anchors.fill: parent
      focus: true

      Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Escape || event.key === Qt.Key_Q || event.key === Qt.Key_Space) {
          root.dismiss();
          event.accepted = true;
        } else if (event.key === Qt.Key_R) {
          root.toggleRedTint();
          event.accepted = true;
        } else if (event.key === Qt.Key_B) {
          root.toggleLowBrightness();
          event.accepted = true;
        } else if (event.key === Qt.Key_C) {
          root.toggleCaffeine();
          event.accepted = true;
        }
      }

      Item {
        anchors.fill: parent
        anchors.margins: Style.gapsOut * 4

        Grid {
          id: contentGrid
          anchors.centerIn: parent
          columns: panel.width > panel.height ? 2 : 1
          flow: Grid.LeftToRight
          verticalItemAlignment: Grid.AlignVCenter
          horizontalItemAlignment: Grid.AlignHCenter
          spacing: Style.gapsOut * 8

          Column {
            spacing: Style.gapsOut

            Text {
              id: timeText
              text: Qt.formatTime(root.currentTime, "h:mm")
              color: root.redTint ? Color.urgent : Color.foreground
              font.family: Style.font.family
              font.pixelSize: Math.min(panel.width, panel.height) / 3.5
              horizontalAlignment: Text.AlignHCenter
            }

            Text {
              text: Qt.formatTime(root.currentTime, "AP").toUpperCase()
              visible: text !== ""
              color: root.redTint ? Color.urgent : Color.foreground
              font.family: Style.font.family
              font.pixelSize: Math.min(panel.width, panel.height) / 10
              horizontalAlignment: Text.AlignHCenter
              anchors.horizontalCenter: parent.horizontalCenter
            }

            Text {
              text: Qt.formatDate(root.currentTime, "dddd, MMMM d")
              color: root.redTint ? Color.urgent : Color.foreground
              font.family: Style.font.family
              font.pixelSize: Math.min(panel.width, panel.height) / 18
              horizontalAlignment: Text.AlignHCenter
              anchors.horizontalCenter: parent.horizontalCenter
              opacity: 0.75
            }
          }

          Column {
            spacing: Style.gapsOut * 2
            visible: root.weatherData.temperature !== undefined || root.weatherError !== ""

            Text {
              text: root.weatherError ? root.weatherError : (root.weatherData.location || "")
              color: root.redTint ? Color.urgent : Color.foreground
              font.family: Style.font.family
              font.pixelSize: Math.min(panel.width, panel.height) / 24
              opacity: 0.6
              horizontalAlignment: Text.AlignLeft
            }

            Text {
              text: root.weatherData.description || ""
              color: root.redTint ? Color.urgent : Color.foreground
              font.family: Style.font.family
              font.pixelSize: Math.min(panel.width, panel.height) / 18
              horizontalAlignment: Text.AlignLeft
            }

            Text {
              text: root.weatherData.temperature ? root.weatherData.temperature : ""
              color: root.redTint ? Color.urgent : Color.foreground
              font.family: Style.font.family
              font.pixelSize: Math.min(panel.width, panel.height) / 10
              horizontalAlignment: Text.AlignLeft
            }

            Row {
              spacing: Style.gapsOut * 2
              Text {
                text: root.weatherData.high ? "H " + root.weatherData.high : ""
                color: root.redTint ? Color.urgent : Color.foreground
                font.family: Style.font.family
                font.pixelSize: Math.min(panel.width, panel.height) / 24
                opacity: 0.7
              }
              Text {
                text: root.weatherData.low ? "L " + root.weatherData.low : ""
                color: root.redTint ? Color.urgent : Color.foreground
                font.family: Style.font.family
                font.pixelSize: Math.min(panel.width, panel.height) / 24
                opacity: 0.7
              }
            }

            Row {
              spacing: Style.gapsOut * 2
              Text {
                text: root.weatherData.sunrise ? "↑ " + root.weatherData.sunrise : ""
                color: root.redTint ? Color.urgent : Color.foreground
                font.family: Style.font.family
                font.pixelSize: Math.min(panel.width, panel.height) / 24
                opacity: 0.7
              }
              Text {
                text: root.weatherData.sunset ? "↓ " + root.weatherData.sunset : ""
                color: root.redTint ? Color.urgent : Color.foreground
                font.family: Style.font.family
                font.pixelSize: Math.min(panel.width, panel.height) / 24
                opacity: 0.7
              }
            }

            Row {
              spacing: Style.gapsOut * 2
              Text {
                text: root.weatherData.humidity ? "Hum " + root.weatherData.humidity : ""
                visible: text !== ""
                color: root.redTint ? Color.urgent : Color.foreground
                font.family: Style.font.family
                font.pixelSize: Math.min(panel.width, panel.height) / 26
                opacity: 0.6
              }
              Text {
                text: root.weatherData.wind ? "Wind " + root.weatherData.wind : ""
                visible: text !== ""
                color: root.redTint ? Color.urgent : Color.foreground
                font.family: Style.font.family
                font.pixelSize: Math.min(panel.width, panel.height) / 26
                opacity: 0.6
              }
            }
          }
        }

        Row {
          anchors.bottom: parent.bottom
          anchors.horizontalCenter: parent.horizontalCenter
          spacing: Style.gapsOut * 3

          Text {
            text: "[R]ed " + (root.redTint ? "on" : "off")
            color: root.redTint ? Color.urgent : Color.foreground
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            opacity: 0.5

            MouseArea {
              anchors.fill: parent
              onClicked: root.toggleRedTint()
            }
          }

          Text {
            text: "[B]right " + (root.lowBrightness ? "low" : "high")
            color: Color.foreground
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            opacity: 0.5

            MouseArea {
              anchors.fill: parent
              onClicked: root.toggleLowBrightness()
            }
          }

          Text {
            text: "[C]affeine " + (root.caffeine ? "on" : "off")
            color: root.caffeine ? Color.urgent : Color.foreground
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            opacity: 0.5

            MouseArea {
              anchors.fill: parent
              onClicked: root.toggleCaffeine()
            }
          }
        }
      }
    }
  }
}
