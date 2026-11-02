# Wallbox – Variante A, Revision 2

`wallbox-a-v2.svg` ist ein eigenständiger visueller Entwurf mit eingebettetem Originalbild. Der Ausschnitt verwendet unveränderte Pixel aus `homeAdvanced.png`; Standfuß und Boden werden durch den SVG-Bildausschnitt ausgeblendet. Es wurde kein Kabel ergänzt.

Titel: Wallbox. Keine Herstellerbezeichnung. Enthält Leistung, Status, Ladekarte, Fahrzeugakku, Verbindung, geschätztes Ladeende, Sitzungsenergie, Ladezeit sowie Kosten heute und diesen Monat.

Beide Ladeaktionen bleiben sichtbar. Der dargestellte Beispielzustand ist Laden; deshalb ist Start ausgegraut. Für die spätere Umsetzung: Start/Stop abhängig vom tatsächlichen Status und der Verfügbarkeit freigeben; fehlende Messwerte als nicht verfügbar anzeigen, ohne Ersatzwerte zu erfinden.

Alle angezeigten Werte sind Beispiele. Kosten sollen aus den vorhandenen cost_day-/cost_month-Entitäten kommen; deren tatsächliche Entity-IDs müssen vor Anschluss geprüft werden. Kostenberechnung muss in den Integrationsoptionen aktiviert sein.

Dieser Entwurf ändert noch nicht die vorhandene Picture-Elements-Vorlage oder das Home-Assistant-Dashboard.


# Detailansicht – Entwurf 1

`wallbox-details-v1.svg` zeigt eine separate, vertikal scrollbar gedachte Detailseite. Der Zurück-Pfeil führt zur Hauptkarte. Der Status bleibt oben sichtbar. Ladeaktionen bleiben auf der Hauptkarte.

- Leistungsverlauf mit Auswahl 24 h / 7 Tage / Monat. In der Umsetzung längere Zeiträume nur anbieten, wenn passende Verlaufs- bzw. Statistikdaten vorhanden sind; Lücken nicht als Nullwerte zeichnen. Der dargestellte Verlauf ist schematisch.
- Tagesenergie nur anzeigen, wenn eine belastbare Tagesaggregation oder passende Entität vorliegt. Sie ist nicht mit der aktuellen Sitzungsenergie gleichzusetzen. Der Entwurf verwendet Beispielwerte.
- Aktuelle Sitzung mit Fahrzeugakku, geschätztem Ladeende, Sitzungsenergie, Ladezeit, Sitzungskosten und Ladekarte. Ohne aktive Sitzung den Zustand ausdrücklich anzeigen; alte Sitzungswerte nicht als laufende Sitzung ausgeben.
- Tages- und Monatskosten aus den vorhandenen Kostenentitäten; bei dynamischem Tarif dessen tatsächliche Konfiguration anzeigen. Kosten sind seit Aktivierung erfasst, keine automatische rückwirkende Monatsabrechnung. Das beispielhafte Erfassungsdatum muss für die Umsetzung aus gespeicherten Daten stammen oder entfallen.
- Technische Details standardmäßig einklappen; zur Vorschau sind sie geöffnet. Zählerstand meint den gerätebezogenen Wallbox-Zähler. Letzte Aktualisierung aus einer tatsächlichen Abfrage, nicht aus der letzten Zustandsänderung ableiten.

Alle Werte, Zeitangaben, Tarifangaben und Datumsangaben im Entwurf sind fiktiv. Es wurden keine Live-Daten aus Home Assistant abgefragt. Der Entwurf ist noch nicht mit Navigation oder Sensoren verbunden.
