import base64
import json
from io import BytesIO

import cv2
import pytesseract
from PIL import Image



from pydantic import BaseModel

from server.core.ai.agents.invoice_image_processing_using_llm import LLMImageProcessor
from server.core.ai.ai_clients.mistal_ai_client import MistralAiClient
from server.core.ai.ai_clients.openai_client import OpenAIClient

INVOICE_EXTRACTION_PROMT = """
The information in the promt is extracted via OCR from an invoice image. Please extract the following information from the text:
- Invoice Number
- Date
- Name to ie the name of person or company to whom the invoice is addressed
- From Company ie the company that issued the invoice
- Customer Number if available this is not a must and can be None

Hints: The from company is usually the first company mentioned in the text. It is also possible that the from_company is a person.
The company from CANT be used in directly next to the name_to, as this is usually the company that issued the invoice. 
The invoice numer is usually mentioned as "Rechnung Nr." or "Rechnungsnummer" or "Invoice Number" or "Invoice No." or "Angebotsnummer" or "Angebots-Nr." or "Bestellnummer" or "Bestell-Nr." or "Auftragsnummer" or "Auftrags-Nr.".

The text is in German. Please return the information in a JSON format with the following keys:
- invoice_number
- date
- name_to
- from_company
- customer_number"""


class InvoiceInformation(BaseModel):
    "This model represents the information from the invoice needed to propose a return."
    invoice_number: str | None = None
    customer_number: str | None = None
    date: str
    name_to: str
    from_company: str

    def __eq__(self, other):
        """Two InvoiceInformation objects are equal if all fields match."""
        if not isinstance(other, InvoiceInformation):
            return False
        return (self.invoice_number == other.invoice_number and
                self.customer_number == other.customer_number and
                self.date == other.date and
                self.name_to == other.name_to and
                self.from_company == other.from_company)

    def to_dict(self):
        """ This class converts the InvoiceInformation to a dictionary, which is in the form used by the 
        frontend and the db"""
        return {
            "invoice_date": self.date,
            "invoice_id": self.invoice_number,
            "customer_id": self.customer_number,
            "name_to": self.name_to,
            "product_from_company": self.from_company
        }

    def from_dict(cls, data: dict):
        """ This class converts a dictionary to an InvoiceInformation object, which is in the form used by the 
        frontend and the db"""
        return cls(
            invoice_number=data.get("invoice_id"),
            customer_number=data.get("customer_id"),
            date=data.get("invoice_date"),
            name_to=data.get("name_to"),
            from_company=data.get("product_from_company")
        )


