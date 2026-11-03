# Hardware validation checklist

## Offline discovery XP — 0.8.5

- [x] Installer applied 0.8.5 to the reconnected device after checking the app
  was closed; native readers and temporary-launch verification passed.
- [ ] Confirm Expedition gains XP with fresh Wi-Fi/BLE observations and GPSd unavailable.
- [ ] Exit/restart and reobserve the same address without earning twice.
- [ ] Confirm located points can enter the map later without a second reward.
- [ ] Confirm unlocated observations stay out of CSV/WDGWars.
- [ ] Confirm migration preserves the pet, previous XP and located reward history.

## Field screenshot — 0.8.4, 2026-11-03

- [x] User screenshot showed increasing Wi-Fi/BLE counts, a recent GPS fix,
  located records, an approximate track distance and the 120-XP daily discovery cap.
- [x] Full quick queue was explicitly shown with expedition CSV preservation.
- [ ] Compare recorded coordinates/timestamps/distance against an independent route.
- [ ] Verify actual WDGWars reception from the field CSV, including records beyond the quick queue.

The 0.8.5 upgrade occurred after that field test. Positive additional discovery
XP cannot be inferred from the installation check: the device had already
reached its daily cap, which this release intentionally preserves.

## Native reader check — 0.8.4, 2026-11-03

- [x] Loaded the corrected native Recon reader on one stock 2.0.0-stable Pager;
  BLOB ASCII addresses decoded and recent AP rows were accepted.
- [x] Loaded the Blue5 LE reader on that Pager; recent LE rows were accepted
  without starting bluetoothd or modifying controller/service configuration.
- [x] Reinstalled the payload with a backup; installer preserved save/config
  and recognized the existing valid theme. Temporary-launch verification passed.
- [x] User confirmed the running Expedition screen increments both Wi-Fi and BLE
  counters after installing 0.8.4 on that 2.0.0-stable Pager.
- [ ] Validate real GPS fixes and timestamp/location association; GPSd was not
  reachable during this reader check.
- [ ] Validate full field duration, power use, WDGWars reception and selected lab tests.

This establishes native database reader compatibility on that device, not full
hardware validation of the complete product or other firmware versions.

## Radio discovery 0.8.3

- [ ] Test native Recon fallback with Client Mode off and with its interface connected.
- [ ] Record actual ssid schema and confirm time is the observation time on firmware 2.0.
- [ ] Verify Recon continues updating while the Hackomon display owns the screen.
- [ ] Old/native unknown-schema data never becomes current located discoveries.
- [ ] BLE controller-off and unavailable states are readable independently of GPS errors.
- [ ] DIAGNOSTICAR.cmd collects the real support report without identifiers or credentials.

## Firmware 2.0.0-stable / 0.8.0 first installation

- [ ] Complete Windows setup after a factory reset; record actual installed package versions.
- [ ] Double-click INSTALAR.cmd; authenticate through native OpenSSH during the binary transfer.
- [ ] On 0.8.2, confirm the temporary launcher check resolves `_PAYLOAD_HOME` and the bundled library.
- [ ] Interrupted copy never reaches setup; a retry preserves progress/config and an existing valid theme.
- [ ] Pinned MIPS library loads and renders correctly on firmware 2.0 (not just API symbol check).
- [ ] Wargames local base passes overlay schema, reference and six-icon layout checks.
- [ ] Hackomon theme appears in Settings > General > Theme; stock Wargames stays selectable.
- [ ] Check dashboard/status bar, lock/unlock, warnings, all menu destinations and legibility.
- [ ] Confirm the new background does not obscure status indicators or selected menu labels.
- [ ] Missing-library/startup error restores the stock UI before displaying its message.
- [ ] Read-only doctor does not initialize framebuffer, scan, pair or upload.
- [ ] Capture real device screenshots and record CPU/RAM/battery before claiming hardware validation.

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

## Resumable synchronization — 0.7.0

- [ ] Validate a real account via /api/me without printing its key.
- [ ] Import a real expedition above 500 records; compare local receipts with server counts.
- [ ] Interrupt connectivity after a confirmed batch; restart and preserve the acknowledged cursor.
- [ ] Ambiguous/202 responses never display completed import; repetition requires explicit confirmation.
- [ ] Server Retry-After is enforced across restart and UI cancellation preserves confirmed progress.
- [ ] Upload during collection leaves newly appended records pending for the next snapshot.
- [ ] Packet captures, recovered keys and client reports do not appear in request bodies.
- [ ] Check memory, TLS certificates and storage use while synchronizing a large expedition.

