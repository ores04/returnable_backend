import base64
import os
import logfire

from mistralai import Mistral, OCRResponse


class MistralAiClient:

    def __init__(self):
        """Initializes the Mistral AI client with the provided API key or from environment variables. We prefer environment variables for security reasons."""
        self.api_key =  os.getenv("MISTRAL_API_KEY", None)

        if not self.api_key:
            raise ValueError("Mistral AI API key is not set in the environment variables.")

        self.client = Mistral(api_key=self.api_key)



    def perform_ocr_on_image(self, base64_image: bytes) -> OCRResponse:
        """Perform OCR on the given base64 encoded image using Mistral AI."""
        logfire.info("Performing OCR on base64 encoded image")
        b64str = base64_image.decode('utf-8')
        ocr_response = self.client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "image_url",
                "image_url": f"data:image/jpeg;base64,{b64str}"
            },
            include_image_base64=True
        )
        return ocr_response

    def perform_ocr_on_pdf(self, base64_pdf: bytes) -> OCRResponse:
        """Perform OCR on the given base64 encoded PDF using Mistral AI."""
        logfire.info("Performing OCR on base64 encoded PDF")
        b64str = base64_pdf.decode('utf-8')
        ocr_response = self.client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "pdf_url",
                "pdf_url": f"data:application/pdf;base64,{b64str}"
            },
            include_image_base64=True
        )
        return ocr_response