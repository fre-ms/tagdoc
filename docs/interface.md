# tagdoc's command line as an interface

**Interface 3**, since tagdoc 0.3.0. One JSON object on standard output for every command, success or failure,
with `interface` and `made_with`; exit status 0 or 2; no path or content of a document in any answer or
message; never the network. Within one interface, new fields and kinds of error may come.

**From interface 2:** tagdoc describes a picture as well as a PDF, and **a picture stays a picture** (no step
of docrepro forces a file type). The description is written into the picture where its format has a place
for it, the picture's own data untouched; `document` in the answer then points at a picture. The kind of
error `not-pdf` is gone (`unsupported` names a type tagdoc cannot open). New in the answer: `written` and
`why_sidecar`; new in `about`: `places` and `heic`.

**From interface 1 (tagdoc 0.2.0):** the answer names the described document `document`, no longer `pdf`.

## `about`

```json
{"interface": 3, "made_with": "tagdoc 0.3.0", "version": "0.3.0",
 "standard": "https://medrds.org/spec/0.15",
 "fields": ["title", "kind", "creator", "description", "subject", "language", "source", "creatorTool",
            "date", "typeCode", "institution", "authenticator", "confidentiality", "cards"],
 "kinds": {"lab": {"en": "Laboratory", "de": "Labor"}, "…": "…"},
 "places": {"pdf": ["xmp", "info"], "jpg": ["xmp", "exif"], "png": ["xmp", "exif"],
            "tiff": ["xmp", "exif"], "webp": ["xmp", "exif"], "heic": ["xmp", "exif"],
            "gif": ["xmp"], "bmp": ["sidecar"], "pnm": ["sidecar"], "…": "…"},
 "heic": true, "window": true}
```

`places` says, for every type of document tagdoc takes, where its description goes (below). `heic` says
whether a HEIC photo can be written into: that needs pillow-heif (the extra "heic"), with which tagdoc
checks what it wrote; without it the description of a HEIC photo goes into a sidecar.

## Where a description goes

The picture's own data are never touched, and the same picture and description give the same bytes.

| document | XMP | in step with it | |
|---|---|---|---|
| PDF | the metadata stream of the catalogue | the information dictionary (`info`) | a signed PDF stays as it is: sidecar |
| JPEG | an APP1 segment | EXIF `ImageDescription`, `Artist` | as medRDS's reference library writes the XMP, byte for byte |
| PNG | the chunk `iTXt` `XML:com.adobe.xmp` | the chunk `eXIf` | as the reference library writes the XMP, byte for byte |
| TIFF | entry 700 of the first directory | entries 270 and 315 of it | every page stays; no BigTIFF |
| WebP | the chunk `XMP ` | the chunk `EXIF` | a file in the simple format gets the header of the extended one |
| HEIC, HEIF | an item `application/rdf+xml` | the item `Exif` | checked by looking before it is trusted (below) |
| GIF | the application extension `XMP Data` | (a GIF has no EXIF) | |
| BMP, PNM | no place | | sidecar `<file name>.xmp` |

**In step** are the two texts EXIF has for what a description says: `ImageDescription` holds the description
and `Artist` the names of the authors (medRDS 7.4). They are replaced, and taken away where the description
has none. Text is written as UTF-8. **Everything else a picture says of itself stays**: the camera, the
moment, the place, a colour profile, and in its XMP every property the standard does not define.

**Nothing moves, and what is replaced is gone.** In an EXIF block and in a TIFF file a value is written where
the old one stood when it fits there, else appended; nothing else in the structure changes place (a camera's
own notes point at theirs). The bytes of a text that was replaced or taken away are set to zero, so that a
description a person corrected does not stay in the file where no program shows it; the tests look for it in
the bytes of every type.

**A HEIC photo is checked by looking.** Its items are listed in a table that grows by an entry, so the
picture's data move back in the file and every place the table names moves with them. tagdoc writes such a
file only when it reads the table in full, and trusts the result only when libheif (through pillow-heif)
shows the very same pixels and finds the description in it. Otherwise the photo stays as it came and the
description goes into a sidecar; `why_sidecar` says so.

**medRDS names fewer places than tagdoc writes.** The standard (0.15, 7.4) names the place for PDF, JPEG and
PNG, and a sidecar for HEIC "until this standard names the place in the file"; TIFF, WebP and GIF it does not
name. tagdoc writes each format's own place for XMP and EXIF. The standard's reference library finds the
description in all of them (it looks for the packet wherever it stands; the tests let it read every type).
`--sidecar` keeps any document as it came.

## `run` and `edit`

```
tagdoc run  <file> --out <folder> [--config <file.tagdoc.json | file.pdf>] [values] [--sidecar]
tagdoc edit <file> --out <folder> [--config …] [values] [--language de|en]
```

