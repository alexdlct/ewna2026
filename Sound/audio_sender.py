import base64
import sounddevice as sd
import numpy as np
import serial
import subprocess
import threading
import time
import glob
import sys

# ============================================================
# SOUND GUARDIAN - AUDIO SENDER
# ============================================================

MIC_NAME = "UAC 1.0 Microphone & HID-Mediakey"

# 16 kHz is what the on-board TinyAudioNet classifier expects (CoreAudio
# resamples if the mic only offers 48 kHz).
SAMPLE_RATE = 16000
BLOCK_DURATION = 0.25
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_DURATION)

# What goes over the wire, one line per block:
#   AUD:<base64 int16 PCM>   the audio itself, for the classifier (CLASSIFIER=stream)
#   VOL:<rms>                legacy volume-only line for the LOUD detector
# ~43 KB/s with audio on; the USB virtual serial port handles that easily.
SEND_AUDIO = True
SEND_VOLUME = False

BAUD_RATE = 115200
PREFERRED_PORT = "/dev/cu.usbmodem22798816512"

# How often macOS checks for the physical USB mic
HARDWARE_CHECK_INTERVAL = 1.0


# ============================================================
# GLOBAL STATE
# ============================================================

usb_mic_present = False
hardware_check_ready = False
running = True


# ============================================================
# PHYSICAL USB MICROPHONE CHECK
# ============================================================

def check_usb_mic_hardware():
    """
    Check macOS hardware for the physical UAC USB microphone.
    """

    try:
        result = subprocess.run(
            ["system_profiler", "SPAudioDataType"],
            capture_output=True,
            text=True,
            timeout=10
        )

        return MIC_NAME in result.stdout

    except Exception:
        return False


def hardware_monitor():
    """
    Runs separately from audio capture so system_profiler
    never blocks the microphone stream.
    """

    global usb_mic_present
    global hardware_check_ready
    global running

    previous_state = None

    while running:

        present = check_usb_mic_hardware()

        usb_mic_present = present
        hardware_check_ready = True

        if present != previous_state:

            if present:
                print()
                print("✓ UAC USB MICROPHONE DETECTED")
                print()

            else:
                print()
                print("⚠ UAC USB MICROPHONE DISCONNECTED")
                print("Audio transmission disabled.")
                print()

            previous_state = present

        time.sleep(HARDWARE_CHECK_INTERVAL)


# ============================================================
# FIND USB MICROPHONE IN SOUNDDEVICE
# ============================================================

def find_usb_microphone():
    """
    Find ONLY the exact UAC microphone.
    Never return the MacBook microphone.
    """

    try:
        devices = sd.query_devices()

        for index, device in enumerate(devices):

            if (
                device["name"] == MIC_NAME
                and device["max_input_channels"] > 0
            ):
                return index

    except Exception:
        pass

    return None


# ============================================================
# WAIT FOR USB MICROPHONE
# ============================================================

def wait_for_usb_microphone():

    print("Waiting for UAC USB microphone...")

    while running:

        # Physical USB mic must exist
        if not usb_mic_present:
            time.sleep(0.5)
            continue

        # PortAudio must also see exact UAC device
        mic_index = find_usb_microphone()

        if mic_index is None:
            print("USB mic detected. Waiting for CoreAudio...")
            time.sleep(1)
            continue

        try:

            device = sd.query_devices(mic_index)

            # Final safety check
            if device["name"] != MIC_NAME:
                time.sleep(1)
                continue

            stream = sd.InputStream(
                device=mic_index,
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=BLOCK_SIZE
            )

            stream.start()

            print()
            print("✓ USB MICROPHONE ACTIVE")
            print(f"  Device #{mic_index}")
            print(f"  {device['name']}")
            print()

            return stream

        except Exception as e:

            print(f"USB mic not ready: {e}")
            time.sleep(2)

    return None


# ============================================================
# UNO Q SERIAL CONNECTION
# ============================================================

def find_uno_port():

    ports = glob.glob("/dev/cu.usbmodem*")

    if PREFERRED_PORT in ports:
        return PREFERRED_PORT

    if ports:
        return ports[0]

    return None


