#! /usr/bin/env python3
"""Convert a Chirp CSV export to a Baofeng DM-32 CPS channel CSV.

Usage:
    chirp2dm32 input_chirp.csv [output_dm32.csv]
    chirp2dm32 --template existing_dm32.csv input_chirp.csv output_dm32.csv

Mapping notes:
  * Chirp Duplex "off" (receive-only) sets TX Frequency = RX Frequency and
    Forbid TX = 1, so the DM-32 will not transmit on those channels.
  * Chirp Mode FM -> 25KHz, NFM -> 12.5KHz.
  * Chirp Power >= 4W -> High, otherwise Low (the DM-32 has two levels).
  * Tone / TSQL / DTCS / Cross modes are mapped into CTC/DCS Encode/Decode.
    DCS codes are written as D023N / D023I.
  * Every other DM-32 column is filled from a default analog row.  Pass
    --template with an existing DM-32 export to take the header and default
    values from its first data row instead.
"""
import argparse
import csv
import sys

DM32_HEADER = [
    "No.", "Channel Name", "Channel Type", "RX Frequency[MHz]",
    "TX Frequency[MHz]", "Power", "Band Width", "Scan List", "TX Admit",
    "Emergency System", "Squelch Level", "APRS Report Type", "Forbid TX",
    "APRS Receive", "Forbid Talkaround", "Auto Scan", "Lone Work",
    "Emergency Indicator", "Emergency ACK", "Analog APRS PTT Mode",
    "Digital APRS PTT Mode", "TX Contact", "RX Group List", "Color Code",
    "Time Slot", "Encryption", "Encryption ID", "APRS Report Channel",
    "Direct Dual Mode", "Private Confirm", "Short Data Confirm", "DMR ID",
    "CTC/DCS Decode", "CTC/DCS Encode", "Scramble", "RX Squelch Mode",
    "Signaling Type", "PTT ID", "VOX Function", "PTT ID Display",
]

# Defaults for a plain analog channel, taken from a DM-32 CPS export.
DM32_DEFAULTS = {
    "Channel Type": "Analog",
    "Power": "Low",
    "Band Width": "12.5KHz",
    "Scan List": "None",
    "TX Admit": "Allow TX",
    "Emergency System": "None",
    "Squelch Level": "3",
    "APRS Report Type": "Off",
    "Forbid TX": "0",
    "APRS Receive": "0",
    "Forbid Talkaround": "0",
    "Auto Scan": "0",
    "Lone Work": "0",
    "Emergency Indicator": "0",
    "Emergency ACK": "0",
    "Analog APRS PTT Mode": "0",
    "Digital APRS PTT Mode": "0",
    "TX Contact": "None",
    "RX Group List": "None",
    "Color Code": "0",
    "Time Slot": "Slot 1",
    "Encryption": "0",
    "Encryption ID": "None",
    "APRS Report Channel": "1",
    "Direct Dual Mode": "0",
    "Private Confirm": "0",
    "Short Data Confirm": "0",
    "DMR ID": "LIME",
    "CTC/DCS Decode": "None",
    "CTC/DCS Encode": "None",
    "Scramble": "None",
    "RX Squelch Mode": "Carrier/CTC",
    "Signaling Type": "None",
    "PTT ID": "OFF",
    "VOX Function": "0",
    "PTT ID Display": "0",
}


def fmt_freq(mhz: float) -> str:
    return f"{mhz:.5f}"


def fmt_ctcss(hz: str) -> str:
    return f"{float(hz):.1f}"


def fmt_dcs(code: str, inverted: bool) -> str:
    return f"D{int(code):03d}{'I' if inverted else 'N'}"


