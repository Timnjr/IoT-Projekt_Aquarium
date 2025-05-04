# ======================================================================
# Programm zum Auswerten eines Temperatursensors (DS18b20)
# und eines Durchflusssensors (YF-S201)
# Steuerung eines Servo-Motors basierend auf MQTT Befehlen
# Anzeige der Werte auf einem Display (ST7789)
# und einem Node-Red Dashboard mithilfe von MQTT
# Autor: Tim-Luca Neujahr
# Erstellt am 22.03.2025
# Letztes Update: 04.05.2025
# Version: 1.0
# ======================================================================

# === Bibliotheken hinzufügen ===
import machine, network, ujson, time, ds18x20, onewire, micropython, sys
from simple import MQTTClient 
from machine import Pin, SPI
import st7789py as st7789
import vga2_16x16 as font

# === Konfiguration ===

# -- WLAN --
wlan_ssid = "WLAN-SSID" #Hier die zu verwendende WLAN SSID eintragen
wlan_passwort = "WLAN-Passwort"   # Hier das dazugehörige WLAN Passwort eintragen

# -- MQTT --
mqtt_broker = "IP-Adresse des MQTT-Brokers"   #IP-Adresse des MQTT-Brokers
mqtt_port = 1883                 #Port des MQTT-Brokers (Standardmäßig 1883)
mqtt_user = "Nutzername"                #Falls eingerichtet Nutzername und Passwort zum verbinden mit dem MQTT-Broker
mqtt_password = "Passwort"
mqtt_publish_thema = "esp32/aquariumwerte" #Das Publish Thema bennenen. Muss übereinstimmen mit MQTT IN in Node-Red!
client_id = "esp32-s3-aquarium"
mqtt_subscribe_servo_thema = b'esp32/servo/set' #Das Subscribe Thema für die Steuerung des Servos. Muss übereinstimmen mit MQTT Out in Node-Red!

# -- Sensoren --
ds18b20_daten_pin = 40  # Daten-Pin für den Temperatursensor
yfs201_sensor_pin = 4   # Daten-pin für den Durchflusssensor
yfs201_kalibrierungsfaktor = 7.5 # Kalibrierungsfaktor wie viele Impulse pro Liter

# -- Servo --
servo_pin = 10        #Pin über den der Servo angesteuert wird
servo_pwm_frequenz = 50
servo_min_impuls_u16 = 1024
servo_max_impuls_u16 = 8192
servo_inaktive_position = 0 # Winkel für "OFF"
servo_aktive_position = 90  # Winkel für "ON"

# -- Display (ST7789) Konfiguration --
display_spi_bus = 1
display_spi_sck_pin = 36
display_spi_mosi_pin = 35
display_spi_miso_pin = 0
display_reset_pin = 6
display_cs_pin = 41
display_dc_pin = 7
display_backlight_pin = 8
display_breite = 240
display_hoehe = 320
display_rotation = 3

# -- Programmablauf --
schleifen_intervall_s = 5 # Hier könnte angepasst werden wie schnell die Schleife sich wiederholt

# === Globale Variablen ===
wlan = network.WLAN(network.STA_IF)
mqtt_client = None
ds_sensor = None
ds_adressen = []
servo_pwm = None
fluss_impuls_zaehler = 0
letzte_fluss_lese_zeit = time.ticks_ms()
aktueller_servo_zustand_on = False
tft = None
spi_display = None

# === Interrupt Service Routine (ISR) für Durchflusssensor ===
def fluss_impuls_isr(pin_referenz):  #Wird bei jedem Impuls aufgerufen um die Pulse zu Zählen
    global fluss_impuls_zaehler
    fluss_impuls_zaehler += 1