def connect_to_uno():

    print("Waiting for UNO Q...")

    while running:

        port = find_uno_port()

        if port:

            try:

                ser = serial.Serial(
                    port,
                    BAUD_RATE,
                    timeout=1
                )

                time.sleep(0.5)

                print()
                print("✓ UNO Q CONNECTED")
                print(f"  {port}")
                print()

                return ser

            except serial.SerialException:
                pass

        time.sleep(1)

    return None


# ============================================================
# CLEANUP
# ============================================================

def close_stream(stream):

    if stream is None:
        return

    try:
        stream.abort()
    except Exception:
        pass

    try:
        stream.close()
    except Exception:
        pass


# ============================================================
# MAIN
# ============================================================

def main():

    global running

    print()
    print("======================================")
    print("          SOUND GUARDIAN")
    print("======================================")
    print()

    # --------------------------------------------------------
    # Start physical USB monitor in background
    # --------------------------------------------------------

    monitor = threading.Thread(
        target=hardware_monitor,
        daemon=True
    )

    monitor.start()

    print("Checking USB microphone hardware...")

    while not hardware_check_ready:
        time.sleep(0.1)

    # --------------------------------------------------------
    # Connect to UNO Q
    # --------------------------------------------------------

    ser = connect_to_uno()

    # --------------------------------------------------------
    # Wait for exact UAC microphone
    # --------------------------------------------------------

    stream = wait_for_usb_microphone()

    if stream is None:
        return

    print("✓ SYSTEM READY")
    print("Listening ONLY to UAC USB microphone...")
    print()

    # ========================================================
    # AUDIO LOOP
    # ========================================================

    while running:

        # ----------------------------------------------------
        # Physical microphone disappeared
        # ----------------------------------------------------

        if not usb_mic_present:

            print()
            print("======================================")
            print("⚠ USB MICROPHONE DISCONNECTED")
            print("Stopping audio transmission.")
            print("======================================")
            print()

            close_stream(stream)

            try:
                ser.close()
            except Exception:
                pass

            # Exit completely.
            # LaunchAgent can restart us with fresh PortAudio.
            sys.exit(1)

        # ----------------------------------------------------
        # Read microphone
        # ----------------------------------------------------

        try:

            audio, overflowed = stream.read(BLOCK_SIZE)

        except (sd.PortAudioError, OSError) as e:

            print()
            print("⚠ USB AUDIO STREAM FAILED")
            print(f"  {e}")
            print("Exiting for clean restart...")
            print()

            close_stream(stream)

            sys.exit(1)

        # ----------------------------------------------------
        # Hardware monitor may have detected unplug while
        # stream.read() was running.
        # ----------------------------------------------------

        if not usb_mic_present:

            print()
            print("⚠ USB MICROPHONE LOST")
            print("Discarding audio block.")
            print("Exiting for clean restart...")
            print()

            close_stream(stream)

            sys.exit(1)

        if overflowed:
            print("⚠ Audio buffer overflow")

        # ----------------------------------------------------
        # Calculate RMS
        # ----------------------------------------------------

        audio = audio[:, 0]

        rms = float(
            np.sqrt(
                np.mean(
                    np.square(audio)
                )
            )
        )

        print(f"USB MIC VOLUME: {rms:.4f}")

        # ----------------------------------------------------
        # Send to UNO Q: audio frames for the on-board
        # classifier and/or the legacy volume line
        # ----------------------------------------------------

        message = ""

        if SEND_VOLUME:
            message += f"VOL:{rms:.4f}\n"

        if SEND_AUDIO:
            pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
            message += "AUD:" + base64.b64encode(pcm.tobytes()).decode("ascii") + "\n"

        try:

            ser.write(message.encode("ascii"))
            ser.flush()

        except serial.SerialException:

            print()
            print("⚠ UNO Q CONNECTION LOST")
            print("Waiting for UNO Q...")
            print()

            try:
                ser.close()
            except Exception:
                pass

            ser = connect_to_uno()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        running = False

        print()
        print("Sound Guardian stopped.")
        print()

        sys.exit(0)
