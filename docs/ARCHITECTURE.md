# Architecture

## Resumable WDGWars synchronization (0.7.0)

`wdgwars` implements the fixed HTTPS account/upload endpoints, redirect refusal,
bounded responses and typed failure outcomes. `sync.Manager` consumes only the
owned expedition CSV paths and the explicit quick-queue snapshot. It validates
and serializes discovery fields, stages bounded payloads privately, and atomically
checkpoints byte offsets/prefix hashes together with queue receipts after server
confirmation. A persisted `sending` state makes crash recovery conservative.

Upload work does not acquire the radio lock. UI progress travels through a
bounded queue; only the main app loop removes confirmed quick-queue records.
Source files are never deleted. Acknowledged temporary payloads can be removed;
archived ambiguous payloads remain private. See [WDGWARS.md](WDGWARS.md).

## Expeditions (0.6.0)

`expedition.Pump` owns a GPS sampler and a serial radio scan thread. A shared
radio lock coordinates discovery and manually selected network assessments.
Workers emit bounded events; only the app loop updates game XP and the journal.
The journal appends private route/observation records, writes a discovery-only
CSV and atomically checkpoints a compact summary. It reconstructs deduplication
from prior records and restores paused, without any active test target.
See [EXPEDITIONS.md](EXPEDITIONS.md) for timestamp, storage and interruption limits.

## Optional network and lab adapters (0.4.0)

The `radio` module invokes bounded installed Linux tools and consumes fresh GPSD
TPV fixes. `exploration` normalizes discovery records, awards capped unique XP
and creates the small persistent upload queue. `wdgwars` serializes only discovery
fields and sends authenticated HTTPS multipart requests without redirects.
`lab` uses an exact, expiring BSSID scope, captures local EAPOL and runs a bounded
offline dictionary test. `bluetooth_lab` uses a separate expiring Bluetooth
address, labels cached metadata and queries classic SDP service records. Reports
remain private and separate from uploads. `network_config` reads device configuration.

The app worker does not mutate game state. Results return through a thread-safe
queue and the main loop updates XP, evolution and persistence atomically in the
same save. Pending network actions complete before leaving; account credentials
and recovered secrets are never placed in the save or upload data. See
[NETWORKS.md](NETWORKS.md) for limits and validation boundaries.

`visit` adds a separate client-session workflow: automatic free-interface
selection, passive AP listing without GPS, on-screen single-AP scope and bounded
assessment. It may create/tune an ephemeral monitor on an idle dedicated PHY,
then removes it after capture. Cached scan evidence older than five minutes is
rejected. The app keeps target choices in RAM only and persists local JSON/text
reports without putting client data in the map queue. Discovery parsing includes
advertised security facts but never treats them as proven vulnerabilities.

## Boundaries

Hackomon is an ordinary payload under `/root/payloads/user/games`. Starting in
0.10.3, `stock_ui` lends the framebuffer by suspending only the recognized
`/pineapple/pineapple` visual process, leaving its service and native backends
running. The stock 2.0.0 `pineapplepager stop` hook also stops/deletes PineAP;
the older launcher incorrectly treated it as a UI-only stop.

A separate guard owns the visual PID/starttime and resumes it on app exit,
start failure, crash or handled termination. It refuses an already suspended
UI and checks identity before resume. Linux signal numbers come from Python
on the device, including MIPS. The app runs in its own process group, and the
guard asks it to clean up on termination. Force-killing the guard itself cannot
run cleanup. No firmware file, boot setting or GPS configuration is replaced.

The app is split into five small layers:

1. `catalog.py` validates and indexes the generated 250-creature catalog.
2. `model.py` owns care stats, elapsed-time decay and serializable game state.
3. `evolution.py` applies the level/care/wellness gates.
4. `sprites.py` turns compact descriptors into 32×32 pixel frames and merges
   adjacent pixels into framebuffer-friendly runs.
5. `backgrounds.py` composes a personalized low-cost environment for every
   creature and evolutionary stage.
6. `app.py` and `ui.py` implement the input loop and 480×222 screens.

`pager_backend.py` is the only hardware-specific module. It uses a minimal
`ctypes` binding to the external MIT-licensed `libpagerctl.so`. Tests use a
memory display and do not need Pager hardware.

## Bestiary

The catalog is generated deterministically by `tools/generate_bestiary.py`.
Each of 10 families supplies a body silhouette; each of five lines supplies a
palette, motif and stable seed; and each of five stages increases size and
ornamentation. The generated JSON is checked into the payload so the Pager does
not spend CPU or storage generating metadata at first launch.

Sprites are rendered directly from descriptors. This avoids 1,000+ small image
files while still giving every creature a stable, distinct sprite. A 32×32
frame is expanded to 4× pixels on screen and drawn as horizontal color runs.
Each family owns a different anatomy, each evolutionary line adds its own
silhouette details, and a derived seven-tone palette supplies outline, shadow,
highlight and glow without enlarging the catalog.

Backgrounds combine the creature family, line motif, palette, stable seed and
stage. Eggs receive contained nest scenes; young stages add landmarks; adults
receive full environments; rare forms add a two-frame ambient effect. They use
the same horizontal-run compaction as sprites so scenery remains practical on
the Pager framebuffer.

## Persistence

The state store writes a temporary file, flushes and fsyncs it, then replaces
the previous save atomically. Invalid saves are quarantined with a timestamp
instead of being silently overwritten. The schema is versioned.

## Progression and evolution gates (0.9.0)

In 0.10.0 a permanent trainer receives all XP, while only the living companion
receives pet XP. Active field counters age each pet without wall-clock aging.
The adult lifecycle lasts 10 valid active hours, followed by a single memorial
entry; the last 200 details are bounded in the atomic state. Successor eggs,
incubation, lineage collection and young-stage branch offers share that save.
Old saves retain the current pet and start active age at zero; a private
pre-generation backup is created on first compatible loading.

The XP cost for level L to L+1 is 40 + 5*(L-1), up to level 100. Old saves
retain XP and earned levels via a one-time level credit. Revisit receipts
enforce a six-hour interval per address/type. Field bonus receipts are saved
atomically with XP and bond; only the current expedition is resumable in the UI.
See [PROGRESSION.md](PROGRESSION.md) for reward rates and migration details.

| Target stage | Minimum level | Care + field bond | Minimum wellness |
| --- | ---: | ---: | ---: |
| Filhote | 3 | 4 | 0 |
| Jovem | 8 | 10 | 35 |
| Adulto | 16 | 20 | 45 |
| Forma rara | 25 | 35 | 55 |

Wellness is the integer average of hunger, happiness and energy. At most one
stage is advanced per care/field reward event. Young-stage advancement now
waits for an explicit offered in-family line choice. Existing forms never regress.