# === MQTT Callback Funktion für empfangene Nachrichten ===
def mqtt_callback(topic, msg):
    global aktueller_servo_zustand_on
    print(f"MQTT Nachricht empfangen - Topic: {topic.decode()}, Nachricht: {msg.decode()}")
    topic_str = topic.decode()
    msg_str = msg.decode().upper() # Umwandeln in Großbuchstaben für einfacheren Vergleich

    if topic == mqtt_subscribe_servo_thema:
        if msg_str == "ON":
            print("Befehl empfangen: Servo AN")
            setze_servo_winkel(servo_aktive_position)
            aktueller_servo_zustand_on = True
        elif msg_str == "OFF":
            print("Befehl empfangen: Servo AUS")
            setze_servo_winkel(servo_inaktive_position)
            aktueller_servo_zustand_on = False
        else:
            print(f"Unbekannter Befehl für Servo empfangen: {msg_str}")
    else:
        print(f"Nachricht auf anderem Topic empfangen: {topic_str}")

# === Funktionen ===
def verbinde_wlan(): # Verbindet mit dem konfigurierten WLAN.
    print("Verbinde mit WLAN:", wlan_ssid)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(wlan_ssid, wlan_passwort)
        verbindungs_versuche = 0
        while not wlan.isconnected() and verbindungs_versuche < 20:
            print(".", end="")
            time.sleep(1)
            verbindungs_versuche += 1
    if wlan.isconnected():
        print("\nWLAN verbunden. IP-Info:", wlan.ifconfig())
        return True
    else:
        print("\nWLAN-Verbindung fehlgeschlagen.")
        wlan.active(False)
        return False

def trenne_wlan(): # Trennt die WLAN-Verbindung
    if wlan and wlan.isconnected():
        wlan.disconnect()
    wlan.active(False)
    print("WLAN getrennt und deaktiviert.")

def verbinde_mqtt(): #Baut eine Verbindung zum konfigurierten MQTT-Broker auf
    global mqtt_client
    if mqtt_client is None:
        mqtt_client = MQTTClient(client_id, mqtt_broker, port=mqtt_port, user=mqtt_user, password=mqtt_password)
        mqtt_client.set_callback(mqtt_callback)
    try:
        print("Verbinde mit MQTT Broker...")
        mqtt_client.connect()
        print("MQTT verbunden.")
        # Servo-Befehls-Topic abonnieren
        mqtt_client.subscribe(mqtt_subscribe_servo_thema)
        print(f"MQTT Topic abonniert: {mqtt_subscribe_servo_thema.decode()}")
        return True
    except Exception as e:
        print(f"MQTT Verbindungsfehler: {e}")
        mqtt_client = None
        return False

def sende_mqtt(thema, daten): #Sendet die Daten an den MQTT-Broker
    global mqtt_client
    if mqtt_client is None or not wlan.isconnected(): return False
    try:
        nutzlast = ujson.dumps(daten)
        mqtt_client.publish(thema, nutzlast)
        return True
    except Exception as e:
        print(f"MQTT Sende-Fehler: {e}")
        try:
            if mqtt_client: mqtt_client.disconnect()
        except Exception: pass
        mqtt_client = None
        return False

def lese_temperatur(): # Liest die Temperatur vom DS18B20 Sensor
    global ds_sensor, ds_adressen
    if not ds_adressen: return None
    try:
        ds_sensor.convert_temp()
        time.sleep_ms(750)
        temp_c = ds_sensor.read_temp(ds_adressen[0])
        if isinstance(temp_c, (int, float)) and -10 <= temp_c <= 50: # Etwas erweiterter Plausibilitätsbereich
             return round(temp_c, 2)
        else:
             print(f"Unplausibler Temp-Wert: {temp_c}")
             return None
    except Exception as e:
        return None


def berechne_flussrate(): #Berechnet die Flussrate aus den gezählten Impulsen.
    global fluss_impuls_zaehler, letzte_fluss_lese_zeit
    aktuelle_zeit = time.ticks_ms()
    zeit_differenz_ms = time.ticks_diff(aktuelle_zeit, letzte_fluss_lese_zeit)

    # Mindestens 1 Sekunde warten für stabilere Messung
    if zeit_differenz_ms < 1000: return -1.0 # Signal: Warte noch

    irq_status = machine.disable_irq() # Interrupts kurz deaktivieren, um Zähler sicher zu lesen
    aktueller_impuls_zaehler = fluss_impuls_zaehler
    fluss_impuls_zaehler = 0 # Zähler zurücksetzen für nächste Messperiode
    machine.enable_irq(irq_status)

    letzte_fluss_lese_zeit = aktuelle_zeit
    zeit_differenz_s = zeit_differenz_ms / 1000.0

    if zeit_differenz_s <= 0: frequenz_hz = 0.0
    else: frequenz_hz = aktueller_impuls_zaehler / zeit_differenz_s

    flussrate_l_min = frequenz_hz / yfs201_kalibrierungsfaktor
    return round(flussrate_l_min, 2)


