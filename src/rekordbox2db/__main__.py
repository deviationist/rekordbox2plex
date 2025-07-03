import os
from .KeyExtractor import KeyExtractor

def main():
    REKORDBOX_EXECUTABLE_PATH = os.getenv("REKORDBOX_EXECUTABLE_PATH")
    ke = KeyExtractor(REKORDBOX_EXECUTABLE_PATH)

    ke.run()
