# Hackomon — Pager Edition

Hackomon is a lightweight virtual-creature game for the Hak5 WiFi
Pineapple Pager. It installs as an independent user payload and does **not**
replace or patch the stock Hak5 firmware.

This first playable release contains:

- 250 creatures: 10 families, 50 evolutionary lines and 5 stages per line;
- deterministic pixel-art sprites generated from compact creature descriptors;
- `idle`, `happy`, `sad`, `sleep` and `walk` animations;
- care actions, experience, levels and gated evolution rules;
- atomic JSON persistence on the Pager's MMC storage;
- a 480×222 interface controlled entirely by the D-pad and A/B buttons;
- no Wi-Fi attacks, association, deauthentication or active network scanning.

![Bestiary preview](docs/images/bestiary-preview.png)

The second preview shows the same creature in `idle`, `happy`, `sad`, `sleep`
and `walk` poses (one pose per row):

![Animation preview](docs/images/animation-preview.png)

## Status

The catalog, game logic, persistence, renderer and desktop test suite are
implemented and tested. The framebuffer/input adapter follows the public
`libpagerctl` API, but this release has not yet been validated on the author's
physical Pager. See [hardware validation](docs/HARDWARE_VALIDATION.md) for the
remaining device checks.

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

This release is a local virtual-pet app. It deliberately does not issue `iw`,
PineAP, BLE or packet-capture commands. A later passive-exploration adapter can
consume already-authorized discovery events without coupling the core game to
radio control.

Hak5 and WiFi Pineapple are trademarks of Hak5 LLC. This community project is
not affiliated with or endorsed by Hak5.

