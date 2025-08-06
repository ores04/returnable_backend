from datasets import load_dataset
import cv2
import numpy as np

from core.invoice_extraction.invoice_image_processing import InvoiceImageProcessing, InvoiceInformation


def test_pytest_setup():
    """
    This test will just ensure that pytest is set up correctly."""
    assert True, "Pytest setup is correct"


def test_invoice_image_extraction():
    """
    This test will run the invoice image extraction process on 10 sample images to ensure that the process works
    """
    invoice_ground_truth = [
        (InvoiceInformation(
            invoice_number="1234",
            customer_number="1234",
            date="29.07.2030",
            name_to="Mia Hobner",
            from_company="Paul Cheung"
        ), 1),
        (InvoiceInformation(
            invoice_number="1234",
            customer_number="1234",
            date="27.09.2030",
            name_to="Lukas Wegerer",
            from_company="Mikoko Ramen- & Sushi-Bar"
        ), 2),
        (InvoiceInformation(
            invoice_number="RE-2017-MAL-11-0003",
            customer_number="12345",
            date="11.05.2017",
            name_to="Max Mustermann",
            from_company="Musterfirma GmbH"
        ), 3),
        (InvoiceInformation(
            invoice_number="257",
            customer_number=None,
            date="21.07.2021",
            name_to="[Name des Kundenunternehmens]",
            from_company="[Unternehmensname]"
        ), 4),
        (InvoiceInformation(
            invoice_number="2021017",
            customer_number="001",
            date="29.03.2021",
            name_to="Ineic Ofen Gmb",
            from_company="Lightweight Aviation GmbH"
        ), 80),
        # Add more expected InvoiceInformation objects as needed
    ]

    dataset = load_dataset("Aoschu/German_invoices_dataset")

    match_count = 0

    for truth, i in invoice_ground_truth:
        first_image = dataset['train'][i]['image']

        # Convert PIL Image to cv2 format
        pil_image = first_image.convert('RGB')
        cv2_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        processor = InvoiceImageProcessing(cv2_image)
        extracted_text = processor.extract_information()

        assert isinstance(
            extracted_text, InvoiceInformation), "Extracted text is not of type InvoiceInformation"

        # Compare extracted text with ground truth
        if extracted_text == truth:
            match_count += 1

    # Calculate accuracy
    accuracy = match_count / len(invoice_ground_truth)
    assert accuracy > 0.8, f"Expected accuracy > 0.8, but got {accuracy}"