def setze_servo_winkel(winkel): # Bewegt den Servo zum gewünschten Winkel (0-180 Grad)
    global servo_pwm
    if servo_pwm is None: return
    effektiver_winkel = max(0, min(180, winkel))
    bereich = servo_max_impuls_u16 - servo_min_impuls_u16
    impuls_u16 = int(servo_min_impuls_u16 + bereich * (effektiver_winkel / 180.0))
    try:
        servo_pwm.duty_u16(impuls_u16)
    except Exception as e:
        print(f"Servo Setz-Fehler: {e}")


# === Initialisierung ===
print("================")
print("Initialisierung")
print("================")

# -- Display Initialisierung --
try:
    miso_pin_obj = Pin(display_spi_miso_pin) if display_spi_miso_pin >= 0 else None

    spi_display = SPI(display_spi_bus, baudrate=20000000, polarity=0, phase=0,
                      sck=Pin(display_spi_sck_pin),
                      mosi=Pin(display_spi_mosi_pin),
                      miso=miso_pin_obj)

    tft = st7789.ST7789( spi_display, display_breite, display_hoehe,
        reset=Pin(display_reset_pin, Pin.OUT), cs=Pin(display_cs_pin, Pin.OUT),
        dc=Pin(display_dc_pin, Pin.OUT), backlight=Pin(display_backlight_pin, Pin.OUT),
        rotation=display_rotation)

    tft.fill(st7789.BLACK)
    print("--- Display initialisiert ---")

except Exception as e:
    print(f"FEHLER bei der Display-Initialisierung: {e}")
    sys.print_exception(e)
    tft = None

# -- WLAN Initialisierung --
print("Init WLAN...")
if not verbinde_wlan(): print("WARNUNG: Keine WLAN-Verbindung möglich!")

# -- DS18B20 Initialisierung --
print("Init DS18B20...")
try:
    ow = onewire.OneWire(machine.Pin(ds18b20_daten_pin))
    ds_sensor = ds18x20.DS18X20(ow)
    ds_adressen = ds_sensor.scan()
    if ds_adressen: print(f"DS18B20 Sensor gefunden: {ds_adressen[0].hex()}") # .hex() für bessere Lesbarkeit
    else: print("WARNUNG: Kein DS18B20 Sensor gefunden!")
except Exception as e: print(f"FEHLER DS18B20 Init: {e}"); ds_sensor = None

# -- YF-S201 Initialisierung --
print("Init Durchflusssensor...")
try:
    sensor_pin_objekt = machine.Pin(yfs201_sensor_pin, machine.Pin.IN, machine.Pin.PULL_UP)
    sensor_pin_objekt.irq(trigger=machine.Pin.IRQ_RISING, handler=fluss_impuls_isr)
    letzte_fluss_lese_zeit = time.ticks_ms()
    print(f"Durchflusssensor an Pin {yfs201_sensor_pin} initialisiert.")
except Exception as e: print(f"FEHLER Durchflusssensor Init: {e}")

# -- Servo Initialisierung --
print("Init Servo...")
try:
    servo_pwm = machine.PWM(machine.Pin(servo_pin), freq=servo_pwm_frequenz)
    initial_winkel = servo_inaktive_position # Startet standardmäßig auf OFF
    aktueller_servo_zustand_on = False
    setze_servo_winkel(initial_winkel)
    print(f"Servo an Pin {servo_pin} initialisiert (auf {initial_winkel}° = OFF).")
    time.sleep(1) # Kurze Pause damit Servo Position erreicht
except Exception as e: print(f"FEHLER Servo Init: {e}"); servo_pwm = None

