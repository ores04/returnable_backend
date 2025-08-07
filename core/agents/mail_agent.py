import json
from core.ai_clients.openai_client import OpenAIClient


def write_return_mail(customer_number: str | None, invoice_number: str,
                      date: str, name_to: str, from_company: str, reclamation_reason: str) -> str:
    """
    This function generates a mail for the customer to request a return.
    """

    openai_client = OpenAIClient()

    instruction = """ Du fungierst als Anwalt für einen Kunden, welcher eine Reklamation bei einem Unternehmen einreichen möchte.
    Bitte schreibe eine E-Mail an das Unternehmen, in der du die Reklamation des Kunden erläuterst.
    Die E-Mail sollte höflich und professionell formuliert sein. Bitte achte darauf, dass die E-Mail alle relevanten Informationen enthält, die für die Reklamation notwendig sind.
    Die E-Mail sollte in Deutsch verfasst sein. Die Mail soll aus der ich Perspektive des Kunden geschrieben sein. Die Mail soll nicht anwaltlich klingen, sondern höflich und professionell.
    Es soll sich an die Mail rückgemeldet werden, von welcher E-Mail Adresse die Mail gesendet wurde."""

    mail_information = {
        "kundennummer": customer_number,
        "rechnungsnummer": invoice_number,
        "rechnungs_datum": date,
        "kunden_name": name_to,
        "firma": from_company,
        "reklamationsgrund": reclamation_reason,
    }

    response = openai_client.request_text_model(
        instruction=instruction,
        prompt=json.dumps(mail_information, ensure_ascii=False),
        model="gpt-5-mini",
    )

    if isinstance(response, str):
        return response.strip()
    elif isinstance(response, dict) and 'text' in response:
        return response['text'].strip()
    else:
        raise ValueError(
            "Unexpected response format from OpenAI API. Expected a string or dict with 'text' key.")


if __name__ == "__main__":
    # Example usage
    email_content = write_return_mail(
        customer_number="12345",
        invoice_number="INV-2023-001",
        date="2023-10-01",
        name_to="Max Mustermann",
        from_company="Beispiel GmbH",
        reclamation_reason="Defekter Artikel"
    )
    print(email_content)
