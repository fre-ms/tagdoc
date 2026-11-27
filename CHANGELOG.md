# Changelog

## 0.4.0 (2026-11-27)

Interface 3 and `tagdoc-config` version 1 stay; one setting is added.

- **The camera's date is the person's choice** (`--camera-date never|missing|first`, in the
  configuration document `options.camera_date`; a field in the window): the date a camera gives,
  when the photo was taken, is suggested as the clinical date nowhere (the default), where the
  text names none, or before the text's. It is the clinical date of a photographed finding, and not
  of a photographed report. tagdoc reads it from the picture's EXIF (`DateTimeOriginal` with its
  offset, else `DateTime`) or XMP, from the pictures a PDF holds as they came, and from the files
  named with `--original` (docrepro names its originals).
- **Every format is written as medRDS's reference library writes it** (0.15.1, which names the
  places of TIFF, WebP, HEIC and GIF now and keeps EXIF in step in every format), byte for byte; a
  test compares both for every format and every layout of a HEIC file tried.
- **The XMP of a TIFF is read from entry 700, that of a HEIC from its item**, as the library reads
  it; a packet elsewhere in such a file (an older one no entry names) no longer counts.
- What is written into a HEIC file is also read back as the library reads it before it is
  trusted: every item there was holds the very bytes it held.

## 0.3.0 (2026-11-27)

A picture stays a picture, and says what it is. docrepro forces no file type; tagdoc now describes
pictures as well as PDFs, in the place each format has for a description. Interface 3;
`tagdoc-config` version 1 stays.

### Added

- **tagdoc describes pictures**: JPEG, PNG, TIFF, WebP, HEIC and HEIF, GIF, BMP, PNM. The picture
  is written under the ending it came with, its own data untouched; the configuration document
  lies beside it.
- **The description goes into the picture where its format has a place**: the XMP in a JPEG's
  APP1 segment and a PNG's `iTXt` chunk (as medRDS's reference library writes them, byte for
  byte), in a TIFF's entry 700, a WebP's chunk `XMP `, a HEIC's item `application/rdf+xml` and a
  GIF's application extension `XMP Data`. A BMP and a PNM have no place: their description goes
  into the sidecar `<file name>.xmp`.
- **EXIF in step** (medRDS 7.4): `ImageDescription` holds the description and `Artist` the names
  of the authors, in the EXIF of a JPEG, PNG, WebP and HEIC and in the directory of a TIFF, as
  UTF-8. Everything else a picture says of itself stays where it stands; the bytes of a text that
  was replaced are set to zero.
- **A HEIC photo is checked by looking** before what was written is trusted: libheif must show
  the same pixels and find the description (pillow-heif, the new extra `heic`). Otherwise the
  photo stays as it came and the description goes into a sidecar.
- **Reading**: a description a document carries already, as the standard writes one, is suggested
  again field by field (a PDF's too); a picture's own description and author (XMP, EXIF) and the
  camera it names are suggested; and for a picture the rules for title, kind, date and language
  work on the reading ocrdoc laid beside it, where that reading names this very picture.
- In the answer: `written` (where the description stands: `xmp`, `info`, `exif`, or `sidecar`)
  and `why_sidecar`; in `about`: `places` (where each type keeps a description) and `heic`.

### Removed

- The kind of error `not-pdf`: a picture is described now. A type tagdoc cannot open is
  `unsupported` (with `suffix`), as in every tool of docrepro.
- `Described.pdf` is `Described.document`.

## 0.2.1 (2026-11-27)

With doccor 0.3.0, which every tool of docrepro names. Nothing a caller relies on changed:
interface 2, `tagdoc-config` version 1.

- tagdoc takes doccor from its tag `v0.3.0`, as typdoc 0.2.1, optdoc 0.10.1 and ocrdoc 0.4.0 do,
  so that the tools can be installed together.
- The kinds of error `unreadable` and `encrypted` are worded in doccor, with the same words.

## 0.2.0 (2026-11-27)

Interface 2: one field renamed, in every tool of docrepro at once.

- **The answer names the described PDF `document`**, no longer `pdf` (`run`, and `edit` on
  Apply); `tagdoc.output.write` returns it under that key. No step of docrepro is to force a file
  type, so a document need not be a PDF, and a field called `pdf` would then point at a picture.
  tagdoc itself still describes PDFs; that it describes a picture as medRDS says for its format
  (7.4) is to come. Callers read `document` where they read `pdf`.

## 0.1.1 (2026-11-26)

- tagdoc takes doccor from its tag `v0.2.0`, as optdoc 0.8.0 and ocrdoc 0.2.0 do, so that the
  tools of docrepro install beside one another (they share one doccor). Nothing of tagdoc's own
  changed: it uses no model.

## 0.1.0 (2026-11-26)

tagdoc, step 40 of docrepro: a document described as the standard medRDS says (chapter 7).

- **The description**: title, kind, document type, authors, institution, authenticator, description,
  keywords, language, source, the program, the clinical date, confidentiality, and copies of the cards
  people are named with (7.2); written into the PDF as XMP with the information dictionary in step
  (7.4), or into a sidecar where the PDF is signed or where asked (7.5). The packet is the reference
  library's, character by character; the tests let the reference library read back what tagdoc wrote.
- **Suggestions** from the text: a title, the kind, the clinical date (not a date of birth), the
  language; a person confirms or changes them.
- **The configuration document** `<stem>.tagdoc.json` (`tagdoc-config` 1): every field with its value
  and who decided it; the same input and document give the same files; on a changed input a person's
  fields stay.
- **The command line** `about`, `run`, `edit` (interface 1), people from an address book by their
  cards; **the window**, a form; **docrepro's step** through the entry point `docrepro.steps`.
