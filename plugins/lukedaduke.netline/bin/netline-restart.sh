#!/bin/sh
# netline restart — bounce the user GUI unit, then the system collector.
# netline.service is a system unit: this goes through polkit, so an
# authentication dialog may appear. Always exits 0; the panel just
# re-polls status afterwards.
systemctl --user restart netline-gui.service 2>/dev/null
systemctl restart netline.service 2>/dev/null
exit 0
