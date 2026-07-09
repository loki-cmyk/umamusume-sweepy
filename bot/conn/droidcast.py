"""
DroidCast_raw screen capture backend.

Uses the DroidCast_raw APK (https://github.com/Torther/DroidCastS) running
on the Android device to serve raw RGB565 bitmaps over HTTP.  This is
significantly faster than the default ADB screencap pipe (~30-60 ms vs
~100-200 ms) because encoding/decoding PNG is skipped entirely.

Lifecycle
---------
1. ``push_apk()``   – one-time push of the APK to /data/local/tmp
2. ``start()``      – launch the DroidCast class via ``app_process``, set up
                       adb forward, and wait for the HTTP server to come online
3. ``capture()``    – HTTP GET /screenshot → decode RGB565 → numpy BGR array
4. ``stop()``       – kill the server process on the device and remove the
                       adb forward rule
"""

import os
import time
import struct
import socket
import subprocess
import threading
from typing import Optional

import cv2
import numpy as np

import bot.base.log as logger
from config import CONFIG

log = logger.get_logger(__name__)

_APK_LOCAL = os.path.join("deps", "droidcast", "DroidCast_raw-release-1.0.apk")
_APK_REMOTE = "/data/local/tmp/DroidCast_raw.apk"
_DROIDCAST_CLASS = "ink.mol.droidcast_raw.Main"
_DEVICE_PORT = getattr(CONFIG.bot.auto.adb, 'droidcast_port', 53516) or 53516


def _http_get_bytes(host: str, port: int, path: str, timeout: float = 3.0) -> Optional[bytes]:
    """Minimal HTTP/1.0 GET without the ``requests`` dependency."""
    if port != _DEVICE_PORT:
        log.warning(f"Connection to port {port} blocked: not the configured DroidCast port ({_DEVICE_PORT}).")
        return None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        request = f"GET {path} HTTP/1.0\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        sock.sendall(request.encode())

        chunks = []
        while True:
            chunk = sock.recv(1048576)
            if not chunk:
                break
            chunks.append(chunk)
        sock.close()
        data = b"".join(chunks)

        # Split header/body on the first blank line
        sep = data.find(b"\r\n\r\n")
        if sep == -1:
            return data  # no header?  just return raw
        return data[sep + 4:]
    except Exception as exc:
        log.debug(f"DroidCast HTTP GET failed: {exc}")
        return None


