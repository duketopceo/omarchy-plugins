import QtQuick 6.11
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import qs.Commons as Commons
import "Hover.js" as Hover
import "Intent.js" as Intent
import "Geom.js" as Geom
import "Zone.js" as Zone
import "Screens.js" as Screens
import "Activity.js" as Activity
import "Presentation.js" as Presentation
import "Alert.js" as Alert

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
  // Recent pointer motion inside the hot zone, for the hover-intent check on
  // the open timer (Intent.js). Hot-zone coordinates shift when the zone
  // commits, so the samples start over then, and on leave.
  property var motion: []
  onZoneChanged: win.motion = []
  onCardShownChanged: {
    if (!win.cardShown) win.hold.ids = []
    if (win.island) win.island.refreshOpened()
    win.refreshAlert()
  }
  // Set while this window is being destroyed, so the root's aggregate
  // `opened` stops counting a card that is going away with it (R17).
  property bool destroying: false
  Component.onDestruction: {
    win.destroying = true
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

  // ---- presentation (KTD2, KTD4-KTD7) ----
  // The alert this window shows now, or null; gated per window so an alert
  // seen while the card is open or under fullscreen never shows later.
  property var alertShown: null
  property int alertBlockedId: 0
  function refreshAlert() {
    if (!win.island) return
    var blocked = !Presentation.showAlert({ cardShown: win.cardShown, fullscreen: win.fullscreenNow, state: win.model.state })
    var g = Alert.gate(win.island.alertModel, win.alertBlockedId, blocked, Date.now())
    win.alertBlockedId = g.blockedId
    var a = g.show ? Alert.current(win.island.alertModel, Date.now()) : null
    if (a !== win.alertShown) win.alertShown = a
    if (a) { alertEnd.interval = Math.max(1, a.until - Date.now() + 20); alertEnd.restart() }
  }
  Connections {
    target: win.island
    function onAlertModelChanged() { win.refreshAlert() }
  }
  // One-shot, armed to the shown alert's end, so it collapses on time.
  Timer {
    id: alertEnd
    interval: 3000 // always overwritten by refreshAlert() before it starts
    onTriggered: win.refreshAlert()
  }
  onModelChanged: win.refreshAlert()

  readonly property bool hasSecond: win.layout.second !== null
  readonly property bool bubbleShown: Presentation.bubbleVisible(win.hasSecond, win.alertShown !== null, win.cardShown)
  readonly property string mode: win.cardShown ? "expanded" : (win.alertShown !== null ? "alert" : (win.bubbleShown ? "split" : "compact"))
  readonly property bool notch: Presentation.surface(win.geom.hasCutout, win.mode) === "notch"
  readonly property int dotCount: (win.island && win.island.micInUse ? 1 : 0) + (win.island && win.island.cameraInUse ? 1 : 0)
  // The compact target: a discrete size from the content, never the animating
  // width, so the hot zone only moves when content or state commits (KTD2).
  readonly property var target: Presentation.compact(win.geom, pill.wantEar,
    { bubble: win.bubbleShown, dots: win.dotCount, screenWidth: win.screen ? win.screen.width : 0 })
  readonly property var alertSize: Presentation.alertSize(win.geom)
  readonly property var zoneRect: Zone.rect(win.zone, win.geom, win.target)
  // Pill text on the black notch surface: the theme's popup text when it reads
  // on black, else the theme background (light themes).
  readonly property color pillText: !win.geom.hasCutout ? Commons.Color.popups.text
    : (Presentation.textOnBlack(Commons.Color.popups.text, Commons.Color.popups.background) === "text"
       ? Commons.Color.popups.text : Commons.Color.popups.background)

  implicitWidth: win.winSize.width
  implicitHeight: win.winSize.height

  // ---- fullscreen step-aside (KTD6) ----
  // Re-read when the root's Hyprland snapshot settles, not bound: the binding
  // looped through the window's own visibility (shell log, 2026-11-15).
  property bool fullscreenNow: false
  function refreshFullscreen() {
    var on = win.island ? win.island.fullscreenOn(win.screen) : false
    if (on === win.fullscreenNow) return
    win.fullscreenNow = on
    win.send(on ? "fullscreenOn" : "fullscreenOff")
  }
  Connections {
    target: win.island
    function onHyprRevisionChanged() { win.refreshFullscreen() }
  }
  Component.onCompleted: win.refreshFullscreen()
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
    onTriggered: win.send({ type: "timer", hovered: hoverHandler.hovered,
                            moving: Intent.moving(win.motion, Date.now()) })
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
    s.presentation = { mode: win.mode, surface: win.notch ? "notch" : "theme", pillWidth: win.target.width,
                       earWidth: win.target.earWidth, bubble: win.bubbleShown }
    s.alert = win.alertShown ? { kind: win.alertShown.kind, title: win.alertShown.title } : null
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
      onHoveredChanged: {
        if (!hovered) win.motion = []
        win.send(hovered ? "enter" : "leave")
      }
      // Motion samples only while arming: that is the one state whose timer
      // reads them, so an open card costs nothing per pointer move.
      onPointChanged: if (hovered && win.model.state === "arming")
        win.motion = Intent.add(win.motion, point.position.x, point.position.y, Date.now())
    }

    // Window-sized and window-anchored: the visuals animate inside the
    // zone's input area without ever moving it.
    Item {
      id: stage
      x: -hotZone.x
      y: -hotZone.y
      width: win.winSize.width
      height: win.winSize.height

      // Spring on growth (OutBack, slight overshoot) and a quick ease-out on
      // shrink, both through Commons.Style.duration so reduced motion snaps
      // (KTD3). Opening and alert growth spring; content changes and closing ease.
      readonly property bool springing: win.cardShown || win.alertShown !== null

      Item {
        id: body
        clip: true
        readonly property int radius: Commons.Style.cornerRadius + Commons.Style.spacing.md
        x: (stage.width - width) / 2
        y: 0
        width: win.mode === "expanded" ? win.geom.card.width : (win.mode === "alert" ? win.alertSize.width : win.target.width)
        height: win.mode === "expanded" ? win.geom.card.height : (win.mode === "alert" ? win.alertSize.height : win.target.height)

        Behavior on width {
          NumberAnimation {
            duration: Commons.Style.duration(stage.springing ? 380 : 240)
            easing.type: stage.springing ? Easing.OutBack : Easing.BezierSpline
            easing.overshoot: 1.2
            easing.bezierCurve: Commons.Style.easeOut
          }
        }
        Behavior on height {
          NumberAnimation {
            duration: Commons.Style.duration(stage.springing ? 380 : 240)
            easing.type: stage.springing ? Easing.OutBack : Easing.BezierSpline
            easing.overshoot: 1.2
            easing.bezierCurve: Commons.Style.easeOut
          }
        }

        // Drawn taller than the shape and clipped at the top edge, so only
        // the bottom corners are rounded. Pure black on a notch screen's
        // compact pill so it merges with the camera cutout (KTD4).
        Rectangle {
          y: -body.radius
          width: parent.width
          height: parent.height + body.radius
          radius: body.radius
          color: win.notch ? Qt.rgba(0, 0, 0, 1) : Commons.Color.popups.background
          border.width: win.notch ? 0 : Commons.Style.normalBorderWidth
          border.color: Commons.Color.popups.border
          Behavior on color { ColorAnimation { duration: Commons.Style.duration(160) } }
        }

        Pill {
          id: pill
          x: (body.width - width) / 2
          y: 0
          width: win.target.width
          height: win.target.height
          opacity: win.alertShown !== null ? 0 : 1
          visible: opacity > 0.01
          now: win.island ? win.island.now : new Date()
          earWidth: win.target.earWidth
          textWidth: win.target.textWidth
          dotSlot: win.target.dotSlot
          cameraWidth: win.geom.cameraWidth
          textColor: win.notch ? win.pillText : Commons.Color.popups.text
          // On the black notch pill the art color is picked against black.
          tint: !win.island ? Commons.Color.accent
            : (win.notch ? (win.island.mediaPillTint ? win.island.mediaPillTint : win.pillText) : win.island.mediaTint)
          topActivity: win.layout.top
          dnd: win.island ? win.island.dndOn : false
          micInUse: win.island ? win.island.micInUse : false
          cameraInUse: win.island ? win.island.cameraInUse : false
          Behavior on opacity { NumberAnimation { duration: Commons.Style.duration(120) } }
        }

        AlertView {
          x: (body.width - width) / 2
          width: win.alertSize.width
          height: win.alertSize.height
          opacity: win.alertShown !== null ? 1 : 0
          visible: opacity > 0.01
          alert: win.alertShown
          Behavior on opacity { NumberAnimation { duration: Commons.Style.duration(160) } }
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
          tint: win.island ? win.island.mediaTint : Commons.Color.accent
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

      // The split presentation's detached bubble (KTD6), right of the pill.
      Bubble {
        x: (stage.width - win.target.width) / 2 + (win.target.bubble ? win.target.bubble.offset : win.target.width)
        y: 0
        width: win.geom.compactHeight
        height: win.geom.compactHeight
        opacity: win.bubbleShown ? 1 : 0
        visible: opacity > 0.01
        activity: win.layout.second
        notch: win.geom.hasCutout
        textColor: win.pillText
        Behavior on opacity { NumberAnimation { duration: Commons.Style.duration(160) } }
        onClicked: {
          // Seed the held order so the card opens with this activity on top.
          if (win.layout.second) win.hold.ids = [String(win.layout.second.id)]
          win.send("click")
        }
      }
    }
  }
}
