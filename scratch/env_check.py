import sys
import os
print("Python:", sys.executable)
print("CWD:", os.getcwd())
try:
    import pygame
    print("pygame ok")
except Exception as e:
    print("pygame fail:", e)

try:
    import groq
    print("groq ok")
except Exception as e:
    print("groq fail:", e)

try:
    import faster_whisper
    print("whisper ok")
except Exception as e:
    print("whisper fail:", e)

try:
    import edge_tts
    print("edge-tts ok")
except Exception as e:
    print("edge-tts fail:", e)
