"""Where each kind of picture keeps a description: written there, the picture's own data
the same pixel for pixel; read again by a reader that knows the format (Pillow, libheif);
what a camera said beside it still there; what was replaced gone from the file; the same
bytes for the same picture and description; and, where the standard's reference library
writes the place too, the very bytes it writes."""

from __future__ import annotations

import io
import struct
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tagdoc import exif, formats, medrds
from tagdoc.formats import gif, heif, jpeg, png, webp
from tests.conftest import MEDRDS, needs_medrds

META = {"title": "Laborbefund", "kind": "lab", "date": "2026-03-12",
        "description": "Befund des Labors, erste Seite",
        "creator": ["Dr. Erika Müller <mailto:mueller@labor.example>"], "language": ["de"]}
TEXTS: dict[int, str | None] = {exif.DESCRIPTION: META["description"],
                                exif.ARTIST: "Dr. Erika Müller"}
SAVE = {"jpg": "JPEG", "png": "PNG", "tiff": "TIFF", "webp": "WEBP", "gif": "GIF", "heic": "HEIF"}
WITH_EXIF = ("jpg", "png", "tiff", "webp", "heic")


def drawing(width: int = 320, height: int = 240) -> object:
    """An invented picture: white, a red square and a blue disc."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 120, 90), fill=(200, 30, 30))
    draw.ellipse((150, 60, 300, 200), fill=(20, 60, 180))
    return image


def camera() -> object:
    """EXIF as a camera writes it: what it is, a description of its own, details in a
    directory of their own, a place."""
    from PIL import Image

    said = Image.Exif()
    said[exif.MAKE], said[exif.MODEL] = "Beispielfon", "Beispielfon 7"
    said[exif.SOFTWARE], said[exif.DESCRIPTION] = "Kamera 3.1", "ALTE BESCHREIBUNG DER KAMERA"
    said.get_ifd(0x8769)[0xA002] = 320
    said.get_ifd(0x8825)[1] = "N"
    return said


def picture(ending: str, with_exif: bool = True, image: object | None = None,
            **options: object) -> bytes:
    """An invented picture of a type, with a camera's EXIF where the type has a place."""
    import pillow_heif

    pillow_heif.register_heif_opener()
    image = image or drawing()
    if ending == "gif":
        image = image.convert("P")  # type: ignore[attr-defined]
    if with_exif and ending in WITH_EXIF:
        options = {"exif": camera(), **options}
    buffer = io.BytesIO()
    image.save(buffer, format=SAVE[ending], **options)  # type: ignore[attr-defined]
    return buffer.getvalue()


def pixels(data: bytes) -> tuple[tuple[int, int], bytes]:
    """What a picture shows: its size and its pixels."""
    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()
    with Image.open(io.BytesIO(data)) as image:
        return image.size, image.convert("RGBA").tobytes()


def said_by_camera(data: bytes) -> tuple[dict, dict, dict]:
    """What Pillow reads of a picture's EXIF: the first directory (but where things lie
    in the file), the details, the place."""
    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()
    with Image.open(io.BytesIO(data)) as image:
        read = image.getexif()
        first = {tag: value for tag, value in read.items()
                 if tag not in (0x8769, 0x8825, 273, 279, 700)}
        return first, dict(read.get_ifd(0x8769)), dict(read.get_ifd(0x8825))


def described(data: bytes, ending: str, meta: dict = META,
              texts: dict[int, str | None] = TEXTS) -> tuple[bytes, tuple[str, ...]]:
    packet = medrds.merge_xmp(formats.held(data, f".{ending}").packet, meta)
    return formats.written(data, f".{ending}", packet, texts)


