# Architecture

## Optional network and lab adapters (0.4.0)

The `radio` module invokes bounded installed Linux tools and consumes fresh GPSD
TPV fixes. `exploration` normalizes discovery records, awards capped unique XP
and creates the small persistent upload queue. `wdgwars` serializes only discovery
fields and sends authenticated HTTPS multipart requests without redirects.
`lab` uses an exact, expiring BSSID scope, captures local EAPOL and runs a bounded
offline dictionary test. `network_config` reads private device configuration.

The app worker does not mutate game state. Results return through a thread-safe
queue and the main loop updates XP, evolution and persistence atomically in the
same save. Pending network actions complete before leaving; account credentials
and recovered secrets are never placed in the save or upload data. See
[NETWORKS.md](NETWORKS.md) for limits and validation boundaries.

## Boundaries

Hackomon is an ordinary payload under `/root/payloads/user/games`. Its launcher
temporarily stops only the stock `pineapplepager` UI service to obtain the
framebuffer, then restores that service on every normal, error or signal exit.
It does not replace firmware files or alter boot configuration.

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

## Evolution gates

| Target stage | Minimum level | Care points | Minimum wellness |
| --- | ---: | ---: | ---: |
| Filhote | 3 | 4 | 0 |
| Jovem | 6 | 10 | 35 |
| Adulto | 10 | 20 | 45 |
| Forma rara | 15 | 35 | 55 |

Wellness is the integer average of hunger, happiness and energy. At most one
stage is advanced per successful care action, so an old or imported save cannot
skip the evolution presentation.

