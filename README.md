# chirp2dm32

Convert a [Chirp](https://chirpmyradio.com/) CSV export into a channel CSV that the
Baofeng DM-32 CPS can import.

**Web version:** https://lrnselfreliance.github.io/chirp2dm32/ — runs entirely in
your browser, nothing is uploaded.

**Command line:**

```
./chirp2dm32.py chirp_export.csv dm32.csv
./chirp2dm32.py --keep-location chirp_export.csv dm32.csv   # keep Chirp channel numbers
./chirp2dm32.py --template existing_dm32.csv chirp_export.csv dm32.csv   # copy defaults from a CPS export
```

Requires Python 3.9+. No dependencies.

## Mapping

| Chirp | DM-32 |
|---|---|
| Frequency, Duplex, Offset | RX Frequency, TX Frequency |
| Duplex `off` | Forbid TX = 1 |
| Mode NFM / FM | Band Width 12.5KHz / 25KHz |
| Power ≥ 4 W | High, otherwise Low |
| Tone / TSQL / DTCS / Cross | CTC/DCS Encode and Decode |

All other columns are filled with plain analog defaults matching a CPS export.

## After importing: zones

The DM-32 only lets you select channels that belong to the current zone. Importing
channels does not put them in a zone. Open the Zone tab in the CPS and add the
channels. Each zone holds at most 64 channels.
