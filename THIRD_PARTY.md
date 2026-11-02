# Third-party components

Hackomon's source code and generated art are original and released under
the MIT License in this repository.

## PAGERCTL

The on-device adapter is compatible with the public API of
[`pineapple-pager-projects/pineapple_pager_pagerctl`](https://github.com/pineapple-pager-projects/pineapple_pager_pagerctl),
created by brAinphreAk and distributed under the MIT License.

No PAGERCTL source or binary is copied into this repository. The payload locates
an independently installed `libpagerctl.so` at runtime. This keeps the release
small, makes the dependency explicit and avoids redistributing an unverified
MIPS binary.

## Hak5 payload format

The `payload.sh` entry point follows the public WiFi Pineapple Pager payload
layout documented by Hak5. No Hak5 firmware, trademarks, DuckyScript source or
proprietary assets are included.

## Optional network tools and service protocols

Hackomon invokes independently installed `iw`, BlueZ `bluetoothctl`, `tcpdump`
and Aircrack-ng, and reads a local GPSD service. None of their source/binaries
is included. The original WDGWars client implements the public multipart API
documented at https://wdgwars.pl/press. CSV export follows WigleWifi-1.6 for
interoperability with Wardrive Go; no Wardrive Go (GPL-3.0) code is copied.
Service accounts and third-party licenses remain separate from Hackomon's MIT
source. WDGWars, Wardrive Go and WiGLE are not affiliated with this project.

