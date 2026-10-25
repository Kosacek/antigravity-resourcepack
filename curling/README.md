# Curling resource pack assets (namespace `curling`)

Build:    `python build_assets.py <out folder>`   (Pillow only; reads sizes from `curling/config.py`)
Preview:  `python preview_assets.py <out folder> <out.png>`   (Pillow + numpy; also writes `<out>_stone.png`)

Output: `<out>/assets/curling/{items,models/item,textures/item}`. 16 model units = 1 block.

| item | model | notes |
|------|-------|-------|
| `stone_red`, `stone_yellow` | 0.6 x 0.24 body (+ handle, 0.38 tall total) | 581 thin tangent quads: 32 around x 15 profile rings (striking band, bevels, concave cup) plus a gooseneck handle (+x) and dark bolt. **Unlit** (tint #FEFDFC = -66052, `shade:false`, `tintindex:0`); shading is painted by height only, so spinning is safe. Textures: shared `stone_granite.png`, `stone_handle_<team>.png`. Bottom at y=8, axis x=z=8. |
| `broom_red`, `broom_yellow` | 0.54 x 1.82 x 0.18 | pad 0.5 x 0.15, dark bristles, shaft 1.5 + grip. Lit normally. Pad bottom at y=0. |
| `delivery_stick` | 0.30 x 1.51 x 0.12 | black shaft, orange grip tape, forked head. Lit normally. |
| `house` | 1 x 1 flat face (up) at y=8 | 512 px texture, 12-ft blue / 8-ft white / 4-ft red / button white, black outlines, transparent outside. **Unlit**. Scale to `2*RING_RADII[0]`. |
| `aim_marker` | 0.5 x 0.5 flat face (up) at y=8 | lime ring + crosshair, see-through middle. **Unlit**. |

Brooms and stick carry `display.thirdperson_righthand` (rotation `[90,0,0]`, translation `[0,0,-4]`:
shaft upright, pad at the feet when the hand is ~0.75 blocks up) and `firstperson_righthand`.
Textures use only opaque or fully transparent pixels. The pack builder only has to copy the
`assets/curling` tree into the pack.
