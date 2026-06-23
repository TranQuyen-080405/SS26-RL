import network

def setup_wifi(essid='xBot_ESP32S3_Web', password='12345678'):
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=essid, password=password)
    return ap.ifconfig()[0]
