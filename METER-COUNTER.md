# Wallbox-Zähler und externe Messquellen – Entwicklungsstand

## Bestätigter Stand

Der Nutzer hat am 01.11.2026 bestätigt, dass die erweiterte Integration in seiner
Home-Assistant-Installation funktioniert. Verwendet wird ein ESPHome-Pulszähler
an der Wallbox. Die Bestätigung wird als funktionaler Praxistest dokumentiert;
sie bedeutet nicht, dass alle Ausfall-/Neustartfälle oder die widersprüchliche
Impulskalibrierung einzeln geprüft wurden.

Vorbereitet für `matzem79/home-assistant-fiftyfive`, Version 0.11.0. Der Name
`matzem79` stammt aus der lokalen GitHub-Kontokonfiguration. Noch keine
GitHub-Veröffentlichung ausgeführt. Basis ist pimhofstees Branch
`feature/add-2fa-support`, Commit `5000d90f307ce7476f1e5f08965cac959e70faf2`,
Version 0.10.16, mit Herkunft aus Crazy-Ducks ursprünglicher Integration.

## Funktionen

Der Sensor **Wallbox-Zählerstand** nutzt absolute `Meter start`-/`Meter stop`-
Werte aus dem Stationsprotokoll, umgerechnet von Wh in kWh. Ohne externe
Energiequelle wird während einer Transaktion die kumulative Portal-
Sitzungsenergie auf den Startstand aufgesetzt. Mit externer Energiequelle
werden stattdessen deren Zuwächse verwendet. Offizielle Readings gleichen den
Stand wieder ab, einschließlich Korrekturen nach unten (`state_class: total`).

**Beide Energiesensoren liefern kWh.** Leistung wird in kW ausgegeben.

Unter **Einstellungen → Geräte & Dienste → 50five → Konfigurieren** wird pro
Wallbox gewählt:

| Auswahl | Leistung | Sitzungsenergie und Zählerfortschreibung |
| --- | --- | --- |
| Keine externe Quelle | Portal | Portal und offizielle Readings |
| Nur Leistungsquelle | Externe Quelle | Portal und offizielle Readings |
| Nur Energiezähler | Portal | Externe Zuwächse und offizielle Readings |
| Beide Quellen | Externe Quelle | Externe Zuwächse und offizielle Readings |

Es muss nicht beides ausgewählt werden. Aus externer Leistung allein wird keine
Energie integriert; aus externer Energie allein keine Momentanleistung abgeleitet.

Leistungswerte über dem einstellbaren Maximum (Standard 11 kW) werden verworfen;
der letzte plausible Wert bleibt erhalten. Null ist gültig. Nicht verfügbare
Quellen fallen auf das Portal zurück. Wiederherstellung und getrennte Anker
verhindern erneutes Addieren derselben Zählerzuwächse nach einem HA-Neustart.

Der Rohzähler darf bei einem ESP-Neustart zurückspringen: Es wird eine neue
Basis gesetzt. Unbekannte Ausfallenergie wird nicht geschätzt; spätere offizielle
Readings gleichen den absoluten Stand ab. Der Leistungsfilter verändert weder
die Rohentität noch die Pulse des Energiezählers.

## Herstellerunabhängige Quellen

Unterstützt werden bestehende HA-Sensoren mit W/kW bzw. kumulativen Wh/kWh.
Daher sind ESPHome, Shelly, Modbus, MQTT oder separate Zähler als Quellen
prinzipiell geeignet. Nur ESPHome wurde vom Nutzer praktisch bestätigt; für die
anderen Quellen ist die Kompatibilität aus dem Sensorvertrag abgeleitet.

Ein separater vorgeschalteter Zähler muss ausschließlich die Wallbox und bei
Drehstrom alle Phasen zusammen erfassen. Mitgemessene Verbraucher sind nicht
geeignet. Standby-Verbrauch und Leitungsverluste können vom internen Zähler
abweichen. Der ausgerichtete Sensor stellt dessen offiziellen Stand dar;
der ursprüngliche externe Sensor bleibt für den unveränderten externen
Gesamtstand erhalten.

