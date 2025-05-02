# IoT Projekt
# Aquarium Überwachungs- und Steuerungssystem

## Beschreibung

Dieses Projekt dient zur Überwachung und Steuerung von Parametern in einem Aquarium. Es misst die Wassertemperatur und die Durchflussrate
eines Filters, zeigt diese Werte auf einem lokalen Display und einem Node-RED Dashboard an, loggt die Daten in einer MariaDB-Datenbank
und steuert einen Servo-Motor. Die Servo-Steuerung kann automatisch basierend auf einem einstellbaren Durchfluss-Schwellenwert oder 
manuell über das Dashboard erfolgen.

## Features

* Echtzeitmessung von Temperatur (DS18B20) und Durchfluss (YF-S201).
* Anzeige der aktuellen Werte und des Servo-Status auf einem lokalen ST7789-Display.
* Integration mit Node-RED über MQTT zur Anzeige und Steuerung.
* Node-RED Dashboard mit:
    * Anzeige von Temperatur und Durchfluss.
    * Grafische Darstellung historischer Daten.
    * Umschaltung zwischen Automatik- und Manuell-Betrieb für den Servo.
    * Einstellbarer Schwellenwert für die Durchflussrate im Automatik-Modus.
    * Manueller Ein-/Ausschalter für den Servo (nur im Manuell-Modus aktiv).
    * LED-Anzeige für den aktuellen Servo-Status.
* Automatische Servo-Steuerung: Servo wird im Automatik-Modus aktiviert, wenn der Durchfluss unter den eingestellten Schwellenwert fällt.
* Datenlogging der Messwerte (Temperatur, Durchfluss, Servo-Status, Zeitstempel) in einer MariaDB-Datenbank.

## Hardware-Komponenten

* ESP32 Mikrocontroller ESP32-S3
* Temperatursensor DS18B20
* Durchflusssensor YF-S201
* Servo-Motor
* Farbdisplay ST7789
* Verbindungskabel
* Stromversorgung für ESP32

## Software & System-Komponenten

* **ESP32:**
    * MicroPython Firmware
    * Benötigte MicroPython-Bibliotheken: `umqtt.simple`, `onewire`, `ds18x20`, `st7789py`, `vga2_16x16`
    * Hauptskript: `aquarium_esp32.py`
* **Node-RED:**
    * Laufende Node-RED Instanz
    * Installierte Nodes: `node-red-dashboard`, `node-red-node-mysql`
    * Importierter Flow (JSON-Datei)
* **MQTT Broker:**
    * Ein erreichbarer MQTT Broker (z.B. Mosquitto)
* **MariaDB Datenbank:**
    * Laufender MariaDB Server

## Konfiguration

### ESP32 (im Python-Skript)

* **WLAN:** `wlan_ssid`, `wlan_passwort`
* **MQTT:** `mqtt_broker`, `mqtt_port`, `mqtt_user`, `mqtt_password`, `client_id`
* **Pins:**
    * `ds18b20_daten_pin = 40`
    * `yfs201_sensor_pin = 4`
    * `servo_pin = 10`
    * Display SPI: `sck=36`, `mosi=35`, `miso=0` (oder -1), `reset=6`, `cs=41`, `dc=7`, `backlight=8`
* **Sensoren:** `yfs201_kalibrierungsfaktor = 7.5` Kalibrierungsfaktor muss selber ertestet werden.
* **Servo:** `servo_inaktive_position = 0`, `servo_aktive_position = 90`
* **Timing:** `schleifen_intervall_s = 5` (Sendeintervall)

### Node-RED

* **MQTT Broker Node:** Muss mit den gleichen Broker-Details wie der ESP32 konfiguriert sein.
* **MariaDB Node:** Muss mit den Zugangsdaten für die `nodered_daten` Datenbank konfiguriert sein.
* **Function Node ("Steuerlogik"):** Enthält Standardwerte für `threshold` (z.B. 7.0), falls keine aus dem Kontext geladen werden können.

## MQTT Topics

* `esp32/aquariumwerte`: ESP32 -> Node-RED (Published JSON mit `{"temperatur": ..., "durchfluss": ...}`)
* `esp32/servo/set`: Node-RED -> ESP32 (Sendet Befehle "ON" oder "OFF")

## Setup (Konzept)

1.  **ESP32:** MicroPython flashen, benötigte Bibliotheken und das Hauptskript hochladen. WLAN- und MQTT-Zugangsdaten im Skript anpassen.
2.  **MariaDB:** Datenbank und Tabelle mit dem oben beschriebenen Schema erstellen. Einen Datenbankbenutzer mit Rechten für diese Tabelle anlegen. Ggf. Server-Zeitzone auf `Europe/Berlin` setzen.
3.  **MQTT Broker:** Sicherstellen, dass der Broker läuft und erreichbar ist. Ggf. Benutzer anlegen.
4.  **Node-RED:** Den Flow importieren. Die MQTT-Broker-Nodes und MariaDB-Nodes mit den korrekten Verbindungsdaten konfigurieren. Dashboard-Layout anpassen.
5.  **Starten:** ESP32 starten, Node-RED deployen.

## Benutzung

* Das Node-RED Dashboard aufrufen.
* Aktuelle Werte für Temperatur und Durchfluss beobachten.
* Den Chart für historische Verläufe ansehen.
* Den Betriebsmodus (AUTO/MANUAL) über den entsprechenden Schalter wählen.
* Im AUTO-Modus den Schwellenwert für den Durchfluss über das numerische Eingabefeld anpassen.
* Im MANUAL-Modus den Servo über den "Servo Manuell"-Schalter direkt ein- und ausschalten.
* Die LED-Anzeige zeigt den aktuell von der Logik berechneten Soll-Zustand des Servos an.
* Die Daten werden automatisch in die MariaDB-Datenbank geloggt.

---
*Autor: Tim-Luca Neujahr*
*Datum: 02.05.2025*
*Version: v1.0*