@pytest.mark.parametrize("ending", list(SAVE))
@pytest.mark.parametrize("with_exif", (True, False))
def test_a_description_in_a_picture(ending: str, with_exif: bool) -> None:
    data = picture(ending, with_exif)
    out, done = described(data, ending)
    assert done == formats.places(f".{ending}") == (("xmp",) if ending == "gif"
                                                    else ("xmp", "exif"))
    assert pixels(out) == pixels(data)  # the picture is the same, pixel for pixel
    assert described(data, ending)[0] == out  # and the same bytes every time
    held = formats.held(out, f".{ending}")
    said, standard = medrds.parse_xmp(held.packet)
    assert standard and said == META
    if ending == "gif":
        assert held.texts == {}
        return
    assert held.texts[exif.DESCRIPTION] == META["description"]
    assert held.texts[exif.ARTIST] == "Dr. Erika Müller"
    assert b"ALTE BESCHREIBUNG" not in out
    if with_exif:  # what the camera said beside it still stands, as another reader sees it
        assert held.texts[exif.MAKE] == "Beispielfon" and held.texts[exif.SOFTWARE] == "Kamera 3.1"
        before, after = said_by_camera(data), said_by_camera(out)
        assert after[0][exif.DESCRIPTION] == META["description"]
        assert {**before[0], exif.DESCRIPTION: None, exif.ARTIST: None} == {
            **after[0], exif.DESCRIPTION: None, exif.ARTIST: None}
        assert before[1:] == after[1:]  # its details and the place
        if ending != "tiff":  # (Pillow writes no such directories into a compressed TIFF)
            assert after[1].get(0xA002) == 320 and after[2].get(1) == "N"


@pytest.mark.parametrize("ending", list(SAVE))
def test_what_is_replaced_is_gone(ending: str) -> None:
    """A description that is corrected leaves nothing behind in the file: not in the
    XMP, not in the EXIF, not in bytes no program shows."""
    first, _ = described(picture(ending), ending, {
        **META, "description": "Vertrauliches, das berichtigt wird",
        "creator": ["Dr. Falsch Benannt <mailto:falsch@labor.example>"]},
        {exif.DESCRIPTION: "Vertrauliches, das berichtigt wird", exif.ARTIST: "Dr. Falsch Benannt"})
    assert b"Vertrauliches" in first
    second, _ = described(first, ending, {"title": "Laborbefund", "kind": "lab"},
                          {exif.DESCRIPTION: None, exif.ARTIST: None})
    assert b"Vertrauliches" not in second and b"Falsch" not in second
    assert second.count(b"<x:xmpmeta") == 1
    held = formats.held(second, f".{ending}")
    assert exif.DESCRIPTION not in held.texts and exif.ARTIST not in held.texts
    assert medrds.parse_xmp(held.packet)[0] == {"title": "Laborbefund", "kind": "lab"}
    assert pixels(second) == pixels(picture(ending))


def test_what_a_packet_held_beyond_the_standard_stays() -> None:
    """A camera's packet names the moment and its program: they stay beside the
    description, in every type."""
    from PIL import Image

    foreign = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="' + medrds.RDF + '">'
               '<rdf:Description rdf:about="" xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"'
               ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
               "<photoshop:DateCreated>2026-03-14T08:15:00</photoshop:DateCreated>"
               '<dc:title><rdf:Alt><rdf:li xml:lang="x-default">IMG_0042</rdf:li></rdf:Alt>'
               "</dc:title></rdf:Description></rdf:RDF></x:xmpmeta>")
    for ending in ("jpg", "png", "tiff", "webp", "gif", "heic"):
        with_packet, _ = formats.written(picture(ending), f".{ending}", foreign, {})
        held = formats.held(with_packet, f".{ending}")
        assert medrds.parse_xmp(held.packet) == ({"title": "IMG_0042"}, False), ending
        out, _ = described(with_packet, ending)
        packet = formats.held(out, f".{ending}").packet or ""
        moment = ET.fromstring(packet).find(
            ".//{http://ns.adobe.com/photoshop/1.0/}DateCreated")
        assert moment is not None and moment.text == "2026-03-14T08:15:00", ending
        assert medrds.parse_xmp(packet)[0]["title"] == "Laborbefund" and "IMG_0042" not in packet
    with Image.open(io.BytesIO(described(picture("jpg"), "jpg")[0])) as image:
        assert b"Laborbefund" in image.info["xmp"]


