# Networks and office laboratory — 0.4.0

## Status

Implemented: Wi-Fi discovery, BLE discovery, CSV export, WDGWars upload,
target-scoped EAPOL capture and an offline WPA/WPA2-PSK dictionary test. Desktop
tests use fixtures and mocked commands. Physical radios, GPS, actual password
recovery, live API acceptance and Wardrive Go import have NOT been validated.
The user identified an authorized office lab and an external GPS; development
has no connection to that hardware or account.

## Local setup

Copy `hackomon/config.example.json` to `/mmc/root/hackomon/config.json`. Set
`wifi_interface` to the actual scanning interface and `wdgwars_api_key` to your
profile key. Keep this file private (`chmod 600` on the Pager). The environment
variable `HACKOMON_WDGWARS_API_KEY` can supply the key instead. No account key is
bundled, printed or needed in chat.

Optional installed dependencies: `iw`; BlueZ `bluetoothctl` supporting `scan le`
and `--timeout`; local `gpsd` on port 2947 connected to the external GPS; Python
SSL support and CA certificates for HTTPS. Lab operations additionally require
`tcpdump` and `aircrack-ng`. Hackomon installs nothing, changes no radio modes or
channels, and does not start/stop Bluetooth or GPS services. Unsupported commands
report failure and award no XP. Existing Internet connectivity is needed to sync.

## Discovery and XP

Choose **Redes / Laboratorio** on the home screen. No scan runs at startup.
Operations run in a worker; the screen keeps rendering, but waits for the
bounded operation to complete before leaving.

- Wi-Fi: `iw dev <interface> scan passive`, bounded to 20 seconds.
- BLE: `bluetoothctl --timeout 8 scan le`, without pairing/connecting. LE
  discovery may send scan requests; it is not radio-silent capture.
- GPS: mode >= 2, UTC fix within 15 seconds, both horizontal error estimates
  present and <= 100 metres, before and after each scan. Missing fix rejects
  the batch. Movement over 30 metres rejects it. These are stationary snapshots,
  not continuous route mapping: the final fix approximates positions during the
  scan, and its reported accuracy does not include all movement/time error.
- New Wi-Fi address: **2 XP**. New BLE address: **1 XP**. Maximum **120 discovery
  XP per UTC day**. No care points: evolution still requires pet care.
- Reward identities use address hashes. BLE random addresses can represent one
  device more than once; the daily cap limits the effect. No de-randomization.
- Names ending `_nomap` or `_optout` are excluded. Privacy zones/blacklists are
  not implemented. Avoid collecting where you do not intend to share locations.
- At most one queued sample per address. A later UTC day can queue the same
  address again after sync, without more XP. Limits: 500 pending records and
  10,000 known addresses. At capacity new records stop being accepted. Queue,
  ledger and XP share the atomic game save; 0.3 saves remain readable.

## Export and upload

**Exportar CSV** writes `/mmc/root/hackomon/discoveries.csv` in WigleWifi-1.6
format, intended for Wardrive Go CSV import. This is file compatibility, not a
live phone connection. Export snapshots the pending queue: export before sync
if you also need the data in the phone app.

**Enviar ao WDGWars** asks confirmation before sharing public names, addresses,
signal, timestamps, advertised security and GPS. It sends HTTPS multipart `file`
to the fixed `https://wdgwars.pl/api/upload-csv`, with `X-API-Key`. Redirects are
refused. Batches are <= 1 MB and requests time out after 15 seconds. Only HTTP
200 JSON with explicit `ok: true` or `success: true` clears the queue. Unknown
responses, async/queued responses, rate limits, TLS errors and timeouts preserve
it. There are no automatic retries. A timeout after server receipt can result in
repeat observations on manual retry. Acceptance does not guarantee map points
for every row; server-side rules still apply. Upload awards no additional XP.

The CSV whitelists discovery fields: no PCAP, password, dictionary or account
credential. Public contracts: [WDGWars developer API](https://wdgwars.pl/press),
[Wardrive Go CSV support](https://github.com/RocketGod-git/wardrive-go),
[GPSD JSON](https://gpsd.gitlab.io/gpsd/gpsd_json.html). All integration code is
original; no third-party application code is redistributed.

## Laboratory with changing equipment

For each session configure `lab.bssid`, `lab.monitor_interface` and
`lab.authorized_until` (UTC Unix seconds; at most 24 hours ahead and at least
45 seconds remaining). SSID changes on the same AP do not change authorization.
Changing hardware/BSSID requires updating the target. No wildcard, multicast or
zero addresses. The existing monitor interface must already be tuned to the lab
AP's channel. Hackomon will not create or retune it.

**Lab: capturar EAPOL** uses a target-specific BPF filter, collecting only EAPOL
involving that BSSID for <= 20 seconds / 80 packets. Reconnect an owned lab
client to generate a normal exchange. No forced disconnection. Private files
are stored in `/mmc/root/hackomon/lab/capture-*.pcap`. EAPOL presence does not
prove a complete handshake and capture alone awards no XP.

**Lab: testar dicionario** uses the latest target-matching capture from the last
24 hours and user-provided `lab/dictionary.txt` (<= 256 KB). Installed Aircrack-ng
runs an offline WPA/WPA2-PSK dictionary test for <= 30 seconds. No dictionary is
bundled/downloaded. Recovered secrets remain in private local `.key` files,
never displayed/uploaded. Confirmed recovery earns 10 XP once per BSSID.
No recovery is inconclusive: incomplete exchange, missing candidate, unsupported
setup or time limit are possible. It does not prove password strength.

WPA3-SAE, enterprise-authentication attacks, Bluetooth pairing/password tests,
mesh adapters and an autonomous attack loop are NOT implemented. BLE presently
covers discovery only; further lab tests require equipment/protocol definitions.
See [Aircrack-ng supported modes](https://www.aircrack-ng.org/doku.php?id=aircrack-ng).
