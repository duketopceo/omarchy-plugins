import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import "Stocks.js" as Stocks
import "Settings.js" as Settings

// Stocks tab of the expanded panel (about 428x164 usable). A scrollable grid
// of small cards (symbol, price, change, sparkline) over one larger chart for
// the selected symbol. Data comes from the `series` block of
// ~/.cache/omarchy/notch.json (bin/notch-data); the tab writes the ranges it
// needs to notch-data's request file and runs it. Settings live under
// `stocks.*` in the notch's shell.json entry (a gear popover edits them).
Item {
  id: tab

  property var notch: null

  readonly property color textColor: notch ? notch.textColor : Commons.Color.foreground
  readonly property color dimColor: notch ? notch.dimColor : Commons.Color.muted
  readonly property string family: notch ? notch.fontFamily : Commons.Style.font.family
  readonly property string pluginDir: notch ? notch.pluginDir : ""
  readonly property string pluginId: notch && notch.pluginId ? notch.pluginId : "io.github.duketopceo.notch"

  implicitWidth: 608
  implicitHeight: 286

  // ---------------------------------------------------------------- state
  property var cache: null              // parsed notch.json
  property string financeText: ""
  property var pending: ({})            // stocks.* values just set from the UI
  property string rangeOverride: ""     // chip choice this session
  property string pickedSymbol: ""
  property bool popoverOpen: false
  property var usedRanges: []

  readonly property var entry: notch ? Settings.pluginEntry(notch.shellConfig, pluginId) : null
  readonly property var cfg: Stocks.settings(entry, pending, financeText)
  readonly property var symbols: cfg.watchlist
  readonly property string range: rangeOverride !== "" ? rangeOverride : cfg.range
  readonly property string style: cfg.style
  readonly property string selected: symbols.indexOf(pickedSymbol) >= 0 ? pickedSymbol : (symbols.length ? symbols[0] : "")
  readonly property var selSeries: Stocks.parseSeries(cache, selected, range)
  readonly property var selChange: Stocks.seriesChange(selSeries, range)
  // Up/down tones follow the notch theme (Stocks.js COLORS stays the
  // standalone fallback); flat keeps the neutral grey.
  readonly property color upTone: notch && notch.themeObj ? notch.themeObj.good : Stocks.COLORS.up
  readonly property color downTone: notch && notch.themeObj ? notch.themeObj.bad : Stocks.COLORS.down
  function toneFor(pct) {
    var d = Stocks.direction(pct)
    return d === "up" ? upTone : (d === "down" ? downTone : Stocks.COLORS.flat)
  }
  readonly property color selTone: selChange ? toneFor(selChange.percent) : Stocks.COLORS.flat

  function put(key, value) {
    var copy = {}
    for (var k in pending) copy[k] = pending[k]
    copy[key] = value
    pending = copy
    if (notch) notch.setSetting(key, value)
  }
  function quoteFor(sym) {
    var items = cache && cache.quotes && Array.isArray(cache.quotes.items) ? cache.quotes.items : []
    for (var i = 0; i < items.length; i++) if (items[i].symbol === sym) return items[i]
    return null
  }

  // ---------------------------------------------------------------- data
  readonly property string cacheDir: (Quickshell.env("XDG_CACHE_HOME") || (Quickshell.env("HOME") + "/.cache")) + "/omarchy"

  FileView {
    path: tab.cacheDir + "/notch.json"
    watchChanges: true
    printErrors: false
    onLoaded: { try { tab.cache = JSON.parse(text()) } catch (e) { tab.cache = null } }
    onFileChanged: reload()
  }
  FileView {
    path: Quickshell.env("HOME") + "/.local/state/omarchy/settings/finance.json"
    printErrors: false
    onLoaded: tab.financeText = text()
  }

  property bool refetch: false
  Process {
    id: fetcher
    onExited: if (tab.refetch) { tab.refetch = false; tab.fetchNow() }
  }
  // Tell notch-data which ranges are in use, then run it (it rate-limits itself).
  function fetchNow() {
    if (pluginDir === "") return
    if (fetcher.running) { refetch = true; return }
    var ranges = usedRanges.slice()
    if (ranges.indexOf(range) < 0) ranges.push(range)
    usedRanges = ranges
    var req = Stocks.requestJson(ranges, Date.now() / 1000)
    fetcher.command = ["sh", "-c", 'mkdir -p "$3" && printf %s "$1" > "$3/notch-stocks-request.json" && exec "$2" --max-age 900', "sh", req, pluginDir + "/bin/notch-data", cacheDir]
    fetcher.running = true
  }
  Timer {
    interval: 5 * 60 * 1000
    repeat: true
    running: tab.visible
    onTriggered: tab.fetchNow()
  }
  onVisibleChanged: if (visible) fetchNow()
  Component.onCompleted: if (visible) fetchNow()
  onRangeChanged: fetchNow()

  function setRange(k) { rangeOverride = k }

  // ---------------------------------------------------------------- pieces
  component Pill: Rectangle {
    id: pill
    property string label: ""
    property bool on: false
    property bool mono: true
    property int pad: 9
    signal clicked()
    implicitWidth: pillText.implicitWidth + pad * 2
    implicitHeight: 18
    radius: 9
    color: on ? Qt.rgba(1, 1, 1, 0.16) : (pillHit.containsMouse ? Qt.rgba(1, 1, 1, 0.09) : Qt.rgba(1, 1, 1, 0.04))
    Text {
      id: pillText
      anchors.centerIn: parent
      textFormat: Text.PlainText
      text: pill.label
      color: pill.on ? tab.textColor : tab.dimColor
      font.family: tab.family
      font.pixelSize: 9
      font.weight: pill.on ? Font.DemiBold : Font.Normal
    }
    MouseArea {
      id: pillHit
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: pill.clicked()
    }
  }

  // ---------------------------------------------------------------- cards
  readonly property int cardH: 34
  readonly property int cardGap: 4
  readonly property int cols: cfg.cards <= 4 ? 2 : 3
  readonly property int cardW: Math.floor((width - (cols - 1) * cardGap) / cols)
  readonly property int pitch: cardH + cardGap
  readonly property int visibleRows: 3
  readonly property int rows: Stocks.gridRows(symbols.length, cols)
  readonly property int cardsHeight: visibleRows * pitch - cardGap
  property real scrollY: 0
  onRowsChanged: scrollY = Stocks.scrollTarget(scrollY, 0, pitch, rows, cardsHeight)
  onColsChanged: scrollY = 0

  Item {
    id: cardsView
    anchors.top: parent.top
    anchors.left: parent.left
    anchors.right: parent.right
    height: tab.cardsHeight
    clip: true

    Item {
      id: cardsContent
      width: parent.width
      height: tab.rows * tab.pitch
      y: -tab.scrollY
      Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

      Repeater {
        model: tab.symbols
        delegate: Rectangle {
          id: card
          required property var modelData
          required property int index
          readonly property string sym: modelData
          readonly property var series: Stocks.parseSeries(tab.cache, sym, tab.range)
          readonly property var chg: Stocks.seriesChange(series, tab.range)
          readonly property var quote: tab.quoteFor(sym)
          // Cards show TODAY's move (vs the previous close): the quote's
          // changePercent, else the 1D series against its previous close. The
          // selected range's change lives only in the chart header.
          readonly property var daySeries: tab.range === "1D" ? series : Stocks.parseSeries(tab.cache, sym, "1D")
          readonly property var dayChg: Stocks.seriesChange(daySeries, "1D")
          readonly property real price: quote && isFinite(Number(quote.price)) ? Number(quote.price) : (chg ? chg.last : NaN)
          readonly property real pct: Stocks.todayPercent(quote, dayChg)
          readonly property color tone: tab.toneFor(pct)
          readonly property bool isSel: sym === tab.selected
          x: (index % tab.cols) * (tab.cardW + tab.cardGap)
          y: Math.floor(index / tab.cols) * tab.pitch
          width: tab.cardW
          height: tab.cardH
          radius: 8
          color: isSel ? Qt.rgba(1, 1, 1, 0.09) : (cardHit.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(1, 1, 1, 0.035))
          border.width: 1
          border.color: isSel ? Qt.rgba(tone.r, tone.g, tone.b, 0.55) : Qt.rgba(1, 1, 1, 0.05)

          Column {
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            spacing: 0
            Text {
              textFormat: Text.PlainText
              text: card.sym
              color: tab.textColor
              font.family: tab.family
              font.pixelSize: 10
              font.weight: Font.DemiBold
            }
            Row {
              spacing: 5
              Text {
                textFormat: Text.PlainText
                text: Stocks.formatPrice(card.price)
                color: tab.textColor
                font.family: tab.family
                font.pixelSize: 9
                font.features: ({ "tnum": 1 })
              }
              Text {
                textFormat: Text.PlainText
                text: Stocks.formatChange(card.pct)
                color: card.tone
                font.family: tab.family
                font.pixelSize: 9
                font.features: ({ "tnum": 1 })
              }
            }
          }
          SparkChart {
            anchors.right: parent.right
            anchors.rightMargin: 6
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(24, parent.width * 0.32)
            height: parent.height - 12
            tone: card.tone
            values: card.series ? Stocks.sparkValues(card.series.points, 40) : []
          }
          MouseArea {
            id: cardHit
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: tab.pickedSymbol = card.sym
          }
        }
      }
    }

    // Wheel scrolls the grid, about 3 rows per notch, eased by the Behavior.
    MouseArea {
      anchors.fill: parent
      acceptedButtons: Qt.NoButton
      onWheel: function (w) { tab.scrollY = Stocks.scrollTarget(tab.scrollY, w.angleDelta.y, tab.pitch, tab.rows, tab.cardsHeight) }
    }
  }

  // ---------------------------------------------------------------- selected chart
  Item {
    id: detail
    anchors.top: cardsView.bottom
    anchors.topMargin: 6
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom

    Item {
      id: bar
      anchors.top: parent.top
      anchors.left: parent.left
      anchors.right: parent.right
      height: 18

      Row {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        spacing: 6
        Text {
          textFormat: Text.PlainText
          text: tab.selected !== "" ? tab.selected : "No symbols"
          color: tab.textColor
          font.family: tab.family
          font.pixelSize: 12
          font.weight: Font.DemiBold
          anchors.verticalCenter: parent.verticalCenter
        }
        Text {
          textFormat: Text.PlainText
          visible: tab.selChange !== null
          text: tab.selChange ? Stocks.formatPrice(tab.selChange.last) : ""
          color: tab.textColor
          font.family: tab.family
          font.pixelSize: 11
          font.features: ({ "tnum": 1 })
          anchors.verticalCenter: parent.verticalCenter
        }
        Text {
          textFormat: Text.PlainText
          visible: tab.selChange !== null
          text: tab.selChange ? Stocks.formatDelta(tab.selChange.value) + "  " + Stocks.formatChange(tab.selChange.percent) : ""
          color: tab.selTone
          font.family: tab.family
          font.pixelSize: 9
          font.features: ({ "tnum": 1 })
          anchors.verticalCenter: parent.verticalCenter
        }
      }

      Row {
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        Repeater {
          model: Stocks.RANGES
          delegate: Pill {
            required property var modelData
            label: modelData.label
            on: modelData.key === tab.range
            pad: 6
            onClicked: tab.setRange(modelData.key)
          }
        }
        Item { width: 4; height: 1 }
        Pill {
          label: tab.style === "candle" ? "Candle" : "Line"
          pad: 7
          onClicked: tab.put("stocks.style", tab.style === "candle" ? "line" : "candle")
        }
        Pill {
          label: "⚙"
          on: tab.popoverOpen
          pad: 6
          onClicked: tab.popoverOpen = !tab.popoverOpen
        }
      }
    }

    CandleChart {
      id: big
      anchors.top: bar.bottom
      anchors.topMargin: 2
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      points: tab.selSeries ? tab.selSeries.points : []
      prev: tab.selSeries && tab.selSeries.prev !== null ? tab.selSeries.prev : NaN
      range: tab.range
      style: tab.style
      tone: tab.selTone
      textColor: tab.textColor
      dimColor: tab.dimColor
      family: tab.family
    }

    Text {
      textFormat: Text.PlainText
      anchors.centerIn: big
      visible: tab.selected !== "" && tab.selSeries === null
      text: "Fetching " + tab.selected + " " + tab.range + "…"
      color: tab.dimColor
      font.family: tab.family
      font.pixelSize: 10
    }
  }

  // ---------------------------------------------------------------- settings popover
  Rectangle {
    id: pop
    visible: tab.popoverOpen
    anchors.fill: parent
    z: 10
    radius: 10
    color: Qt.rgba(0.05, 0.05, 0.06, 0.985)
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.10)

    MouseArea { anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.AllButtons; onWheel: function (w) { w.accepted = true } }

    // Left: watchlist
    Column {
      anchors.left: parent.left
      anchors.top: parent.top
      anchors.margins: 10
      width: parent.width * 0.5 - 14
      spacing: 5

      Text {
        textFormat: Text.PlainText
        text: "Watchlist"
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: 9
      }
      Flow {
        width: parent.width
        spacing: 4
        Repeater {
          model: tab.symbols
          delegate: Rectangle {
            id: sym
            required property var modelData
            implicitWidth: symText.implicitWidth + 24
            implicitHeight: 18
            width: implicitWidth
            height: implicitHeight
            radius: 9
            color: Qt.rgba(1, 1, 1, 0.07)
            Text {
              id: symText
              anchors.left: parent.left
              anchors.leftMargin: 8
              anchors.verticalCenter: parent.verticalCenter
              textFormat: Text.PlainText
              text: sym.modelData
              color: tab.textColor
              font.family: tab.family
              font.pixelSize: 9
            }
            Text {
              anchors.right: parent.right
              anchors.rightMargin: 6
              anchors.verticalCenter: parent.verticalCenter
              textFormat: Text.PlainText
              text: "×"
              color: rm.containsMouse ? Stocks.COLORS.down : tab.dimColor
              font.family: tab.family
              font.pixelSize: 11
              MouseArea {
                id: rm
                anchors.fill: parent
                anchors.margins: -4
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: tab.put("stocks.watchlist", Stocks.removeSymbol(tab.symbols, sym.modelData))
              }
            }
          }
        }
      }
      Row {
        spacing: 4
        Rectangle {
          width: 84; height: 20; radius: 10
          color: Qt.rgba(1, 1, 1, 0.07)
          border.width: addInput.activeFocus ? 1 : 0
          border.color: Qt.rgba(1, 1, 1, 0.3)
          TextInput {
            id: addInput
            anchors.fill: parent
            anchors.leftMargin: 9
            anchors.rightMargin: 9
            verticalAlignment: TextInput.AlignVCenter
            color: tab.textColor
            font.family: tab.family
            font.pixelSize: 10
            maximumLength: 12
            clip: true
            onAccepted: { tab.put("stocks.watchlist", Stocks.addSymbol(tab.symbols, text)); text = "" }
            Text {
              textFormat: Text.PlainText
              visible: addInput.text === "" && !addInput.activeFocus
              anchors.verticalCenter: parent.verticalCenter
              text: "add symbol"
              color: tab.dimColor
              font.family: tab.family
              font.pixelSize: 9
            }
            MouseArea { anchors.fill: parent; onPressed: function (m) { addInput.forceActiveFocus(); m.accepted = false } }
          }
        }
        Pill {
          label: "Add"
          onClicked: { tab.put("stocks.watchlist", Stocks.addSymbol(tab.symbols, addInput.text)); addInput.text = "" }
        }
      }
      Row {
        spacing: 4
        Repeater {
          model: ["QQQ", "GLD", "BTC-USD", "MSFT"].filter(function (s) { return tab.symbols.indexOf(s) < 0 }).slice(0, 3)
          delegate: Pill {
            required property var modelData
            label: "+ " + modelData
            onClicked: tab.put("stocks.watchlist", Stocks.addSymbol(tab.symbols, modelData))
          }
        }
      }
    }

    // Right: settings
    Column {
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: 10
      anchors.rightMargin: 34
      width: parent.width * 0.5 - 14
      spacing: 7

      component Row2: Item {
        id: r2
        property string label: ""
        default property alias content: slot.data
        width: parent.width
        height: 20
        Text {
          textFormat: Text.PlainText
          anchors.verticalCenter: parent.verticalCenter
          text: r2.label
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: 9
        }
        Row {
          id: slot
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          spacing: 2
        }
      }

      Row2 {
        label: "Default range"
        Repeater {
          model: Stocks.RANGES
          delegate: Pill {
            required property var modelData
            label: modelData.label
            on: modelData.key === tab.cfg.range
            pad: 5
            onClicked: { tab.put("stocks.range", modelData.key); tab.rangeOverride = modelData.key }
          }
        }
      }
      Row2 {
        label: "Chart style"
        Pill { label: "Line"; on: tab.style === "line"; onClicked: tab.put("stocks.style", "line") }
        Pill { label: "Candle"; on: tab.style === "candle"; onClicked: tab.put("stocks.style", "candle") }
      }
      Row2 {
        label: "Pre/post market"
        Pill { label: "Off"; on: !tab.cfg.prepost; onClicked: tab.put("stocks.prepost", false) }
        Pill { label: "On"; on: tab.cfg.prepost; onClicked: tab.put("stocks.prepost", true) }
      }
      Row2 {
        label: "Cards"
        Repeater {
          model: Stocks.CARD_CHOICES
          delegate: Pill {
            required property var modelData
            label: String(modelData)
            on: modelData === tab.cfg.cards
            pad: 8
            onClicked: tab.put("stocks.cards", modelData)
          }
        }
      }
    }

    Text {
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: 10
      textFormat: Text.PlainText
      text: "✕"
      color: closeHit.containsMouse ? tab.textColor : tab.dimColor
      font.family: tab.family
      font.pixelSize: 11
      MouseArea {
        id: closeHit
        anchors.fill: parent
        anchors.margins: -5
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: tab.popoverOpen = false
      }
    }
  }
}