class InvoiceImageProcessing:

    def __init__(self, image, _image_pil:Image =None):
        self.image = image
        self.pil_image: Image = _image_pil
        self.ocr_engine = pytesseract.pytesseract

    def preprocess_image(self):
        """
        Preprocess the invoice image for better OCR results.
        This includes converting to grayscale, thresholding, and resizing.
        """
        gray_image = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)

        _, thresh_image = cv2.threshold(
            gray_image, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh_image

    def process_image(self):
        """
        Process the invoice image to extract text using OCR.
        Returns the extracted text.
        """
        preprocessed_image = self.preprocess_image()
        # option to use german language and treat as multiple blocks of text
        custom_config = r'--oem 3 --psm 6 -l deu'
        self.extracted_text = self.ocr_engine.image_to_data(
            preprocessed_image, output_type=pytesseract.Output.DICT, config=custom_config)
        return self.extracted_text

    def group_text_by_indent_refactored(self, ocr_data, indent_tolerance=10):
        """
        Groups text from Tesseract OCR data into a hierarchical JSON structure
        based on line indentation with a configurable tolerance.

        Args:
            ocr_data (dict): The dictionary output from pytesseract.image_to_data.
            indent_tolerance (int): The number of pixels to tolerate when comparing
                                    indentation levels. Lines with indents that
                                    differ by less than this value are treated as
                                    being at the same level.

        Returns:
            str: A JSON string representing the nested structure of the text.
        """
        # --- 1. Reconstruct lines from word data robustly ---
        lines = {}
        # Gracefully handle invalid top-level input
        if not isinstance(ocr_data, dict) or 'text' not in ocr_data:
            return json.dumps([], indent=2)

        for i in range(len(ocr_data['text'])):
            try:
                # Skip non-word elements and empty text
                conf = int(ocr_data['conf'][i])
                text = ocr_data['text'][i].strip()
                if conf < 0 or not text:
                    continue

                line_key = (
                    ocr_data['page_num'][i],
                    ocr_data['block_num'][i],
                    ocr_data['par_num'][i],
                    ocr_data['line_num'][i],
                )

                word_info = {
                    'text': text,
                    'left': int(ocr_data['left'][i]),
                    'word_num': int(ocr_data['word_num'][i]),
                }
                # Also capture 'top' at the word level for later sorting
                if i == 0 or line_key not in lines:
                    word_info['top'] = int(ocr_data['top'][i])

                lines.setdefault(line_key, []).append(word_info)

            except (KeyError, ValueError):
                # If a word entry is malformed (e.g., missing key or non-numeric
                # value), skip it instead of crashing.
                continue

        # --- 2. Process and sort the reconstructed lines ---
        processed_lines = []
        for words in lines.values():
            if not words:
                continue

            sorted_words = sorted(words, key=lambda w: w['word_num'])
            full_text = ' '.join(w['text'] for w in sorted_words)

            # Use the 'top' of the first word for vertical sorting
            line_top = words[0].get('top', 0)

            processed_lines.append({
                'text': full_text,
                'indent': sorted_words[0]['left'],
                'top': line_top,
            })

        # Sort all lines based on their vertical position
        sorted_lines = sorted(processed_lines, key=lambda l: l['top'])

        # --- 3. Build the hierarchical tree using a stack and tolerance ---
        root = {'children': []}
        # The stack holds tuples of (indentation_level, parent_node)
        stack = [(-1, root)]

        for line in sorted_lines:
            current_indent = line['indent']
            node = {'text': line['text']}

            # Pop from stack until we find a parent with a smaller indent,
            # using the tolerance to group similar-level indents.
            # A parent's indent must be less than the child's indent minus the tolerance.
            while stack and stack[-1][0] >= current_indent - indent_tolerance:
                stack.pop()

            # The last item on the stack is now the correct parent.
            parent_node = stack[-1][1]

            # Use setdefault for a cleaner way to add children list
            parent_node.setdefault('children', []).append(node)

            # The current node becomes a potential parent for subsequent lines.
            stack.append((current_indent, node))

        # The redundant cleanup step is no longer needed.

        # Return the final structure as a formatted JSON string
        return json.dumps(root.get('children', []), indent=2, ensure_ascii=False)

    def extract_information(self, is_pdf: bool) -> InvoiceInformation:
        """
        Extract specific information from the processed image.
        This can be extended to extract fields like invoice number, date, total amount, etc.
        """
        mistal_client = MistralAiClient()

        im_file = BytesIO()
        self.pil_image.save(im_file, format="JPEG")
        im_bytes = im_file.getvalue()  # im_bytes: image in binary format.
        im_b64 = base64.b64encode(im_bytes)

        text = LLMImageProcessor(mistal_client).process_image(im_b64, is_pdf)
        print("Extracted text from OCR:", text)

        openai_client = OpenAIClient()

        response = openai_client.request_text_model(
            instruction=INVOICE_EXTRACTION_PROMT,
            prompt=text,
            model="gpt-4o",
            response_model=InvoiceInformation
        )
        return response


if __name__ == "__main__":
    # download test data
    import numpy as np
    from datasets import load_dataset

    dataset = load_dataset("Aoschu/German_invoices_dataset")

    first_image = dataset['train'][60]['image']

    # The image is a PIL Image object, so you can display it
    first_image.show()

    # Convert PIL Image to cv2 format
    # PIL uses RGB, cv2 uses BGR, so we need to convert
    pil_image = first_image.convert('RGB')  # Ensure RGB format
    cv2_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    # Now you can use the cv2_image with your InvoiceImageProcessing class
    processor = InvoiceImageProcessing(cv2_image)
    extracted_text = processor.extract_information()
    print("Extracted text:", extracted_text)
