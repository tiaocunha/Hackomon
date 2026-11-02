# Hardware validation checklist

Desktop validation cannot prove framebuffer orientation, physical button
mapping or service handoff on a specific firmware build. Before calling this a
hardware-validated release, run the following checks on a stock Pager:

- [ ] Payload appears under User → Games and exits cleanly when B is pressed.
- [ ] Display is landscape 480×222 with no clipping or upside-down content.
- [ ] D-pad directions and green/red buttons match the on-screen help.
- [ ] Idle animation remains responsive for at least 15 minutes.
- [ ] A care action persists after exiting and relaunching.
- [ ] An evolution persists and its prior stages appear unlocked.
- [ ] Corrupting a test save quarantines it and starts a new game.
- [ ] The stock `pineapplepager` service returns after normal exit.
- [ ] The stock service returns after sending TERM to the payload.
- [ ] Rebooting after a payload run starts the original Hak5 interface.
- [ ] Memory and CPU remain acceptable while browsing all 250 entries.

Known limitation: this repository cannot validate a physical Pager from the
desktop environment. No claim of on-device validation should be made until the
checklist above has been completed and the firmware version recorded.

