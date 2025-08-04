from dotenv import load_dotenv
import os
import openai
from typing import Optional, Type, TypeVar, Union
from pydantic import BaseModel


load_dotenv()

OPENAI_API_KEY = os.getenv("openai_api_key")


class OpenAIClient:
    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError(
                "OpenAI API key is not set in the environment variables.")
        self.api_key = OPENAI_API_KEY

        self.client = openai.Client(api_key=self.api_key)

    def request_text_model(
        self,
        instruction: str,
        prompt: str,
        model: str = "gpt-4.1",
        response_model: Optional[BaseModel] = None
    ) -> Union[BaseModel, str]:

        if response_model:
            response = self.client.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": prompt}
                ],
                response_format=response_model,
            )
            return response.choices[0].message.parsed

        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()

    def request_audio_model(self, text: str, model: str = "tts-1", voice: str = "alloy") -> bytes:
        """
        Generates audio from the given text using the OpenAI TTS model.

        Args:
            text (str): The text to be converted to speech.
            model (str): The TTS model to use.
            voice (str): The voice to use for the audio.

        Returns:
            bytes: The audio content in bytes.
        """
        response = self.client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
        )
        return response.content
