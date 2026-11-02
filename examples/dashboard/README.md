# Grafische Wallbox-Karte wallbox

1. `images/homeAdvanced.png` nach `/config/www/images/homeAdvanced.png` kopieren. Den Zielordner bei Bedarf anlegen.
2. Im Dashboard eine manuelle Karte hinzufügen und den Inhalt von `wallbox-picture-elements.yaml` einfügen oder die bestehende Karte damit ersetzen.

Die Vorlage verwendet die vom Nutzer angegebenen Entity-IDs für wallbox und das Fahrzeug vehicle. Bei anderen Installationen die IDs anpassen.

Die LED sitzt an der Position aus der bisherigen Karte: Laden blau, Bereit gelb, Laden (voll) grün, Transaktion abschließen orange, sonst grau (einschließlich unbekannt/nicht verfügbar). Die Bedingungen vergleichen die tatsächlichen Zustände exakt.

Rechts stehen Status, Ladekarte, Leistung, Sitzungsenergie, Ladezeit, Fahrzeugakku und geschätztes Ladeende. Werte und Steckersymbol öffnen beim Antippen die Details. Start und Stop führen beim Antippen `button.press` aus; langes Drücken öffnet die Details. Das Erstellen oder Kopieren dieser Vorlage löst keine Ladeaktion aus.

Keine zusätzliche Frontend-Erweiterung erforderlich. Die Karte behält die Bildproportionen; ihre Höhe ergibt sich aus der Breite. Das Layout wurde nicht in einer laufenden Home-Assistant-Oberfläche geprüft.

Die YAML-Datei ist eine Dashboard-Vorlage. Durch Kopieren des Integrationsordners wird sie nicht automatisch zum Dashboard hinzugefügt. Ein Neustart ist für eine Änderung der Dashboard-Karte nicht erforderlich.

## Eigene Karte mit Detailansicht

Die überarbeitete Variante A ist als eigene Karte unter [frontend](../../frontend/README.md) umgesetzt. Sie ersetzt die oben beschriebene Picture-Elements-Vorlage bei Verwendung der neuen Karte.
