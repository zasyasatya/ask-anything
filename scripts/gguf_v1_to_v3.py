"""Rewrite a GGUF **v1** container as GGUF **v3** (llama.cpp dropped v1 support).

v1: magic|ver(u32)|n_tensors(u32)|n_kv(u32)|kv*|tensor_info*|<data, unpadded>
    strings/dims use u32 lengths.
v3: magic|ver(u32)|n_tensors(u64)|n_kv(u64)|kv*|tensor_info*|<pad to align>|<data>
    strings/dims use u64 lengths; tensor offsets are relative to the padded
    start of the data section.

Tensor payload bytes are copied verbatim (same ggml type codes), so this is a
pure container upgrade.
"""
import struct, sys

STR, ARR = 8, 9
SCALAR = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f",
          7: "<B", 10: "<Q", 11: "<q", 12: "<d"}
# ggml type -> (block size, bytes per block)
QT = {0: (1, 4), 1: (1, 2), 2: (32, 18), 3: (32, 20), 6: (32, 22), 7: (32, 24),
      8: (32, 34), 9: (32, 40), 10: (256, 84), 11: (256, 110), 12: (256, 144),
      13: (256, 176), 14: (256, 210), 15: (256, 296), 16: (256, 80)}
ALIGN = 32


def rd_str32(f):
    n, = struct.unpack("<I", f.read(4)); return f.read(n).decode("utf-8", "replace")


def rd_val32(f, vt):
    if vt == STR:
        return rd_str32(f)
    if vt == ARR:
        et, = struct.unpack("<I", f.read(4))
        n, = struct.unpack("<I", f.read(4))
        return (et, [rd_val32(f, et) for _ in range(n)])
    v, = struct.unpack(SCALAR[vt], f.read(struct.calcsize(SCALAR[vt])))
    return bool(v) if vt == 7 else v


def wr_str(buf, s):
    b = s.encode("utf-8"); buf += struct.pack("<Q", len(b)) + b


def wr_val(buf, vt, val):
    buf += struct.pack("<I", vt)
    if vt == STR:
        wr_str(buf, val)
    elif vt == ARR:
        # the element type is written once; elements are bare values
        et, items = val
        buf += struct.pack("<I", et) + struct.pack("<Q", len(items))
        for it in items:
            if et == STR:
                wr_str(buf, it)
            elif et == 7:
                buf += struct.pack("<B", 1 if it else 0)
            else:
                buf += struct.pack(SCALAR[et], it)
    elif vt == 7:
        buf += struct.pack("<B", 1 if val else 0)
    else:
        buf += struct.pack(SCALAR[vt], val)


def tensor_nbytes(dims, ttype):
    n = 1
    for d in dims:
        n *= d
    blk, bpb = QT.get(ttype, (1, 4))
    return (n // blk) * bpb


def main(src, dst):
    f = open(src, "rb")
    assert f.read(4) == b"GGUF", "not a GGUF file"
    version, = struct.unpack("<I", f.read(4))
    n_tensors, = struct.unpack("<I", f.read(4))
    n_kv, = struct.unpack("<I", f.read(4))
    print(f"src: version={version} tensors={n_tensors} kv={n_kv}")

    meta = []
    for _ in range(n_kv):
        key = rd_str32(f)
        vt, = struct.unpack("<I", f.read(4))
        meta.append((key, vt, rd_val32(f, vt)))

    infos = []
    for _ in range(n_tensors):
        name = rd_str32(f)
        n_dims, = struct.unpack("<I", f.read(4))
        dims = [struct.unpack("<I", f.read(4))[0] for _ in range(n_dims)]
        ttype, = struct.unpack("<I", f.read(4))
        off, = struct.unpack("<Q", f.read(8))
        infos.append({"name": name, "dims": dims, "type": ttype, "offset": off,
                      "nbytes": tensor_nbytes(dims, ttype)})
    data_start = f.tell()

    # ---- header (v3) ----
    head = bytearray(b"GGUF" + struct.pack("<I", 3)
                     + struct.pack("<Q", len(infos)) + struct.pack("<Q", len(meta)))
    for key, vt, val in meta:
        wr_str(head, key); wr_val(head, vt, val)
    infos_sorted = sorted(infos, key=lambda t: t["offset"])
    for t in infos_sorted:
        wr_str(head, t["name"])
        head += struct.pack("<I", len(t["dims"]))
        head += b"".join(struct.pack("<Q", d) for d in t["dims"])
        head += struct.pack("<I", t["type"])
        head += struct.pack("<Q", t["offset"])       # v1 offsets == data order
    head += b"\x00" * ((ALIGN - len(head) % ALIGN) % ALIGN)

    with open(dst, "wb") as out:
        out.write(head)
        for t in infos_sorted:
            f.seek(data_start + t["offset"])
            blob = f.read(t["nbytes"])
            assert len(blob) == t["nbytes"], (t["name"], len(blob), t["nbytes"])
            out.write(blob)
            out.write(b"\x00" * ((ALIGN - t["nbytes"] % ALIGN) % ALIGN))
    print(f"wrote {dst}: {len(head) + sum(t['nbytes'] for t in infos)}+ bytes")
    for key, vt, val in meta[:6]:
        print("  kv:", key, "=", str(val)[:60])


if __name__ == "__main__":
    main(*sys.argv[1:])
