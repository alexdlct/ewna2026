import os
import socket
import time

# USB serial device where data from the Mac arrives
SERIAL = "/dev/ttyGS0"

# App Lab Docker container
APP_HOST = "172.18.0.2"
APP_PORT = 8765


def connect():
    """Keep trying to connect to the App Lab TCP server."""
    while True:
        try:
            sock = socket.create_connection(
                (APP_HOST, APP_PORT),
                timeout=2
            )

            # Return to normal blocking mode after connection
            sock.settimeout(None)

            print("Connected to App Lab")
            return sock

        except Exception as e:
            print("Waiting for App Lab:", e)
            time.sleep(1)


print("USB relay starting...")
print("Reading:", SERIAL)
print("Forwarding to:", APP_HOST, APP_PORT)


while True:

    try:
        # Open USB serial gadget
        fd = os.open(
            SERIAL,
            os.O_RDONLY
        )

        print("USB ready")

        # Connect to App Lab
        sock = connect()

        forwarded = 0
        last_report = time.time()

        while True:

            # Read bytes coming from Mac
            data = os.read(
                fd,
                4096
            )

            if not data:
                continue

            # With audio frames (AUD: lines) this is ~43 KB/s; printing every
            # chunk would flood the console, so report a running total instead.
            forwarded += len(data)

            if time.time() - last_report >= 5:
                print(
                    f"USB -> App Lab: {forwarded / 1024:.0f} KB forwarded"
                )
                last_report = time.time()

            # Forward exact bytes to App Lab
            try:
                sock.sendall(data)

            except Exception as e:

                print(
                    "App Lab connection lost:",
                    e
                )

                try:
                    sock.close()
                except Exception:
                    pass

                sock = connect()

                # Send the data again after reconnecting
                sock.sendall(data)

    except Exception as e:

        print(
            "Relay error:",
            e
        )

        try:
            os.close(fd)
        except Exception:
            pass

        try:
            sock.close()
        except Exception:
            pass

        time.sleep(1)