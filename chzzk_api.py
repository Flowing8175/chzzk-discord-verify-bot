import os
import aiohttp
import logging
from typing import Optional

class ChzzkAPI:
    """A wrapper for the Chzzk API."""

    def __init__(self, client_id: str, client_secret: str, access_token: str, refresh_token: str):
        self.api_url = "https://openapi.chzzk.naver.com"
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._session = aiohttp.ClientSession()
        logging.info("ChzzkAPI initialized.")

    async def close(self):
        """Closes the aiohttp session."""
        await self._session.close()

    async def refresh_access_token(self) -> bool:
        """
        Refreshes the access token using the refresh token.
        Returns True if successful, False otherwise.
        """
        url = f"{self.api_url}/auth/v1/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        try:
            async with self._session.post(url, json=data) as response:
                if response.status == 200:
                    content = await response.json()
                    self.access_token = content["content"]["accessToken"]
                    self.refresh_token = content["content"]["refreshToken"]
                    logging.info("Successfully refreshed Chzzk access token.")
                    return True
                else:
                    logging.error(f"Failed to refresh Chzzk token. Status: {response.status}, Body: {await response.text()}")
                    return False
        except Exception as e:
            logging.error(f"An exception occurred while refreshing Chzzk token: {e}")
            return False

    async def get_websocket_url(self) -> Optional[str]:
        """
        Gets the WebSocket URL for the chat server.
        """
        url = f"{self.api_url}/open/v1/sessions/auth"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            async with self._session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("content", {}).get("url")
                else:
                    logging.error(f"Failed to get WebSocket URL. Status: {response.status}, Body: {await response.text()}")
                    return None
        except Exception as e:
            logging.error(f"An exception occurred while getting WebSocket URL: {e}")
            return None

    async def subscribe_to_chat(self, session_key: str) -> bool:
        """
        Subscribes to chat events for the session.
        """
        url = f"{self.api_url}/open/v1/sessions/events/subscribe/chat"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        data = {"sessionKey": session_key}
        try:
            async with self._session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    logging.info(f"Successfully subscribed to chat events for session {session_key}.")
                    return True
                else:
                    logging.error(f"Failed to subscribe to chat. Status: {response.status}, Body: {await response.text()}")
                    return False
        except Exception as e:
            logging.error(f"An exception occurred while subscribing to chat: {e}")
            return False

    async def send_chat_message(self, message: str) -> bool:
        """
        Sends a message to the chat of the authenticated user's channel.
        """
        url = f"{self.api_url}/open/v1/chats/send"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        # The API implicitly uses the authenticated user's channel.
        data = {"message": message}
        try:
            async with self._session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    logging.info(f"Sent Chzzk chat message: '{message}'")
                    return True
                else:
                    logging.error(f"Failed to send Chzzk chat message. Status: {response.status}, Body: {await response.text()}")
                    return False
        except Exception as e:
            logging.error(f"An exception occurred while sending chat message: {e}")
            return False
