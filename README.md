# tagdoc

tagdoc describes a document and writes what it says about itself: its title, its kind, the clinical date,
who wrote it and for which body, who took responsibility, keywords, the language, where it can be found
again, how confidential it is, and copies of the cards of an address book that the people and bodies it
names are named with. It suggests what the text tells (a title, the kind, the date, the language), a person
confirms or changes it, and tagdoc writes it as the standard [medRDS](https://medrds.org) says (chapter 7):
into the PDF, as XMP with the information dictionary in step; into a picture, as its XMP with its EXIF in
step; or, where the file must stay as it is (signed by someone else) or has no place for it, into a sidecar.
Everything runs on your own computer; nothing is sent anywhere.

**A document need not be a PDF.** tagdoc describes JPEG, PNG, TIFF, WebP, HEIC and GIF pictures in the place
each format has for a description, and BMP and PNM pictures beside them; a picture stays a picture, and its
own data are never touched.

It is step 40 of **docrepro**, a family of tools that reproduce photographed and scanned documents as real
digital documents, one tool for one step: [typdoc](https://github.com/fre-ms/typdoc) changes the type
(binds pictures into a PDF), [optdoc](https://github.com/fre-ms/optdoc) makes the page faithful,
[ocrdoc](https://github.com/fre-ms/ocrdoc) recognises what is on it, tagdoc describes it. It works on any
PDF and any picture on its own as well.

**Status: pre-alpha (0.4.0).**

## What tagdoc writes, and what it leaves to the records app

medRDS's metadata say two kinds of thing. **What the document is**, tagdoc's: title (`dc:title`), kind
(`dc:type`, one of the standard's kinds), document type (`medrds:typeCode`), authors (`dc:creator`),
institution and authenticator (`medrds:…`), description, keywords, language, source (`dc:source`), the
program it was made with (`xmp:CreatorTool`), the clinical date (`xmp:CreateDate`), confidentiality, and the
copies of the cards (`medrds:cards`). **How it is filed**, the records app's at check-in: the record, the
document and version IDs, the previous version and the history, who filed it and when, where it came from,
the version of the standard. A records app that files tagdoc's PDF reads tagdoc's description from it and
writes its own beside it.

People and bodies are named as 7.2 says: the name, and after it identifiers in angle brackets, an e-mail
address first, and, where they are taken from an address book, the card by its UID:

```
Labor Muster GmbH <mailto:befunde@labor.example> <urn:uuid:4d2c9b1e-7a3f-4c5d-9e8f-0a1b2c3d4e5f>
```

A copy of that card goes with the file, holding who someone is and how they are reached and nothing else
(no photo, no key, nothing sealed, no property of medDAV but the identifiers of practitioners and bodies).

## Following the standard

tagdoc writes the packet **exactly as medRDS's reference library writes it** (`lib/xmp.mjs`), line by line
and character by character; the tests compare both, and let the reference library read back the PDF and the
sidecar tagdoc wrote. The vocabulary comes from the standard's schema, of which tagdoc carries a copy
(`tagdoc/schema/medrds.json`, medRDS 0.15, MIT licence, `tagdoc/schema/LICENSE-MIT.txt`); a test checks it
against the standard's own where that is at hand (`MEDRDS=<path>`). What a PDF's own metadata held beyond the
standard stays (a mark of PDF/A, the producer).

## Pictures: read and written in the place each format has

| picture | XMP | EXIF, in step with it |
|---|---|---|
| JPEG | an APP1 segment | `ImageDescription`, `Artist` in the EXIF segment |
| PNG | the chunk `iTXt` `XML:com.adobe.xmp` | the chunk `eXIf` |
| TIFF | entry 700 of the first directory | entries 270 and 315 of it |
| WebP | the chunk `XMP ` | the chunk `EXIF` |
| HEIC, HEIF | an item `application/rdf+xml` | the item `Exif` |
| GIF | the application extension `XMP Data` | (a GIF has none) |
| BMP, PNM | no place: the sidecar `<file name>.xmp` | |

- **The picture's own data are not touched**: the tests decode every type before and after and compare the
  pixels. Every format is written as medRDS's reference library writes it (0.15.1), byte for byte, and
  that library reads the description back from every type.
- **What the picture says of itself stays**: the camera, the moment, the place, a colour profile, every
  property of its XMP the standard does not define. tagdoc reads it too: a description and an author the
  picture names are suggested, and the camera as the program it was made with.
- **The camera's date is a choice** (`--camera-date never|missing|first`): it says when the photo was
  taken, which is the clinical date of a photographed finding and not of a photographed report. By default
  it is suggested nowhere; `missing` suggests it where the text names no date, `first` before the text's.
- **In step** are the two texts EXIF has for what a description says, `ImageDescription` (the description)
  and `Artist` (the names of the authors), written as UTF-8.
- **Nothing moves, and what is replaced is gone.** An EXIF block keeps every entry where it stands (a
  camera's own notes point at theirs); the bytes of a text that was corrected are set to zero, so that it
  does not stay in the file where no program shows it.
- **A HEIC photo is checked by looking**: tagdoc trusts what it wrote only when libheif shows the same
  pixels and finds the description (pillow-heif, the extra `heic`); otherwise the photo stays as it came
  and the description goes into a sidecar. The answer says where a description went, and why.
- **What tagdoc suggests for a picture** comes from the reading ocrdoc laid beside it
  (`<name>.reading.json`, where it names this very picture): the same rules as for the text of a PDF.

These are the places medRDS names (7.4, from medRDS 0.15.1). `--sidecar` keeps any file as it came.

## Every step can be reproduced and resumed

The configuration document (`<name>.tagdoc.json`, also inside a PDF; beside a picture only) holds every
field with its value and who decided it ("auto": tagdoc's suggestion, "person"), and nothing else. The same
file and document give the same files, byte for byte. A description is of the whole document: when the file
changed (optdoc or ocrdoc made it anew), every field a person decided stays, and tagdoc's suggestions are
made again from the new text.

## Command line

```
tagdoc about
tagdoc run befund.pdf --out results/ --kind lab --institution-card labor.vcf --keyword Kalium
tagdoc run befund.pdf --out results/ --config results/befund.tagdoc.json
tagdoc edit befund.pdf --out results/ --language de
tagdoc run foto.heic --out results/ --kind lab --date 2026-03-12
```

`run` writes the document under the ending it came with (`<name>.pdf`, `<name>.heic` …), with the
description inside, and `<name>.tagdoc.json`; or, for a signed PDF, a type without a place for a description
and with `--sidecar`, the file as it came and `<file name>.xmp`. Values given are a person's: `--title`, `--kind`,
`--date` (ISO 8601), `--creator`, `--institution`, `--authenticator`, `--description`, `--keyword`,
`--content-language`, `--source`, `--type-code`, `--confidentiality N|R|V`, `--creator-tool`, and people from an
address book as their cards: `--creator-card`, `--institution-card`, `--authenticator-card`. The answer names
what is still missing (a title, a kind and a date are required) and what is wrong with the cards. One JSON
answer for every command, failures with their kind in English and German, no path or content in any message,
never the network ([docs/interface.md](docs/interface.md)).

## Licence

GNU Affero General Public License 3.0 or later (see `LICENSE`); the copy of medRDS's schema is MIT.