Details und Einschränkungen: [External meters](docs/EXTERNAL-METERS.md).

## Installation und ESP-Firmware

Den bestehenden Ordner `/config/custom_components/fiftyfive` sichern, durch den
vollständigen Ordner aus dem ZIP ersetzen und Home Assistant neu starten.
Bestehende Einrichtung und Unique-IDs bleiben erhalten. Bei HACS muss dieser
Fork als Quelle hinterlegt sein, sonst können Updates die Erweiterung ersetzen.

Eine ESP-YAML-Änderung ist optional: Die Integration filtert eingehende Peaks.
[Der Sensorblock](examples/esphome/pulse-sensor-filter.yaml) filtert zusätzlich
vor der EMA und setzt die kW-Anzeige auf drei Nachkommastellen. Keine
Zugangsdaten enthalten. Firmware wurde hier weder kompiliert noch geflasht.

Die bereitgestellten Faktoren 0.06 (kW) und 0.001 (kWh) entsprechen **1000
Imp/kWh bzw. 1 Wh/Imp**. Die ursprünglichen Kommentare nannten 0,1 Wh/Imp;
dafür wären 0.006 und 0.0001 erforderlich. Die tatsächliche Zählerbeschriftung
ist noch zu bestätigen. Vorhandene Faktoren unverändert gelassen.

## Validierung

29 lokale isolierte Tests für Logauswertung, kumulative Energie, Endkorrektur,
Wh-Migration, Wiederherstellung, getrennte Stationen, Einheiten, Leistungspeaks,
Zählerrücksprung, Ausfall/Wiederverbindung und alle vier Quellenkombinationen.

```sh
python3 -m unittest discover -s tests -v
```

Syntax-/JSON-Prüfung und `git diff --check` zusätzlich ausgeführt. Die Tests
ersetzen keinen vollständigen HA-Lauf. Optionsdialog und Firmware werden nicht
automatisiert geprüft. Ruff/hassfest konnten lokal mangels verfügbarer
Umgebung bzw. Netzwerkzugriff nicht ausgeführt werden. GitHub Actions sind
vorbereitet; deren Erfolg ist noch zu prüfen.

Zusätzlich behoben: Das für die Update-Prüfung benötigte `update_state` wurde
in `FiftyfiveData` mit `default_factory=dict` ergänzt; der überflüssige
Konstruktorparameter in `__init__.py` wurde entfernt.

## Übernommener Upstream-Dauerfix

Der Dauerparser unterstützt nun neben `hh:mm` auch Tagesangaben wie
`1d01:30` (= 1530 Minuten). Grundlage ist der Fix für
[Crazy-Duck #83](https://github.com/Crazy-Duck/home-assistant-fiftyfive/issues/83)
aus Upstream-Version 0.10.0. Ungültige Angaben ergeben wie upstream 0 Minuten
statt einer Exception. Fünf zusätzliche Tests prüfen Stunden, einen/mehrere
Tage sowie leere und ungültige Angaben. Insgesamt 29 Tests erfolgreich.

## Kostenberechnung (0.12.0)

Pro Wallbox ist ein fester Preis pro kWh oder eine dynamische Preisentität
konfigurierbar. Vier zusätzliche Geldsensoren liefern Kosten der Sitzung,
heute, im laufenden Monat und insgesamt seit Erfassungsbeginn. Währung und
Kalenderzeitzone stammen aus Home Assistant. Negative Preise sind zulässig.
Details: [Kosten und Preisquellen](docs/COSTS.md).

Die Funktion erfasst ab der ersten beobachteten Energie nach Aktivierung.
Bei dynamischen Tarifen werden verspätete Energiemengen zeitanteilig auf die
beobachteten Preisintervalle verteilt; keine Abrechnungsgenauigkeit zugesichert.
Unbepreiste kWh sind als Attribut sichtbar. Kosten werden separat in HA-Storage
gespeichert und beim Neustart wiederhergestellt. Kein Live-Test dieser neuen
Funktion bisher; 19 zusätzliche Tests, insgesamt 48 lokale Tests erfolgreich.
