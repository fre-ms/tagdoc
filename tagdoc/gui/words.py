"""Every word tagdoc's window shows, in English and German, registered with doccor's words
(:mod:`doccor.gui.words`); a key another tool of docrepro has means the same here."""

from __future__ import annotations

from doccor.gui import words as _words
from doccor.gui.words import LANGUAGES, Words, system_language

WORDS: dict[str, tuple[str, str]] = {  # key: (English, German)
    "title": ("{tool}: {name}", "{tool}: {name}"),
    "apply": ("Apply", "Übernehmen"),
    "later": ("Save and continue later", "Speichern und später weitermachen"),
    "cancel": ("Cancel", "Abbrechen"),
    "discard_title": ("Discard the work?", "Arbeit verwerfen?"),
    "discard_text": ("Nothing will be written. Discard what was done in this window?",
                     "Es wird nichts geschrieben. Das in diesem Fenster Getane verwerfen?"),
    "failed": ("That did not work: {error}", "Das ging nicht: {error}"),
    "describe_help": ("What the document says about itself, as medRDS writes it into the PDF "
                      "(or into a sidecar). Grey: tagdoc's suggestion from the text; what you "
                      "change is yours. Filing it (record, versions) is the records app's.",
                      "Was das Dokument über sich sagt, wie medRDS es ins PDF schreibt (oder in "
                      "eine Begleitdatei). Grau: tagdocs Vorschlag aus dem Text; was Sie ändern, "
                      "ist Ihres. Das Ablegen (Akte, Fassungen) macht das Aktenprogramm."),
    "field_title": ("Title", "Titel"),
    "field_kind": ("Kind", "Art"),
    "field_date": ("Clinical date", "Klinisches Datum"),
    "field_creator": ("Authors (one per line)", "Autoren (je Zeile einer)"),
    "field_institution": ("Institution (one per line)", "Einrichtung (je Zeile eine)"),
    "field_authenticator": ("Responsible", "Verantwortlich"),
    "field_description": ("Description", "Beschreibung"),
    "field_subject": ("Keywords (comma between)", "Schlagworte (durch Komma getrennt)"),
    "field_language": ("Language of the content", "Sprache des Inhalts"),
    "field_source": ("Source (where to find it again)", "Quelle (wo es wieder zu finden ist)"),
    "field_typeCode": ("Document type (system|code)", "Dokumenttyp (System|Code)"),
    "field_confidentiality": ("Confidentiality", "Vertraulichkeit"),
    "field_creatorTool": ("Made with", "Erstellt mit"),
    "field_cards": ("Cards kept with the file", "Karten beim Dokument"),
    "conf_none": ("(normal, not said)", "(normal, nicht angegeben)"),
    "conf_N": ("N normal", "N normal"),
    "conf_R": ("R restricted", "R eingeschränkt"),
    "conf_V": ("V very restricted", "V streng vertraulich"),
    "kind_none": ("(none yet)", "(noch keine)"),
    "from_card": ("From a card …", "Aus einer Karte …"),
    "remove_card": ("Remove the card", "Karte entfernen"),
    "restore_all": ("tagdoc's suggestions again", "Wieder tagdocs Vorschläge"),
    "date_tip": ("ISO 8601: 2026-03-12, or 2026-03-12T10:00:00+01:00",
                 "ISO 8601: 2026-03-12 oder 2026-03-12T10:00:00+01:00"),
    "missing": ("Still missing: {fields}", "Fehlt noch: {fields}"),
    "complete": ("Complete as medRDS requires.", "Vollständig, wie medRDS es verlangt."),
    "card_problem": ("Card: {why}", "Karte: {why}"),
    "wrong_value": ("{field}: {rule}", "{field}: {rule}"),
    "sidecar_note": ("This PDF is signed: it stays as it is, the description goes into a "
                     "sidecar.", "Dieses PDF ist signiert: es bleibt, wie es ist; die "
                     "Beschreibung kommt in eine Begleitdatei."),
}

_words.register(WORDS)
__all__ = ["LANGUAGES", "WORDS", "Words", "system_language"]
