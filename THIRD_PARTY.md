# Third-party components

TamaFi Reborn's source code and generated art are original and released under
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

