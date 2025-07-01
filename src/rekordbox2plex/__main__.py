from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env

from .rekordbox_file_resolver import resolve_track
import json

def main():
  file_path = "/data/music/main/Minimal but pling plong/Cajal - 0220 (Original Mix).aiff"
  print(f"Resolving file: {file_path}")
  track = resolve_track(file_path)
  if track:
      print("File resolved successfully:", json.dumps(track, indent=2))
  else:
      print("File could not be resolved.")  

if __name__ == "__main__":
    main()