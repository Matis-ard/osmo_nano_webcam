#!/usr/bin/env python3
"""Experimental DJI Osmo Nano live-view receiver.

The camera must already be connected to the computer's Wi-Fi network.
This prototype negotiates the UDP datalink and writes Annex-B H.264 to a file.
"""

from __future__ import annotations

import argparse
import random
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path


CAMERA_HOST = "192.168.2.1"
CAMERA_PORT = 9004


def crc8(data: bytes) -> int:
    value = 0x77
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = ((value >> 1) ^ 0x8C) if value & 1 else value >> 1
    return value


def crc16(data: bytes) -> int:
    value = 0x3692
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = ((value >> 1) ^ 0x8408) if value & 1 else value >> 1
    return value


def duml_frame(receiver: int, command_set: int, command_id: int,
               payload: bytes, sequence: int) -> bytes:
    body = bytes((0x02, receiver)) + struct.pack("<H", sequence)
    body += bytes((0x40, command_set, command_id)) + payload
    total = 13 + len(payload)
    header = bytes((0x55, total & 0xFF, 0x04 | ((total >> 8) & 3)))
    frame = header + bytes((crc8(header),)) + body
    return frame + struct.pack("<H", crc16(frame))


def transport_header(packet_type: int, payload_length: int,
                     session: int, sequence: int) -> bytes:
    total = 8 + payload_length
    word = 0x8000 | (total & 0x3FFF)
    header = struct.pack("<HHHB", word, session, sequence, packet_type)
    return header + bytes((__import__("functools").reduce(int.__xor__, header, 0),))


def handshake_payload(base_sequence: int) -> bytes:
    payload = bytearray((
        0, 0, 0x64, 0, 0x64, 0, 0xC0, 5, 0x14, 0, 0, 0x64, 0, 0,
        1, 0x90, 1, 0xC0, 5, 0x14, 0, 0, 0x64, 0, 0x14, 0, 0x64, 0,
        0xC0, 5, 0x14, 0, 0, 0x64, 0, 1, 1, 4, 1, 2,
    ))
    payload[0:2] = struct.pack("<H", base_sequence)
    return bytes(payload)


def routing_header(sequence: int, counter: int) -> bytes:
    return struct.pack("<HH", (sequence - 8) & 0xFFFF, sequence) + bytes(
        (0, 0, 0, 0, counter & 0xFF, 1, 0, 0)
    )


def command_packet(frame: bytes, session: int, transport_sequence: int,
                   command_counter: int) -> bytes:
    payload = routing_header(transport_sequence, command_counter) + frame
    return transport_header(5, len(payload), session, transport_sequence) + payload


def ack_packet(session: int, sequence: int, video_cursor: int,
               acked_data_cursor: int, extra_cursor: int) -> bytes:
    def group(value: int) -> bytes:
        return struct.pack("<HH", value, value) + bytes(4)

    payload = (group(video_cursor) + group(acked_data_cursor)
               + group(extra_cursor) + bytes(2))
    return transport_header(4, len(payload), session, sequence) + payload


def subscription(name: str, sub_id: int) -> bytes:
    raw = name.encode("utf-8")
    inner_length = len(raw) + 6
    return bytes((2, 2, 0, 0)) + struct.pack("<I", sub_id) + bytes(3)
    # The remaining bytes are appended by the caller; kept explicit below.


def subscription_payload(name: str, sub_id: int) -> bytes:
    raw = name.encode("utf-8")
    return (bytes((2, 2, 0, 0)) + struct.pack("<I", sub_id) + bytes(3)
            + struct.pack("<HH", len(raw) + 6, len(raw)) + raw + bytes(4))


