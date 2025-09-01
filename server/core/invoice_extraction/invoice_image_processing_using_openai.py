from mistralai import OCRResponse

from server.core.ai_clients.mistal_ai_client import MistralAiClient


class LLMImageProcessor:
    def __init__(self, llm_client: MistralAiClient):
        self.llm_client = llm_client

    def process_image(self, image_base64: bytes, is_pdf: bool = False):
        # Implement image processing logic using the LLM client
        if is_pdf:
            ocr_result: OCRResponse = self.llm_client.perform_ocr_on_pdf(image_base64)
        else:
            ocr_result: OCRResponse = self.llm_client.perform_ocr_on_image(image_base64)

        # because the image is one page we just return the text of the first page
        text = ocr_result.pages[0].markdown
        return text

