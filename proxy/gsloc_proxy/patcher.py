from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatchTarget:
    lat: float
    lng: float
    mode: str = "clamp"
    scale: float = 1.0
    sample_limit: int = 5


@dataclass(frozen=True)
class PatchStats:
    patched: int
    old_center: tuple[float, float] | None = None
    target: tuple[float, float] | None = None
    mode: str = "clamp"
    scale: float = 1.0
    sample: tuple[str, ...] = ()
    reason: str | None = None
    accuracy: int | None = None


def read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while pos < len(buf) and shift < 70:
        c = buf[pos]
        pos += 1
        value |= (c & 0x7F) << shift
        if not (c & 0x80):
            return value, pos
        shift += 7
    raise ValueError("bad varint")


def enc_varint(value: int) -> bytes:
    value = int(value)
    if value < 0:
        value &= (1 << 64) - 1
    out = bytearray()
    while True:
        c = value & 0x7F
        value >>= 7
        if value:
            out.append(c | 0x80)
        else:
            out.append(c)
            return bytes(out)


def normalize_longitude(lon: float) -> float:
    return ((((lon + 180) % 360) + 360) % 360) - 180



def parse_fields(buf: bytes) -> list[list[object]]:
    fields: list[list[object]] = []
    pos = 0
    while pos < len(buf):
        key, pos = read_varint(buf, pos)
        field = key >> 3
        wire = key & 7
        if wire == 0:
            val, pos = read_varint(buf, pos)
        elif wire == 1:
            val = buf[pos : pos + 8]
            pos += 8
        elif wire == 2:
            ln, pos = read_varint(buf, pos)
            val = buf[pos : pos + ln]
            pos += ln
        elif wire == 5:
            val = buf[pos : pos + 4]
            pos += 4
        else:
            raise ValueError(f"unsupported wire {wire}")
        fields.append([field, wire, val])
    return fields


def build_fields(fields: list[list[object]]) -> bytes:
    out = bytearray()
    for field_obj, wire_obj, val in fields:
        field = int(field_obj)
        wire = int(wire_obj)
        out += enc_varint((field << 3) | wire)
        if wire == 0:
            out += enc_varint(int(val))
        elif wire == 2:
            data = bytes(val)
            out += enc_varint(len(data))
            out += data
        else:
            out += bytes(val)
    return bytes(out)


def patch_gsloc_payload(raw: bytes, target: PatchTarget) -> tuple[bytes, PatchStats]:
    # gs-loc gzip payload has a 10-byte prefix before protobuf.
    if len(raw) <= 10:
        return raw, PatchStats(patched=0, reason="short", mode=target.mode, scale=target.scale)

    prefix = bytearray(raw[:10])
    frame_len = (raw[8] << 8) | raw[9]
    if frame_len and 10 + frame_len <= len(raw):
        payload = raw[10 : 10 + frame_len]
        suffix = raw[10 + frame_len :]
        framed = True
    else:
        payload = raw[10:]
        suffix = b""
        framed = False
    top = parse_fields(payload)
    records = []

    for idx, item in enumerate(top):
        field, wire, val = item
        if field not in (2, 22, 24) or wire != 2:
            continue
        location_field = 2 if field == 2 else 5
        try:
            msg = parse_fields(bytes(val))
        except Exception:
            continue
        for j, sub in enumerate(msg):
            if sub[0] != location_field or sub[1] != 2:
                continue
            try:
                loc = parse_fields(bytes(sub[2]))
            except Exception:
                continue
            lat_i = lon_i = None
            for lf in loc:
                if lf[0] == 1 and lf[1] == 0:
                    lat_i = int(lf[2])
                elif lf[0] == 2 and lf[1] == 0:
                    lon_i = int(lf[2])
            if lat_i is None or lon_i is None:
                continue
            lat = lat_i / 1e8
            lon = lon_i / 1e8
            records.append((idx, msg, j, loc, lat, lon))

    if not records:
        return raw, PatchStats(patched=0, reason="no_records", mode=target.mode, scale=target.scale)

    center_lat = sum(r[4] for r in records) / len(records)
    center_lon = sum(r[5] for r in records) / len(records)
    factor = 0.05 if target.mode == "clamp" else target.scale
    sample: list[str] = []

    for idx, msg, j, loc, lat, lon in records:
        new_lat = target.lat + (lat - center_lat) * factor
        new_lon = normalize_longitude(target.lng + (lon - center_lon) * factor)
        for lf in loc:
            if lf[0] == 1 and lf[1] == 0:
                lf[2] = int(round(new_lat * 1e8))
            elif lf[0] == 2 and lf[1] == 0:
                lf[2] = int(round(new_lon * 1e8))
            elif lf[0] == 3 and lf[1] == 0:
                lf[2] = 25
        msg[j][2] = build_fields(loc)
        top[idx][2] = build_fields(msg)
        if len(sample) < target.sample_limit:
            sample.append(f"{lat:.8f},{lon:.8f}->{new_lat:.8f},{new_lon:.8f}")

    stats = PatchStats(
        patched=len(records),
        old_center=(round(center_lat, 8), round(center_lon, 8)),
        target=(target.lat, target.lng),
        mode=target.mode,
        scale=target.scale,
        sample=tuple(sample),
        accuracy=25,
    )
    patched_payload = build_fields(top)
    if framed:
        if len(patched_payload) > 0xFFFF:
            return raw, PatchStats(patched=0, reason="frame_too_large", mode=target.mode, scale=target.scale)
        prefix[8] = (len(patched_payload) >> 8) & 0xFF
        prefix[9] = len(patched_payload) & 0xFF
    return bytes(prefix) + patched_payload + suffix, stats