print("========================================")
print(" Initialisierung abgeschlossen")
print(" Starte Hauptschleife...")
print("========================================")
time.sleep(1)

# === Hauptschleife ===
while True:
    schleifen_start_zeit = time.ticks_ms()

    # --- 1. Verbindungen prüfen und ggf. (neu) herstellen ---
    if not wlan.isconnected():
        print("WLAN nicht verbunden. Versuche Reconnect...")
        trenne_wlan() # Sicherstellen, dass alter Zustand sauber ist
        time.sleep(5)
        verbinde_wlan()
    # Prüfen ob MQTT verbunden ist, wenn WLAN da ist
    if wlan.isconnected() and mqtt_client is None:
        verbinde_mqtt() # Versucht Verbindung inkl. Subscription

    # --- Auf MQTT Nachrichten prüfen ---
    if mqtt_client:
        try:
            # Prüft ob Nachrichten auf abonnierten Topics anliegen und ruft Callback auf
            mqtt_client.check_msg()
        except Exception as e:
            print(f"MQTT check_msg Fehler: {e}")
            try: # Bei Fehler Verbindung zurücksetzen und neu versuchen
                mqtt_client.disconnect()
            except: pass
            mqtt_client = None

    # --- 2. Sensoren auslesen ---
    temperatur_aktuell = lese_temperatur()
    durchfluss_aktuell = berechne_flussrate() # Gibt -1.0 zurück wenn Messintervall zu kurz ist

    # --- 3. Daten für MQTT vorbereiten ---
    werte_fuer_mqtt = {}
    valid_data_found = False
    if temperatur_aktuell is not None:
        werte_fuer_mqtt["temperatur"] = temperatur_aktuell
        valid_data_found = True
    if durchfluss_aktuell >= 0: # Nur senden, wenn ein gültiger Wert berechnet wurde (nicht -1.0)
        werte_fuer_mqtt["durchfluss"] = durchfluss_aktuell
        valid_data_found = True

    # --- 4. Daten senden via MQTT ---
    if valid_data_found and mqtt_client is not None and wlan.isconnected():
        if not sende_mqtt(mqtt_publish_thema, werte_fuer_mqtt): # Sende auf dem Publish-Thema
             print("MQTT Senden fehlgeschlagen.")

    # --- 5. Display aktualisieren ---
    if tft:
        try:
            tft.fill(st7789.BLACK)

            temp_text = f"Temp: {temperatur_aktuell:.1f} C" if temperatur_aktuell is not None else "Temp: --.- C"
            flow_text = f"Fluss: {durchfluss_aktuell:.1f} L/m" if durchfluss_aktuell >= 0 else "Fluss: Warte..."

            if servo_pwm is None:
                 servo_status_text = "Servo: Fehler"
                 servo_farbe = st7789.YELLOW
            else:
                 servo_status_text = "Servo: Aktiv" if aktueller_servo_zustand_on else "Servo: Inaktiv"
                 servo_farbe = st7789.RED if aktueller_servo_zustand_on else st7789.BLUE

            # Texte schreiben
            tft.text(font, temp_text, 30, 10, st7789.CYAN, st7789.BLACK)
            tft.text(font, flow_text, 30, 40, st7789.GREEN, st7789.BLACK)
            tft.text(font, servo_status_text, 30, 70, servo_farbe, st7789.BLACK)

        except Exception as e:
            print(f"Fehler beim Aktualisieren des Displays: {e}")

    # --- 6. Warte bis zum nächsten Intervall ---
    schleifen_end_zeit = time.ticks_ms()
    verstrichene_zeit_ms = time.ticks_diff(schleifen_end_zeit, schleifen_start_zeit)
    schlaf_zeit_s = max(0, schleifen_intervall_s - (verstrichene_zeit_ms / 1000.0))
    time.sleep(schlaf_zeit_s)

# === Ende der Hauptschleife ===

# === Programmende ===
print("Programm beendet.")
if mqtt_client:
    try: mqtt_client.disconnect()
    except: pass
if tft:
    try: tft.fill(st7789.BLACK)
    except: pass
trenne_wlan()