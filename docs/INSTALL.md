# Install on a WiFi Pineapple Pager

0.8.6 removes the daily discovery XP ceiling. Existing progress and address
deduplication remain; fresh new addresses can earn more XP on the same day.

0.8.5 separates Expedition discovery XP from GPS/map eligibility: fresh new
Wi-Fi/BLE addresses can earn XP without creating unlocated upload rows.
Old saves migrate their previous rewards; close the app before reinstalling.

For a fresh-reset Pager running **2.0.0-stable**, use the complete
[Portuguese install and test guide](INSTALAR_2_0.md) and
`hackomon-instalar-0.8.6.zip`: extract everything and double-click `INSTALAR.cmd`
(app + original stock-theme overlay + Windows setup).
That installer explicitly provisions missing base dependencies; the app itself
does not install packages. Its theme validation is a file/layout check, not
physical firmware validation.

Version 0.8.2 fixes startup under the Hak5 temporary runner: `_PAYLOAD_HOME`
locates the installed app and bundled library. The installer checks that same
temporary-launch path before reporting success. Reapply the installer to fix
an earlier successful installation that nevertheless asks for PAGERCTL.

Version 0.8.3 adds native Recon AP fallback when auto Wi-Fi scanning has no free
managed interface, fails or returns no APs. Only a recognized local database
and observations <=30 seconds old are accepted. `python3-sqlite3` may be needed.
Radio errors remain visible separately from GPS. Double-click `DIAGNOSTICAR.cmd`
to collect a read-only, identifier-free support report if counters remain zero.

Version 0.8.4 accepts decimal iw frequencies and native BLOB-encoded addresses,
prioritizes native Wi-Fi observations, and reads recent LE records from the
native Blue5 database when present. It does not enable a competing bluetoothd
or reconfigure the Bluetooth controller. Native database compatibility was
based on a real 2.0.0-stable device report; full expedition validation is separate.

For the existing network field flow, see [TESTE_RAPIDO.txt](TESTE_RAPIDO.txt) in the repository
or `LEIA_PRIMEIRO.txt` at the root of the release ZIP. Expeditions use the same
installed dependencies; no firmware is replaced and the existing pet save remains.

## Prerequisites

- Stock Hak5 Pager firmware with SSH access.
- The Pager's internal eMMC storage mounted at `/mmc`.
- `python3` and `python3-ctypes` installed to MMC.
- The MIT-licensed PAGERCTL utility, including `libpagerctl.so`.

PAGERCTL source and build/install instructions are available from its
[upstream repository](https://github.com/pineapple-pager-projects/pineapple_pager_pagerctl).
Hackomon checks these common locations:

- `/root/payloads/user/utilities/PAGERCTL/libpagerctl.so`
- `/mmc/root/payloads/user/utilities/PAGERCTL/libpagerctl.so`
- `hackomon/lib/libpagerctl.so`

## Copy the payload

From a computer on the Pager's management connection, extract the release and
copy the folder:

```text
scp -r hackomon root@172.16.52.1:/root/payloads/user/games/
```

Then open **Payloads → User → Games → Hackomon** on the Pager.

The launcher does not install packages or download remote scripts. If Python or
PAGERCTL is missing, it shows the missing dependency and exits without changing
the system.

## Save data

Optional network/laboratory setup is in [NETWORKS.md](NETWORKS.md). Copy the
included configuration example to the save directory and supply the actual
radio interfaces and local account key there. The installed app otherwise
continues to work as a pet without network dependencies.

Client visits in 0.5.0 do not need a pre-registered BSSID or GPS: choose
**Redes / Laboratorio → Atendimento** and select the client's AP from the list.
The app tries to find a free managed radio automatically. A supported driver,
`iw`, `ip`, and the optional capture/dictionary tools are still device dependencies.
If radio auto-detection cannot find a free interface, set `wifi_interface` once;
that is device setup, not registering each customer network.

The default save lives at:

```text
/mmc/root/hackomon/state.json
```

For a temporary test save, set `HACKOMON_DATA_DIR` before launching the Python
entry point.

## Uninstall

Remove only the payload directory:

```text
rm -r /root/payloads/user/games/hackomon
```

The save remains intact. Remove `/mmc/root/hackomon` separately only if
you intentionally want to erase all progress.

