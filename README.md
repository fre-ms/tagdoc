# tagdoc

tagdoc describes a document and writes what it says about itself: its title, its kind, the clinical date,
who wrote it and for which body, who took responsibility, keywords, the language, where it can be found
again, how confidential it is, and copies of the cards of an address book that the people and bodies it
names are named with. It suggests what the text tells (a title, the kind, the date, the language), a person
confirms or changes it, and tagdoc writes it as the standard [medRDS](https://medrds.org) says (chapter 7):
into the PDF, as XMP with the information dictionary in step, or, where the PDF must stay as it is (signed
by someone else), into a sidecar. Everything runs on your own computer; nothing is sent anywhere.

It is step 40 of **docrepro**, a family of tools that reproduce photographed and scanned documents as real
digital documents, one tool for one step: [optdoc](https://github.com/fre-ms/optdoc) makes the page
faithful, [ocrdoc](https://github.com/fre-ms/ocrdoc) recognises what is on it, semdoc (to come) understands
it, tagdoc describes it. It works on any PDF on its own as well.

**Status: pre-alpha (0.1.1).**

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

## Every step can be reproduced and resumed

The configuration document (`<name>.tagdoc.json`, also inside the PDF) holds every field with its value and
who decided it ("auto": tagdoc's suggestion, "person"), and nothing else. The same PDF and document give the
same files, byte for byte. A description is of the whole document: when the PDF changed (optdoc or ocrdoc
made it anew), every field a person decided stays, and tagdoc's suggestions are made again from the new text.

## Command line

```
tagdoc about
tagdoc run befund.pdf --out results/ --kind lab --institution-card labor.vcf --keyword Kalium
tagdoc run befund.pdf --out results/ --config results/befund.tagdoc.json
tagdoc edit befund.pdf --out results/ --language de
```

`run` writes `<name>.pdf` (with the description) and `<name>.tagdoc.json`, or for a signed PDF (or with
`--sidecar`) the PDF as it came and `<name>.pdf.xmp`. Values given are a person's: `--title`, `--kind`,
`--date` (ISO 8601), `--creator`, `--institution`, `--authenticator`, `--description`, `--keyword`,
`--content-language`, `--source`, `--type-code`, `--confidentiality N|R|V`, `--creator-tool`, and people from an
address book as their cards: `--creator-card`, `--institution-card`, `--authenticator-card`. The answer names
what is still missing (a title, a kind and a date are required) and what is wrong with the cards. One JSON
answer for every command, failures with their kind in English and German, no path or content in any message,
never the network ([docs/interface.md](docs/interface.md)).

## Licence

GNU Affero General Public License 3.0 or later (see `LICENSE`); the copy of medRDS's schema is MIT.
