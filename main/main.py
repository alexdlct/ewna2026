import socket
import threading
import queue
import time

from arduino.app_utils import App, Bridge


HOST = "0.0.0.0"
PORT = 8765

commands = queue.Queue()
was_loud = False

def command_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server.bind((HOST, PORT))
    server.listen(5)

    print("Command server listening on port", PORT)

    while True:
        conn, addr = server.accept()
        print("Relay connected:", addr)

        buffer = b""

        try:
            while True:
                data = conn.recv(1024)

                if not data:
                    break

                buffer += data

                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)

                    command = line.decode(
                        "utf-8",
                        errors="ignore"
                    ).strip()

                    if command:
                        commands.put(command)

        except Exception as e:
            print("Connection error:", e)

        finally:
            conn.close()


def handle_command(command):

    global was_loud

    if command.startswith("VOL:"):
        try:
            volume = float(command.split(":", 1)[1])

            print(f"MIC VOLUME: {volume:.4f}")

            if volume > 0.065:
                if not was_loud:
                    print(">>> LOUD -> MCU")
                    Bridge.notify("sound_event", "LOUD")
                    was_loud = True
            else:
                was_loud = False

        except ValueError:
            print("Invalid volume:", command)

    elif command == "VOICE":
        print(">>> HUMAN VOICE")

    elif command == "GLASS":
        print(">>> GLASS BREAK")

    elif command == "WATER":
        print(">>> WATER")

    elif command == "ALARM":
        print(">>> ALARM")

    elif command == "SOS":
        print(">>> SOS")

    elif command == "CLEAR":
        print(">>> CLEAR")

    else:
        print(">>> UNKNOWN:", command)

def loop():

    # Process every waiting command
    while not commands.empty():
        command = commands.get()
        handle_command(command)

    time.sleep(0.01)


# Start TCP receiver in background
threading.Thread(
    target=command_server,
    daemon=True
).start()


print("UNO Q App Lab receiver started")

App.run(user_loop=loop)