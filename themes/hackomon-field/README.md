# Hackomon Field Companion

Author: tiaocunha. Overlay version: 0.8.0.

Original night-observatory wallpaper with an amber radio familiar, cyan/mint
accents, a branded dashboard and lock screen. Image: 480x222 RGB PNG.
Wallpaper created with OpenAI's built-in image generator; no franchise art or
Hak5 images are distributed in this overlay. The original prompt is in PROMPT.txt.

Target: stock Hak5 firmware **2.0.0-stable**, Wargames theme_version 2.0.0,
theme_framework_version 0.9 and its six-icon dashboard. These are different
version identifiers. Desktop checks validate the file contract; **not yet
validated on physical hardware**. Other layouts/versions are rejected.

`tools/install_theme.py` copies the user's locally installed Wargames theme
to a new lowercase folder, then changes its palette and two screen backgrounds.
Existing controls, menu destinations, status indicators and other screen art
come from that local firmware base. This is not a complete redraw of all menus.
No animation is added to the stock theme; creature animations remain in the app.
No automatic theme selection, service restart or boot/firmware modification.

The stock base is normally `/lib/pager/themes/wargames`; installation writes
only to `/root/themes/hackomon-field`. Install:
`python3 tools/install_theme.py --dry-run`, then repeat without
`--dry-run`. Use `--base /path/to/wargames` if automatic discovery cannot find it.
Select **Settings > General > Theme > hackomon-field** on the Pager.
Return to **wargames** from the same menu to revert. A reboot may be needed
to refresh the list after copying. Existing Hackomon theme folders are never
overwritten; a second install can use `--name hackomon-field-test`.

License: original overlay code and art are released under this repository's MIT
license. The local derivative still contains Hak5 components and images, which
remain subject to Hak5's license (https://hak5.org/license). Do not publish the
assembled theme under MIT or redistribute the copied base as your own art.
