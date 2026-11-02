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
- optional Wi-Fi passive scans and BLE discovery with external GPSD fixes;
- discovery XP, an offline queue, CSV export and manual WDGWars upload;
- scoped office-lab EAPOL capture and bounded offline WPA/WPA2-PSK dictionary tests.

![Bestiary preview](docs/images/bestiary-preview.png)

The second preview shows the same creature in `idle`, `happy`, `sad`, `sleep`
and `walk` poses (one pose per row):

![Animation preview](docs/images/animation-preview.png)

The evolution sheet shows one line from every family progressing from egg to
rare form, including the matching environment growth:

![Evolution environment preview](docs/images/evolution-preview.png)

## Status

The catalog, game logic, persistence, renderer and desktop test suite are
implemented and tested. The framebuffer/input adapter follows the public
`libpagerctl` API, but this release has not yet been validated on the author's
physical Pager. See [hardware validation](docs/HARDWARE_VALIDATION.md) for the
remaining device checks.

Network and lab adapters in **0.4.0 are experimental**: desktop tests use fixtures
and mocked commands, not physical radios, actual password recovery or a live
WDGWars account. See [network setup and limits](docs/NETWORKS.md).

## Install

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

```text
python -m unittest discover -s tests -v
python tools/generate_bestiary.py --check
python tools/render_preview.py
python tools/build_release.py
```

The payload itself has no Python package downloads and never fetches code at
runtime. Generated release archives are written to `dist/`.

## Scope and safety

Radio operations run only when selected under **Redes / Laboratorio**. Lab
operations require one exact BSSID, an existing monitor interface and a local
authorization valid for at most 24 hours. No deauthentication, injection or
automatic association is implemented. Uploads contain discovery metadata and
GPS, never captures or recovered passwords. Keep account keys in local
configuration, not in Git or chat.

Hak5 and WiFi Pineapple are trademarks of Hak5 LLC. This community project is
not affiliated with or endorsed by Hak5.

