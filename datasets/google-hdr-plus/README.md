# Google HDR+ Burst Photography Dataset

**Source:** Google Research, released 2018-02-12 (last data fix 2020-12-15).
**Paper:** S. W. Hasinoff, D. Sharlet, R. Geiss, A. Adams, J. T. Barron, F. Kainz, J. Chen, M. Levoy,
"Burst photography for high dynamic range and low-light imaging on mobile cameras",
ACM Transactions on Graphics 35(6) (Proc. SIGGRAPH Asia 2016).
**Licence:** Creative Commons **CC BY-SA** (as stated in the dataset README). Google asks that usage stay
scientific and "in good taste": the subjects include the authors' friends and family.
**Official pages:** [blog announcement](https://research.google/blog/introducing-the-hdr-burst-photography-dataset/) ·
[paper](https://research.google/pubs/burst-photography-for-high-dynamic-range-and-low-light-imaging-on-mobile-cameras/) ·
[dataset README](https://storage.googleapis.com/hdrplusdata/README.html) · bucket `gs://hdrplusdata`.

**The dataset is not redistributed in this repository.** This folder is git-ignored except for this file.

## Citation

```bibtex
@article{hasinoff2016burst,
  author  = {Samuel W. Hasinoff and Dillon Sharlet and Ryan Geiss and Andrew Adams and
             Jonathan T. Barron and Florian Kainz and Jiawen Chen and Marc Levoy},
  title   = {Burst photography for high dynamic range and low-light imaging on mobile cameras},
  journal = {ACM Transactions on Graphics (Proc. SIGGRAPH Asia)},
  volume  = {35}, number = {6}, year = {2016},
}
```

## Getting the data

Anonymous HTTPS download, MD5-verified against the bucket's object metadata:

```bash
hie data list                                  # 153 bursts in the curated subset
hie data download 0006_20160722_115157_431 …   # bursts + results_20171023
```

Or mirror everything with Google's own tool: `gsutil -m cp -r gs://hdrplusdata/20171106_subset .`.
Set `HIE_HDRPLUS_ROOT` to use a location outside the repository.

Every downloaded file is appended to `manifest.jsonl` (object name, size, MD5, bucket generation,
URL, download time), which records the exact dataset version an experiment used.

## Archive layout (inspected 2026-09-22, not assumed)

The local mirror keeps the bucket's layout unchanged so provenance stays unambiguous:

```text
20171106_subset/                         153 bursts, ~30 GB of DNGs (full set: 20171106/, 3,640 bursts)
├── bursts/<burst_id>/
│   ├── payload_N000.dng …               input frames (2–10), Bayer DNG, lossless-JPEG tiles
│   ├── lens_shading_map_N000.tiff …     (h, w, 4) float gains, channel order R, Gr, Gb, B
│   ├── rgb2rgb.txt                      3×3, white-balanced camera RGB → linear sRGB, row-major
│   └── timing.txt                       on-device align/merge/finish timings (optional)
├── results_20161014/<burst_id>/         pipeline as in the paper
└── results_20171023/<burst_id>/         later tuned pipeline (HIE default)
    ├── merged.dng                       HDR+ align+merge output (higher precision; GainMap in OpcodeList2)
    ├── final.jpg                        HDR+ finished output, upright, quality 95
    └── reference_frame.txt              zero-based reference frame index
```

Mapping to the brief's suggested folders: `raw/` → `bursts/*/payload_*.dng`;
`metadata/` → sidecars and DNG tags; `hdrplus_intermediate/` → `results_*/merged.dng`;
`hdrplus_final/` → `results_*/final.jpg`. HIE outputs go to `benchmarks/results/`, never into this tree.

## Facts measured on the downloaded files

- Pixel-era frames are 4048×3036, 10-bit data in 16-bit containers, CFA **BGGR**, black level
  **fractional** (e.g. 63.75 / 63.5): LibRaw rounds these to 63, so HIE reads DNG tags directly.
- Each DNG carries a `NoiseProfile` (S, O). Our burst- and single-image estimators agree within
  ~10–25 % on most bursts; on one ISO-755 burst the profile is ~40 % above the measured noise.
- The 2015 Nexus 5 bursts (3280×2464, RGGB) store ExposureTime/ISO in IFD0 instead of the EXIF IFD,
  have **no NoiseProfile**, and their **last frame uses a longer exposure**. Google's README says
  its results ignore those frames. HIE detects the mismatch and excludes the frame *with a recorded
  note*; the loader itself never drops frames.
- `merged.dng` keeps lens shading as a GainMap opcode, and its peak gain (4.397) matches the sidecar
  `lens_shading_map` of the same burst, which cross-validates HIE's opcode parser.
- Google's `rgb2rgb.txt` is close to the matrix HIE derives from the DNG ColorMatrix tags, but more
  saturated (max element difference 0.15 on burst 0006_20160722_115157_431).

## Bursts used in EXP-hdrplus (12)

Chosen to span devices, ISO 50–2056 and day to night; see `benchmarks/reports/` for per-burst metadata.

```text
0006_20160722_115157_431  0006_20160727_200154_366  0043_20160917_113940_016  0047_20160609_133132_746
0127_20161018_111029_303  0127_20161107_171749_524  0155_20160816_115629_383  5066_20160413_171343_904
5066_20160504_181920_148  5066_20160504_184741_899  5a9e_20150328_173812_141  c1b1_20150424_201100_596
```
