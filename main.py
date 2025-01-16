from flask import Flask, request
import google.generativeai as genai
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import os
from dotenv import load_dotenv
import subprocess
import time

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Configure Twilio client
twilio_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)


def kill_existing_ngrok():
    """Kill any existing ngrok processes"""
    try:
        subprocess.run(['pkill', 'ngrok'], stderr=subprocess.DEVNULL)
        print("✓ Cleaned up existing ngrok processes")
        time.sleep(2)  # Give system time to clean up
    except Exception:
        pass


def get_ngrok_url():
    """Get the current ngrok public URL"""
    try:
        # Use curl to get the ngrok API response
        response = subprocess.check_output(
            ['curl', 'http://localhost:4040/api/tunnels'],
            stderr=subprocess.DEVNULL
        )
        data = response.decode('utf-8')

        # Parse the URL from the response
        import json
        tunnels = json.loads(data)['tunnels']
        if tunnels:
            return tunnels[0]['public_url']
    except Exception:
        return None


def setup_ngrok():
    """Setup ngrok using subprocess"""
    try:
        # Kill any existing ngrok processes first
        kill_existing_ngrok()

        # Start ngrok in background
        subprocess.Popen(['ngrok', 'http', '5000'],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)

        # Wait for tunnel to be established
        time.sleep(3)

        # Get the public URL
        public_url = get_ngrok_url()
        if public_url:
            print(f"\n✓ Ngrok tunnel established at: {public_url}")
            return public_url

        return None

    except Exception as e:
        print(f"\n✗ Failed to establish ngrok tunnel: {str(e)}")
        print("\nTroubleshooting steps:")
        print("1. Make sure ngrok is installed (brew install ngrok)")
        print("2. Try running 'ngrok http 5000' manually to verify it works")
        print("3. Kill any existing ngrok processes and try again")
        return None


@app.route('/')
def home():
    return 'WhatsApp Bot is running!'


@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming WhatsApp messages"""
    try:
        # Get the message details
        incoming_msg = request.values.get('Body', '').strip()
        sender_number = request.values.get('From', '')

        print(f"\nReceived message: '{incoming_msg}' from {sender_number}")

        # Create response object
        response = MessagingResponse()

        if not incoming_msg:
            response.message("I received an empty message. Please send some text!")
            return str(response)

        # Get AI response from Gemini
        try:
            ai_response = model.generate_content(incoming_msg)
            reply_text = ai_response.text
            print(f"Gemini response: {reply_text}")
        except Exception as e:
            reply_text = "Sorry, I had trouble generating a response. Please try again."
            print(f"Gemini API error: {str(e)}")

        # Send the response
        response.message(reply_text)
        return str(response)

    except Exception as e:
        print(f"Webhook error: {str(e)}")
        return str(MessagingResponse().message("An error occurred"))


def verify_credentials():
    """Verify API credentials are working"""
    print("\nVerifying credentials...")

    try:
        # Check Twilio credentials
        account = twilio_client.api.accounts(os.getenv('TWILIO_ACCOUNT_SID')).fetch()
        print("✓ Twilio credentials verified")
        print(f"  Account Name: {account.friendly_name}")

        # Check Gemini credentials
        response = model.generate_content("Test")
        print("✓ Gemini API credentials verified")

        return True
    except Exception as e:
        print(f"✗ Credential verification failed: {str(e)}")
        return False


if __name__ == '__main__':
    # Check required environment variables
    required_vars = [
        'GOOGLE_API_KEY',
        'TWILIO_ACCOUNT_SID',
        'TWILIO_AUTH_TOKEN',
        'TWILIO_WHATSAPP_NUMBER',
        'TEST_PHONE_NUMBER',
        'NGROK_AUTH_TOKEN'
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print("\nMissing required environment variables:")
        for var in missing_vars:
            print(f"- {var}")
        exit(1)

    # Verify credentials
    if not verify_credentials():
        print("\nPlease check your credentials and try again.")
        exit(1)

    print("\nStarting WhatsApp bot...")

    # Setup ngrok tunnel
    public_url = setup_ngrok()
    if not public_url:
        print("\nFailed to start ngrok tunnel.")
        print("Please try setting up ngrok manually:")
        print("1. Open a new terminal")
        print("2. Run: ngrok http 5000")
        print("3. Copy the forwarding URL and update your Twilio webhook")
        exit(1)

    print("\nIMPORTANT: Update your Twilio webhook URL to:")
    print(f"{public_url}/webhook")
    print("\nGo to Twilio Console > WhatsApp Sandbox Settings to update the URL")

    print("\nBot is ready! You can now:")
    print("1. Send a message to your Twilio WhatsApp number")
    print("2. Wait for the response from Gemini")
    print("\nPress Ctrl+C to stop the bot")

    # Run the Flask app
    app.run(debug=True)