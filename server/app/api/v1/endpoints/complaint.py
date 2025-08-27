"""
endpoints that are used in the complaint process
"""
import time
from fastapi import APIRouter, UploadFile, Request
from typing import Dict, Any
import numpy as np
import cv2
from PIL import Image
from io import BytesIO

from pydantic import BaseModel


from core.invoice_extraction.invoice_image_processing import InvoiceImageProcessing
from core.agents.contact_information_agent import master_search_agent, SearchDeps, search_usage_limit
from core.agents.mail_agent import write_return_mail

router = APIRouter()


class ProposeActionProps(BaseModel):
    """This model represents the properties needed to propose a complaint action."""
    invoice_number: str
    customer_number: str | None = None
    date: str
    name_to: str
    from_company: str
    complaint_reason: str
    mock: bool = False  # This is used to mock the response to not use ai credits


@router.post("/process-pdf")
async def process_pdf(file: UploadFile) -> Dict[str, Any]:
    """Accepts a PDF file and processes it to extract information."""

    print(f"Processing PDF file: {file.filename}")

    contents = await file.read()

    try:
        # convert the file to a cv2 image
        image = Image.open(BytesIO(contents))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        cv2_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to process PDF: {str(e)}"
        }

    # use the image processing class to extract information
    processor = InvoiceImageProcessing(cv2_image)
    extracted_info = processor.extract_information()

    return {
        "status": "success",
        "message": "PDF processed successfully",
        "data": extracted_info
    }


@router.post("/process-file")
async def process_file(request: Request) -> Dict[str, Any]:
    """Accepts raw image bytes in the request body and processes them like /process-pdf."""
    contents = await request.body()

    try:
        # convert the raw body to a cv2 image
        image = Image.open(BytesIO(contents))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        cv2_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to process image: {str(e)}"
        }

    # use the image processing class to extract information
    processor = InvoiceImageProcessing(cv2_image)
    extracted_info = processor.extract_information()

    return {
        "status": "success",
        "message": "Image processed successfully",
        # Assuming extract_information returns a dict-like object
        "data": extracted_info.to_dict()
    }

mocked_response = {
    "status": "success",
    "message": "Complaint action proposed successfully",
    "data": {
        "email_content": "Lore Ipsum dolor sit amet, consectetur adipiscing elit.",
        "email_address": "test@example.com"
    }
}


@router.post("/propose-mail")
async def process_mail(data: ProposeActionProps) -> Dict[str, Any]:
    """This endpoint constructs a mail to an adress to propose a complaint action."""

    if data.mock:
        return mocked_response

    result = await master_search_agent.run(
        f"Find the customer support email address for the company {data.from_company}.",
        deps=SearchDeps(max_results_per_query=5),
        usage_limits=search_usage_limit,
    )
    email_address = result.output

    if not email_address:
        return {
            "status": "error",
            "message": "Could not find a customer support email address."
        }

    email = write_return_mail(
        customer_number=data.customer_number,
        invoice_number=data.invoice_number,
        date=data.date,
        name_to=data.name_to,
        from_company=data.from_company,
        reclamation_reason=data.complaint_reason
    )
    return {
        "status": "success",
        "message": "Complaint action proposed successfully",
        "data": {
            "email_content": email,
            "email_address": email_address
        }
    }


class FireMailProps(BaseModel):
    """This model represents the properties required to fire a complaint email."""
    email_content: str
    email_address: str
    mock: bool = False


@router.post("/fire-mail")
async def fire_mail(data: FireMailProps) -> Dict[str, Any]:
    """This endpoint sends the proposed complaint action email."""

    if data.mock:
        time.sleep(3)
        return {
            "status": "success",
            "message": "Complaint action email sent successfully",
        }

    # Here you would implement the actual email sending logic
    # For example, using an email sending service or library

    return {
        "status": "success",
        "message": "Complaint action email sent successfully",
    }
