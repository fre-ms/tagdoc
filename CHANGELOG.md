# Changelog

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
