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
    refreshWeather();
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

  function refreshWeather() {
    weatherProc.running = false;
    weatherProc.running = true;
    weatherDeadline.restart();
  }

  // Absolute tool paths and no shell: a PATH-preceding shadow binary or a
  // hostile HOME must never reach a shell or run inside this long-lived
  // process.
  readonly property string py: "/usr/bin/python3"
  readonly property string pluginRoot: {
    var p = Qt.resolvedUrl(".").toString()
    if (p.indexOf("file://") === 0)
      p = p.substring(7)
    if (p.length > 1 && p.charAt(p.length - 1) === "/")
      p = p.substring(0, p.length - 1)
    return p
  }
  readonly property var procEnv: ({
    "PATH": "/usr/bin:/bin",
    "HOME": null,
    "XDG_RUNTIME_DIR": null,
    "LANG": null,
    "LC_ALL": "C"
  })

  function toggleCaffeine() {
    if (root.caffeine) {
      Quickshell.execDetached([root.py, "-c",
        "import os,pathlib; p=pathlib.Path.home()/'.local/state/omarchy/indicators/stay-awake'; p.unlink(missing_ok=True)"]);
    } else {
      Quickshell.execDetached([root.py, "-c",
        "import os,pathlib; d=pathlib.Path.home()/'.local/state/omarchy/indicators'; d.mkdir(parents=True,exist_ok=True); (d/'stay-awake').touch(exist_ok=True)"]);
    }
  }

  function toggleRedTint() { root.redTint = !root.redTint; }
  function toggleLowBrightness() { root.lowBrightness = !root.lowBrightness; }

  readonly property color textColor: root.redTint
    ? Qt.tint(Color.foreground, Qt.rgba(Color.urgent.r, Color.urgent.g, Color.urgent.b, 0.10))
    : Color.foreground
  property real contentOpacity: root.lowBrightness ? 0.05 : 1.0

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
    onTriggered: root.refreshWeather()
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
    command: [root.py, root.pluginRoot + "/bin/standby-data"]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        weatherDeadline.stop();
        var raw = String(text || "").trim();
        if (!raw) {
          root.weatherError = "weather unavailable";
          return;
        }
        if (raw.length > 200000) {
          root.weatherError = "oversized weather payload";
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
    onExited: weatherDeadline.stop()
  }

  // Hard whole-job deadline: the weather fetch is killed and reaped rather
  // than left running indefinitely.
  Timer {
    id: weatherDeadline
    interval: 20000
    onTriggered: {
      if (weatherProc.running) {
        weatherProc.signal(9);
        root.weatherError = "weather timeout";
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
        root.refreshWeather();
        Qt.callLater(function() { keyCatcher.forceActiveFocus(); });
      }
    }

    Rectangle {
      anchors.fill: parent
      color: "black"
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
        anchors.margins: Style.gapsOut * 3

        Grid {
          id: contentGrid
          anchors.centerIn: parent
          columns: panel.width > panel.height ? 2 : 1
          flow: Grid.LeftToRight
          verticalItemAlignment: Grid.AlignVCenter
          horizontalItemAlignment: Grid.AlignHCenter
          spacing: Style.gapsOut * 6
          opacity: root.contentOpacity

          Column {
            id: clockColumn
            spacing: Style.gapsOut

            Text {
              id: timeText
              text: Qt.formatTime(root.currentTime, "h:mm")
              color: root.textColor
              font.family: Style.font.family
textFormat: Text.PlainText
              font.pixelSize: Math.min(panel.width, panel.height) / 3.5
              horizontalAlignment: Text.AlignHCenter
            }

            Text {
              text: Qt.formatTime(root.currentTime, "AP").toUpperCase()
              visible: text !== ""
              color: root.textColor
              font.family: Style.font.family
textFormat: Text.PlainText
              font.pixelSize: Math.min(panel.width, panel.height) / 10
              horizontalAlignment: Text.AlignHCenter
              anchors.horizontalCenter: parent.horizontalCenter
              opacity: 0.8
            }

            Text {
              text: Qt.formatDate(root.currentTime, "dddd, MMMM d")
              color: root.textColor
              font.family: Style.font.family
textFormat: Text.PlainText
              font.pixelSize: Math.min(panel.width, panel.height) / 18
              horizontalAlignment: Text.AlignHCenter
              anchors.horizontalCenter: parent.horizontalCenter
              opacity: 0.6
            }
          }

          Column {
            spacing: Style.gapsOut * 2
            visible: root.weatherData.temperature !== undefined || root.weatherError !== ""

            Text {
              text: root.weatherError ? root.weatherError : (root.weatherData.location || "")
              color: root.textColor
              font.family: Style.font.family
textFormat: Text.PlainText
              font.pixelSize: Math.min(panel.width, panel.height) / 24
              opacity: 0.5
              horizontalAlignment: Text.AlignLeft
            }

            Text {
              text: root.weatherData.description || ""
              color: root.textColor
              font.family: Style.font.family
textFormat: Text.PlainText
              font.pixelSize: Math.min(panel.width, panel.height) / 18
              horizontalAlignment: Text.AlignLeft
            }

            Text {
              text: root.weatherData.temperature ? root.weatherData.temperature : ""
              color: root.textColor
              font.family: Style.font.family
textFormat: Text.PlainText
              font.pixelSize: Math.min(panel.width, panel.height) / 10
              horizontalAlignment: Text.AlignLeft
            }

            Row {
              spacing: Style.gapsOut * 2
              Text {
                text: root.weatherData.high ? "H " + root.weatherData.high : ""
                color: root.textColor
                font.family: Style.font.family
textFormat: Text.PlainText
                font.pixelSize: Math.min(panel.width, panel.height) / 24
                opacity: 0.7
              }
              Text {
                text: root.weatherData.low ? "L " + root.weatherData.low : ""
                color: root.textColor
                font.family: Style.font.family
textFormat: Text.PlainText
                font.pixelSize: Math.min(panel.width, panel.height) / 24
                opacity: 0.7
              }
            }

            Row {
              spacing: Style.gapsOut * 2
              Text {
                text: root.weatherData.sunrise ? "↑ " + root.weatherData.sunrise : ""
                color: root.textColor
                font.family: Style.font.family
textFormat: Text.PlainText
                font.pixelSize: Math.min(panel.width, panel.height) / 24
                opacity: 0.7
              }
              Text {
                text: root.weatherData.sunset ? "↓ " + root.weatherData.sunset : ""
                color: root.textColor
                font.family: Style.font.family
textFormat: Text.PlainText
                font.pixelSize: Math.min(panel.width, panel.height) / 24
                opacity: 0.7
              }
            }

            Row {
              spacing: Style.gapsOut * 2
              Text {
                text: root.weatherData.humidity ? "Hum " + root.weatherData.humidity : ""
                visible: text !== ""
                color: root.textColor
                font.family: Style.font.family
textFormat: Text.PlainText
                font.pixelSize: Math.min(panel.width, panel.height) / 26
                opacity: 0.55
              }
              Text {
                text: root.weatherData.wind ? "Wind " + root.weatherData.wind : ""
                visible: text !== ""
                color: root.textColor
                font.family: Style.font.family
textFormat: Text.PlainText
                font.pixelSize: Math.min(panel.width, panel.height) / 26
                opacity: 0.55
              }
            }
          }

        }

        Row {
          anchors.bottom: parent.bottom
          anchors.horizontalCenter: parent.horizontalCenter
          spacing: Style.gapsOut * 3
          opacity: root.lowBrightness ? 0.12 : 0.55

          Text {
            text: "[R]ed " + (root.redTint ? "on" : "off")
            color: root.textColor
            font.family: Style.font.family
textFormat: Text.PlainText
            font.pixelSize: Style.font.body
            opacity: 0.45

            MouseArea {
              anchors.fill: parent
              onClicked: root.toggleRedTint()
            }
          }

          Text {
            text: "[B]right " + (root.lowBrightness ? "low" : "high")
            color: root.textColor
            font.family: Style.font.family
textFormat: Text.PlainText
            font.pixelSize: Style.font.body
            opacity: 0.45

            MouseArea {
              anchors.fill: parent
              onClicked: root.toggleLowBrightness()
            }
          }

          Text {
            text: "[C]affeine " + (root.caffeine ? "on" : "off")
            color: root.caffeine ? Color.urgent : root.textColor
            font.family: Style.font.family
textFormat: Text.PlainText
            font.pixelSize: Style.font.body
            opacity: 0.45

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
