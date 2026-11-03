# Hackomon — Pager Edition

Hackomon is a lightweight virtual-creature game for the Hak5 WiFi
Pineapple Pager. It installs as an independent user payload and does **not**
replace or patch the stock Hak5 firmware.

This incremental release contains:

- 250 creatures: 10 families, 50 evolutionary lines and 5 stages per line;
- detailed 32×32 pixel-art sprites with family anatomy, shading and line-specific ornaments;
- 250 personalized environments that change with family, line and evolutionary stage;
- `idle`, `happy`, `sad`, `sleep` and `walk` animations;
- care actions, experience, levels and gated evolution rules;
- atomic JSON persistence on the Pager's MMC storage;
- a 480×222 interface controlled entirely by the D-pad and A/B buttons;
- optional Wi-Fi passive scans and BLE discovery with fixes from the stock GPSd service;
- discovery XP, an offline queue, CSV export and manual WDGWars upload;
- scoped office-lab EAPOL capture and bounded offline WPA/WPA2-PSK dictionary tests.
- target-scoped Bluetooth metadata and classic SDP service inventory, with local reports.
- a client-visit workflow: discover, choose the client's AP on screen, assess and
  save local JSON/text reports without pre-registering a BSSID or requiring GPS.
- offline expeditions with repeated Wi-Fi/BLE scan cycles, continuous GPS sampling,
  pause/resume, local trails/CSV, pet reactions and a scoped hybrid assessment flow.
- full expedition CSV synchronization in small resumable WDGWars batches, account
  validation, local receipts/history, cancellation and explicit uncertain-upload recovery.
- an original Hackomon Field Companion overlay for the stock 2.0 Wargames theme,
  a double-click Windows installer and read-only `--doctor` diagnostics;
- native Recon AP fallback, independent Wi-Fi/BLE status and a double-click
  read-only radio support report;
- compatibility with decimal iw frequencies, BLOB Wi-Fi addresses and native
  Blue5 LE records observed on firmware 2.0.0-stable (0.8.4).
- discovery XP without GPS in Expeditions, with persistent duplicate protection;
  map uploads still require valid location (0.8.5).
- no daily discovery XP ceiling; fresh new addresses keep earning 2 XP Wi-Fi
  and 1 XP BLE while repeat-address protection remains (0.8.6).
- expeditions use their durable CSVs directly, without filling the 500-entry
  standalone queue; new/known discovery feedback, sensor freshness states and
  an outing summary with local per-account pending counts (0.8.7).

![Bestiary preview](docs/images/bestiary-preview.png)

The second preview shows the same creature in `idle`, `happy`, `sad`, `sleep`
and `walk` poses (one pose per row):

![Animation preview](docs/images/animation-preview.png)

The evolution sheet shows one line from every family progressing from egg to
rare form, including the matching environment growth:

![Evolution environment preview](docs/images/evolution-preview.png)

## Status

The catalog, game logic, persistence, renderer and desktop test suite are
implemented and tested. Earlier builds ran on the user's stock 2.0.0-stable
Pager; the 0.8.7 changes still require a device field test. See
[hardware validation](docs/HARDWARE_VALIDATION.md) for the remaining checks.

Network and lab adapters remain **experimental in 0.8.7**. Automated tests use
fixtures and mocked commands. Native Recon Wi-Fi and Blue5 LE readers were
also checked on one physical 2.0.0-stable Pager and returned recent observations.
The user also confirmed both Expedition discovery counters increment on that
device. Long-run expedition behavior, GPS association, battery, actual password
recovery and live WDGWars acceptance remain separate validation.
See [network setup and limits](docs/NETWORKS.md).
For the field-test release, start with [the short Portuguese guide](docs/TESTE_RAPIDO.txt)
and [expedition behavior and limits](docs/EXPEDITIONS.md).
The [WDGWars synchronization guide](docs/WDGWARS.md) explains checkpoints,
server acceptance versus imported counts, and recovery from interrupted uploads.