`<file>` is a PDF or a picture (JPEG, PNG, TIFF, HEIC or HEIF, WebP, GIF, BMP, PNM). tagdoc writes the
document under the ending it came with, and beside it the configuration document; a picture has no place
for that one, a PDF carries it inside as well.

Values (each a person's decision): `--title`, `--kind <kind>`, `--date <ISO 8601>`, `--creator <person>` and
`--institution <body>` (repeatable), `--authenticator <person>`, `--creator-card`, `--institution-card`,
`--authenticator-card <file.vcf>` (repeatable for the first two), `--description`, `--keyword` (repeatable),
`--content-language <BCP 47>` (repeatable), `--source`, `--type-code <system|code>` (repeatable),
`--confidentiality N|R|V`, `--creator-tool`. With `--config` the document decides; a value beside it is a
`usage` error.

```json
{"interface": 3, "made_with": "tagdoc 0.3.0",
 "document": "<folder>/<stem>.jpg", "config": "<folder>/<stem>.tagdoc.json", "sidecar": null,
 "written": ["xmp", "exif"], "why_sidecar": null,
 "signed": false, "rebased": false, "decided": ["institution", "kind"],
 "problems": [{"code": "META_MISSING", "field": "date", "why": "date is required"}]}
```

`written` says where the description stands: `"xmp"` with `"info"` in a PDF; `"xmp"` in a picture, with
`"exif"` where its EXIF says one of the two texts; or `"sidecar"`. `sidecar` then names the file
`<file name>.xmp` (`<stem>.pdf.xmp`, `<stem>.heic.xmp`), the document is written as it came, byte for byte,
and `why_sidecar` says why:

| `why_sidecar` | |
|---|---|
| `asked` | `--sidecar` |
| `signed` | a PDF signed or time-stamped by someone else |
| `no-place` | a type without a place for a description (BMP, PNM) |
| `xmp-too-long` | a JPEG takes a packet of 64 kilobytes at most (many cards may be more) |
| `heif-structure` | a HEIC file whose table of items tagdoc does not read in full, or a sequence of pictures |
| `heif-unchecked` | what was written into a HEIC file did not show the same picture: it was thrown away |
| `needs-pillow-heif` | a HEIC file, and pillow-heif is not installed to check it |
| `not-jpeg`, `not-png` … | the file is not what its name says |

**What tagdoc suggests** comes from three sides, in this order: a description the document carries already,
as the standard writes one (every field of it); what its text says, by rules (a title, the kind, the
clinical date, the language: from the text of a PDF, and for a picture from the reading ocrdoc laid beside
it, `<stem>.reading.json`, where that reading names this very picture by its SHA-256); and what a picture
says of itself otherwise (a description and who made it, from its XMP or EXIF; the camera or program it
names). A camera's date is never taken for the clinical date: it says when the photo was taken.

`rebased` is true where the configuration document was made on another input: the
person's fields stayed, the suggestions were made again. `problems`: required fields still missing
(`META_MISSING`) and what medRDS's own check finds wrong with the cards (`CARD_MISSING`, `CARD_CONTENT`,
`CARD_UNUSED`, `META_INVALID`). `edit` answers as `run` with `"finished": true`, or after *Save and continue
later* `{"config": …, "finished": false}`; *Cancel* is the error `cancelled`.

## The configuration document: `tagdoc-config`, version 1

```json
{"format": "tagdoc-config", "version": 1, "made_with": "tagdoc 0.3.0",
 "standard": "https://medrds.org/spec/0.15",
 "input": {"sha256": "…", "bytes": 245678, "suffix": ".pdf"},
 "options": {"sidecar": false, "creator_tool": "docrepro 0.1.0"},
 "fields": {"title": {"value": "Laborbefund", "by": "auto"},
            "institution": {"value": ["Labor Muster GmbH <mailto:befunde@labor.example> <urn:uuid:…>"],
                            "by": "person"},
            "cards": {"value": ["BEGIN:VCARD\nVERSION:4.0\nUID:urn:uuid:…\n…\nEND:VCARD\n"], "by": "person"},
            "…": "…"}}
```

## Failures

The common kinds (`missing`, `bad-config`, `same-as-source`, `unwritable`, `cancelled`, `no-gui`, `network`,
`usage`, `internal`) and tagdoc's own:

| `error` | when | `details` |
|---|---|---|
| `unsupported` | neither a PDF nor a picture | `suffix` |
| `unreadable` | the file cannot be read, or is not what its name says | |
| `encrypted` | the PDF needs a password | |
| `bad-field` | a value is not of its kind | `field`, `rule` |
| `bad-card` | a card is no vCard with a UID | |

## In docrepro

tagdoc joins docrepro as step 40 through the entry point `docrepro.steps` (`tagdoc.docrepro:TagdocAdapter`):
it takes the document of the step before (ocrdoc's PDF, or a picture with its reading beside it), names
docrepro as the program the document is made with, and brings its form for docrepro's window (tab 5,
"Describe").
