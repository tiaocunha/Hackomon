# Install on a WiFi Pineapple Pager

For a fresh-reset Pager running **2.0.0-stable**, use the complete
[Portuguese install and test guide](INSTALAR_2_0.md) and
`hackomon-instalar-0.8.2.zip`: extract everything and double-click `INSTALAR.cmd`
(app + original stock-theme overlay + Windows setup).
That installer explicitly provisions missing base dependencies; the app itself
does not install packages. Its theme validation is a file/layout check, not
physical firmware validation.

Version 0.8.2 fixes startup under the Hak5 temporary runner: `_PAYLOAD_HOME`
locates the installed app and bundled library. The installer checks that same
temporary-launch path before reporting success. Reapply the installer to fix
an earlier successful installation that nevertheless asks for PAGERCTL.

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

