# Install on a WiFi Pineapple Pager

## Prerequisites

- Stock Hak5 Pager firmware with SSH access.
- A microSD/MMC installation available at `/mmc`.
- `python3` and `python3-ctypes` installed to MMC.
- The MIT-licensed PAGERCTL utility, including `libpagerctl.so`.

PAGERCTL source and build/install instructions are available from its
[upstream repository](https://github.com/pineapple-pager-projects/pineapple_pager_pagerctl).
TamaFi checks these common locations:

- `/root/payloads/user/utilities/PAGERCTL/libpagerctl.so`
- `/mmc/root/payloads/user/utilities/PAGERCTL/libpagerctl.so`
- `tamafi_reborn/lib/libpagerctl.so`

## Copy the payload

From a computer on the Pager's management connection, extract the release and
copy the folder:

```text
scp -r tamafi_reborn root@172.16.52.1:/root/payloads/user/games/
```

Then open **Payloads → User → Games → TamaFi Reborn** on the Pager.

The launcher does not install packages or download remote scripts. If Python or
PAGERCTL is missing, it shows the missing dependency and exits without changing
the system.

## Save data

The default save lives at:

```text
/mmc/root/tamafi-reborn/state.json
```

For a temporary test save, set `TAMAFI_DATA_DIR` before launching the Python
entry point.

## Uninstall

Remove only the payload directory:

```text
rm -r /root/payloads/user/games/tamafi_reborn
```

The save remains intact. Remove `/mmc/root/tamafi-reborn` separately only if
you intentionally want to erase all progress.

