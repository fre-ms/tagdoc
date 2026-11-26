# tagdoc's command line as an interface

**Interface 1**, since tagdoc 0.1.0. One JSON object on standard output for every command, success or failure,
with `interface` and `made_with`; exit status 0 or 2; no path or content of a document in any answer or
message; never the network. Within one interface, new fields and kinds of error may come.

## `about`

```json
{"interface": 1, "made_with": "tagdoc 0.1.0", "version": "0.1.0",
 "standard": "https://medrds.org/spec/0.15",
 "fields": ["title", "kind", "creator", "description", "subject", "language", "source", "creatorTool",
            "date", "typeCode", "institution", "authenticator", "confidentiality", "cards"],
 "kinds": {"lab": {"en": "Laboratory", "de": "Labor"}, "…": "…"}, "window": true}
```

## `run` and `edit`

```
tagdoc run  <file.pdf> --out <folder> [--config <file.tagdoc.json | file.pdf>] [values] [--sidecar]
tagdoc edit <file.pdf> --out <folder> [--config …] [values] [--language de|en]
```

Values (each a person's decision): `--title`, `--kind <kind>`, `--date <ISO 8601>`, `--creator <person>` and
`--institution <body>` (repeatable), `--authenticator <person>`, `--creator-card`, `--institution-card`,
`--authenticator-card <file.vcf>` (repeatable for the first two), `--description`, `--keyword` (repeatable),
`--content-language <BCP 47>` (repeatable), `--source`, `--type-code <system|code>` (repeatable),
`--confidentiality N|R|V`, `--creator-tool`. With `--config` the document decides; a value beside it is a
`usage` error.

```json
{"interface": 1, "made_with": "tagdoc 0.1.0",
 "pdf": "<folder>/<stem>.pdf", "config": "<folder>/<stem>.tagdoc.json", "sidecar": null,
 "signed": false, "rebased": false, "decided": ["institution", "kind"],
 "problems": [{"code": "META_MISSING", "field": "date", "why": "date is required"}]}
```

`sidecar` names `<stem>.pdf.xmp` where the description went into one (a signed PDF, which is then written as
it came, or `--sidecar`). `rebased` is true where the configuration document was made on another input: the
person's fields stayed, the suggestions were made again. `problems`: required fields still missing
(`META_MISSING`) and what medRDS's own check finds wrong with the cards (`CARD_MISSING`, `CARD_CONTENT`,
`CARD_UNUSED`, `META_INVALID`). `edit` answers as `run` with `"finished": true`, or after *Save and continue
later* `{"config": …, "finished": false}`; *Cancel* is the error `cancelled`.

## The configuration document: `tagdoc-config`, version 1

```json
{"format": "tagdoc-config", "version": 1, "made_with": "tagdoc 0.1.0",
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
| `not-pdf` | not a PDF | |
| `unreadable` | the PDF cannot be read | |
| `encrypted` | the PDF needs a password | |
| `bad-field` | a value is not of its kind | `field`, `rule` |
| `bad-card` | a card is no vCard with a UID | |

## In docrepro

tagdoc joins docrepro as step 40 through the entry point `docrepro.steps` (`tagdoc.docrepro:TagdocAdapter`):
it takes ocrdoc's PDF, names docrepro as the program the document is made with, and brings its form for
docrepro's window (tab 5, "Describe").
