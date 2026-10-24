# Pool datapack patch

The two bot functions from the Pool and Billiards **datapack** v1.3.7 (Squid Workshop, MPL-2.0) as
changed for Minecraft 26.x: they hid the balls by giving them an air item, which 26.x rejects, so they
now hide the balls (and the server's lighting overlays riding them) by view range. Lines marked
"Antigravity Server". They go in `data/pool/function/classes/bot/generic/`.