@needs_medrds
@pytest.mark.parametrize("ending", ("jpg", "png"))
def test_the_same_bytes_as_the_reference_library(tmp_path: Path, ending: str) -> None:
    """The XMP of a JPEG and of a PNG is written as the standard's own library writes
    it: the same picture and packet, the same file."""
    data = picture(ending)
    packet = medrds.serialise_xmp(META)
    (tmp_path / "in").write_bytes(data)
    (tmp_path / "packet").write_text(packet, encoding="utf-8")
    name = "embedXmpJpeg" if ending == "jpg" else "embedXmpPng"
    script = ("import { readFileSync, writeFileSync } from 'node:fs';"
              f"import {{ {name} }} from '{MEDRDS / 'lib' / 'index.mjs'}';"
              f"writeFileSync('{tmp_path / 'out'}', {name}(new Uint8Array(readFileSync("
              f"'{tmp_path / 'in'}')), readFileSync('{tmp_path / 'packet'}', 'utf8')));")
    subprocess.run(["node", "--input-type=module", "-e", script], check=True)
    ours = jpeg.with_packet(data, packet) if ending == "jpg" else png.with_packet(data, packet)
    assert ours == (tmp_path / "out").read_bytes()
    again = jpeg.with_packet(ours, packet) if ending == "jpg" else png.with_packet(ours, packet)
    assert again == ours  # a packet in place of the one that was there


@needs_medrds
@pytest.mark.parametrize("ending", list(SAVE))
def test_medrds_reads_what_was_written(tmp_path: Path, ending: str) -> None:
    """The standard's reference library finds the description in every type."""
    from tests.conftest import medrds_reads

    path = tmp_path / f"bild.{ending}"
    path.write_bytes(described(picture(ending), ending)[0])
    meta = medrds_reads(path, ending)
    assert meta["title"] == "Laborbefund" and meta["kind"] == "lab"
    assert meta["date"] == "2026-03-12" and meta["creator"] == META["creator"]


def test_webp_in_its_simple_formats() -> None:
    """A WebP without the extended header gets one that says its size and what the file
    holds; with loss, without loss, and with transparency."""
    from PIL import Image

    clear = Image.new("RGBA", (64, 48), (0, 0, 0, 0))
    clear.paste((0, 120, 0, 255), (0, 0, 32, 24))
    for image, options in ((drawing(), {"quality": 80}), (drawing(), {"lossless": True}),
                           (clear, {"lossless": True})):
        data = picture("webp", False, image, **options)
        assert data[12:16] in (b"VP8 ", b"VP8L")  # the simple format
        out, _ = described(data, "webp")
        assert out[12:16] == b"VP8X" and pixels(out) == pixels(data)
        flags = out[20]
        assert flags & 0x08 and flags & 0x04  # it says that it holds EXIF and XMP
        assert bool(flags & 0x10) == (image is clear)  # and whether it is transparent
        width, height = image.size  # type: ignore[attr-defined]
        assert int.from_bytes(out[24:27], "little") == width - 1
        assert int.from_bytes(out[27:30], "little") == height - 1
        assert int.from_bytes(out[4:8], "little") == len(out) - 8
        assert webp.exif_of(out) is not None


def test_a_gif_of_the_older_version() -> None:
    data = picture("gif")
    older = b"GIF87a" + data[6:]
    out = gif.with_packet(older, medrds.serialise_xmp(META))
    assert out[:6] == b"GIF89a" and pixels(out) == pixels(data)
    assert gif.with_packet(out, medrds.serialise_xmp(META)) == out  # in place of the old one


def test_a_tiff_of_several_pages_keeps_them() -> None:
    from PIL import Image

    buffer = io.BytesIO()
    drawing().save(buffer, format="TIFF", save_all=True,  # type: ignore[attr-defined]
                   append_images=[Image.new("RGB", (90, 60), (0, 90, 0))], compression="tiff_lzw")
    data = buffer.getvalue()
    out, done = described(data, "tiff")
    assert done == ("xmp", "exif") and out[:len(data) - 0] != data and len(out) > len(data)
    with Image.open(io.BytesIO(out)) as image:
        assert image.n_frames == 2
        assert image.tag_v2[270] == META["description"]
        image.seek(1)
        assert image.size == (90, 60) and image.convert("RGB").getpixel((5, 5)) == (0, 90, 0)


