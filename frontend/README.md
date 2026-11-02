# Wallbox-Karte

Eigenständige Home-Assistant-Dashboard-Karte entsprechend Variante A und der Detailansicht. Keine weiteren Karten-Erweiterungen erforderlich. Die Integration liefert die Sensoren; die Karte wird separat als Dashboard-Ressource eingebunden.

## Installation

1. Den Ordner `wallbox` vollständig nach `/config/www/wallbox` kopieren. Ergebnis: `/config/www/wallbox/wallbox-card.js` und `/config/www/wallbox/homeAdvanced.png`.
2. Im Benutzerprofil den erweiterten Modus aktivieren. Unter **Einstellungen → Dashboards → Ressourcen** eine JavaScript-Modul-Ressource mit URL `/local/wallbox/wallbox-card.js?v=1` hinzufügen. Bei YAML-Ressourcen `type: module` verwenden.
3. Dashboard bearbeiten, manuelle Karte hinzufügen und `wallbox-card.yaml` einfügen.
4. Alle Beispiel-Entity-IDs, einschließlich der Fahrzeug- und Wallbox-Sensoren sowie Start/Stop, an die eigene Installation anpassen. Die leeren Felder `cost_day`, `cost_month`, `cost_session` und `meter` mit den tatsächlichen Entity-IDs aus **Entwicklerwerkzeuge → Zustände** füllen. Gesucht sind „Kosten heute“, „Kosten Monat“, „Kosten Sitzung“ und „Wallbox-Zählerstand“ der gewünschten Wallbox. Kostenberechnung muss in den Integrationsoptionen aktiviert sein. Solange Felder leer sind, zeigt die Karte „Nicht verfügbar“.
5. Browser neu laden. Ein Home-Assistant-Neustart ist für die Dashboard-Karte nicht nötig. Bei späteren JS-Updates die Versionsnummer in der Ressourcen-URL erhöhen.

Alternativ enthält `wallbox-dashboard.zip` die Dateien bereits in der Zielstruktur `www/wallbox/`, plus die Kartenkonfiguration und diese Anleitung. Nicht nach `custom_components` kopieren.

## Verhalten

- Das Feld `entities.connected` verwendet standardmäßig `sensor.vehicle_charge_state` und zeigt den Ladestatus an, etwa „Nicht ladebereit“ für `NOT_READY_FOR_CHARGING`. Daraus wird kein Stecker-Verbindungszustand abgeleitet. Ein konfigurierter binärer Stecker-Sensor mit `on`/`off` wird weiterhin unterstützt.
- Das Originalbild wird im Browser auf den Wallbox-Körper beschnitten. Kein nachgezeichnetes Kabel, kein Herstellername, kein Standfuß.
- Start und Stop bleiben sichtbar. Standardmäßig ist Start bei `Bereit` aktiv; Stop bei `Laden` oder `Laden (voll)`. Fehlende oder nicht verfügbare Status-/Button-Entitäten sperren die Aktionen. Statuswerte werden exakt verglichen. Bei Bedarf `start_states` und `stop_states` als Listen im YAML setzen. Die Buttons verwenden ausschließlich die konfigurierten `button`-Entitäten.
- Leistung, Sitzungsenergie, Dauer, Fahrzeugwerte und Kosten kommen aus den konfigurierten Entitäten. Keine Demowerte und keine automatische Berechnung aus unsicheren Differenzen. Unvollständige Kosten (`cost_complete: false`) werden mit Stern und Erklärung gekennzeichnet.
- „Details und Verlauf“ öffnet innerhalb der Karte die Detailansicht, Zurück die Hauptkarte. Einzelne Werte öffnen den Home-Assistant-Dialog des jeweiligen Sensors. Die Karte respektiert helle/dunkle Themes.
- Der native Leistungsverlauf bietet 24 Stunden, 7 Tage und 30 Tage. Die verfügbaren Daten hängen von Recorder-Konfiguration, Aufbewahrung und Sensorhistorie ab; die Karte importiert keine Daten und ersetzt keine fehlenden Werte durch Null. 30 Tage sind kein Kalendermonat.
- „Heute geladen“ erscheint nur, wenn `entities.energy_day` ausdrücklich konfiguriert ist. Keine Gleichsetzung mit Sitzungsenergie.
- Die Kosten sind die von der Integration erfassten Beträge seit Aktivierung; eine rückwirkende Monatsabrechnung wird nicht behauptet. Aktueller Preis erscheint nur, wenn die Kostenentität ihn liefert.
- Die technische Detailansicht verwendet den gerätebezogenen Zähler, nicht den portalweiten Gesamtverbrauch. Ein Zeitstempel für die letzte erfolgreiche Abfrage wird nicht erfunden.
- Fehlgeschlagene Ladeaktionen zeigen eine Fehlermeldung. Während eines laufenden Aufrufs sind beide Aktionen gesperrt. Die erfolgreiche Ausführung einer Aktion bestätigt noch keinen tatsächlichen Ladestart: Maßgeblich bleibt der nächste Sensorstatus.

## Prüfung

`node --check frontend/wallbox/wallbox-card.js`

`node --test tests/test_wallbox_card.cjs`

Die Karte wurde mit simulierten Home-Assistant-Zuständen und Serviceaufrufen geprüft. Eine Prüfung in einer laufenden Home-Assistant-Oberfläche steht aus.
