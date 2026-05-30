"""Probe: can we decode the public.getDispensary blob to recover phone?

weed.th's public.getDispensary endpoint returns a shop record where the
`dispensary` field is encoded as a long base64-looking string. If that decodes
to the full shop record (including phone), we can skip auth + skip the browser
entirely for the contact_method=phone API.
"""

import base64
import json
import re
import sys
import urllib.parse

import requests

UUID = "ae7ba0c9-5842-4387-8245-7c6172141f8c"
NAME = "BoomTreeHC"
ENDPOINT = "https://weed.th/api/trpc/public.getDispensary"


def fetch_full() -> dict:
    params = {"input": json.dumps({"json": {"id": UUID}})}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    r = requests.get(ENDPOINT, params=params, headers=headers, timeout=15)
    print(f"[probe] status={r.status_code} url={r.url[:120]}...")
    return r.json()


def try_decodings(blob: str) -> None:
    print(f"\n[probe] blob length: {len(blob)} chars")
    print(f"[probe] blob preview: {blob[:120]}...")

    # 1) Plain base64
    for variant_name, variant in [("standard", blob), ("urlsafe", blob.replace("+", "-").replace("/", "_"))]:
        # Try with padding adjustments
        padded = variant + "=" * ((4 - len(variant) % 4) % 4)
        try:
            raw = base64.b64decode(padded, validate=False)
            preview = raw[:200]
            printable = sum(1 for b in preview if 32 <= b < 127)
            ratio = printable / max(len(preview), 1)
            print(f"\n[probe] base64 {variant_name}: {len(raw)} bytes, printable={ratio:.0%}")
            print(f"  first 200 bytes (latin1): {raw[:200].decode('latin1', errors='replace')!r}")
            if ratio > 0.7:
                # Try as utf-8 / json
                try:
                    text = raw.decode("utf-8")
                    print(f"  UTF-8 decode OK, first 300 chars: {text[:300]}")
                except UnicodeDecodeError as e:
                    print(f"  UTF-8 decode failed: {e}")
                # Phone search in decoded bytes
                phone_hits = re.findall(rb"\+66[\d \-]{6,15}|\b0[689]\d[\d \-]{6,12}", raw)
                print(f"  Phone-pattern hits in decoded bytes: {phone_hits}")
        except Exception as e:
            print(f"  base64 {variant_name} decode failed: {e}")

    # 2) Maybe XOR with a known key (shop UUID? a static key?). Check entropy first.
    try:
        raw = base64.b64decode(blob + "=" * ((4 - len(blob) % 4) % 4), validate=False)
        # If most bytes are within a narrow range (e.g. all 0-127), XOR with single byte may reveal text.
        from collections import Counter
        cnts = Counter(raw)
        top5 = cnts.most_common(5)
        print(f"\n[probe] top byte frequencies in decoded: {top5}")
        # Try single-byte XOR with each of the top values
        for byte_val, _ in top5:
            xored = bytes(b ^ byte_val for b in raw[:300])
            printable = sum(1 for b in xored if 32 <= b < 127 or b in (9, 10, 13))
            ratio = printable / len(xored)
            if ratio > 0.85:
                print(f"  XOR with 0x{byte_val:02x}: printable={ratio:.0%}")
                try:
                    print(f"  preview: {xored.decode('utf-8', errors='replace')[:200]!r}")
                except Exception:
                    pass
        # Try XOR with shop UUID bytes (32 hex chars = 16 raw bytes)
        uuid_bytes = bytes.fromhex(UUID.replace("-", ""))
        xored = bytes(b ^ uuid_bytes[i % len(uuid_bytes)] for i, b in enumerate(raw[:300]))
        printable = sum(1 for b in xored if 32 <= b < 127 or b in (9, 10, 13))
        print(f"  XOR with UUID bytes: printable={printable / len(xored):.0%}")
        if printable / len(xored) > 0.7:
            print(f"  preview: {xored.decode('utf-8', errors='replace')[:200]!r}")
    except Exception as e:
        print(f"[probe] xor-analysis failed: {e}")


def main() -> int:
    try:
        data = fetch_full()
    except Exception as e:
        print(f"FETCH FAILED: {e}")
        return 1

    # Print top-level structure
    print(f"\n[probe] response top-level keys: {list(data.keys())}")
    print(f"[probe] raw response (first 2000 chars):")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
    print("..." if len(json.dumps(data)) > 2000 else "")

    # Phone search in raw response text
    raw_text = json.dumps(data, ensure_ascii=False)
    phone_hits = re.findall(r"\+66[\d \-]{6,15}|\b0[689]\d[\d \-]{6,12}", raw_text)
    print(f"\n[probe] phone-pattern hits in raw JSON: {phone_hits or '(none)'}")
    if NAME.lower() in raw_text.lower():
        print(f"[probe] shop name {NAME!r} appears in response: yes")
    else:
        print(f"[probe] shop name {NAME!r} appears in response: NO -- response may be encoded")

    # Drill into result.data.json.dispensary
    try:
        dispensary = data["result"]["data"]["json"]["dispensary"]
        if isinstance(dispensary, str):
            try_decodings(dispensary)
        else:
            print(f"\n[probe] dispensary is not a string: {type(dispensary).__name__}")
            print(f"  keys (if dict): {list(dispensary.keys()) if isinstance(dispensary, dict) else 'n/a'}")
    except KeyError as e:
        print(f"[probe] could not find result.data.json.dispensary: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