def test_the_entries_of_a_directory() -> None:
    """Nothing moves: a value is written where the old one stood when it fits, else
    appended; an entry more makes a new directory at the end; the bytes of a value that
    went are zero, unless something else points at them."""
    block = (b"MM\0*" + struct.pack(">I", 8) + struct.pack(">H", 2)
             + struct.pack(">HHII", exif.DESCRIPTION, 2, 12, 38)
             + struct.pack(">HHI", exif.MAKE, 2, 4) + b"Abc\0"
             + struct.pack(">I", 0) + b"Lang genug!\0")
    assert exif.read(block) == {exif.DESCRIPTION: "Lang genug!", exif.MAKE: "Abc"}
    shorter = exif.changed(block, {exif.DESCRIPTION: exif.as_text("Kurz!")})
    assert len(shorter) == len(block) and exif.read(shorter)[exif.DESCRIPTION] == "Kurz!"
    assert shorter[38:50] == b"Kurz!\0" + bytes(6)  # in its place, the rest set to zero
    longer = exif.changed(block, {exif.DESCRIPTION: exif.as_text("Viel länger als zuvor")})
    assert longer[38:50] == bytes(12) and exif.read(longer)[exif.DESCRIPTION].startswith("Viel")
    assert struct.unpack_from(">I", longer, 4)[0] == 8  # the directory stayed where it was
    more = exif.changed(block, {exif.ARTIST: exif.as_text("Dr. Erika Müller")})
    assert struct.unpack_from(">I", more, 4)[0] > len(block) and more[8:38] == bytes(30)
    assert exif.read(more) == {exif.DESCRIPTION: "Lang genug!", exif.MAKE: "Abc",
                               exif.ARTIST: "Dr. Erika Müller"}
    fewer = exif.changed(more, {exif.DESCRIPTION: None, exif.ARTIST: None})
    assert exif.read(fewer) == {exif.MAKE: "Abc"} and b"Lang genug" not in fewer
    assert exif.changed(block, {}) == block and exif.changed(block, {exif.ARTIST: None}) == block
    # two entries that point at the same bytes: taking one away leaves the other its text
    shared = (b"II*\0" + struct.pack("<I", 8) + struct.pack("<H", 2)
              + struct.pack("<HHII", exif.DESCRIPTION, 2, 10, 38)
              + struct.pack("<HHII", exif.SOFTWARE, 2, 10, 38)
              + struct.pack("<I", 0) + b"Geteilt!!\0")
    kept = exif.changed(shared, {exif.DESCRIPTION: None})
    assert exif.read(kept) == {exif.SOFTWARE: "Geteilt!!"}
    assert exif.new({exif.DESCRIPTION: None}) is None
    assert exif.read(exif.new({exif.DESCRIPTION: exif.as_text("Neu")}) or b"") == {
        exif.DESCRIPTION: "Neu"}
    for broken in (b"", b"II+\0" + bytes(12), b"XX*\0" + bytes(12),
                   b"II*\0" + struct.pack("<I", 99)):
        with pytest.raises(exif.NotExif):
            exif.changed(broken, {exif.DESCRIPTION: exif.as_text("x")})


def test_what_is_no_place() -> None:
    """A type without a place, a file that is not what its name says, a packet too long
    for a JPEG, a sequence of pictures: the description is to go into a sidecar."""
    packet = medrds.serialise_xmp(META)
    for data, suffix in ((b"BM" + bytes(60), ".bmp"), (b"P6 1 1 255 abc", ".pnm"),
                         (picture("png"), ".jpg"), (b"not a picture", ".heic"),
                         (picture("jpg")[:2] + b"cut", ".png")):
        with pytest.raises(formats.NoPlace):
            formats.written(data, suffix, packet, TEXTS)
    with pytest.raises(formats.NoPlace) as caught:
        formats.written(picture("jpg"), ".jpg", medrds.serialise_xmp(
            {**META, "description": "x" * 70000}), {})
    assert caught.value.reason == "xmp-too-long"
    data = picture("heic")
    sequence = data + (8).to_bytes(4, "big") + b"moov"
    with pytest.raises(formats.NoPlace) as caught:
        heif.written(sequence, packet, None)
    assert caught.value.reason == "heif-structure"
    assert formats.places(".bmp") == () and formats.places(".HEIC") == ("xmp", "exif")
    assert formats.genuine(b"BM" + bytes(4), ".bmp") and not formats.genuine(b"PK", ".png")
    assert formats.held(b"not a picture", ".jpg") == formats.Held()


