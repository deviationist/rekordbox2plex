__import__('dotenv').load_dotenv()
from .track_sync import track_metadata_sync
from .playlist_sync import playlist_sync

def main():
  track_metadata_sync()
  #playlist_sync()
