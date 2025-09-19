import imapclient
import logfire


class GMXMailService:
    """ This class provides methods to interact with the GMX email service. """

    def __init__(self, username: str, password: str):
        """
        Initialize the GMXMailService with user credentials.

        :param username: GMX email username
        :param password: GMX email password
        """
        self.username = username
        self.password = password

    def execute_with_imap_connection(self, func: callable):
        """This method open an IMAP connection and executes a function with it, after which it closes the connection.
        :param func: A callable that takes an IMAPClient instance as an argument.
        :return: The result of the callable function."""
        with imapclient.IMAPClient('imap.gmx.com') as client:
            client.login(self.username, self.password)
            return func(client)

    def fetch_mails(self, client: imapclient.IMAPClient) -> list:
        """Fetches emails from the GMX inbox.

        :param client: An instance of IMAPClient connected to GMX.
        :return: A list of emails.
        """
        client.select_folder('INBOX')
        messages = client.search(['NOT', 'DELETED'])
        return client.fetch(messages, ['ENVELOPE', 'BODY[]']).items()

    def sent_mail(self, client: imapclient.IMAPClient, to: str, subject: str, body: str) -> None:
        """Sends an email using the GMX service.

        :param client: An instance of IMAPClient connected to GMX.
        :param to: Recipient email address.
        :param subject: Subject of the email.
        :param body: Body of the email.
        """


if __name__ == "__main__":
    # Example usage
    service = GMXMailService('********', '*******')
    emails = service.execute_with_imap_connection(service.fetch_mails)
    for msgid, data in emails:
        logfire.info(f"Message ID: {msgid}")
        logfire.info(f"Subject: {data[b'ENVELOPE'].subject.decode()}")
        logfire.info(f"Body: {data[b'BODY[]'][:100]}...")
