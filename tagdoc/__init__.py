"""tagdoc: describes a document and writes what it says about itself.

The title, the kind, the clinical date, who wrote it and for which body, keywords, the
language, where it can be found again, how confidential it is, and copies of the cards of
an address book that the people it names are named with: suggested from the document's
text (:mod:`tagdoc.describe`), confirmed by a person, and written as the standard medRDS
says (:mod:`tagdoc.medrds`, chapter 7) into the PDF (XMP and the information dictionary)
or, where the PDF must stay as it is, into a sidecar.  Every decision is kept in a
configuration document, from which the same result is made again, byte for byte.  It is
step 40 of docrepro; filing the document (its record, its versions) is the records app's.
Everything runs locally.

What the tools of docrepro share is doccor's (:mod:`doccor`).
"""

__version__ = "0.1.1"
