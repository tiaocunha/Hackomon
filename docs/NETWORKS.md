# Networks and office laboratory — 0.7.0

Version 0.7.0 replaces the on-device upload flow with resumable expedition and
quick-queue synchronization. See [WDGWARS.md](WDGWARS.md) for the current UI,
receipt handling and recovery rules; the legacy single-request contract below
describes the original adapter and remains available internally.

The original network/visit adapters are documented below. Version 0.6.0 adds
[expeditions and serial hybrid assessments](EXPEDITIONS.md), with separate
movement-aware GPS association and private session journals. This release is
experimental and has not been tested on physical Pager radios.

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
`tcpdump` and `aircrack-ng`. Hackomon installs nothing and does not start/stop
Bluetooth or GPS services. Only the client-visit workflow may create a temporary
monitor and tune a free radio as described below. Unsupported commands
report failure and award no XP. Existing Internet connectivity is needed to sync.

## Discovery and XP

Choose **Redes / Laboratorio** on the home screen. No scan runs at startup.
Operations run in a worker; the screen keeps rendering, but waits for the
bounded operation to complete before leaving.

These GPS discovery rules apply to map collection. The client-visit workflow
below does not require GPS and never queues client evidence for the map.

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

**WDGWars: sincronizacao e conta** opens the 0.7.0 panel. It offers full expedition
CSV/quick-queue synchronization, account validation, local receipt history,
cancellation and explicit recovery of uncertain uploads. Each data transfer asks
confirmation before sharing names, addresses, signal, timestamps, advertised
security and GPS. See [WDGWARS.md](WDGWARS.md) for the current response schemas,
checkpoints and failure rules. Server acceptance does not guarantee map points
for every row, and upload awards no additional XP.

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
mesh adapters and an autonomous attack loop are NOT implemented. BLE live operations
cover discovery; known advertised service metadata can also be inventoried locally.
Further lab tests require equipment/protocol definitions.
See [Aircrack-ng supported modes](https://www.aircrack-ng.org/doku.php?id=aircrack-ng).

## Bluetooth laboratory inventory (0.4.1)

Device kinds: `phone`, `speaker`, `headset`, `mouse`, `keyboard`. This is the
user's declared category, not an identification or vulnerability fingerprint.
Each category can use classic Bluetooth, BLE or both.

Configure the independent `lab.bluetooth` object in the supplied example:
`address` is the exact current Bluetooth address, `kind` is one category above,
`transport` is `auto`, `bredr` or `le`, and `authorized_until` is UTC Unix seconds
at most 24 hours ahead. At least 30 seconds must remain to start. Changing
equipment or a rotating BLE address requires updating this target. No wildcards.
This scope is separate from the Wi-Fi BSSID and does not require a GPS fix.

**Lab: auditar Bluetooth** first calls `bluetoothctl --timeout 5 info <address>`.
The report labels that information as the BlueZ cache: names, advertised UUIDs
and paired/bonded/trusted/connected flags describe what the Pager knows and its
own relationship. They do not establish current presence or the target's
authentication policy. For `auto`/`bredr`, installed BlueZ `sdptool browse
<address>` queries only that target's classic SDP services with a 10-second
process limit. No returned records means inconclusive, not evidence that the
device is secure or has no services. `le` mode skips SDP; it inventories known
metadata only and remains partial.

Private reports are written to `/mmc/root/hackomon/lab/bluetooth-*.json`, including
tool failures and explicit untested categories. They list no verified
vulnerabilities: visible services alone do not prove access. No PIN attempts,
pairing, GATT value reads/writes, input injection, audio capture or connection to
HID/audio profiles are performed. SDP itself uses a targeted service connection.
Missing tools are recorded as inconclusive, without installing packages or
falling back to broad searches. Nothing changes existing pairings.

A successful SDP service inventory earns **5 XP once per Bluetooth address**.
Cached data, timeouts and missing tools earn no audit XP. BLE discoveries retain
their existing capped rewards. Audit reports never enter the WDGWars queue;
only ordinary discovery records can be uploaded. Desktop tests use fixtures;
physical support on the Pager remains unvalidated. BlueZ command reference:
[upstream SDP tool](https://github.com/bluez/bluez/blob/master/tools/sdptool.c).

## Client visits without pre-registering networks (0.5.0)

Open **Redes / Laboratorio → Atendimento**. The app discovers nearby Wi-Fi APs
and shows SSID, BSSID, signal and advertised security. Choose the client's AP
and press A to assess it. No typing MAC addresses or changing the static lab
configuration for each customer. Left refreshes; B returns. Names alone cannot
establish ownership: neighboring APs and other APs sharing an SSID are not
automatically added to the selected target.

If `wifi_interface` is empty, the app enumerates `iw dev` and chooses a managed
interface reporting `Not connected.` (at most three candidates). It skips APs
and does not disconnect associated interfaces. Explicit `wifi_interface` remains
a one-time device override when automatic selection is unavailable. This does
not bypass firmware/driver limitations or install missing tools. No GPS is used.

Selection creates an in-memory, one-BSSID scope for one hour, from an observation
no older than five minutes. It does not rewrite `config.json`. Targets are not
restored on app restart. Each assessment:

1. Records advertised authentication, WPA legacy support, ciphers, WPS and RSN
   management-frame protection when present. It distinguishes unknown/partial
   announcements from open networks and records observations, not confirmed
   exploits. No observations is not a clean security bill.
2. For WPA/WPA2-compatible announcements, uses an existing monitor already on the
   selected frequency. Otherwise it may create `hkm<random>` on a free PHY having
   exactly one disconnected managed interface. PHYs carrying APs, other monitors
   or unaccounted interfaces are not auto-tuned. It runs installed `iw` and `ip`,
   activates/tunes only the temporary interface to the selected frequency, and
   removes only that interface in normal completion/error cleanup.
3. Runs the bounded target-only passive EAPOL capture. No forced reconnection;
   the authorized client may reconnect a device normally during the window.
   An EAPOL file does not establish a complete handshake.
4. If PSK is advertised and the local `lab/dictionary.txt` exists, runs the
   existing bounded offline dictionary test. No dictionary is bundled/fetched.
   Unknown AKM, enterprise authentication and SAE-only networks do not trigger
   a PSK dictionary test. A missing tool/radio/dictionary or absent exchange is
   reported as not run/inconclusive; no successful recovery is invented.
5. Writes private `visits/visit-*.json` evidence and a readable Portuguese `.txt`
   report with observations, recommendations and untested categories. Nothing
   from this workflow enters WDGWars or the map export. A completed local
   assessment earns 5 XP once per BSSID, including when capture is unavailable;
   this rewards the assessment, not an invented compromise.

Operations are bounded to roughly 90 seconds in the normal failure paths. Monitor
cleanup runs after capture, before the offline dictionary step. Cleanup failure
is shown prominently and names the temporary interface in the report; inspect
and remove it before continuing. Abrupt power loss/forced process termination
can bypass cleanup. Normal hardware behavior and cleanup still require physical
Pager validation. The app does not change firmware, but this workflow does
temporarily configure a free radio. Its disconnected managed interface's PHY
can change frequency; it is not an associated management connection.

This is an initial field-assessment workflow, not a complete autonomous pentest:
router administration, firmware CVEs, LAN service scanning, segmentation,
client isolation, WPS PIN testing and WPA3 authentication attacks remain untested.
Bluetooth still uses its separate laboratory target configuration; this visit
picker currently covers Wi-Fi APs. No unsupported test is reported as complete.
