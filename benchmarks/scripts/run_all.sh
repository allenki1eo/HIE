#!/usr/bin/env bash
# Reproduce the v0.1 benchmark from a clean checkout (after `pip install -e ".[dev]"`).
set -euo pipefail
test -z "$(git status --porcelain)" || { echo "Commit your changes first: results record the commit." >&2; exit 1; }
hie data download 0006_20160722_115157_431 0006_20160727_200154_366 0043_20160917_113940_016 \
  0047_20160609_133132_746 0127_20161018_111029_303 0127_20161107_171749_524 0155_20160816_115629_383 \
  5066_20160413_171343_904 5066_20160504_181920_148 5066_20160504_184741_899 5a9e_20150328_173812_141 \
  c1b1_20150424_201100_596
hie bench synthetic --split test
hie bench hdrplus
