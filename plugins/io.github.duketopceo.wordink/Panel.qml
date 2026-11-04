import QtQuick 6.11
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// WordInk bar widget. Talks only to the local `wordink` CLI (no network, no
// keys). State comes from following `wordink logs -f` (live.ndjson events);
// when WordInk is not running (CLI exit 3) or the follow ends, it polls
// `wordink status --json` every 5 s and restarts the follow on return.
// Left click toggles a dictation; right click / middle click opens the panel.
Panel {
  id: root
  moduleName: "io.github.duketopceo.wordink"
  ipcTarget: "io.github.duketopceo.wordink"

  readonly property string installLine:
    "curl -fsSL https://github.com/duketopceo/WordInk/releases/latest/download/install.sh | sh"

  property bool installed: true
  property bool running: false
  property bool known: false
  property string capState: "idle"      // idle | recording | transcribing
  property bool hasError: false
  property string errorText: ""
  property string modelName: ""
  property string engineText: ""
  property string micId: ""
  property var devices: []              // [{name, kind, id, isDefault}]
  property var recents: []              // [{id, text}]
  property var usage: ({})              // {words, cost}
  property string notice: ""

  // not-running | idle | recording | transcribing | error
  readonly property string visual: !installed || !running ? "off"
    : hasError ? "error" : capState

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.5)
  readonly property color urgent: Color.urgent
  readonly property color accent: Color.accent
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property string pluginRoot: {
    var p = Qt.resolvedUrl(".").toString()
    if (p.indexOf("file://") === 0) p = p.substring(7)
    if (p.length > 1 && p.charAt(p.length - 1) === "/") p = p.substring(0, p.length - 1)
    return p
  }
  readonly property string launcher: pluginRoot + "/bin/wordink-cli.sh"

  readonly property string glyph: {
    if (visual === "off") return String.fromCodePoint(0xF036D)        // mic-off
    if (visual === "transcribing") return String.fromCodePoint(0xF051F) // hourglass
    if (visual === "error") return String.fromCodePoint(0xF0026)      // alert
    return String.fromCodePoint(0xF036C)                              // mic
  }
  readonly property color glyphColor: visual === "off" ? dim
    : visual === "recording" || visual === "error" ? urgent
    : visual === "transcribing" ? accent : foreground
  readonly property string stateLabel: visual === "off"
    ? (installed ? "Not running" : "Not installed")
    : visual === "recording" ? "Recording"
    : visual === "transcribing" ? "Transcribing"
    : visual === "error" ? "Needs attention" : "Idle"

  function fillFor(c, alpha) { return Qt.rgba(c.r, c.g, c.b, alpha) }

  function cli(argv) { return ["/bin/sh", root.launcher].concat(argv) }

  function copy(text, label) {
    if (!text) return
    Quickshell.execDetached(["/usr/bin/wl-copy", "--", String(text)])
    root.say("Copied " + label)
  }

  function say(msg) { root.notice = msg; noticeTimer.restart() }

  function run(argv, label) {
    Quickshell.execDetached(root.cli(argv))
    if (label) root.say(label)
  }

  // ---- state ----
  function applyVoiceState(s) {
    if (s === "listening" || s === "dictating") root.capState = "recording"
    else if (s === "transcribing" || s === "stopping") root.capState = "transcribing"
    else root.capState = "idle"
  }

  function applyStatus(d) {
    if (!d || typeof d !== "object") return
    root.running = true
    root.known = true
    var cap = d.capture && typeof d.capture.state === "string" ? d.capture.state : "idle"
    root.capState = cap === "recording" ? "recording"
      : cap === "transcribing" ? "transcribing" : "idle"
    var m = d.model || {}
    root.modelName = typeof m.name === "string" ? m.name : ""
    var err = ""
    if (m.error) err = String(m.error)
    else if (d.model && m.installed === false) err = "Local model not installed"
    else if (d.permissions && d.permissions.ready === false) err = "Permissions missing"
    else if (d.listener && d.listener.status && d.listener.status !== "Enabled")
      err = "Listener: " + d.listener.status
    root.errorText = err
    root.hasError = err !== ""
  }

  function markNotRunning() {
    root.running = false
    root.known = true
    root.capState = "idle"
    root.hasError = false
  }

  function pollStatus() {
    if (statusProc.running) return
    statusProc.running = true
  }

  function startFollow() {
    if (followProc.running || !root.installed || !root.running) return
    followProc.running = true
  }

  function refreshPanel() {
    root.pollStatus()
    if (!root.installed || !root.running) return
    micProc.running = true
    devProc.running = true
    histProc.running = true
    usageProc.running = true
    engineProc.running = true
  }

  function pickMic(id) {
    if (!/^[A-Za-z0-9_.:@+-]+$/.test(id)) return
    root.micId = id
    root.run(["settings", "set", "microphone", id], "Microphone set")
  }

  function copyDiagnostics() {
    if (diagProc.running) return
    diagProc.running = true
  }

  onOpenedChanged: if (opened) root.refreshPanel()

  // Bounded output for everything below: reject anything unreasonably large.
  readonly property int maxText: 200000

  Process {
    id: statusProc
    command: root.cli(["status", "--json"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          if (text && text.length < root.maxText) root.applyStatus(JSON.parse(text))
        } catch (e) {}
      }
    }
    onExited: function (code) {
      if (code === 127) { root.installed = false; root.known = true; root.running = false }
      else if (code === 3) { root.installed = true; root.markNotRunning() }
      else if (code === 0) {
        root.installed = true
        root.startFollow()
      }
    }
  }

  Process {
    id: followProc
    command: root.cli(["logs", "-f", "-n", "0"])
    stdout: SplitParser {
      onRead: function (line) {
        if (line.length > 4000) return
        try {
          var ev = JSON.parse(line)
          if (ev.kind === "state" && typeof ev.state === "string") {
            root.applyVoiceState(ev.state)
            if (ev.state === "sleeping") root.pollStatus()
          } else if (ev.kind === "api_server_stopped") {
            root.pollStatus()
          } else if (ev.kind === "dictation" && ev.phase === "pasted" && root.opened) {
            histProc.running = true
          }
        } catch (e) {}
      }
    }
    // Follow ended (app quit, crash, CLI failure): fall back to polling.
    onExited: root.pollStatus()
  }

  Timer {
    id: pollTimer
    interval: 5000
    running: true
    repeat: true
    triggeredOnStart: true
    // Only needed while the event follow is not live.
    onTriggered: if (!followProc.running) root.pollStatus()
  }

  Timer { id: noticeTimer; interval: 3000; onTriggered: root.notice = "" }

  Process {
    id: micProc
    command: root.cli(["settings", "get", "microphone"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 1000) root.micId = text.trim()
    }
  }

  Process {
    id: engineProc
    command: root.cli(["settings", "get", "engine"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 1000) root.engineText = text.trim()
    }
  }

  Process {
    id: devProc
    command: root.cli(["devices"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (!text || text.length > root.maxText) return
        var out = []
        var lines = text.split("\n")
        for (var i = 0; i < lines.length && out.length < 20; i++) {
          var f = lines[i].split("\t")
          if (f.length < 3 || f[2] === "") continue
          out.push({ "name": f[0], "kind": f[1], "id": f[2], "isDefault": f[3] === "default" })
        }
        root.devices = out
      }
    }
  }

  Process {
    id: histProc
    command: root.cli(["history", "--limit", "3", "--json"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          if (!text || text.length > root.maxText) return
          var d = JSON.parse(text)
          var out = []
          var es = d.entries || []
          for (var i = 0; i < es.length && out.length < 3; i++)
            out.push({ "id": es[i].id, "text": String(es[i].final_text || "") })
          root.recents = out
        } catch (e) {}
      }
    }
  }

  Process {
    id: usageProc
    command: root.cli(["usage", "--window", "week", "--json"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          if (!text || text.length > root.maxText) return
          var d = JSON.parse(text)
          var t = d.totals || {}
          var eng = (d.dictation_engines && d.dictation_engines.length > 0) ? d.dictation_engines[0] : null
          root.usage = {
            "words": t.words || 0,
            "cost": t.cost_usd || 0,
            "engine": eng ? (eng.provider + " · " + eng.model) : ""
          }
        } catch (e) {}
      }
    }
  }

  Process {
    id: diagProc
    command: root.cli(["diagnostics"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (text && text.length < root.maxText) root.copy(text, "diagnostics")
        else root.say("Diagnostics unavailable")
      }
    }
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.glyph
    tooltipText: "WordInk · " + root.stateLabel
      + (root.hasError && root.errorText ? "\n" + root.errorText : "")
      + "\nclick: dictate · right-click: panel"
    active: root.visual === "recording" || root.visual === "transcribing" || root.visual === "error"
    activeColor: root.glyphColor
    foreground: root.glyphColor
    onPressed: function (b) {
      if (b === Qt.RightButton || b === Qt.MiddleButton) {
        root.refreshPanel()
        root.toggle()
      } else if (!root.installed) {
        root.toggle()
      } else if (!root.running) {
        // WordInk is not running: start it (control commands never launch it).
        root.run(["app", "--hidden"])
        root.pollStatus()
      } else {
        root.run(["dictation", "toggle"])
      }
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: panel.fittedContentWidth(Style.space(380), 420)
    contentHeight: panel.fittedContentHeight(mainColumn.implicitHeight, 620)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()

      Column {
        id: mainColumn
        width: parent.width
        spacing: Style.space(10)

        // ---- header ----
        Row {
          width: parent.width
          spacing: Style.space(10)
          Rectangle {
            id: iconTile
            width: Style.space(34); height: Style.space(34)
            radius: Style.cornerRadius
            color: root.fillFor(root.glyphColor, 0.12)
            anchors.verticalCenter: parent.verticalCenter
            Text {
              anchors.centerIn: parent
              text: root.glyph; textFormat: Text.PlainText
              color: root.glyphColor
              font.family: root.fontFamily; font.pixelSize: Style.font.iconLarge
            }
          }
          Column {
            width: parent.width - iconTile.width - statePill.width - parent.spacing * 2
            spacing: Style.space(2)
            anchors.verticalCenter: parent.verticalCenter
            Text {
              text: "WORDINK"; textFormat: Text.PlainText
              color: root.foreground
              font.family: root.fontFamily; font.pixelSize: Style.font.subtitle; font.bold: true
            }
            Text {
              width: parent.width
              text: root.installed
                ? (root.running ? "click the icon to dictate" : "WordInk is not running")
                : "WordInk is not installed"
              textFormat: Text.PlainText; color: root.dim
              font.family: root.fontFamily; font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }
          }
          Rectangle {
            id: statePill
            height: Style.space(22)
            width: pillText.implicitWidth + Style.space(16)
            radius: height / 2
            color: root.fillFor(root.glyphColor, 0.15)
            border.color: root.fillFor(root.glyphColor, 0.4)
            anchors.verticalCenter: parent.verticalCenter
            Text {
              id: pillText
              anchors.centerIn: parent
              text: root.stateLabel.toUpperCase(); textFormat: Text.PlainText
              color: root.glyphColor
              font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true
            }
          }
        }

        // ---- not installed ----
        Column {
          width: parent.width
          visible: !root.installed
          spacing: Style.space(6)
          Text {
            width: parent.width
            text: "Install WordInk, then reopen this panel:"
            textFormat: Text.PlainText; color: root.foreground
            font.family: root.fontFamily; font.pixelSize: Style.font.body
            wrapMode: Text.WordWrap
          }
          Rectangle {
            width: parent.width
            height: installText.implicitHeight + Style.space(16)
            radius: Style.cornerRadius
            color: root.fillFor(root.foreground, 0.06)
            Text {
              id: installText
              x: Style.space(8); y: Style.space(8)
              width: parent.width - Style.space(16)
              text: root.installLine; textFormat: Text.PlainText
              color: root.foreground; wrapMode: Text.WrapAnywhere
              font.family: root.fontFamily; font.pixelSize: Style.font.caption
            }
            MouseArea {
              anchors.fill: parent; cursorShape: Qt.PointingHandCursor
              onClicked: root.copy(root.installLine, "install command")
            }
          }
          Text {
            text: "click the command to copy it"
            textFormat: Text.PlainText; color: root.dim
            font.family: root.fontFamily; font.pixelSize: Style.font.caption
          }
        }

        // ---- error ----
        Text {
          width: parent.width
          visible: root.installed && root.running && root.hasError
          text: "! " + root.errorText
          textFormat: Text.PlainText; color: root.urgent
          font.family: root.fontFamily; font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }

        // ---- engine ----
        PanelSectionHeader {
          visible: root.installed && root.running
          text: "ENGINE"
          foreground: root.foreground; fontFamily: root.fontFamily
        }
        Column {
          width: parent.width
          visible: root.installed && root.running
          spacing: Style.space(2)
          Text {
            width: parent.width
            text: "Engine: " + (root.engineText || "auto")
              + (root.usage.engine ? "  (" + root.usage.engine + ")" : "")
            textFormat: Text.PlainText; color: root.foreground
            font.family: root.fontFamily; font.pixelSize: Style.font.body
            elide: Text.ElideRight
          }
          Text {
            width: parent.width
            text: "Local model: " + (root.modelName || "none")
            textFormat: Text.PlainText; color: root.dim
            font.family: root.fontFamily; font.pixelSize: Style.font.caption
            elide: Text.ElideRight
          }
        }

        // ---- microphone ----
        PanelSectionHeader {
          visible: root.installed && root.running && root.devices.length > 0
          text: "MICROPHONE"
          foreground: root.foreground; fontFamily: root.fontFamily
        }
        Column {
          width: parent.width
          visible: root.installed && root.running
          spacing: Style.space(2)
          Repeater {
            model: root.devices
            delegate: Rectangle {
              readonly property bool selected: modelData.id === root.micId
                || (root.micId === "" && modelData.isDefault)
              width: parent.width; height: Style.space(30)
              radius: Style.cornerRadius
              color: selected ? root.fillFor(root.accent, 0.12)
                : micMouse.containsMouse ? root.fillFor(root.accent, 0.08)
                : root.fillFor(root.foreground, 0.04)
              border.color: selected ? root.fillFor(root.accent, 0.4) : "transparent"
              Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left; anchors.leftMargin: Style.space(10)
                anchors.right: kindText.left; anchors.rightMargin: Style.space(8)
                text: modelData.name + (modelData.isDefault ? " (default)" : "")
                textFormat: Text.PlainText
                color: selected ? root.accent : root.foreground
                font.family: root.fontFamily; font.pixelSize: Style.font.body
                elide: Text.ElideRight
              }
              Text {
                id: kindText
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right; anchors.rightMargin: Style.space(10)
                text: modelData.kind; textFormat: Text.PlainText
                color: root.dim
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
              }
              MouseArea {
                id: micMouse; anchors.fill: parent; hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.pickMic(modelData.id)
              }
            }
          }
        }

        // ---- recent dictations ----
        PanelSectionHeader {
          visible: root.installed && root.running && root.recents.length > 0
          text: "RECENT"
          foreground: root.foreground; fontFamily: root.fontFamily
        }
        Column {
          width: parent.width
          visible: root.installed && root.running
          spacing: Style.space(2)
          Repeater {
            model: root.recents
            delegate: Rectangle {
              width: parent.width
              height: Math.max(Style.space(30), recentText.implicitHeight + Style.space(12))
              radius: Style.cornerRadius
              color: root.fillFor(root.foreground, 0.04)
              Text {
                id: recentText
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left; anchors.leftMargin: Style.space(10)
                anchors.right: copyPill.left; anchors.rightMargin: Style.space(8)
                text: modelData.text; textFormat: Text.PlainText
                color: root.foreground; maximumLineCount: 2
                wrapMode: Text.WordWrap; elide: Text.ElideRight
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
              }
              Rectangle {
                id: copyPill
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right; anchors.rightMargin: Style.space(6)
                height: Style.space(22)
                width: copyLabel.implicitWidth + Style.space(14)
                radius: height / 2
                color: copyMouse.containsMouse ? root.fillFor(root.accent, 0.18) : root.fillFor(root.accent, 0.08)
                Text {
                  id: copyLabel; anchors.centerIn: parent
                  text: "Copy"; textFormat: Text.PlainText; color: root.accent
                  font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true
                }
                MouseArea {
                  id: copyMouse; anchors.fill: parent; hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.copy(modelData.text, "dictation")
                }
              }
            }
          }
        }

        // ---- usage ----
        Row {
          width: parent.width
          visible: root.installed && root.running && root.usage.words !== undefined
          Text {
            width: parent.width
            text: "This week: " + (root.usage.words || 0) + " words · $"
              + (root.usage.cost || 0).toFixed(4)
            textFormat: Text.PlainText; color: root.dim
            font.family: root.fontFamily; font.pixelSize: Style.font.caption
          }
        }

        // ---- actions ----
        Row {
          width: parent.width
          visible: root.installed
          spacing: Style.space(6)
          Repeater {
            model: [
              { "label": "Open WordInk", "act": "open" },
              { "label": "Settings", "act": "settings" },
              { "label": "Copy diagnostics", "act": "diag" }
            ]
            delegate: Rectangle {
              width: (parent.width - parent.spacing * 2) / 3
              height: Style.space(30)
              radius: Style.cornerRadius
              color: actMouse.containsMouse ? root.fillFor(root.accent, 0.14) : root.fillFor(root.accent, 0.06)
              border.color: root.fillFor(root.accent, 0.3)
              Text {
                anchors.centerIn: parent
                width: parent.width - Style.space(8)
                horizontalAlignment: Text.AlignHCenter
                text: modelData.label; textFormat: Text.PlainText
                color: root.accent; elide: Text.ElideRight
                font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true
              }
              MouseArea {
                id: actMouse; anchors.fill: parent; hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                  if (modelData.act === "open") root.run(["app"])
                  else if (modelData.act === "settings") root.run(["window", "show", "settings"])
                  else root.copyDiagnostics()
                }
              }
            }
          }
        }

        Text {
          width: parent.width
          visible: root.notice !== ""
          text: root.notice; textFormat: Text.PlainText
          color: root.dim
          font.family: root.fontFamily; font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }
      }
    }
  }
}