def tones(row: dict) -> tuple[str, str]:
    """Return (decode, encode) for the DM-32 from a Chirp row."""
    mode = row.get("Tone", "").strip()
    rtone = row.get("rToneFreq", "88.5")
    ctone = row.get("cToneFreq", "88.5")
    dtcs = row.get("DtcsCode", "023")
    rx_dtcs = row.get("RxDtcsCode", dtcs) or dtcs
    pol = row.get("DtcsPolarity", "NN") or "NN"
    tx_inv, rx_inv = pol[0] == "R", pol[-1] == "R"

    if mode == "":
        return "None", "None"
    if mode == "Tone":
        return "None", fmt_ctcss(rtone)
    if mode == "TSQL":
        return fmt_ctcss(ctone), fmt_ctcss(ctone)
    if mode == "DTCS":
        return fmt_dcs(dtcs, rx_inv), fmt_dcs(dtcs, tx_inv)
    if mode == "Cross":
        tx_kind, rx_kind = row.get("CrossMode", "Tone->Tone").split("->")
        enc = {"Tone": lambda: fmt_ctcss(rtone),
               "DTCS": lambda: fmt_dcs(dtcs, tx_inv),
               "": lambda: "None"}[tx_kind]()
        dec = {"Tone": lambda: fmt_ctcss(ctone),
               "DTCS": lambda: fmt_dcs(rx_dtcs, rx_inv),
               "": lambda: "None"}[rx_kind]()
        return dec, enc
    raise ValueError(f"Unknown Chirp tone mode {mode!r} on {row.get('Name')}")


def power(chirp_power: str) -> str:
    try:
        watts = float(chirp_power.rstrip("Ww"))
    except ValueError:
        return "Low"
    return "High" if watts >= 4.0 else "Low"


def convert_row(row: dict, number: int, defaults: dict) -> dict:
    out = dict(defaults)
    rx = float(row["Frequency"])
    offset = float(row.get("Offset") or 0)
    duplex = row.get("Duplex", "").strip()

    if duplex == "+":
        tx = rx + offset
    elif duplex == "-":
        tx = rx - offset
    elif duplex == "split":
        tx = offset
    else:  # "" (simplex) or "off" (RX only)
        tx = rx
    if duplex == "off":
        out["Forbid TX"] = "1"

    dec, enc = tones(row)
    out.update({
        "No.": str(number),
        "Channel Name": row["Name"].strip(),
        "Channel Type": "Analog",
        "RX Frequency[MHz]": fmt_freq(rx),
        "TX Frequency[MHz]": fmt_freq(tx),
        "Power": power(row.get("Power", "")),
        "Band Width": "12.5KHz" if row.get("Mode", "FM") == "NFM" else "25KHz",
        "CTC/DCS Decode": dec,
        "CTC/DCS Encode": enc,
    })
    return out


def load_template(path: str) -> tuple[list, dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        first = next(reader, None)
    defaults = dict(DM32_DEFAULTS)
    if first:
        defaults.update({k: v for k, v in first.items() if k in header})
    return header, defaults


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="Chirp CSV export")
    ap.add_argument("output", nargs="?", help="DM-32 CSV to write (default: stdout)")
    ap.add_argument("--template", help="existing DM-32 CSV to copy header/defaults from")
    ap.add_argument("--keep-location", action="store_true",
                    help="use Chirp's Location column as the DM-32 channel number "
                         "instead of renumbering from --start")
    ap.add_argument("--start", type=int, default=1,
                    help="first DM-32 channel number when renumbering (default 1)")
    args = ap.parse_args()

    if args.template:
        header, defaults = load_template(args.template)
    else:
        header, defaults = DM32_HEADER, dict(DM32_DEFAULTS)

    with open(args.input, newline="", encoding="utf-8-sig") as f:
        chirp_rows = [r for r in csv.DictReader(f) if r.get("Frequency")]

    out_rows = []
    for i, row in enumerate(chirp_rows):
        number = int(row["Location"]) if args.keep_location else args.start + i
        out_rows.append(convert_row(row, number, defaults))

    out = open(args.output, "w", newline="", encoding="utf-8") if args.output else sys.stdout
    with out:
        writer = csv.DictWriter(out, fieldnames=header, lineterminator="\r\n",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"Converted {len(out_rows)} channels", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