def test_a_heic_is_checked_by_looking(monkeypatch: pytest.MonkeyPatch) -> None:
    """What was written into a HEIC file is trusted only when a reader of the format
    shows the same pixels and finds the description: a file that came out wrong, and a
    computer without that reader, mean a sidecar."""
    import sys

    data = picture("heic")
    packet = medrds.serialise_xmp(META)
    out = heif.written(data, packet, None)
    assert heif.same_picture(data, out, packet, None)
    assert not heif.same_picture(data, picture("heic", image=drawing(300, 200)), packet, None)
    assert not heif.same_picture(data, out, packet.replace("Laborbefund", "Anderes"), None)
    assert not heif.same_picture(data, out[:-40], packet, None)
    monkeypatch.setitem(sys.modules, "pillow_heif", None)
    with pytest.raises(formats.NoPlace) as caught:
        formats.written(data, ".heic", packet, TEXTS)
    assert caught.value.reason == "needs-pillow-heif"


def _heic_as(data: bytes, version: int = 0, offset_size: int = 4, base_size: int = 4,
             meta_last: bool = False, open_ended: bool = False, in_list: bool = False) -> bytes:
    """The same HEIC picture laid out another way, as other programs write it: the box of
    places in another version and with other widths, the list behind the picture's data,
    the last box reaching to the end of the file, the EXIF held in the list's own data."""
    file = heif._read(data)
    places = file.locations
    absolute = {item.ident: [(item.base + offset, length) for _i, offset, length in item.extents]
                for item in places.items}
    places.version, places.offset_size, places.base_size = version, offset_size, base_size
    held = b""
    exif_item = file.found(b"Exif")
    if in_list and exif_item is not None:  # its data go into a box of the list (method 1)
        item = file.item(exif_item)
        assert item is not None and version >= 1
        held = file.bytes_of(item)
        item.method_field = 1
        absolute[exif_item] = [(0, len(held))]

    def meta(shift: int) -> bytes:
        for item in places.items:
            moved = [(start + (0 if item.method == 1 else shift), length)
                     for start, length in absolute[item.ident]]
            if base_size and item.method == 0:
                item.base, item.extents = moved[0][0], [[0, s - moved[0][0], n] for s, n in moved]
            else:
                item.base, item.extents = 0, [[0, s, n] for s, n in moved]
        parts = [data[file.meta.body:file.meta.body + 4]]
        for child in file.children:
            parts.append(heif._written_locations(places) if child.kind == b"iloc"
                         else data[child.start:child.end])
        if held:
            parts.append(heif._box(b"idat", held))
        return heif._box(b"meta", b"".join(parts))

    old = file.meta.end - file.meta.start
    before, after = data[:file.meta.start], data[file.meta.end:]
    if open_ended:  # the picture's data in a box that reaches to the end of the file
        assert after[4:8] == b"mdat"
        after = bytes(4) + after[4:]
    if meta_last:
        return before + after + meta(-old)
    return before + meta(len(meta(0)) - old) + after


@pytest.mark.parametrize("layout", (
    {}, {"version": 1}, {"version": 2, "offset_size": 8}, {"version": 1, "base_size": 0},
    {"meta_last": True}, {"open_ended": True}, {"version": 1, "in_list": True},
    {"version": 2, "base_size": 8, "offset_size": 4, "meta_last": True, "in_list": True}))