## Product direction

The product direction combines a wardriving companion, expeditions and
an authorized pentesting assistant. Version 0.6.0 implements the first serial
hybrid workflow; advanced scheduling, affinities and computer/AI integration
remain future work. See the
[wardriving and hybrid-mode design](docs/WARDRIVING_DESIGN.md) (Portuguese).

## Install

For **Hak5 2.0.0-stable after a factory reset**, start with
[the Portuguese setup guide](docs/INSTALAR_2_0.md): extract
`hackomon-instalar-0.8.7.zip`, double-click **INSTALAR.cmd**, then enter the Pager
system password when OpenSSH asks. No manual PowerShell or file copy is needed.
The installer uses one SSH session and preserves a recognized existing theme.
Version 0.8.2 fixes launch from the Hak5 temporary runner using `_PAYLOAD_HOME`
and checks a temporary diagnostic launch before reporting installation success.
Users seeing a PAGERCTL prompt after an earlier successful setup should reapply
the current installer; no separate PAGERCTL demo payload is needed.
If the app starts but discovers nothing, 0.8.3 adds native Recon fallback and
persistent per-radio status. `DIAGNOSTICAR.cmd` generates a read-only support
report without SSIDs, device addresses, GPS coordinates or account credentials.
The 0.8.4 readers target the native Recon/Blue5 schema observed on a real
2.0.0-stable unit; old/classic-only/unknown records are not fresh BLE discoveries.
The app does not start a competing Bluetooth daemon or retune native collectors.
In 0.8.6, new fresh discoveries in Expeditions grant 2 XP per Wi-Fi address and
1 XP per BLE address without requiring GPS, once per address/type, with no daily
XP ceiling. A separate persisted hash ledger prevents repeat rewards.
Unlocated sightings stay local; later GPS mapping does not award the same XP twice.
The full setup archive also
creates a locally derived stock theme, preserving firmware-specific menus.
The original overlay contains no copied Hak5 assets; the assembled on-device
theme remains subject to Hak5 licensing. No physical 2.0 compatibility claim is made.

The short version:

1. Install Python 3 + `python3-ctypes` on MMC and the MIT-licensed PAGERCTL
   utility on the Pager.
2. Copy `payload/hackomon` to
   `/root/payloads/user/games/hackomon`.
3. Open **Payloads → User → Games → Hackomon**.

Full commands and uninstall steps are in [docs/INSTALL.md](docs/INSTALL.md).

## Controls

| Control | Home | Bestiary / help |
| --- | --- | --- |
| D-pad | Select an action | Browse entries/pages |
| A / green | Confirm | Return |
| B / red | Exit | Return |

Progress is stored in `/mmc/root/hackomon/state.json`. Reinstalling the
payload does not erase the save.

## Development

Only the Python standard library is required on a development computer.
Windows integration tests additionally use the built-in Windows PowerShell,
tar, a local compiled fixture and loopback port 22; they simulate the Pager.

```text
python -m unittest discover -s tests -v
python tools/generate_bestiary.py --check
python tools/render_preview.py
python tools/build_release.py
```

For Windows binary-transport checks, also run
`powershell -NoProfile -ExecutionPolicy Bypass -File tests/test_installer_transport.ps1`.

The payload itself has no Python package downloads and never fetches code at
runtime. Generated release archives are written to `dist/`.

## Scope and safety

Radio operations run only when selected under **Redes / Laboratorio**. Client
visits choose the exact AP from a fresh scan; scope is session-only, without
manual address registration. The visit adapter can prepare/remove a temporary
monitor on a free radio. The original lab menu still supports static targets.
No deauthentication, injection or
automatic association is implemented. Uploads contain discovery metadata and
GPS, never captures or recovered passwords. Keep account keys in local
configuration, not in Git or chat.

Hak5 and WiFi Pineapple are trademarks of Hak5 LLC. This community project is
not affiliated with or endorsed by Hak5.

