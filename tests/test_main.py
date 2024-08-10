import pytest
from unittest import mock
from main import validate_business_connection, get_message_content, improve_transcription


# Mock data
class MockMessage:
    def __init__(self, content_type, text=None, voice=None):
        self.content_type = content_type
        self.text = text
        self.voice = voice

class MockVoice:
    def __init__(self, duration):
        self.duration = duration

# Test validate_business_connection
@mock.patch.dict('os.environ', {'ALLOWED_BID_CONNECTIONS': "['valid_id']"})
def test_validate_business_connection():
    assert validate_business_connection("valid_id") == True
    assert validate_business_connection("invalid_id") == False

# Test get_message_content
def test_get_message_content_text():
    message = MockMessage(content_type="text", text="Hello, world!")
    assert get_message_content(message) == "Hello, world!"

def test_get_message_content_long_text():
    long_text = "a" * 201
    message = MockMessage(content_type="text", text=long_text)
    assert get_message_content(message) == "a" * 200 + "..."

def test_get_message_content_voice():
    voice = MockVoice(duration=5)
    message = MockMessage(content_type="voice", voice=voice)
    assert get_message_content(message) == "Voice message (duration: 5s)"

def test_get_message_content_other():
    message = MockMessage(content_type="photo")
    assert get_message_content(message) == "photo content"

def test_improve_transcription():
    mock_response = mock.MagicMock()
    mock_response.choices = [mock.MagicMock(message=mock.MagicMock(content="Improved transcription"))]
    with mock.patch('main.client.chat.completions.create', return_value=mock_response):
        transcription = "This is a test transcription."
        improved = improve_transcription(transcription)
        assert improved == "Improved transcription"