class DroidCastCapture:
    """Manages DroidCast_raw server lifecycle and captures screenshots."""

    def __init__(self, adb_path: str, device_name: str):
        self._adb = adb_path          # e.g. "deps\\adb\\"
        self._device = device_name    # e.g. "127.0.0.1:16384"
        self._local_port: int = 0
        self._started = False
        self._lock = threading.Lock()


    def _adb_cmd(self, *args, timeout=10) -> subprocess.CompletedProcess:
        cmd = [os.path.join(self._adb, "adb.exe"), "-s", self._device, *args]
        log.debug(f"DroidCast ADB: {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=True, timeout=timeout)

    def _adb_shell_bg(self, shell_cmd: str):
        """Run an adb shell command in the background (non-blocking)."""
        cmd = [os.path.join(self._adb, "adb.exe"), "-s", self._device, "shell", shell_cmd]
        log.debug(f"DroidCast ADB bg: {' '.join(cmd)}")
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


    def push_apk(self):
        """Push the DroidCast_raw APK to the device if not already present."""
        check = self._adb_cmd("shell", "ls", _APK_REMOTE)
        if _APK_REMOTE.split("/")[-1].encode() in check.stdout:
            log.info("DroidCast APK already on device")
            return
        log.info("Pushing DroidCast APK to device …")
        result = self._adb_cmd("push", _APK_LOCAL, _APK_REMOTE)
        if result.returncode != 0:
            log.error(f"Failed to push APK: {result.stderr.decode()}")
            raise RuntimeError("DroidCast APK push failed")
        log.info("DroidCast APK pushed successfully")

    def _setup_forward(self):
        """Set up adb forward from a local port to the DroidCast port on device."""
        # Check for existing forwards first
        result = self._adb_cmd("forward", "--list")
        for line in result.stdout.decode().splitlines():
            parts = line.split()
            if len(parts) >= 3:
                device_serial, local_spec, remote_spec = parts[0], parts[1], parts[2]
                if device_serial == self._device:
                    if remote_spec == f"tcp:{_DEVICE_PORT}":
                        local_port_str = local_spec.split(":")[1]
                        if local_port_str.isdigit():
                            local_port = int(local_port_str)
                            # Safeguard: only reuse if the local port is equal to our configured port
                            if local_port == _DEVICE_PORT:
                                self._local_port = local_port
                                log.info(f"Reusing existing forward on port {self._local_port}")
                                return
                            else:
                                log.warning(f"Ignoring existing forward on port {local_port} for {self._device} as it is not the configured port {_DEVICE_PORT}")

        # Create new forward
        self._local_port = _DEVICE_PORT
        result = self._adb_cmd("forward", f"tcp:{self._local_port}", f"tcp:{_DEVICE_PORT}")
        if result.returncode != 0:
            log.warning(f"adb forward failed, trying to remove existing forward and retry...")
            # If it failed (likely already bound or stale), remove any existing forward for our port and try again
            self._adb_cmd("forward", "--remove", f"tcp:{self._local_port}")
            result = self._adb_cmd("forward", f"tcp:{self._local_port}", f"tcp:{_DEVICE_PORT}")
            if result.returncode != 0:
                log.error(f"adb forward failed after cleanup: {result.stderr.decode()}")
                raise RuntimeError("adb forward failed")
        log.info(f"ADB forward set: localhost:{self._local_port} → device:{_DEVICE_PORT}")

    def _remove_forward(self):
        """Remove the adb forward rule."""
        if self._local_port:
            if self._local_port != _DEVICE_PORT:
                log.warning(f"Blocked removing forward for unconfigured port: {self._local_port}")
                return
            try:
                self._adb_cmd("forward", "--remove", f"tcp:{self._local_port}")
            except Exception:
                pass
            self._local_port = 0

    def _kill_server(self):
        """Kill any running DroidCast processes on the device."""
        try:
            result = self._adb_cmd("shell", "ps | grep droidcast_raw")
            for line in result.stdout.decode().splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    pid = parts[1]
                    self._adb_cmd("shell", "kill", "-9", pid)
                    log.info(f"Killed DroidCast pid {pid}")
        except Exception as exc:
            log.debug(f"Error killing DroidCast: {exc}")

    def start(self):
        """Start the DroidCast_raw server on the device."""
        with self._lock:
            if self._started:
                return

            log.info("Starting DroidCast_raw server …")
            self._kill_server()
            # If there's an issue and we're restarting/starting, remove the existing forward rule first
            if self._local_port:
                self._remove_forward()
            self.push_apk()

            # Launch via app_process
            self._adb_shell_bg(
                f"CLASSPATH={_APK_REMOTE} app_process / {_DROIDCAST_CLASS} > /dev/null 2>&1"
            )

            self._setup_forward()

            # Wait for startup
            if self._wait_startup():
                self._started = True
                log.info("DroidCast_raw server is online")
            else:
                log.warning("DroidCast_raw startup timed out, will attempt capture anyway")
                self._started = True

    def _wait_startup(self, timeout: float = 10.0) -> bool:
        """Wait for the DroidCast HTTP server to respond."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.25)
            try:
                resp = _http_get_bytes("127.0.0.1", self._local_port, "/", timeout=2.0)
                if resp is not None:
                    log.debug("DroidCast server responded")
                    return True
            except Exception:
                pass
        return False

    def capture(self) -> Optional[np.ndarray]:
        """
        Capture a screenshot via DroidCast_raw.

        Returns an OpenCV BGR numpy array, or None on failure.
        """
        if not self._started:
            self.start()

        data = _http_get_bytes("127.0.0.1", self._local_port, "/screenshot", timeout=3.0)
        if data is None or len(data) < 100:
            log.warning("DroidCast capture returned no data, retrying after restart …")
            self._started = False
            self.start()
            data = _http_get_bytes("127.0.0.1", self._local_port, "/screenshot", timeout=3.0)
            if data is None or len(data) < 100:
                log.error("DroidCast capture failed after restart")
                return None

        try:
            return self._decode_rgb565(data)
        except Exception as exc:
            log.error(f"DroidCast decode failed: {exc}")
            # Maybe it returned PNG instead of raw (DroidCast vs DroidCast_raw)
            try:
                return self._decode_png(data)
            except Exception:
                return None

    @staticmethod
    def _decode_rgb565(data: bytes) -> np.ndarray:
        """Decode RGB565 raw bitmap data to BGR numpy array."""
        arr = np.frombuffer(data, dtype=np.uint16)

        # Try common resolutions to determine shape
        for h, w in [(1280, 720), (1920, 1080), (2560, 1440), (2340, 1080),
                      (720, 1280), (1080, 1920), (1440, 2560), (1080, 2340)]:
            if arr.size == h * w:
                arr = arr.reshape((h, w))
                break
        else:
            # Try to infer from pixel count
            total = arr.size
            # Assume 720 width (portrait) as fallback
            if total % 720 == 0:
                h = total // 720
                arr = arr.reshape((h, 720))
            elif total % 1280 == 0:
                h = total // 1280
                arr = arr.reshape((h, 1280))
            else:
                raise ValueError(f"Cannot determine image dimensions from {total} pixels")

        # RGB565 → RGB888 conversion (optimized, ~2.7ms on typical resolution)
        # Ported from ALAS DroidCast implementation
        tmp = np.empty_like(arr)

        cv2.bitwise_and(arr, 0b1111100000000000, dst=tmp)
        r = cv2.convertScaleAbs(tmp, alpha=0.0040283203125)  # (1/256) * (256/248) roughly

        cv2.bitwise_and(arr, 0b0000011111100000, dst=tmp)
        g = cv2.convertScaleAbs(tmp, alpha=0.126953125)       # (1/8) * (256/252)

        cv2.bitwise_and(arr, 0b0000000000011111, dst=tmp)
        b = cv2.convertScaleAbs(tmp, alpha=8.25)              # 8 * (256/248)

        image = cv2.merge([b, g, r])  # Note: BGR order for OpenCV
        return image

    @staticmethod
    def _decode_png(data: bytes) -> np.ndarray:
        """Fallback: decode PNG data."""
        arr = np.frombuffer(data, np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Failed to decode PNG image")
        return image

    def stop(self):
        """Stop the DroidCast server and clean up."""
        with self._lock:
            if not self._started:
                return
            log.info("Stopping DroidCast_raw server …")
            self._kill_server()
            self._remove_forward()
            self._started = False
            log.info("DroidCast_raw stopped")

    @property
    def is_running(self) -> bool:
        return self._started
