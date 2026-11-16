import QtQuick 6.11
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import qs.Commons as Commons
import "Hover.js" as Hover
import "Geom.js" as Geom
import "Zone.js" as Zone
import "Screens.js" as Screens
import "Activity.js" as Activity

// One screen's island. The window is fixed at card size plus slop and never
// resizes. The input mask is the hot zone: a separate, non-animating item whose
// rectangle changes only when Hover.js commits a state change (KTD2). The one
// always-enabled HoverHandler lives on it; the timers re-read it when they fire
// (KTD3). Hover.js owns every open/close rule; this file feeds it events and
// runs the one timer it asks for.
PanelWindow {
  id: win

  // The Island root: settings, probe, cameraWidth, fullscreenOn(), saveSettings().
  property var island: null
  required property var modelData

  // The single place that picks the layer. Overlay, because the Omarchy bar is
  // also on Top and two Top surfaces stack by map order, which a shell restart
  // can flip (U1 probe, 2026-11-15). The window hides under real fullscreen
  // (KTD6), so Overlay never costs a fullscreen app its direct scanout.
  readonly property int windowLayer: WlrLayer.Overlay

  screen: modelData
  color: "transparent"
  anchors.top: true
  exclusionMode: ExclusionMode.Ignore
  WlrLayershell.namespace: "omarchy-island"
  WlrLayershell.layer: win.windowLayer
  WlrLayershell.keyboardFocus: win.model.focused ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None

  // ---- state ----
  property var model: Hover.initial()
  property string page: "now"
  readonly property bool cardShown: Hover.cardShown(win.model)
  readonly property string zone: Hover.zoneFor(win.model)
  onCardShownChanged: {
    if (!win.cardShown) win.hold.ids = []
    if (win.island) win.island.refreshOpened()
  }

  // ---- live activities (KTD3) ----
  // Ids this window's card is showing, in slot order; empty while closed.
  // Mutated in place, never reassigned: the layout only needs the hold the
  // next time the activities or cardShown change, and a notifying write here
  // would make `layout` depend on its own result (a binding loop).
  property var hold: ({ ids: [] })
  readonly property var layout: Activity.layout(win.island ? win.island.activities : [], win.hold.ids,
                                                win.cardShown, win.island ? win.island.activityClock : 0)
  onLayoutChanged: win.hold.ids = win.cardShown ? win.layout.held : []

  // ---- geometry ----
  readonly property var monitor: Hyprland.monitorFor(win.screen)
  readonly property var screenInfo: Screens.describe(win.screen, win.monitor ? win.monitor.lastIpcObject : null)
  readonly property var geom: Geom.compute(win.island ? win.island.probe : null, win.screenInfo,
                                          win.island ? win.island.cameraWidth : 0)
  readonly property var winSize: Zone.windowSize(win.geom)
  readonly property var zoneRect: Zone.rect(win.zone, win.geom)

  implicitWidth: win.winSize.width
  implicitHeight: win.winSize.height

  // ---- fullscreen step-aside (KTD6) ----
  readonly property bool fullscreenNow: win.island ? win.island.fullscreenOn(win.screen) : false
  onFullscreenNowChanged: win.send(win.fullscreenNow ? "fullscreenOn" : "fullscreenOff")
  visible: !win.fullscreenNow

  mask: Region { item: hotZone }

  // ---- event plumbing ----
  function send(event) {
    var r = Hover.step(win.model, event, win.island ? win.island.settings : null)
    win.model = r.model
    if (r.timer > 0) {
      hoverTimer.interval = r.timer
      hoverTimer.restart()
    } else if (r.timer === 0) {
      hoverTimer.stop()
    }
  }

  // The single open/close/summon timer. It re-reads the live hover state when
  // it fires instead of trusting a stale enter/leave.
  Timer {
    id: hoverTimer
    interval: 1000 // always overwritten by send() before it starts
    repeat: false
    onTriggered: win.send({ type: "timer", hovered: hoverHandler.hovered })
  }

  // IPC entry points (the root picks the window).
  function summon(pageId) {
    if (pageId === "now" || pageId === "settings") win.page = pageId
    win.send("summon")
  }
  function closeByIpc() { win.send("ipcClose") }
  function focusCard() { win.send("focus") }
  // Drop keyboard focus but keep the card open, so a dictation paste lands in
  // the window the owner was typing in (KTD4).
  function unfocus() { win.send("unfocus") }

  function snapshot() {
    var s = Zone.snapshot(win.screen.name, win.model, win.zoneRect)
    s.zone = win.zone
    s.hidden = win.fullscreenNow
    s.origin = { x: win.screen.x + (win.screen.width - win.winSize.width) / 2, y: win.screen.y }
    s.window = win.winSize
    s.pillRect = Zone.rect("pill", win.geom)
    s.cardRect = Zone.rect("card", win.geom)
    s.pinCenter = card.pinCenter()
    s.top = win.layout.top ? win.layout.top.id : ""
    s.second = win.layout.second ? win.layout.second.id : ""
    s.held = win.hold.ids
    return s
  }

  // ---- keyboard (KTD5) ----
  // OnDemand focus only, no HyprlandFocusGrab: the U1 probe showed an active
  // grab stops Hyprland sending pointer leave, which would keep a focused
  // card open after the pointer leaves.
  Shortcut {
    sequence: "Escape"
    enabled: win.model.focused && win.cardShown
    onActivated: win.send("escape")
  }

  // ---- hot zone, hover source and visuals ----
  Item {
    id: hotZone
    x: win.zoneRect.x
    y: win.zoneRect.y
    width: win.zoneRect.width
    height: win.zoneRect.height

    HoverHandler {
      id: hoverHandler
      onHoveredChanged: win.send(hovered ? "enter" : "leave")
    }

    // Window-sized and window-anchored: the visuals animate inside the
    // zone's input area without ever moving it.
    Item {
      id: stage
      x: -hotZone.x
      y: -hotZone.y
      width: win.winSize.width
      height: win.winSize.height

      Item {
        id: body
        clip: true
        readonly property int radius: Commons.Style.cornerRadius + Commons.Style.spacing.md
        x: (stage.width - width) / 2
        y: 0
        width: win.cardShown ? win.geom.card.width : win.geom.compactWidth
        height: win.cardShown ? win.geom.card.height : win.geom.compactHeight

        Behavior on width { NumberAnimation { duration: Commons.Style.duration(240); easing.type: Easing.BezierSpline; easing.bezierCurve: Commons.Style.easeOut } }
        Behavior on height { NumberAnimation { duration: Commons.Style.duration(240); easing.type: Easing.BezierSpline; easing.bezierCurve: Commons.Style.easeOut } }

        // Drawn taller than the shape and clipped at the top edge, so only
        // the bottom corners are rounded.
        Rectangle {
          y: -body.radius
          width: parent.width
          height: parent.height + body.radius
          radius: body.radius
          color: Commons.Color.popups.background
          border.width: Commons.Style.normalBorderWidth
          border.color: Commons.Color.popups.border
        }

        Pill {
          x: (body.width - width) / 2
          y: 0
          width: win.geom.compactWidth
          height: win.geom.compactHeight
          now: win.island ? win.island.now : new Date()
          earWidth: win.geom.earWidth
          cameraWidth: win.geom.cameraWidth
          topActivity: win.layout.top
          secondActivity: win.layout.second
        }

        Card {
          id: card
          x: (body.width - width) / 2
          y: win.geom.compactHeight
          width: win.geom.card.width
          height: win.geom.card.height - win.geom.compactHeight
          opacity: win.cardShown ? 1 : 0
          visible: opacity > 0.01
          now: win.island ? win.island.now : new Date()
          page: win.page
          pinned: win.model.pinned
          island: win.island
          layout: win.layout
          onAct: function(id, action, value) { if (win.island) win.island.act(id, action, value) }
          onPageSelected: function(id) { win.page = id }
          onPinClicked: win.send(win.model.pinned ? "unpin" : "pin")
          onCardClicked: win.send("cardClick")
          onHoldStart: win.send("holdStart")
          onHoldEnd: win.send("holdEnd")

          Behavior on opacity { NumberAnimation { duration: Commons.Style.duration(160); easing.type: Easing.BezierSpline; easing.bezierCurve: Commons.Style.easeOut } }
        }

        // A click on the compact pill opens the card without pinning; the
        // Card handles its own clicks.
        TapHandler {
          enabled: !win.cardShown
          onTapped: win.send("click")
        }
      }
    }
  }
}
