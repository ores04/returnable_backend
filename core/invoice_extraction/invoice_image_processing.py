import cv2
import pytesseract


class InvoiceImageProcessing:

    def __init__(self, image: cv2.Mat):
        self.image = image
        self.ocr_engine = pytesseract.pytesseract

    def preprocess_image(self):
        """
        Preprocess the invoice image for better OCR results.
        This includes converting to grayscale, thresholding, and resizing.
        """
        gray_image = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        _, thresh_image = cv2.threshold(
            gray_image, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        resized_image = cv2.resize(thresh_image, (800, 600))
        return resized_image

    def process_image(self):
        """
        Process the invoice image to extract text using OCR.
        Returns the extracted text.
        """
        preprocessed_image = self.preprocess_image()
        extracted_text = self.ocr_engine.image_to_data(
            preprocessed_image, output_type=pytesseract.Output.DICT)
        return extracted_text


if __name__ == "__main__":
    # download test data
    import pandas as pd

    df = pd.read_parquet(
        "hf://datasets/Aoschu/German_invoices_dataset/data/train-00000-of-00001-f9d614282a2aa4e0.parquet")
    print(df.head(10))
    # save the first 10 rows to a CSV file
    df.head(10).to_csv("test_data.csv", index=False)
