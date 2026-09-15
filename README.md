# Osmo Nano Receiver

Eksperymentalny odbiornik podgladu DJI Osmo Nano dla Windows. Program laczy sie z kamera przez jej Wi-Fi, negocjuje UDP DUML na porcie `9004` i zapisuje odebrane fragmenty AVC do `nano-live.h264`.

## Wymagania

- Windows 10/11
- Python 3.10 lub nowszy
- komputer polaczony z siecia Wi-Fi Osmo Nano

## Uruchomienie

```powershell
cd C:\Users\mbiel\OsmoNanoReceiver
python .\osmo_nano_receiver.py --seconds 30
```

Po udanym odbiorze sprawdz plik narzedziem FFmpeg:

```powershell
ffplay -f h264 .\nano-live.h264
```

Podglad na zywo z jednoczesnym zapisem:

```powershell
python .\osmo_nano_receiver.py --seconds 300 --preview
```

W OBS dodaj **Window Capture**, wybierz okno `ffplay`, a nastepnie kliknij
**Start Virtual Camera**. W aplikacji docelowej wybierz `OBS Virtual Camera`.

Prototyp nie zmienia ustawien nagrywania. Jesli kamera nie odpowie, zamknij DJI Mimo i upewnij sie, ze komputer jest jedynym klientem wykonujacym polaczenie z kamera.