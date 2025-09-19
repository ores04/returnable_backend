import os
import logfire

from google import genai
from google.genai.types import GenerateImagesConfig

from dotenv import load_dotenv
load_dotenv()


IMAGEN_MODEL = "imagen-4.0-generate-preview-06-06"

gemini_api_key = os.getenv("google_cloud_api_key")
PROJECT_ID = "triple-backbone-463818-h5"
LOCATION = "us-central1"


class GoogleAiClient:
    def __init__(self):
        self.client = genai.Client(
            vertexai=True, location=LOCATION, project=PROJECT_ID)

    def generate_image(self, prompt, output_file):
        image = self.client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=prompt,
            config=GenerateImagesConfig(
                image_size="2K",
                number_of_images=1,
            ),
        )

        image.generated_images[0].image.save(output_file)

        logfire.info(
            f"Created output image using {len(image.generated_images[0].image.image_bytes)} bytes"
        )
        # Example response:
        # Created output image using 1234567 bytes
        image_size = "2K",

        image.generated_images[0].image.save(output_file)


if __name__ == "__main__":
    client = GoogleAiClient()
    client.generate_image(
        "A futuristic city skyline at sunset", "output_image.png")
    logfire.info("Image generation complete.")
