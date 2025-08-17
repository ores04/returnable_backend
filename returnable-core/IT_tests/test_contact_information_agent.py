import pytest
from core.agents.contact_information_agent import extract_email_from_text


class TestExtractEmailFromText:
    """Test suite for the extract_email_from_text function."""

    def test_extract_single_email_basic(self):
        """Test extraction of a single basic email address."""
        text = "Please contact us at support@company.com for assistance."
        result = extract_email_from_text(text)
        assert result == "support@company.com"

    def test_extract_email_with_numbers(self):
        """Test extraction of email with numbers in local part."""
        text = "Send reports to admin123@example.org"
        result = extract_email_from_text(text)
        assert result == "admin123@example.org"

    def test_extract_email_with_dots_and_underscores(self):
        """Test extraction of email with dots and underscores."""
        text = "Contact first.last_name@sub.domain.com"
        result = extract_email_from_text(text)
        assert result == "first.last_name@sub.domain.com"

    def test_extract_email_with_plus_sign(self):
        """Test extraction of email with plus sign (common in Gmail)."""
        text = "Email user+tag@gmail.com for updates"
        result = extract_email_from_text(text)
        assert result == "user+tag@gmail.com"

    def test_extract_email_with_hyphen_in_domain(self):
        """Test extraction of email with hyphen in domain."""
        text = "Reach out to info@my-company.co.uk"
        result = extract_email_from_text(text)
        assert result == "info@my-company.co.uk"

    def test_extract_multiple_emails_returns_first(self):
        """Test that when multiple emails exist, the first one is returned."""
        text = "Contact sales@company.com or support@company.com for help."
        result = extract_email_from_text(text)
        assert result == "sales@company.com"

    def test_extract_email_from_complex_text(self):
        """Test extraction from text with lots of other content."""
        text = """
        Welcome to our website! We offer various services.
        For customer support, please email help@service.net
        Our office hours are 9-5 Monday through Friday.
        """
        result = extract_email_from_text(text)
        assert result == "help@service.net"

    def test_no_email_in_text(self):
        """Test that None is returned when no email is present."""
        text = "This text has no email addresses in it at all."
        result = extract_email_from_text(text)
        assert result is None

    def test_empty_string(self):
        """Test that None is returned for empty string."""
        text = ""
        result = extract_email_from_text(text)
        assert result is None

    def test_whitespace_only(self):
        """Test that None is returned for whitespace-only string."""
        text = "   \n\t   "
        result = extract_email_from_text(text)
        assert result is None

    def test_invalid_email_format_no_at_symbol(self):
        """Test that invalid email without @ symbol is not matched."""
        text = "Contact us at usercompany.com"
        result = extract_email_from_text(text)
        assert result is None

    def test_invalid_email_format_no_domain(self):
        """Test that invalid email without domain is not matched."""
        text = "Send to user@"
        result = extract_email_from_text(text)
        assert result is None

    def test_invalid_email_format_no_tld(self):
        """Test that invalid email without TLD is not matched."""
        text = "Email user@domain"
        result = extract_email_from_text(text)
        assert result is None

    def test_invalid_email_format_short_tld(self):
        """Test that email with single character TLD is not matched."""
        text = "Contact admin@site.x"
        result = extract_email_from_text(text)
        assert result is None

    def test_email_in_parentheses(self):
        """Test extraction of email within parentheses."""
        text = "Contact our support team (help@company.com) for assistance."
        result = extract_email_from_text(text)
        assert result == "help@company.com"

    def test_email_with_surrounding_punctuation(self):
        """Test extraction of email surrounded by punctuation."""
        text = "Email: info@example.com, or call us."
        result = extract_email_from_text(text)
        assert result == "info@example.com"

    def test_email_at_start_of_text(self):
        """Test extraction when email is at the beginning of text."""
        text = "admin@startup.io is our main contact address"
        result = extract_email_from_text(text)
        assert result == "admin@startup.io"

    def test_email_at_end_of_text(self):
        """Test extraction when email is at the end of text."""
        text = "For more information, contact sales@business.net"
        result = extract_email_from_text(text)
        assert result == "sales@business.net"

    def test_email_with_long_tld(self):
        """Test extraction of email with longer TLD."""
        text = "Visit contact@example.museum for details"
        result = extract_email_from_text(text)
        assert result == "contact@example.museum"

    def test_email_case_sensitivity(self):
        """Test that email extraction preserves case."""
        text = "Contact Support@Company.COM"
        result = extract_email_from_text(text)
        assert result == "Support@Company.COM"

    def test_malformed_email_spaces(self):
        """Test that email with spaces is not matched."""
        text = "Email user @company.com"
        result = extract_email_from_text(text)
        assert result is None

    def test_email_like_but_invalid(self):
        """Test text that looks like email but is invalid."""
        text = "Visit www@site.com (not an email)"
        result = extract_email_from_text(text)
        assert result == "www@site.com"  # Current regex would match this

    def test_multiple_domains_subdomain(self):
        """Test email with multiple subdomains."""
        text = "Admin contact: tech@mail.sub.example.com"
        result = extract_email_from_text(text)
        assert result == "tech@mail.sub.example.com"
