"""
Symbol Cycle - standby demo app.

Everything happens in the sketch (sketch/sketch.ino), which cycles through
every Sound Guardian symbol on the 8x8 RGB matrix. This Python side only
keeps the App Lab app alive; it sends nothing over the Bridge.
"""

from arduino.app_utils import App

print("Symbol Cycle: the sketch is cycling all symbols on the matrix (pin 6)")

App.run()
