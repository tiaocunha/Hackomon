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

The optional Windows fresh-install helper downloads the upstream binary from
commit `30ef1028500ba1d0303d24ea5d62497407bac77d` directly to the user's machine,
checks SHA-256 `f0f5d3213c77e360fa4cf912c5a122d2dd1b39713ae2cdf7c6ba6dc7ead5e4e5`,
then installs it separately on the Pager. This download is not a reproducible
source build or evidence of firmware-2.0 ABI compatibility. The bundled archives
and Git repository still contain no PAGERCTL binary/source.

## Hak5 payload format

The `payload.sh` entry point follows the public WiFi Pineapple Pager payload
layout documented by Hak5. No Hak5 firmware, trademarks, DuckyScript source or
proprietary assets are included.

## Hackomon Field Companion theme

Only the original wallpaper, palette, prompt and overlay installer are included.
The wallpaper was created with OpenAI's built-in image generator and resized
to 480x222. The installer copies the user's licensed Wargames base locally,
preserves its firmware components and adds Hackomon branding. The resulting
on-device derivative contains Hak5 material, remains subject to
[Hak5 licensing](https://hak5.org/license), and is not wholly MIT. Do not
redistribute it as original Hackomon art. Stock icons and other screen art are
inherited locally, not embedded in these release archives.

## Optional network tools and service protocols

Hackomon invokes independently installed `iw`, `ip`, BlueZ `bluetoothctl`/`sdptool`, `tcpdump`
and Aircrack-ng, and reads a local GPSD service. None of their source/binaries
is included. The original WDGWars client implements the public multipart API
documented at https://wdgwars.pl/press. CSV export follows WigleWifi-1.6 for
interoperability with Wardrive Go; no Wardrive Go (GPL-3.0) code is copied.
Service accounts and third-party licenses remain separate from Hackomon's MIT
source. WDGWars, Wardrive Go and WiGLE are not affiliated with this project.

## Native Recon database adapter

The original read-only adapter uses the public database path and column contract
shown by the community-maintained
[Recon report payload in Hak5's repository](https://github.com/hak5/wifipineapplepager-payloads/blob/master/library/user/reconnaissance/recondb_reporting/payload.sh).
No reporting code or SQL expressions were copied. No native database, identifiers,
captured credentials or firmware source is distributed. Unknown schema/freshness
fails explicitly; this public example does not prove the exact on-device schema.
Bluetooth readiness checks follow BlueZ's public bluetoothctl controller properties.

The 0.8.4 Blue5 adapter and decimal/BLOB compatibility were developed from
identifier-free diagnostic metadata on a stock 2.0.0-stable unit. The native
database column/transport contract is specific to the observed firmware; no
Blue5 executable, firmware source or collected device records are distributed.
Compatibility with other Blue5 versions is not implied.

