import QtQuick 6.11
import qs.Commons as Commons

// The soft rounded plate every tile sits on (Agents, System, Dayflow, More,
// Home). Nothing but a fill and a corner radius, so the pages share one look;
// the radius is the theme's own rounding plus one step, so a square theme still
// gets soft tiles and a round one stays in proportion.
Rectangle {
  id: plate

  // One step stronger for a plate that is the page's one hero.
  property bool strong: false

  radius: Commons.Style.cornerRadius + Commons.Style.spacing.xxl
  color: Qt.alpha(Commons.Color.popups.text, plate.strong ? 0.09 : 0.06)
}
