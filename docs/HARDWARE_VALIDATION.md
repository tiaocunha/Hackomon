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

## Experimental networks and laboratory

- [ ] Record firmware, iw, BlueZ, gpsd, tcpdump and Aircrack-ng versions.
- [ ] External GPS supplies fresh TPV reports and horizontal error estimates.
- [ ] Missing/stale GPS prevents map collection; movement over 30m rejects a batch.
- [ ] Wi-Fi passive scan works on the chosen interface without disrupting management.
- [ ] LE scan exits within its bound and does not pair/connect.
- [ ] Discovery XP and pending observations survive restart.
- [ ] CSV round-trips through Wardrive Go import with correct positions and names.
- [ ] A real WDGWars account accepts the request and its response schema is recorded.
- [ ] Offline, HTTP failure and unexpected success schemas preserve the queue.
- [ ] Target-specific monitor capture observes only the lab BSSID's EAPOL.
- [ ] A known lab password is recovered from a complete exchange and test dictionary.
- [ ] No-match, incomplete exchange and timeout never report a recovered password.
- [ ] PCAP/key files have private permissions and no secrets enter logs/uploads.
- [ ] Expired/changed BSSID rejects capture and old target's dictionary input.
- [ ] Radio operation completion and TERM restore the stock interface correctly.
- [ ] Bluetooth audit receives services from a known classic lab target via sdptool.
- [ ] BLE-only/cached metadata and unavailable devices are shown as partial/inconclusive.
- [ ] Rotating BLE addresses work in discovery and require updated lab target scope.
- [ ] Audit earns 5 XP once, persists it and never queues the local report for upload.
- [ ] SDP timeout ends cleanly without changing pairings or HID/audio connections.
- [ ] Client visit discovers APs without GPS or a pre-registered BSSID.
- [ ] Auto-scan chooses a free managed interface and skips management/AP connections.
- [ ] Selecting one AP confines capture/testing to that BSSID even with same-SSID neighbors.
- [ ] Temporary monitor creation/tuning works only on a free PHY and cleanup removes it.
- [ ] Capture failure also cleans up; cleanup failure is visible and names the interface.
- [ ] Client report lists unsupported/unexecuted tests accurately and never enters upload queue.
- [ ] Restart forgets the prior client target while keeping earned XP and private reports.

## Expedition field test — 0.6.0

- [ ] Start/pause/resume/end from the on-device Expedition screen; no automatic restart after relaunch.
- [ ] GPS UTC fix history aligns with iw age/BlueZ receive times during actual movement.
- [ ] A driver without last-seen metadata produces local unlocated records, not invented positions.
- [ ] Wi-Fi and BLE cycles alternate without overlapping a selected assessment's radio use.
- [ ] The selected authorized BSSID is frozen while the discovery list continues changing.
- [ ] Assessment pauses collection, preserves separate evidence and resumes after cleanup.
- [ ] Stop/exit waits for bounded commands, leaves a resumable journal and restores stock UI.
- [ ] Full 500-record map queue preserves additional located observations in expedition CSV.
- [ ] GPS loss, optical/physical button mapping, storage-full and missing dependencies are visible.
- [ ] CSV imports in Wardrive Go; actual WDGWars reception is verified with the user's account.
- [ ] Record CPU, memory and battery impact over at least one hour; check 4-FPS UI readability.

