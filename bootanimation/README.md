# bootanimation.zip

Generated (not hand-made) and committed here: `tools/make-bootanimation.sh` renders deterministic
Tokyo Night frames (flat `#1a1b26` sky, moon, pagoda, progress dots; 1080×2424 @ 30 fps) and
mounts the zip with Python stdlib `zipfile` (`ZIP_STORED`, fixed `date_time`), so re-running the
script reproduces the identical bytes.

Inside the zip: `desc.txt` (`1080 2424 30`, `p 1 0 part0`, `p 0 0 part1`), `part0/` intro (plays
once) and `part1/` loop; every entry is Stored (no Deflate). `omarchy.mk` copies it to
`/product/media/bootanimation.zip` when the file exists.
