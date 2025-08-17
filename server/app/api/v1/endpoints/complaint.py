"""
endpoints that are used in the complaint process
"""
from fastapi import APIRouter, UploadFile
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
router.prefix = "/complaint"


class ProposeActionProps(BaseModel):
    """This model represents the properties needed to propose a complaint action."""
    invoice_number: str
    customer_number: str | None = None
    date: str
    name_to: str
    from_company: str
    email_address: str
    complaint_reason: str


@router.post("/process-pdf")
async def process_pdf(file: UploadFile) -> Dict[str, Any]:
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


@router.post("/propose-action")
async def propose_action(data: ProposeActionProps) -> Dict[str, Any]:
    """This endpoint constructs a mail to an adress to propose a complaint action."""

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