class NanoReceiver:
    def __init__(self, output: Path, timeout: float) -> None:
        self.output = output
        self.timeout = timeout
        self.session = random.randrange(0x1000, 0xFFFE)
        self.base_sequence = random.randrange(0x1000, 0xF000) & 0xFFF8
        self.transport_sequence = 0
        self.command_sequence = 0xA000
        self.command_counter = 0
        self.video_cursor = 0
        self.acked_data_cursor = self.base_sequence
        self.extra_cursor = self.base_sequence
        self.video_seen = False
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 0))
        self.sock.settimeout(0.25)

    def send_raw(self, packet_type: int, payload: bytes) -> None:
        packet = transport_header(packet_type, len(payload), self.session,
                                   self.transport_sequence) + payload
        self.sock.sendto(packet, (CAMERA_HOST, CAMERA_PORT))
        self.transport_sequence = (self.transport_sequence + 8) & 0xFFFF

    def send_command(self, command_set: int, command_id: int, payload: bytes) -> None:
        frame = duml_frame(0x41 if (command_set, command_id) == (0x09, 0xA8) else 0x01,
                           command_set, command_id, payload, self.command_sequence)
        packet = command_packet(frame, self.session, self.transport_sequence,
                                self.command_counter)
        self.sock.sendto(packet, (CAMERA_HOST, CAMERA_PORT))
        self.transport_sequence = (self.transport_sequence + 8) & 0xFFFF
        self.command_sequence = (self.command_sequence + 1) & 0xFFFF
        self.command_counter = (self.command_counter + 1) & 0xFF

    def handshake(self) -> None:
        for _ in range(20):
            self.send_raw(0, handshake_payload(self.base_sequence))
            deadline = time.monotonic() + 0.35
            while time.monotonic() < deadline:
                try:
                    data, _ = self.sock.recvfrom(65535)
                except socket.timeout:
                    break
                if len(data) >= 8 and data[6] == 0:
                    self.transport_sequence = (self.base_sequence + 8) & 0xFFFF
                    print("Handshake OK")
                    return
        raise RuntimeError("Kamera nie odpowiedziala na handshake. Sprawdz Wi-Fi i adres 192.168.2.1.")

    def start_session(self) -> None:
        # Registration and one status subscription are enough to arm the media path.
        registration = bytes(1) + b"APP" + bytes(38) + bytes((2, 0, 0, 0, 0, 0, 0, 0, 0, 2, 8)) + bytes(11)
        self.send_command(0x00, 0x81, registration)
        self.send_command(0x00, 0x99, subscription_payload("cam_status", 0x69DF))
        self.send_command(0x02, 0x09, bytes(10) + bytes((3,)))
        self.send_command(0x09, 0xA8, bytes((0, 4, 2, 0, 0, 0, 0, 0, 0, 0)))
        print("Wyslano rejestracje i start podgladu Nano")

    def ack_loop(self) -> None:
        while self.running:
            self.send_raw(4, ack_packet(self.session, self.transport_sequence,
                                        self.video_cursor,
                                        self.acked_data_cursor,
                                        self.extra_cursor)[8:])
            time.sleep(0.025)

    def receive(self, preview: bool) -> None:
        frames: dict[int, bytearray] = {}
        current = None
        stream_started = False
        capture_started = time.monotonic()
        player = None
        if preview:
            try:
                player = subprocess.Popen(
                    ["ffplay", "-fflags", "nobuffer+discardcorrupt", "-flags", "low_delay",
                     "-framedrop", "-sync", "video", "-probesize", "32",
                     "-analyzeduration", "0", "-f", "h264", "-i", "pipe:0"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError as error:
                raise RuntimeError("Nie znaleziono ffplay. Zainstaluj FFmpeg albo uruchom bez --preview.") from error

        def write_frame(stream, frame_id: int) -> None:
            nonlocal stream_started
            data = bytes(frames.pop(frame_id, b""))
            if not stream_started:
                keyframe = data.find(b"\x00\x00\x01\x67")
                if keyframe < 0:
                    keyframe = data.find(b"\x00\x00\x00\x01\x67")
                if keyframe < 0:
                    return
                stream_started = True
                data = data[keyframe:]
            if data:
                stream.write(data)
                stream.flush()
                if player is not None and player.stdin is not None:
                    try:
                        player.stdin.write(data)
                        player.stdin.flush()
                    except (BrokenPipeError, OSError):
                        pass

        try:
            with self.output.open("wb") as stream:
                while time.monotonic() - capture_started < self.timeout:
                    try:
                        packet, _ = self.sock.recvfrom(65535)
                    except socket.timeout:
                        continue
                    if len(packet) < 20:
                        continue
                    packet_type = packet[6]
                    packet_cursor = struct.unpack_from("<H", packet, 4)[0]
                    if packet_type == 1 and len(packet) >= 34:
                        # Telemetry seeds the non-video ACK windows.
                        self.acked_data_cursor = struct.unpack_from("<H", packet, 18)[0]
                        self.extra_cursor = struct.unpack_from("<H", packet, 26)[0]
                    elif packet_type == 3:
                        self.acked_data_cursor = packet_cursor
                    if packet_type != 2:
                        continue
                    self.video_cursor = packet_cursor
                    self.video_seen = True
                    frame_id = packet[16]
                    if current is not None and frame_id != current:
                        write_frame(stream, current)
                        current = frame_id
                    if current is None:
                        current = frame_id
                    frames.setdefault(frame_id, bytearray()).extend(packet[20:])
                if current is not None:
                    write_frame(stream, current)
                print(f"Odebrano pakietow wideo: {'tak' if self.video_seen else 'nie'}")
        finally:
            if player is not None:
                if player.stdin is not None:
                    player.stdin.close()
                player.wait(timeout=3)

    def run(self, preview: bool) -> None:
        try:
            self.handshake()
            self.start_session()
            thread = threading.Thread(target=self.ack_loop, daemon=True)
            thread.start()
            self.receive(preview)
        finally:
            self.running = False
            self.sock.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", type=Path, default=Path("nano-live.h264"))
    parser.add_argument("-t", "--seconds", type=float, default=30)
    parser.add_argument("--preview", action="store_true", help="otworz podglad przez ffplay")
    args = parser.parse_args()
    NanoReceiver(args.output, args.seconds).run(args.preview)


if __name__ == "__main__":
    main()