@pytest.mark.parametrize("with_exif", (True, False))
def test_a_heic_as_other_programs_lay_it_out(layout: dict, with_exif: bool) -> None:
    """The box that says where a HEIC file's data lie comes in three versions, with places
    of four or eight bytes, counted from the file's beginning or from a base, in the file
    or in the list itself; the list may stand behind the data.  In each, an item more
    moves what lies behind the list, and libheif still shows the same picture and finds
    the description."""
    import pillow_heif

    data = _heic_as(picture("heic", with_exif, drawing(640, 480)), **layout)
    assert pixels(data) == pixels(picture("heic", with_exif, drawing(640, 480)))
    out, done = described(data, "heic")
    assert done == ("xmp", "exif") and pixels(out) == pixels(data)
    read = pillow_heif.open_heif(out)
    assert b"Laborbefund" in read.info["xmp"]
    held = formats.held(out, ".heic")
    assert held.texts[exif.DESCRIPTION] == META["description"]
    assert (held.texts.get(exif.MAKE) == "Beispielfon") == with_exif
    assert described(data, "heic")[0] == out
    again, _ = described(out, "heic", {"title": "Neu", "kind": "lab"},
                         {exif.DESCRIPTION: None, exif.ARTIST: None})
    assert pixels(again) == pixels(data) and b"Befund des Labors" not in again
    assert again.count(b"<x:xmpmeta") == 1



def _variants() -> dict[str, tuple[str, bytes]]:
    """Pictures of every type in the ways they come, for the comparison with the library."""
    cases = {}
    for ending in SAVE:
        for with_exif in (True, False):
            kind = "exif" if with_exif else "plain"
            cases[f"{ending}-{kind}"] = (ending, picture(ending, with_exif))
    cases["webp-simple"] = ("webp", picture("webp", False, lossless=True))
    layouts: dict[str, dict] = {
        "v1": {"version": 1}, "v2-8": {"version": 2, "offset_size": 8},
        "no-base": {"version": 1, "base_size": 0}, "meta-last": {"meta_last": True},
        "open": {"open_ended": True}, "idat": {"version": 1, "in_list": True}}
    for name, layout in layouts.items():
        heic = picture("heic", True, drawing(320, 240))
        cases[f"heic-{name}"] = ("heic", _heic_as(heic, **layout))
    return cases


@needs_medrds
def test_the_same_bytes_as_the_library_in_every_format(tmp_path: Path) -> None:
    """tagdoc and the standard's reference library write a description into a picture of
    every type, in every layout tried, and give the very same bytes; and the description
    written again over the first, too."""
    import json

    names = "; ".join(medrds.parse_person(c)[0] or c for c in META["creator"])
    texts = {exif.DESCRIPTION: META["description"], exif.ARTIST: names}
    ours = {}
    for name, (ending, data) in _variants().items():
        (tmp_path / f"{name}.{ending}").write_bytes(data)
        once, _ = formats.written(data, f".{ending}", medrds.merge_xmp(
            formats.held(data, f".{ending}").packet, META), texts)
        twice, _ = formats.written(once, f".{ending}", medrds.merge_xmp(
            formats.held(once, f".{ending}").packet, {"title": "Neu", "kind": "lab"}),
            {exif.DESCRIPTION: None, exif.ARTIST: None})
        ours[name] = (ending, once, twice)
    (tmp_path / "meta.json").write_text(json.dumps(META), encoding="utf-8")
    script = (
        "import { readFileSync, writeFileSync } from 'node:fs';"
        f"import {{ writePicture }} from '{MEDRDS / 'lib' / 'index.mjs'}';"
        f"const schema = JSON.parse(readFileSync('{MEDRDS / 'schema' / 'medrds.json'}', 'utf8'));"
        f"const meta = JSON.parse(readFileSync('{tmp_path / 'meta.json'}', 'utf8'));"
        f"for (const [name, ext] of {json.dumps([[n, e] for n, (e, _o, _t) in ours.items()])}) {{"
        f"  const data = new Uint8Array(readFileSync(`{tmp_path}/${{name}}.${{ext}}`));"
        "  const once = writePicture(data, ext, meta, schema).bytes;"
        f"  writeFileSync(`{tmp_path}/${{name}}.once`, once);"
        "  const twice = writePicture(once, ext, { title: 'Neu', kind: 'lab' }, schema).bytes;"
        f"  writeFileSync(`{tmp_path}/${{name}}.twice`, twice);"
        "}")
    subprocess.run(["node", "--input-type=module", "-e", script], check=True)
    for name, (_ending, once, twice) in ours.items():
        assert (tmp_path / f"{name}.once").read_bytes() == once, name
        assert (tmp_path / f"{name}.twice").read_bytes() == twice, name
