import os
import logging
from obswebsocket import obsws, requests, exceptions

class ObsManager:
    def __init__(self):
        self.host = os.getenv("OBS_WEBSOCKET_HOST", "localhost")
        self.port = int(os.getenv("OBS_WEBSOCKET_PORT", 4455))
        self.password = os.getenv("OBS_WEBSOCKET_PASSWORD", "")
        self.text_source_name = os.getenv("OBS_TEXT_SOURCE_NAME")
        self.ws = None

    def connect(self):
        if not self.text_source_name:
            logging.warning("OBS_TEXT_SOURCE_NAME is not set. OBS integration will be disabled.")
            return False

        try:
            self.ws = obsws(self.host, self.port, self.password)
            self.ws.connect()
            logging.info("Successfully connected to OBS WebSocket.")
            return True
        except exceptions.ConnectionFailure as e:
            logging.error(f"Failed to connect to OBS WebSocket: {e}")
            self.ws = None
            return False
        except Exception as e:
            logging.error(f"An unexpected error occurred during OBS connection: {e}")
            self.ws = None
            return False

    def disconnect(self):
        if self.ws:
            self.ws.disconnect()
            logging.info("Disconnected from OBS WebSocket.")
            self.ws = None

    def update_text_source(self, text):
        if not self.ws:
            # Don't log every time if connection was never established
            # A warning is already issued during connect()
            return

        try:
            # The request is SetInputSettings
            # The input name is the name of the text source
            # The settings object contains the new text
            request = requests.SetInputSettings(
                inputName=self.text_source_name,
                inputSettings={'text': text}
            )
            self.ws.call(request)
            logging.info(f"Updated OBS text source '{self.text_source_name}' with new text.")
        except exceptions.ConnectionFailure:
            logging.error("Lost connection to OBS WebSocket. Will try to reconnect.")
            self.disconnect()
            self.connect()
        except Exception as e:
            logging.error(f"Failed to update OBS text source: {e}")

    def format_queue_text(self, queue):
        """Formats the queue list into a string for OBS."""
        if not queue:
            return "" # Return an empty string if the queue is empty

        # Format: "1. Nickname1   2. Nickname2   3. Nickname3"
        # Using a few spaces as a separator.
        formatted_queue = "   ".join(f"{i+1}. {name}" for i, name in enumerate(queue))
        return formatted_queue
