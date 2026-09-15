Osmo Nano Receiver
Experimental DJI Osmo Nano preview receiver for Windows. The program connects to the camera via its Wi‑Fi, negotiates UDP DUML on port 9004, and saves the received AVC fragments to nano-live.h264.


Python 3.10 or newer

Computer connected to the Osmo Nano Wi‑Fi network
terminal:

python3 osmo_nano_receiver.py --seconds 99999 --preview

powershell:
python .\osmo_nano_receiver.py --seconds 99999 --preview

In OBS, add Window Capture, select the ffplay window, then click Start Virtual Camera. In the target application, choose OBS Virtual Camera.

This prototype does not change the camera’s recording settings. If the camera does not respond, close DJI Mimo and ensure your computer is the only client connecting to the camera.








# Osmo Nano Receiver

Eksperymentalny odbiornik podgladu DJI Osmo Nano dla Windows. Program laczy sie z kamera przez jej Wi-Fi, negocjuje UDP DUML na porcie `9004` i zapisuje odebrane fragmenty AVC do `nano-live.h264`.

- komputer polaczony z siecia Wi-Fi Osmo Nano

## Uruchomienie

terminal: 
python3 osmo_nano_receiver.py --seconds 99999 --preview

powershell:
python .\osmo_nano_receiver.py --seconds 99999 --preview

W OBS dodaj **Window Capture**, wybierz okno `ffplay`, a nastepnie kliknij
**Start Virtual Camera**. W aplikacji docelowej wybierz `OBS Virtual Camera`.

Prototyp nie zmienia ustawien nagrywania. Jesli kamera nie odpowie, zamknij DJI Mimo i upewnij sie, ze komputer jest jedynym klientem wykonujacym polaczenie z kamera.
