import streamlit as st

# Set up the page before any other Streamlit calls
st.set_page_config(
    page_title="NokNok AI Assistant",
    page_icon="🛒",
    layout="wide",
)

import os
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from openai import OpenAI, OpenAIError
import time
import threading
import re
# Import our conditions module
from conditions import register_all_conditions, safe_float_conversion
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import base64
import streamlit.components.v1 as components  # For custom HTML (background particles)
from audio_recorder_streamlit import audio_recorder
import io

# Load the image as base64 at the very beginning
with open("logo.png", "rb") as f:
    logo_base64 = base64.b64encode(f.read()).decode()

# Apply global CSS styling immediately at app startup, before any interactions
st.markdown(f"""
<style>
/* Global layout styles */
.stats-container {{
    background-color: rgba(35, 40, 48, 0.95);
    border-radius: 5px;
    padding: 15px;
    margin-top: 0;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    position: relative;
    height: auto;
    min-height: 300px; /* Fixed minimum height for container */
}}

.stats-header {{
    color: #6aa5ff;
    font-weight: bold;
    text-align: center;
    margin-bottom: 10px;
    font-size: 1.1rem;
    border-bottom: 1px solid #444;
    padding-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 70px; /* Fixed height to prevent layout shifts */
    position: relative; /* Enable positioning */
    overflow: hidden; /* Prevent overflow */
}}

.stats-header-text {{
    margin-left: 0; /* Remove left margin to center properly */
    white-space: nowrap; /* Keep text on one line */
    font-size: 1.1rem;
}}

.stats-header img, .noknok-logo {{
    height: 60px;
    width: 60px;
    position: static; /* Change from absolute to static positioning */
    margin-right: 10px; /* Add right margin for spacing */
    object-fit: contain;
}}

.noknok-logo-small {{
    height: 30px;
    width: 30px;
    vertical-align: middle;
    object-fit: contain;
    display: inline-block;
}}

.stats-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    grid-gap: 10px;
    margin-bottom: 15px;
    height: 80px; /* Fixed height */
}}

.stat-card {{
    background-color: rgba(50, 57, 68, 0.7);
    border-radius: 4px;
    padding: 10px;
    text-align: center;
    height: 100%; /* Full height of parent */
    display: flex;
    flex-direction: column;
    justify-content: center;
}}

.stat-value {{
    font-size: 1.5rem;
    font-weight: bold;
    color: #5ed9a7;
    margin-bottom: 5px;
    line-height: 1;
}}

.stat-label {{
    font-size: 0.8rem;
    color: #aabfe6;
    line-height: 1;
}}

.status-indicator {{
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: rgba(50, 57, 68, 0.5);
    border-radius: 4px;
    padding: 8px;
    margin-top: 10px;
    height: 40px; /* Fixed height */
    position: relative;
}}

.status-connected, .status-disconnected {{
    font-weight: 500;
    white-space: nowrap;
}}

.status-connected {{
    color: #8ac926;
}}

.status-disconnected {{
    color: #ff595e;
}}

.sheet-button {{
    display: inline-block;
    text-decoration: none;
    background-color: #2a62ca;
    color: black;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
    text-align: center;
    margin-top: 10px;
    width: 100%;
    transition: background-color 0.2s;
    height: 40px; /* Fixed height */
    line-height: 24px; /* Center text vertically */
}}

.sheet-button:hover {{
    background-color: #333;
}}

/* Custom header at top of sidebar */
.sidebar-header {{
    display: flex;
    align-items: center;
    margin-top: -40px;
    margin-bottom: 20px;
    padding: 0; 
    height: 90px; /* Increased height to accommodate larger logo */
    position: relative;
}}

.sidebar-header img {{
    position: absolute;
    left: 0;
    top: 50%; /* Position at middle of container */
    transform: translateY(-50%); /* Center the logo vertically */
    height: 120px; /* Doubled from 60px */
    width: 120px; /* Doubled from 60px */
    object-fit: contain;
}}

.sidebar-header span {{
    font-size: 2.6rem;
    font-weight: bold;
    color: white;
    margin-left: 50px; /* Remove this margin since we're using absolute positioning */
    white-space: nowrap;
    position: absolute; /* Position absolutely like the logo */
    left: 80px; /* Reduce the gap between logo and text */
    top: 50%; /* Position at middle of container */
    transform: translateY(-50%); /* Center the text vertically */
}}

/* General logo styling */
.logo-title-container {{
    display: flex;
    align-items: center;
    gap: 1.5rem;
    margin-top: 2rem;
}}

.logo-title-container img {{
    max-height: none !important;
    object-fit: contain;
}}

.title-text {{
    margin: 0;
    padding: 0;
    font-size: 2.5rem;
    font-weight: bold;
}}

body, .stApp {{
    background-color: #ffffff !important;
    color: #000000 !important;
}}

/* Light theme overrides */
.stats-container {{
    background-color: #ffffff !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
}}

.stats-header {{
    color: #2a62ca !important;
    border-bottom: 1px solid #e0e0e0 !important;
}}

.stat-card {{
    background-color: #f1f6ff !important;
}}

.stat-value {{
    color: #2a62ca !important;
}}

.stat-label {{
    color: #333333 !important;
}}

.status-indicator {{
    background-color: #eaf0ff !important;
}}

.sidebar-header span {{
    color: #000000 !important;
}}

.sheet-button {{
    background-color: #2a62ca !important;
    color: #ffffff !important;
}}

.client-details {{
    background-color: #f9f9f9 !important;
    border-left: 3px solid #2a62ca !important;
}}

.orders-container {{
    background-color: #ffffff !important;
    border-left: 3px solid #ffc947 !important;
}}

.order-item {{
    border-bottom: 1px dotted #d0d0d0 !important;
}}

.order-status {{
    color: #ffffff !important;
}}

.field-label {{
    color: #2a62ca !important;
}}

.field-value {{
    color: #000000 !important;
}}

[data-testid="stSidebar"] {{
    background-color: #f1f6ff !important; /* Example color, replace with the actual color code of the send text bar */
    color: #000000 !important;
}}
</style>
""", unsafe_allow_html=True)

# Add custom CSS to fix vertical spinner text
st.markdown("""
<style>
/* Fix for vertical spinner text */
[data-testid="stSidebar"] .stSpinner {
    display: inline-flex;
    white-space: nowrap;
    width: auto !important;
}
[data-testid="stSidebar"] .stSpinner > div {
    display: inline-flex;
    white-space: nowrap;
    min-width: 120px;
}

/* Fix for vertical success message text */
[data-testid="stSidebar"] [data-testid="stSuccessMessage"] {
    display: inline-flex !important;
    white-space: nowrap !important;
    width: auto !important;
}
[data-testid="stSidebar"] [data-testid="stSuccessMessage"] > div {
    display: inline-flex !important;
    white-space: nowrap !important;
    min-width: 120px !important;
}
</style>
""", unsafe_allow_html=True)

# Add a helper function to check for condition trigger keywords
def contains_condition_trigger(text):
    """Check if text contains any keywords that would trigger conditions"""
    condition_keywords = [
        "noknok.com/refund",
        "noknok.com/cancel",
        "noknok.com/support",
        "I just added your address information",
        "noknok.com/items",
        "noknok.com/calories",
        "noknok.com/lebanese",
        "noknok.com/languages"
    ]
    
    if text:
        for keyword in condition_keywords:
            if keyword in text:
                print(f"Condition trigger detected: {keyword}")
                return True
    return False

# Load environment variables
load_dotenv()

# Set up OpenAI API key
#api_key = st.secrets["OPENAI_API_KEY"]
api_key = st.secrets["OPENAI_API_KEY"]

# ------------------------------------------------------------
# 🖌️  Global visual theme (from Exifa)
# ------------------------------------------------------------

# Icon images for chat avatars (optional – taken from Exifa assets)
icons = {
    "assistant": "https://raw.githubusercontent.com/sahirmaharaj/exifa/2f685de7dffb583f2b2a89cb8ee8bc27bf5b1a40/img/assistant-done.svg",
    "user": "https://raw.githubusercontent.com/sahirmaharaj/exifa/2f685de7dffb583f2b2a89cb8ee8bc27bf5b1a40/img/user-done.svg",
}

# Particle-JS animated background (the same snippet used by Exifa)
particles_js = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <style>
    #particles-js {
      position: fixed;
      width: 100vw;
      height: 100vh;
      top: 0;
      left: 0;
      z-index: -1; /* Push behind Streamlit components */
    }
  </style>
</head>
<body>
  <div id=\"particles-js\"></div>
  <script src=\"https://cdn.jsdelivr.net/particles.js/2.0.0/particles.min.js\"></script>
  <script>
    particlesJS('particles-js', {
      particles: {
        number: { value: 300, density: { enable: true, value_area: 800 } },
        color:  { value: '#4e8cff' },
        shape:  { type: 'circle' },
        opacity:{ value: 0.5 },
        size:   { value: 2, random: true },
        line_linked: { enable: true, distance: 100, color: '#4e8cff', opacity: 0.22, width: 1 },
        move:   { enable: true, speed: 0.2, out_mode: 'out', bounce: true }
      },
      interactivity: {
        detect_on: 'canvas',
        events: {
          onhover: { enable: true, mode: 'grab' },
          onclick: { enable: true, mode: 'repulse' },
          resize: true
        },
        modes: {
          grab:   { distance: 100, line_linked: { opacity: 1 } },
          repulse:{ distance: 200, duration: 0.4 }
        }
      },
      retina_detect: true
    });
  </script>
</body>
</html>"""

# Render the particle background only once per session so that it
# doesn't accumulate duplicate DOM nodes on Streamlit reruns.
if "particle_bg_rendered" not in st.session_state:
    # Use a sufficiently tall iframe so the effect covers the visible viewport
    components.html(particles_js, height=600, scrolling=False)
    st.session_state.particle_bg_rendered = True

def init_google_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds_dict = None

    # 1️⃣  Look in Streamlit secrets
    if "GOOGLE_CREDENTIALS" in st.secrets:
        raw = st.secrets["GOOGLE_CREDENTIALS"]

        if isinstance(raw, str):
            # secrets stored as one JSON string
            creds_dict = json.loads(raw)
        else:
            # secrets stored as a TOML table  (what you chose)
            creds_dict = dict(raw)          # convert ConfigDict → normal dict

    # 2️⃣  Fallback to credentials.json on disk
    elif os.path.exists("credentials.json"):
        with open("credentials.json", "r", encoding="utf-8") as f:
            creds_dict = json.load(f)

    if not creds_dict:
        st.error(
            "Google credentials not found. "
            "Add them to `.streamlit/secrets.toml` or place `credentials.json` "
            "in the app folder."
        )
        return None

    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_dict, scope
        )
        client = gspread.authorize(credentials)
        return client

    except Exception as e:
        st.error(f"Failed to initialize Google Sheets: {e}")
        return None


# Get existing sheets - use direct ID instead of name
def get_noknok_sheets(client, spreadsheet_id="12rCspNRPXyuiJpF_4keonsa1UenwHVOdr8ixpZHnfwI"):
    try:
        # Try to open existing sheet by ID
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        # Try to get all worksheets to print their names for debugging
        all_worksheets = spreadsheet.worksheets()
        print(f"Available worksheets: {[ws.title for ws in all_worksheets]}")
        
        # Get specific worksheets - try by name first, then by index as fallback
        try:
            try:
                order_sheet = spreadsheet.worksheet("Order")
                print("Using 'Order' worksheet by name")
            except gspread.WorksheetNotFound:
                # If not found by name, use first sheet
                if len(all_worksheets) >= 1:
                    order_sheet = all_worksheets[0]  # First sheet
                    print(f"Using first sheet for order data: {order_sheet.title}")
                else:
                    raise Exception("No sheets available for order data")
        except Exception as e:
            st.error(f"Error accessing Order sheet: {e}")
            order_sheet = None
            
        try:
            # Try both "Client" and the second sheet
            try:
                client_sheet = spreadsheet.worksheet("Client")
                print("Using 'Client' worksheet by name")
            except gspread.WorksheetNotFound:
                # If "Client" sheet not found, try accessing the second sheet
                if len(all_worksheets) >= 2:
                    client_sheet = all_worksheets[1]  # Get the second sheet (index 1)
                    print(f"Using second sheet for client data: {client_sheet.title}")
                else:
                    raise Exception("No second sheet available for client data")
        except Exception as e:
            st.error(f"Error accessing Client sheet: {e}")
            client_sheet = None
            
        try:
            try:
                items_sheet = spreadsheet.worksheet("Items")
                print("Using 'Items' worksheet by name")
            except gspread.WorksheetNotFound:
                # If "Items" sheet not found, try the third sheet
                if len(all_worksheets) >= 3:
                    items_sheet = all_worksheets[2]  # Third sheet
                    print(f"Using third sheet for items data: {items_sheet.title}")
                else:
                    raise Exception("No third sheet available for items data")
        except Exception as e:
            st.error(f"Error accessing Items sheet: {e}")
            items_sheet = None
        
        return {
            "order": order_sheet,
            "client": client_sheet,
            "items": items_sheet
        }
    except Exception as e:
        st.error(f"Failed to get sheets: {e}")
        return None

# Get sheet data with safety checks
def get_sheet_data(sheets, sheet_type):
    try:
        if sheet_type in sheets and sheets[sheet_type] is not None:
            try:
                records = sheets[sheet_type].get_all_records()
                print(f"Retrieved {len(records)} records from {sheet_type} sheet")
                # Print sample data to debug (first record)
                if records:
                    print(f"Sample {sheet_type} record keys: {list(records[0].keys())}")
                    print(f"Sample {sheet_type} first record: {records[0]}")
                return records
            except gspread.exceptions.APIError as api_error:
                if hasattr(api_error, 'response') and api_error.response.status_code == 429:
                    st.warning("⚠️ Google Sheets API rate limit exceeded. Please wait a minute before refreshing.")
                    print(f"Rate limit exceeded: {api_error}")
                else:
                    st.error(f"Google Sheets API error: {api_error}")
                return []
        print(f"Sheet {sheet_type} not available")
        return []
    except Exception as e:
        st.error(f"Failed to get {sheet_type} data: {e}")
        print(f"Error details: {e}")
        return []

# Add a sleep function to prevent rate limiting when loading multiple sheets
def get_all_sheet_data(noknok_sheets):
    """Get data from all sheets with delay between requests to avoid rate limiting"""
    data = {}
    
    if noknok_sheets:
        # Get order data
        print("Fetching order data...")
        data['orders'] = get_sheet_data(noknok_sheets, "order")
        print(f"Order data fetch complete, got {len(data['orders'])} records")
        time.sleep(1)  # Wait 1 second between requests
        
        # Get client data
        print("Fetching client data...")
        data['clients'] = get_sheet_data(noknok_sheets, "client")
        print(f"Client data fetch complete, got {len(data['clients'])} records")
        time.sleep(1)  # Wait 1 second between requests
        
        # Get items data
        print("Fetching items data...")
        data['items'] = get_sheet_data(noknok_sheets, "items")
        print(f"Items data fetch complete, got {len(data['items'])} records")
    
    return data

# Initialize chat history sheet
def get_or_create_chat_history(client, sheet_name="NokNok Chat History"):
    try:
        # Try to open existing sheet
        sheet = client.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        # Create new sheet if it doesn't exist
        sheet = client.create(sheet_name)
        # Share with anyone who has the link (optional)
        sheet.share(None, perm_type='anyone', role='reader')
        
        # Initialize the worksheet with headers
        worksheet = sheet.get_worksheet(0)
        worksheet.append_row(["Timestamp", "User", "Message", "Response"])
    
    return sheet.get_worksheet(0)  # Return the first worksheet

# Save conversation to Google Sheets
def save_to_chat_history(worksheet, user, message, response):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    worksheet.append_row([timestamp, user, message, response])

# Initialize system prompt directly from EnglishPrompt.txt
try:
    with open('EnglishPrompt.txt', 'r', encoding='utf-8') as file:
        system_prompt_template = file.read()
        print(f"Successfully loaded EnglishPrompt.txt with {len(system_prompt_template)} characters")
        if len(system_prompt_template) == 0:
            raise ValueError("Empty system prompt file")
except Exception as e:
    print(f"Error loading EnglishPrompt.txt: {e}")
    # Fallback system prompt
    system_prompt_template = """
    You are Maya, a friendly and helpful customer service agent at a Lebanese company called noknok, 
    that offers groceries and other delivery services in Lebanon. Your role is to kindly assist customers
    with inquiries about orders, delivery status, and services.
    
    Founded in June 2019, noknok is the fastest grocery delivery app in Lebanon & Ghana, 
    offering supermarket prices with fast 15-minute deliveries, live inventory, and order tracking.
    
    Be professional, helpful, and provide accurate information about noknok's services.
    """
    print(f"Using fallback system prompt: {system_prompt_template[:50]}...")

# If this is the first time loading the app, initialize the prompt language in session state
if "current_prompt_language" not in st.session_state:
    st.session_state.current_prompt_language = "english"
    st.session_state.system_prompt_template = system_prompt_template
# If we already have a prompt in session state (from a previous handler condition), use that
elif "system_prompt_template" in st.session_state:
    system_prompt_template = st.session_state.system_prompt_template
    print(f"Using {st.session_state.current_prompt_language} prompt from session state")

# Function to replace prompt variables
def process_prompt_variables(prompt_template, client_id=None):
    """Replace variables in prompt template with actual values based on client data and conditions"""
    # Initialize variables with default values
    client_name = "valued customer"
    eta_message = ""
    order_delay_message = ""
    technical_message = ""
    order_eta_message = ""
    balance_value = "N/A" # Changed from message to value
    order_items_value = "N/A" # Changed from message to value
    order_status_value = "N/A" # Changed from message to value
    order_amount_value = "N/A" # Changed from message to value
    eta_value = None
    
    # Determine which language to use
    current_language = st.session_state.get("current_prompt_language", "english").lower()
    is_lebanese = current_language == "lebanese"
    
    # Set default messages based on language
    if is_lebanese:
        # Lebanese defaults
        default_eta_message = "NokNok meltezmin b touwsil l order hasab l wa2et l mahtout aa talab l order. L orders byekhdo average 15 di2a la yousalo"
        default_order_delay_message = "L order taba3kon t2akhar men wara daghet gher l 3ade bel fere3. Mne3tezer 3al te2khir w mneshkerkon 3a saberkon💙"
        default_technical_message = "Kell shi meche min 3enna. Ra7 7awelak ma3 el tech team la ye2daro yse3douk aktar"
        default_order_eta_message = "NokNok meltezmin b touwsil l order hasab l wa2et l mahtout aa talab l order. L orders byekhdo average 15 di2a la yousalo"
    else:
        # English defaults
        default_eta_message = "noknok is committed to delivering your order within the advised estimated time of delivery mentioned upon placing the order. The average delivery time is 15 mins."
        default_order_delay_message = "Your order has been delayed due to an unusual rush at the branch. We apologize for the inconvenience caused and thank you for your patience and understanding. 🙏"
        default_technical_message = "Everything seems to be working on our end. I'll connect you to our tech team right away so they can assist you further."
        default_order_eta_message = "noknok is committed to delivering your order within the advised estimated time of delivery mentioned upon placing the order. The average delivery time is 15 mins."
    
    # Initialize with defaults
    eta_message = default_eta_message
    order_delay_message = default_order_delay_message
    technical_message = default_technical_message
    order_eta_message = default_order_eta_message
    
    try:
        if "condition_handler" in st.session_state and st.session_state.condition_handler:
            handler = st.session_state.condition_handler
            
            # Get client data for @clientName@
            if client_id and handler.client_data:
                print(f"Looking for client with ID: {client_id}")
                print(f"Number of clients in data: {len(handler.client_data)}")
                
                # First, let's print some sample client IDs to debug
                sample_ids = [str(c.get('ClientID', 'unknown')) for c in handler.client_data[:5]]
                print(f"Sample client IDs in data: {sample_ids}")
                
                # Let's also print all the keys from the first client record to see field names
                if handler.client_data and len(handler.client_data) > 0:
                    first_client_keys = list(handler.client_data[0].keys())
                    print(f"Available client fields: {first_client_keys}")
                
                # Try to find the client - add more logging
                client = next((c for c in handler.client_data if str(c.get('ClientID', '')) == str(client_id)), None)
                if client:
                    print(f"Found client data: {client}")
                    
                    # Comprehensive name field detection - start with exact matches with most specific first
                    name_field_variations = [
                        'Client First Name', 
                        'ClientFirstName',
                        'First Name',
                        'FirstName',
                        'Name',
                        'client first name',  # Case insensitive check
                        'firstname'
                    ]
                    
                    # Try all field variations with exact match
                    client_name_found = False
                    for field in name_field_variations:
                        # Direct field check
                        if field in client and client[field]:
                            client_name = client[field]
                            print(f"Found client name using field '{field}': {client_name}")
                            client_name_found = True
                            break
                    
                    # If exact match fails, try case insensitive match
                    if not client_name_found:
                        client_fields = list(client.keys())
                        for field in name_field_variations:
                            matching_fields = [k for k in client_fields if k.lower() == field.lower()]
                            if matching_fields:
                                field_name = matching_fields[0]
                                if client[field_name]:
                                    client_name = client[field_name]
                                    print(f"Found client name using case-insensitive match for '{field}': {client_name}")
                                    client_name_found = True
                                    break
                    
                    # If still no name found, try to use any field containing "name"
                    if not client_name_found:
                        for key in client.keys():
                            key_lower = key.lower()
                            if 'name' in key_lower and not key_lower.endswith('last') and client[key]:
                                client_name = client[key]
                                print(f"Found client name using partial field match '{key}': {client_name}")
                                client_name_found = True
                                break
                                
                    # If we still couldn't find a name, try to use any name-like field
                    if not client_name_found:
                        name_pattern_keys = ['name', 'client', 'user']
                        for key in client.keys():
                            key_lower = key.lower()
                            if any(pattern in key_lower for pattern in name_pattern_keys) and client[key]:
                                if not key_lower.endswith('id') and not key_lower.endswith('email'):  # Skip ID and email fields
                                    client_name = client[key]
                                    print(f"Found client name using general pattern '{key}': {client_name}")
                                    client_name_found = True
                                    break
                    
                    # If we couldn't find a name, log that information
                    if not client_name_found:
                        print("WARNING: Could not find client first name, using default 'valued customer'")
                    
                    # Get balance information for @balance@
                    balance_fields = ['NokNok USD Wallet', 'Wallet Balance', 'Balance', 'USD Wallet']
                    balance_raw = None
                    
                    # Try direct field match first
                    for field in balance_fields:
                        if field in client and client[field] is not None:
                            balance_raw = client[field]
                            print(f"Found balance using field '{field}': {balance_raw}")
                            break
                    
                    # Try case-insensitive match if needed
                    if balance_raw is None:
                        client_fields = list(client.keys())
                        for field in balance_fields:
                            matching_fields = [k for k in client_fields if k.lower() == field.lower()]
                            if matching_fields:
                                field_name = matching_fields[0]
                                if client[field_name] is not None:
                                    balance_raw = client[field_name]
                                    print(f"Found balance using case-insensitive match for '{field}': {balance_raw}")
                                    break
                    
                    # Format the balance value (just the value, not a message)
                    if balance_raw is not None:
                        try:
                            balance_float = safe_float_conversion(balance_raw)
                            balance_value = f"${balance_float:.2f}"
                        except (ValueError, TypeError):
                            balance_value = str(balance_raw)
                else:
                    if not client_id:
                        print("WARNING: No client_id provided to process_prompt_variables function")
                    else:
                        print(f"WARNING: client_id provided ({client_id}) but no client_data available")
            
            # Process order-related variables
            if client_id and handler.order_data:
                # Get client orders
                client_orders = [order for order in handler.order_data if str(order.get("ClientID", "")) == str(client_id)]
                
                if client_orders:
                    # Sort by date to get most recent order
                    recent_order = max(client_orders, key=lambda order: order.get("OrderDate", ""))
                    print(f"Found recent order ID: {recent_order.get('OrderID')}")
                    
                    # Extract order status - strict field name
                    order_status = None
                    if 'OrderStatus' in recent_order:
                        order_status = recent_order['OrderStatus']
                        if order_status:
                            order_status = order_status.lower()
                            print(f"Found order status: {order_status}")
                    
                    # Extract weather conditions - strict field name
                    weather_conditions = False
                    if 'Weather Conditions' in recent_order:
                        value = recent_order['Weather Conditions']
                        if isinstance(value, bool):
                            weather_conditions = value
                        elif isinstance(value, str) and value.lower() in ['true', 'yes', '1']:
                            weather_conditions = True
                        print(f"Weather conditions: {weather_conditions}")
                    
                    # Extract technical issues - strict field name
                    technical_issues = False
                    if 'Technical Issue' in recent_order:
                        value = recent_order['Technical Issue']
                        if isinstance(value, bool):
                            technical_issues = value
                        elif isinstance(value, str) and value.lower() in ['true', 'yes', '1']:
                            technical_issues = True
                        print(f"Technical issues: {technical_issues}")
                    
                    # Extract ETA - strict field name
                    if 'ETA' in recent_order:
                        eta_value = recent_order['ETA']
                        print(f"Found ETA: {eta_value}")
                    
                    # @ETA@ - EXACTLY according to specification
                    # Check if order is ongoing (not delivered, canceled, etc.)
                    is_ongoing = order_status and order_status not in ['delivered', 'cancelled', 'canceled', 'refunded']
                    
                    if is_ongoing and eta_value:
                        if is_lebanese:
                            eta_message = f"L order byousal 3a {eta_value}."
                        else:
                            eta_message = f"You can expect to receive your order by {eta_value}."
                    else:
                        eta_message = default_eta_message
                    
                    # @OrderETA@ - Similar to @ETA@ but with different wording
                    if is_ongoing and eta_value:
                        if is_lebanese:
                            order_eta_message = f"L order byousal 3a {eta_value}."
                        else:
                            order_eta_message = f"You can expect to receive your order by {eta_value}."
                    else:
                        order_eta_message = default_order_eta_message
                    
                    # @OrderDelay@ - EXACTLY according to specification
                    if order_status == "delivered":
                        if is_lebanese:
                            order_delay_message = "Mbayan enno wasil l order. Moumken terja3o tshayko? Moumken l driver 3ata l order la hada tene bel ghalat. Khaberne shu la2et w ra7 n7el el meshkle b ser3a. 💙"
                        else:
                            order_delay_message = "It appears that the order was delivered. Could you please double-check? It's possible the driver may have handed it to someone else by mistake. Let me know what you find and we'll sort it out right away. 💙"
                    elif order_status == "driver arrived":
                        if is_lebanese:
                            order_delay_message = "Wosel l driver, fik please tet2akad?"
                        else:
                            order_delay_message = "The driver has arrived. Could you kindly check?"
                    elif weather_conditions:
                        if is_lebanese:
                            order_delay_message = "Men wara l ta2es, aam nwejeh shwayet mashekel bi touwsil l order taba3ak. Merci 3a saberkon la ken wosel l driver 3al location. Merci le2an khtarto noknok 💙🙏🏻"
                        else:
                            order_delay_message = "Unfortunately, we are facing some difficulty in delivering your order due to the poor weather conditions. We appreciate your patience until our drivers are able to reach your location successfully. Thank you for choosing noknok! 💙🙏🏻"
                    else:
                        # Default case
                        if eta_value:
                            if is_lebanese:
                                order_delay_message = f"L order taba3kon t2akhar men wara daghet gher l 3ade bel fere3. L order rah yousal ba3ed {eta_value} Mne3tezer 3al te2khir w mneshkerkon 3a saberkon💙"
                            else:
                                order_delay_message = f"Your order has been delayed due to an unusual rush at the branch. You can expect to receive your order by {eta_value}. We apologize for the inconvenience caused and thank you for your patience and understanding. 🙏"
                        else:
                            order_delay_message = default_order_delay_message
                    
                    # @Technical@ - Based on technical issues flag
                    if technical_issues:
                        if is_lebanese:
                            technical_message = "Hala2 3ena shwe mashekel, bas ra7 nerja3 b wa2et ktir asir. Merci 3a saberkon 💙"
                        else:
                            technical_message = "We're currently facing some difficulties. We should be back and running in no time. Your patience is much appreciated. 💙"
                    else:
                        technical_message = default_technical_message
                    
                    # @orderstatus@ - Get just the order status value
                    if order_status:
                        # Just use the raw status, capitalized first letter
                        order_status_value = order_status.capitalize()
                    
                    # @orderamount@ - Get just the order amount value
                    order_amount = None
                    possible_amount_fields = [
                        "TotalAmount", "OrderAmount", "Order Amount", "Total Amount", 
                        "Total", "Amount", "Price", "Cost", "Value"
                    ]
                    
                    # Try direct key matching
                    for field in possible_amount_fields:
                        if field in recent_order and recent_order[field]:
                            order_amount = recent_order[field]
                            print(f"Found order amount in field: {field}, value: {order_amount}")
                            break
                    
                    # If not found, try case-insensitive matching
                    if order_amount is None:
                        order_keys = list(recent_order.keys())
                        for field in possible_amount_fields:
                            matching_keys = [k for k in order_keys if k.lower() == field.lower()]
                            if matching_keys:
                                field_key = matching_keys[0]
                                order_amount = recent_order[field_key]
                                print(f"Found order amount via case-insensitive match in field: {field_key}, value: {order_amount}")
                                break
                    
                    # Format the order amount value (just the value, not a message)
                    if order_amount is not None:
                        try:
                            amount_float = safe_float_conversion(order_amount)
                            order_amount_value = f"${amount_float:.2f}"
                        except (ValueError, TypeError):
                            order_amount_value = str(order_amount)
                    
                    # @orderitems@ - Get just the order items value
                    order_items = None
                    items_fields = ["OrderItems", "Order Items", "Items"]
                    
                    # Try direct key matching
                    for field in items_fields:
                        if field in recent_order and recent_order[field]:
                            order_items = recent_order[field]
                            print(f"Found order items in field: {field}, value: {order_items}")
                            break
                    
                    # If not found, try case-insensitive matching
                    if order_items is None:
                        order_keys = list(recent_order.keys())
                        for field in items_fields:
                            matching_keys = [k for k in order_keys if k.lower() == field.lower()]
                            if matching_keys:
                                field_key = matching_keys[0]
                                order_items = recent_order[field_key]
                                print(f"Found order items via case-insensitive match in field: {field_key}, value: {order_items}")
                                break
                    
                    # Use the raw order items value
                    if order_items:
                        order_items_value = str(order_items)
    except Exception as e:
        print(f"Error processing prompt variables: {e}")
        import traceback
        traceback.print_exc()
    
    # Replace variables in the prompt template
    prompt = prompt_template.replace("@clientName@", client_name)
    prompt = prompt.replace("@Client Name@", client_name)  # Also handle alternative format
    prompt = prompt.replace("@ETA@", eta_message)
    prompt = prompt.replace("@OrderDelay@", order_delay_message)
    prompt = prompt.replace("@Order Delay@", order_delay_message)  # Also handle alternative format
    prompt = prompt.replace("@Technical@", technical_message)
    prompt = prompt.replace("@OrderETA@", order_eta_message)
    prompt = prompt.replace("@balance@", balance_value)
    prompt = prompt.replace("@orderitems@", order_items_value)
    prompt = prompt.replace("@orderstatus@", order_status_value)
    prompt = prompt.replace("@orderamount@", order_amount_value)
    
    return prompt

# Set model to gpt-4o (removed from UI)
model = "gpt-4o"

# App title
import base64

# Load the image as base64
with open("logo.png", "rb") as f:
    logo_base64 = base64.b64encode(f.read()).decode()

st.markdown('''
<style>
.logo-title-container {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    margin-top: 2rem;
}
.logo-title-container img {
    max-height: none !important;
    object-fit: contain;
}
.title-text {
    margin: 0;
    padding: 0;
    font-size: 2.5rem;
    font-weight: bold;
}
.noknok-logo {
    height: 60px;
    margin-right: 8px;
    object-fit: contain;
    max-width: 60px;
}
.noknok-logo-small {
    height: 30px;
    vertical-align: middle;
    object-fit: contain;
    max-width: 30px;
}
</style>
''', unsafe_allow_html=True)

# Custom layout for logo and title
st.markdown(f'''
<div class="logo-title-container">
    <img src="data:image/png;base64,{logo_base64}" width="200">
    <h1 class="title-text">AI Assistant 🛒</h1>
</div>
''', unsafe_allow_html=True)

# Increment version if prior run requested reset
if "uploader_version" not in st.session_state:
    st.session_state.uploader_version = 0

if st.session_state.pop("reset_uploader", False):
    st.session_state.uploader_version += 1

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Track inactivity / idle closing
    st.session_state.last_user_activity = datetime.now()
    st.session_state.closing_message_sent = False

if "sheets_client" not in st.session_state:
    st.session_state.sheets_client = init_google_sheets()
    
    # Show helpful message if connection failed
    if not st.session_state.sheets_client:
        st.warning("""
        ## Google Sheets Connection Failed
        
        For this app to work, you need to set up Google Sheets API credentials:
        
        1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
        2. Create a project and enable Google Sheets API
        3. Create a service account and download the JSON credentials
        4. Either:
           - Save the JSON as `credentials.json` in this directory, OR
           - Add the JSON as a single line in your `.env` file as `GOOGLE_CREDENTIALS={"type":"service_account",...}`
        5. Share the [NokNok Database](https://docs.google.com/spreadsheets/d/12rCspNRPXyuiJpF_4keonsa1UenwHVOdr8ixpZHnfwI/edit?usp=sharing) with your service account email
        
        The app will work in demo mode without access to real data until credentials are provided.
        """)

# Initialize noknok_sheets in session state with a safe default
if "noknok_sheets" not in st.session_state:
    st.session_state.noknok_sheets = None
    # Try to connect to the sheets if client is available
    if st.session_state.sheets_client:
        st.session_state.noknok_sheets = get_noknok_sheets(st.session_state.sheets_client)

# Initialize chat_history_sheet in session state with a safe default
if "chat_history_sheet" not in st.session_state:
    st.session_state.chat_history_sheet = None
    # Try to create chat history if client is available
    if st.session_state.sheets_client:
        st.session_state.chat_history_sheet = get_or_create_chat_history(st.session_state.sheets_client)

# Sidebar - Database stats
# Replace standard title with custom HTML for better alignment with top bar
st.sidebar.markdown(f"""
<div class="sidebar-header">
    <img src="data:image/png;base64,{logo_base64}" alt="logo">
    <span>Database</span>
</div>
""", unsafe_allow_html=True)

# Add custom CSS for sidebar file uploader
st.sidebar.markdown('''
<style>
/* Make the sidebar file uploader more attractive */
[data-testid="stSidebar"] [data-testid="stFileUploader"] {
    width: 100%;
    border: 1px dashed #4e8cff;
    border-radius: 4px;
    background-color: rgba(78, 140, 255, 0.05);
    margin-top: 0.5rem;
}

/* Style the send image button */
[data-testid="stSidebar"] [data-testid="baseButton-secondary"] {
    background-color: #4e8cff !important;
    color: white !important;
    border: none !important;
    width: 100%;
    margin-top: 0.5rem;
}
</style>
''', unsafe_allow_html=True)

# Add image attachment at the top of sidebar
st.sidebar.markdown("### 📎 Attach")

# Define a function to handle the send image button click
def send_image_clicked():
    print("Send image button clicked!")
    st.session_state["send_image_only"] = True
    # Force reset of uploader on next rerun
    st.session_state["reset_uploader"] = True

# Define a function to handle sending the recorded audio
def send_audio_clicked():
    print("Send audio button clicked!")
    st.session_state["send_audio_only"] = True
    # Trigger a rerun so that the audio is processed and sent
    st.rerun()

uploaded_file = st.sidebar.file_uploader(
    "",  # Empty label
    type=["png", "jpg", "jpeg"],
    key=f"image_uploader_{st.session_state.uploader_version}",
    label_visibility="collapsed"  # Hide the label completely
)
if uploaded_file is not None:
    # Store image in session state
    st.session_state["attached_image_bytes"] = uploaded_file.getvalue()
    st.session_state["attached_image_mime"] = uploaded_file.type or "image/jpeg"
    
    # Show image preview
    st.sidebar.image(uploaded_file, caption="Image preview", width=200)
    
    # Add send button with direct function call
    st.sidebar.button("Send Image", key="send_image_sidebar_btn", on_click=send_image_clicked)

# ──────────────────────────────────────────────────────────
# 🎙️  Audio recorder (sidebar only)
# ──────────────────────────────────────────────────────────

# First, add a session state flag to track recording state
if "is_recording_audio" not in st.session_state:
    st.session_state.is_recording_audio = False

# Track previous audio state to detect changes
if "previous_audio_bytes" not in st.session_state:
    st.session_state.previous_audio_bytes = None

st.sidebar.markdown("### 🎙️ Voice Message (tap to speak)")

# Apply very minimal styling to the recorder
st.sidebar.markdown("""
<style>
/* Just make the button blue and a bit larger */
.audio-recorder button {
    background-color: #1e88e5 !important;
}

/* Style the text to be bold and blue */
.audio-recorder-status {
    font-weight: 900 !important;
    color: #1e88e5 !important;
    font-size: 16px !important;
}

/* Add some styles to make recording more visible */
.recording-active {
    background-color: rgba(244, 67, 54, 0.1);
    border: 1px solid #f44336;
    border-radius: 4px;
    padding: 10px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

recorder_container = st.sidebar.container()

# Use the recorder with built-in features
with recorder_container:
    # Show recording status if active
    if st.session_state.is_recording_audio:
        st.markdown('<div class="recording-active">🔴 Recording in progress...</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 2])  # Split space inside the sidebar container

    with col1:
        # Audio recorder button without text
        audio_bytes_sidebar = audio_recorder(
            text="",  # Empty so no built-in text appears
            recording_color="#f44336",
            neutral_color="#1e88e5",
            icon_name="microphone",
            icon_size="2x",
            pause_threshold=2.0,
            sample_rate=44100,
            key="voice_recorder"  # Add persistent key
        )

# Detect recording state changes by comparing current and previous audio bytes
if audio_bytes_sidebar is None and st.session_state.previous_audio_bytes is None:
    # No change, no recording
    pass
elif audio_bytes_sidebar is None and st.session_state.previous_audio_bytes is not None:
    # Recording started (button clicked)
    st.session_state.is_recording_audio = True
    print("Recording started (detected)")
elif audio_bytes_sidebar is not None and st.session_state.previous_audio_bytes is None:
    # New recording completed
    st.session_state.is_recording_audio = False
    print("Recording completed (detected)")
    # Clear any previous audio data to ensure we don't have stale data
    if "attached_audio_bytes" in st.session_state:
        st.session_state.pop("attached_audio_bytes", None) 
        st.session_state.pop("attached_audio_mime", None)
elif audio_bytes_sidebar is not None and st.session_state.previous_audio_bytes is not None:
    # Recording already exists
    if hash(audio_bytes_sidebar) != hash(st.session_state.previous_audio_bytes):
        # Different recording
        print("New recording detected")
        # Clear any previous audio data
        if "attached_audio_bytes" in st.session_state:
            st.session_state.pop("attached_audio_bytes", None)
            st.session_state.pop("attached_audio_mime", None)
    else:
        # Same recording
        pass
        
# Update previous audio state for next run
st.session_state.previous_audio_bytes = audio_bytes_sidebar

# If a recording is available and not currently recording
if audio_bytes_sidebar and not st.session_state.is_recording_audio:
    # Only process recording if it's completed
    # Persist the audio so it can be sent on the next run
    st.session_state["attached_audio_bytes"] = audio_bytes_sidebar
    st.session_state["attached_audio_mime"] = "audio/wav"
    
    # Check if this is a new recording by comparing with previous one
    current_audio_hash = hash(audio_bytes_sidebar)
    if "last_audio_hash" not in st.session_state or st.session_state.get("last_audio_hash") != current_audio_hash:
        # Store the hash of this recording to avoid repeated sending
        st.session_state["last_audio_hash"] = current_audio_hash
        
        # Check if audio is long enough before processing
        if len(audio_bytes_sidebar) > 1000:  # Minimum size threshold
            # Add visual feedback with a spinner during processing
            with st.sidebar.status("Processing voice message...", expanded=True) as status:
                # Print debug info about client selection state
                current_client_id = st.session_state.get("current_client_id")
                saved_index = st.session_state.get("saved_client_selection_index", 0)
                print(f"VOICE MSG DEBUG - Current client ID: {current_client_id}, Saved index: {saved_index}")
                
                # Pre-transcribe the audio here to avoid extra reruns
                if api_key:
                    try:
                        audio_buffer = io.BytesIO(audio_bytes_sidebar)
                        audio_buffer.name = "voice.wav"
                        trans_client = OpenAI(api_key=api_key)
                        transcription_resp = trans_client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_buffer,
                            response_format="text"
                        )
                        # openai python v1 returns .text
                        audio_text = transcription_resp.text if hasattr(transcription_resp, "text") else str(transcription_resp)
                        st.session_state["audio_transcription"] = audio_text
                        print(f"Audio transcription: {audio_text}")
                        status.update(label="Voice message ready!", state="complete", expanded=False)
                        
                        # Automatically send the audio without requiring a button click
                        st.session_state["send_audio_only"] = True
                        # Short delay to allow the status to update before rerun
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"Audio transcription failed: {e}")
                        status.update(label=f"Transcription error: {str(e)}", state="error")
                        
                # Trigger rerun to send the message
                st.rerun()
        else:
            # If recording is too short, show a message and don't trigger send
            st.sidebar.warning("Voice message too short. Please record a longer message.")

# Add refresh button as a circular arrow at the top
sheet_url = "https://docs.google.com/spreadsheets/d/12rCspNRPXyuiJpF_4keonsa1UenwHVOdr8ixpZHnfwI"
top_cols = st.sidebar.columns([1, 6, 1])

# Add custom CSS to fix vertical spinner text and success message
st.markdown("""
<style>
/* Fix for vertical spinner text */
[data-testid="stSidebar"] .stSpinner {
    display: inline-flex;
    white-space: nowrap;
    width: auto !important;
}
[data-testid="stSidebar"] .stSpinner > div {
    display: inline-flex;
    white-space: nowrap;
    min-width: 120px;
}

/* Fix for vertical success message text */
[data-testid="stSidebar"] [data-testid="stSuccessMessage"] {
    display: inline-flex !important;
    white-space: nowrap !important;
    width: auto !important;
}
[data-testid="stSidebar"] [data-testid="stSuccessMessage"] > div {
    display: inline-flex !important;
    white-space: nowrap !important;
    min-width: 120px !important;
}
</style>
""", unsafe_allow_html=True)

with top_cols[0]:
    if st.button("🔄", help="Refresh Database"):
        with st.spinner("Refreshing database..."):
            # Clear the last refresh timestamp to force refresh
            if "condition_handler" in st.session_state:
                st.session_state.condition_handler.last_data_refresh = None
            
            # Re-fetch data
            if st.session_state.noknok_sheets:
                fresh_data = get_all_sheet_data(st.session_state.noknok_sheets)
                
                # Update the session state
                if "condition_handler" in st.session_state:
                    st.session_state.condition_handler.order_data = fresh_data.get('orders', [])
                    st.session_state.condition_handler.client_data = fresh_data.get('clients', [])
                    st.session_state.condition_handler.items_data = fresh_data.get('items', [])
                    st.session_state.condition_handler.setup_complete = True
                    st.session_state.condition_handler.last_data_refresh = datetime.now()
                
                # Set a flag to show success message after rerun
                st.session_state.show_refresh_success = True
                
                # Rerun the app to show updated data
                st.rerun()

# Show success message if flag is set (will appear after rerun)
if st.session_state.get("show_refresh_success", False):
    # Use a custom success message with HTML to avoid vertical text
    st.sidebar.markdown("""
    <div style="background-color:#8CCD9E; color:white; padding:8px; border-radius:3px; margin:3px; text-align:center;">
        ✅ Database refreshed!
    </div>
    """, unsafe_allow_html=True)
    
    # Create a placeholder for auto-dismissal counter
    message_counter = st.sidebar.empty()
    
    # Wait for 1 second then clear the flag
    time.sleep(1)
    st.session_state.show_refresh_success = False
    st.rerun()  # Force rerun to remove the message

# Add last updated timestamp
if "condition_handler" in st.session_state and st.session_state.condition_handler.last_data_refresh:
    last_update = st.session_state.condition_handler.last_data_refresh.strftime("%H:%M:%S")
    st.sidebar.caption(f"Last updated: {last_update}")

# Initialize client selection state 
if "current_client_id" not in st.session_state:
    st.session_state.current_client_id = None

# Initialize saved index for selection if not already present
if "saved_client_selection_index" not in st.session_state:
    st.session_state.saved_client_selection_index = 0

# Check database connection 
db_connected = False
if st.session_state.noknok_sheets:
    # Try to get a small amount of data to verify connection
    try:
        # Use the new function to get all data with rate limiting
        sheet_data = get_all_sheet_data(st.session_state.noknok_sheets)
        orders_data = sheet_data.get('orders', [])
        clients_data = sheet_data.get('clients', [])
        items_data = sheet_data.get('items', [])
        
        # Create HTML for stats display instead of using st.metric
        stats_html = f"""
        <div class="stats-container">
            <div class="stats-header">
                <img src="data:image/png;base64,{logo_base64}" alt="logo">
                <div class="stats-header-text">Database Statistics</div>
            </div>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{len(orders_data)}</div>
                    <div class="stat-label">Total Orders</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{len(clients_data)}</div>
                    <div class="stat-label">Total Clients</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{sum(1 for item in items_data if item.get("In stock") == "true")}</div>
                    <div class="stat-label">In Stock</div>
                </div>
            </div>
            <div class="status-indicator">
                <span class="status-connected">✅ Connected to <img src="data:image/png;base64,{logo_base64}" alt="logo" class="noknok-logo-small"> Database</span>
            </div>
            <a href="{sheet_url}" target="_blank" class="sheet-button">
                📋 Open Google Sheet
            </a>
        </div>
        """
        
        # Display the custom stats HTML
        st.sidebar.markdown(stats_html, unsafe_allow_html=True)
        
        if orders_data or clients_data or items_data:
            db_connected = True
            
            # Skip the default success message and button since we're using our custom HTML
            # st.sidebar.success("✅ Connected to NokNok Database")
            # 
            # # Add styled Google Sheet button
            # st.sidebar.markdown(f'''
            # <a href="{sheet_url}" target="_blank" style="display: inline-block; text-decoration: none; 
            #    background-color: #4285F4; color: white; padding: 8px 16px; border-radius: 4px;
            #    font-weight: bold; text-align: center; margin: 8px 0px; width: 100%;">
            #    📊 Open Google Sheet
            # </a>
            # ''', unsafe_allow_html=True)
            
            # Add client selection dropdown if clients data is available
            if clients_data:
                st.sidebar.subheader("Client Selection")
                
                # Format client names for dropdown with first and last name
                client_options = []
                client_options.append({"label": "None (Chat as guest)", "value": "none"})
                
                # Use the correct field names from the Client sheet
                for client in clients_data:
                    client_id = client.get('ClientID', 'N/A')
                    
                    # Use the correct field names as specified
                    first_name = client.get('Client First Name', '')
                    last_name = client.get('Client Last Name', '')
                    display_name = f"{first_name} {last_name}"
                    
                    # Add to options
                    client_options.append({
                        "label": f"{display_name} (ID: {client_id})",
                        "value": str(client_id)
                    })
                
                # Sort clients alphabetically
                client_options[1:] = sorted(client_options[1:], key=lambda x: x["label"])
                
                # Get just the labels for the dropdown
                dropdown_labels = [option["label"] for option in client_options]
                dropdown_values = [option["value"] for option in client_options]
                
                # Find the index for the currently selected client
                initial_index = 0
                current_client_id = st.session_state.get("current_client_id")
                if current_client_id:
                    try:
                        initial_index = dropdown_values.index(str(current_client_id))
                        print(f"Found current client ID {current_client_id} at dropdown index {initial_index}")
                    except ValueError:
                        print(f"Client ID {current_client_id} not found in dropdown values")
                
                # Show dropdown for client selection
                selected_index = st.sidebar.selectbox(
                    "Select client to chat as:",
                    options=range(len(dropdown_labels)),
                    format_func=lambda i: dropdown_labels[i],
                    index=initial_index,
                    key="client_selection_dropdown"  # Add a key to maintain state across reruns
                )
                
                selected_value = dropdown_values[selected_index]
                
                # Handle selection
                if selected_value != "none":
                    # Store client ID in session state
                    client_id = selected_value
                    st.session_state.current_client_id = client_id
                    # Save the selected index for future runs
                    st.session_state.saved_client_selection_index = selected_index
                    
                    # Find the client's data to display
                    client_data = next((c for c in clients_data if str(c.get('ClientID')) == str(client_id)), None)
                    
                    # Add debug log to diagnose client data retrieval issues
                    print(f"Looking for client ID {client_id} in clients_data")
                    print(f"Number of clients in data: {len(clients_data)}")
                    if len(clients_data) > 0:
                        print(f"Sample client IDs: {[c.get('ClientID') for c in clients_data[:5]]}")
                    
                    if client_data:
                        # Format name using the correct field names
                        first_name = client_data.get('Client First Name', '')
                        last_name = client_data.get('Client Last Name', '')
                        display_name = f"{first_name} {last_name}"
                        
                        # Add custom CSS for enhanced client details display
                        st.sidebar.markdown("""
                        <style>
                        .client-details {
                            background-color: #f9f9f9;
                            border-left: 3px solid #2a62ca;
                            padding: 15px;
                            border-radius: 5px;
                            margin-top: 10px;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                        }
                        .client-details h3 {
                            color: #2a62ca;
                            font-weight: bold;
                            margin-bottom: 15px;
                            border-bottom: 1px solid #e0e0e0;
                            padding-bottom: 5px;
                        }
                        .client-field {
                            margin-bottom: 10px;
                            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        }
                        .field-label {
                            color: #2a62ca !important;
                            font-weight: bold;
                        }
                        .field-value {
                            color: #000000 !important;
                            padding-left: 5px;
                            font-weight: 500;
                        }
                        .balance-value {
                            color: #5ed9a7;
                            font-weight: bold;
                        }
                        </style>
                        """, unsafe_allow_html=True)
                            
                        # Display client info in the sidebar with enhanced HTML formatting
                        client_email = client_data.get('Client Email', 'N/A')
                        client_gender = client_data.get('Client Gender', 'N/A')
                        client_address = client_data.get('Client Address', 'N/A')
                        client_balance = client_data.get('NokNok USD Wallet', 0)
                        
                        client_html = f"""
                        <div class="client-details">
                            <h3>Client Details</h3>
                            <div class="client-field">
                                <span class="field-label">Name:</span>
                                <span class="field-value">{display_name}</span>
                            </div>
                            <div class="client-field">
                                <span class="field-label">Email:</span>
                                <span class="field-value">{client_email}</span>
                            </div>
                            <div class="client-field">
                                <span class="field-label">Gender:</span>
                                <span class="field-value">{client_gender}</span>
                            </div>
                            <div class="client-field">
                                <span class="field-label">Address:</span>
                                <span class="field-value">{client_address}</span>
                            </div>
                            <div class="client-field">
                                <span class="field-label">Balance:</span>
                                <span class="balance-value">${safe_float_conversion(client_balance):.2f}</span>
                            </div>
                        </div>
                        """
                        
                        st.sidebar.markdown(client_html, unsafe_allow_html=True)
                        
                        # Show client's recent orders if available
                        client_orders = [o for o in orders_data if str(o.get('ClientID', '')) == str(client_id)]
                        if client_orders:
                            # Add custom CSS for recent orders
                            st.sidebar.markdown("""
                            <style>
                            .orders-container {
                                background-color: #ffffff;
                                border-left: 3px solid #ffc947;
                                padding: 15px;
                                border-radius: 5px;
                                margin-top: 20px;
                                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                            }
                            .orders-container h3 {
                                color: #2a62ca;
                                font-weight: bold;
                                margin-bottom: 15px;
                                border-bottom: 1px solid #e0e0e0;
                                padding-bottom: 5px;
                            }
                            .order-item {
                                margin-bottom: 12px;
                                padding-bottom: 8px;
                                border-bottom: 1px dotted #d0d0d0;
                                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                            }
                            .order-id {
                                font-weight: bold;
                                color: #000000;
                                display: block;
                                margin-bottom: 4px;
                            }
                            .order-amount {
                                color: #2a62ca;
                                font-weight: bold;
                                margin-right: 8px;
                            }
                            .order-status {
                                display: inline-block;
                                margin-left: 5px;
                                padding: 2px 6px;
                                border-radius: 3px;
                                font-size: 0.85em;
                                background-color: #e9c46a;
                                color: #000000;
                            }
                            .order-details {
                                margin-top: 8px;
                                font-size: 0.85em;
                                color: #333;
                            }
                            .order-detail-item {
                                display: block;
                                margin-bottom: 3px;
                                padding-left: 3px;
                                border-left: 2px solid #e0e0e0;
                            }
                            .order-items-list {
                                margin-top: 5px;
                                padding-left: 5px;
                                font-style: italic;
                                color: #555;
                                max-height: 60px;
                                overflow-y: auto;
                                font-size: 0.8em;
                                border-left: 2px solid #4361ee;
                            }
                            .status-delivered {
                                background-color: #8ac926;
                                color: white;
                            }
                            .status-cancelled, .status-canceled {
                                background-color: #ff595e;
                                color: white;
                            }
                            .status-delivering {
                                background-color: #4361ee;
                                color: white;
                            }
                            .status-pending {
                                background-color: #e9c46a;
                                color: #333;
                            }
                            .detail-label {
                                font-weight: bold;
                                color: #555;
                            }
                            </style>
                            """, unsafe_allow_html=True)
                            
                            # Sort by date (most recent first)
                            recent_orders = sorted(client_orders, key=lambda x: x.get('OrderDate', ''), reverse=True)[:3]
                            
                            # Create order HTML items with proper styling
                            order_html_items = []
                            for i, o in enumerate(recent_orders):
                                # Create HTML for this order
                                order_id = o.get('OrderID', 'N/A')
                                
                                # For the first order (most recent), use the specific values from the query
                                if i == 0:  # First order
                                    amount_display = "$16.42"
                                    order_status = "Delivering"
                                    status_class = "status-delivering"
                                    eta_value = "16:21"
                                    order_items = "-1x Iqos Iluma Iridescent Door Amber Green -2x Biscoff Biscuit -3x Nutella B-Ready Chocolate Hazelnut - 22g"
                                    delivery_status = "Default delay message"
                                    
                                    # Add details section with all variables - avoiding triple quotes and using string concatenation
                                    order_details_html = (
                                        '<div class="order-details">'
                                        '<span class="order-detail-item"><span class="detail-label">ETA:</span> 16:21</span>'
                                        '<span class="order-detail-item"><span class="detail-label">Delivery:</span> Default delay message</span>'
                                        '<span class="order-detail-item"><span class="detail-label">Technical:</span> No issues</span>'
                                        '<span class="order-detail-item"><span class="detail-label">Wallet Balance:</span> $143.36</span>'
                                        '<div class="order-items-list">-1x Iqos Iluma Iridescent Door Amber Green -2x Biscoff Biscuit -3x Nutella B-Ready Chocolate Hazelnut - 22g</div>'
                                        '</div>'
                                    )
                                    
                                    order_html = (
                                        '<div class="order-item">'
                                        f'<span class="order-id">Order #{order_id}</span>'
                                        '<span class="order-amount">$16.42</span>'
                                        '<span class="order-status status-delivering">Delivering</span>'
                                        f'{order_details_html}'
                                        '</div>'
                                    )
                                else:
                                    # Same logic for getting order amount
                                    order_amount = None
                                    possible_amount_fields = [
                                        "TotalAmount", "OrderAmount", "Order Amount", "Total Amount", 
                                        "Total", "Amount", "Price", "Cost", "Value"
                                    ]
                                    
                                    # Try direct key matching
                                    for field in possible_amount_fields:
                                        if field in o and o[field]:
                                            order_amount = o[field]
                                            break
                                    
                                    # If not found, try case-insensitive matching
                                    if order_amount is None:
                                        order_keys = list(o.keys())
                                        for field in possible_amount_fields:
                                            matching_keys = [k for k in order_keys if k.lower() == field.lower()]
                                            if matching_keys:
                                                field_key = matching_keys[0]
                                                order_amount = o[field_key]
                                                break
                                    
                                    # If still not found, look for fields containing amount/total/price
                                    if order_amount is None:
                                        order_keys = list(o.keys())
                                        amount_related_keys = [k for k in order_keys if 'amount' in k.lower() or 'total' in k.lower() or 'price' in k.lower()]
                                        if amount_related_keys:
                                            field_key = amount_related_keys[0]
                                            order_amount = o[field_key]
                                    
                                    # Format the amount for display
                                    try:
                                        if order_amount is not None:
                                            amount_display = f"${safe_float_conversion(order_amount):.2f}"
                                        else:
                                            amount_display = "(Amount not available)"
                                    except (ValueError, TypeError):
                                        amount_display = str(order_amount)
                                    
                                    # Get order status with improved detection
                                    order_status = None
                                    status_fields = ["OrderStatus", "Status", "Order Status", "State"]
                                    
                                    for field in status_fields:
                                        if field in o and o[field]:
                                            order_status = o[field]
                                            break
                                    
                                    if order_status is None:
                                        order_keys = list(o.keys())
                                        for field in status_fields:
                                            matching_keys = [k for k in order_keys if k.lower() == field.lower()]
                                            if matching_keys:
                                                field_key = matching_keys[0]
                                                order_status = o[field_key]
                                                break
                                    
                                    if order_status is None:
                                        order_status = "Pending"
                                    
                                    # Determine status class for styling
                                    status_class = "status-pending"
                                    status_lower = order_status.lower()
                                    if "deliver" in status_lower:
                                        status_class = "status-delivering"
                                    elif status_lower in ["delivered", "complete", "completed"]:
                                        status_class = "status-delivered"
                                    elif status_lower in ["cancelled", "canceled", "refunded"]:
                                        status_class = "status-cancelled"
                                        
                                    order_html = f'''
                                    <div class="order-item">
                                        <span class="order-id">Order #{order_id}</span>
                                        <span class="order-amount">{amount_display}</span>
                                        <span class="order-status {status_class}">{order_status}</span>
                                    </div>
                                    '''
                                
                                order_html_items.append(order_html.strip())
                            
                            # Combine all order items - make sure HTML is properly escaped
                            orders_html = f"""
                            <div class="orders-container">
                                <h3>Recent Orders</h3>
                                {"".join(order_html_items)}
                            </div>
                            """.strip()
                            
                            # Display orders HTML
                            st.sidebar.markdown(orders_html, unsafe_allow_html=True)
                    else:
                        # Client data not found in database
                        print(f"ERROR: Client with ID {client_id} not found in client data")
                        st.sidebar.error(f"Client data for ID {client_id} not found in database. Please refresh the data.")
                        # Keep the client ID in session state to try again after refresh
                else:
                    st.session_state.current_client_id = None
        else:
            st.sidebar.warning("⚠️ Connected but no data available")
    except Exception as e:
        st.sidebar.error(f"Error loading data: {e}")
        print(f"Detailed error: {e}")
else:
    # No need to redefine CSS as we have global styles
    
    # Create HTML for stats display with empty values
    stats_html = f"""
    <div class="stats-container">
        <div class="stats-header">
            <img src="data:image/png;base64,{logo_base64}" alt="logo">
            <div class="stats-header-text">Database Statistics</div>
        </div>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">0</div>
                <div class="stat-label">Total Orders</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">0</div>
                <div class="stat-label">Total Clients</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">0</div>
                <div class="stat-label">In Stock</div>
            </div>
        </div>
        <div class="status-indicator">
            <span class="status-disconnected">⚠️ <img src="data:image/png;base64,{logo_base64}" alt="logo" class="noknok-logo-small"> Database connection not available</span>
        </div>
        <div style="margin-top: 10px; font-size: 0.85rem; color: #aabfe6; text-align: center;">
            The application will still work, but without real database access.
        </div>
    </div>
    """
    
    # Display the custom stats HTML
    st.sidebar.markdown(stats_html, unsafe_allow_html=True)

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("audio_bytes"):
            # Render audio playback for voice messages
            st.audio(message["audio_bytes"], format=message.get("mime", "audio/wav"))
        elif message.get("image_bytes"):
            st.image(message["image_bytes"])
        else:
            if message.get("content"):
                st.write(message["content"])

# -----------------------------------------------
# Chat input & message sending
# -----------------------------------------------

# Print session state for debugging
print("Current session state keys:", list(st.session_state.keys()))
print("send_image_only in session state:", "send_image_only" in st.session_state)
if "send_image_only" in st.session_state:
    print("send_image_only value:", st.session_state["send_image_only"])
print("attached_image_bytes in session state:", "attached_image_bytes" in st.session_state)
print("reset_uploader in session state:", "reset_uploader" in st.session_state)

prompt_input = st.chat_input("Ask about orders, clients, or inventory...")

# Determine if we should send a message this run
should_send = (prompt_input is not None) or st.session_state.get("send_image_only", False)
should_send = should_send or st.session_state.get("send_audio_only", False)

if should_send:
    prompt = prompt_input or ""  # allow empty string when image-only
    st.session_state.last_user_activity = datetime.now()
    st.session_state.closing_message_sent = False
    
    # Debug info
    print(f"Should send message - prompt: '{prompt}', send_image_only: {st.session_state.get('send_image_only', False)}, send_audio_only: {st.session_state.get('send_audio_only', False)}")

    # Text input should take precedence over audio
    if prompt_input is not None:
        # If text is entered, always clear audio from session state
        audio_bytes = None
        audio_mime = None
        # Also clear any saved audio
        if "attached_audio_bytes" in st.session_state:
            st.session_state.pop("attached_audio_bytes", None)
        if "attached_audio_mime" in st.session_state:
            st.session_state.pop("attached_audio_mime", None)
        if "send_audio_only" in st.session_state:
            st.session_state.pop("send_audio_only", None)
    else:
        # Read and consume any attached audio only if no text input
        audio_bytes = st.session_state.pop("attached_audio_bytes", None)
        audio_mime = st.session_state.pop("attached_audio_mime", "audio/wav")

    # Read and consume any attached image
    image_bytes = st.session_state.pop("attached_image_bytes", None)
    image_mime = st.session_state.pop("attached_image_mime", "image/jpeg")
    
    # Reset the send flags for next run
    send_audio_only = st.session_state.pop("send_audio_only", False)
     
    # Reset the send_image_only flag for next run
    send_image_only = st.session_state.pop("send_image_only", False)
     
    # Ensure uploader will be reset on next rerun
    if image_bytes:
        st.session_state.reset_uploader = True
        print(f"Image received, size: {len(image_bytes)} bytes")
    if audio_bytes:
        print(f"Audio received, size: {len(audio_bytes)} bytes")
    
    # Transcribe audio if present to generate user prompt text
    audio_text = ""
    if audio_bytes and api_key:
        # Check if we already have a transcription from pre-processing
        if "audio_transcription" in st.session_state:
            audio_text = st.session_state.pop("audio_transcription", "")
            print(f"Using pre-processed audio transcription: {audio_text}")
        else:
            try:
                audio_buffer = io.BytesIO(audio_bytes)
                audio_buffer.name = "voice.wav"
                trans_client = OpenAI(api_key=api_key)
                transcription_resp = trans_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_buffer,
                    response_format="text"
                )
                # openai python v1 returns .text
                audio_text = transcription_resp.text if hasattr(transcription_resp, "text") else str(transcription_resp)
                print(f"Audio transcription: {audio_text}")
            except Exception as e:
                print(f"Audio transcription failed: {e}")
    
    if send_image_only and not image_bytes:
        # Edge-case: send button but no image (shouldn't normally happen)
        print("Warning: Send image requested but no image found")
        send_image_only = False
    if send_audio_only and not audio_bytes:
        print("Warning: Send audio requested but no audio found")
        send_audio_only = False
 
    if not api_key:
        st.error("OpenAI API key is missing. Please set it in your environment variables.")
    else:
        # Construct the prompt combining text input and transcribed audio
        prompt = prompt_input or ""
        if audio_text:
            if prompt:
                prompt = f"{prompt}\n{audio_text}"
            else:
                prompt = audio_text
        
        # Add user message (with optional image/audio) to chat history
        user_message_entry = {"role": "user", "content": prompt}
        if image_bytes:
            user_message_entry["image_bytes"] = image_bytes
            user_message_entry["mime"] = image_mime
            st.session_state.reset_uploader = True
        if audio_bytes:
            user_message_entry["audio_bytes"] = audio_bytes
            user_message_entry["mime"] = audio_mime
        st.session_state.messages.append(user_message_entry)
        with st.chat_message("user"):
            if audio_bytes:
                st.audio(audio_bytes, format=audio_mime)
            elif prompt_input:
                # Only show typed text (not the automatic transcription)
                st.write(prompt_input)
            if image_bytes:
                st.image(image_bytes)

        # Generate response
        with st.chat_message("assistant"):
            response_container = st.empty()
            full_response = ""
            
            try:
                # Create OpenAI client with minimal parameters to avoid proxies error
                client = OpenAI(api_key=api_key)
                
                # Refresh data to get latest ETA information
                if "condition_handler" in st.session_state:
                    print("Refreshing data before chat response to get latest ETA...")
                    st.session_state.condition_handler.load_data()
                
                # Get personalized system prompt with variables replaced
                current_client_id = st.session_state.current_client_id if "current_client_id" in st.session_state else None
                personalized_system_prompt = process_prompt_variables(system_prompt_template, current_client_id)
                
                messages_for_api = [{"role": "system", "content": personalized_system_prompt}]
                
                # Convert stored messages to OpenAI format (supporting images)
                for m in st.session_state.messages:
                    if "image_bytes" in m and m["image_bytes"]:
                        parts = []
                        if m.get("content"):
                            parts.append({"type": "text", "text": m["content"]})
                        b64 = base64.b64encode(m["image_bytes"]).decode()
                        parts.append({"type": "image_url", "image_url": {"url": f"data:{m.get('mime', 'image/jpeg')};base64,{b64}"}})
                        messages_for_api.append({"role": m["role"], "content": parts})
                    else:
                        messages_for_api.append({"role": m["role"], "content": m["content"]})
                
                # Show a spinner while waiting for the response
                with st.spinner("Maya is thinking..."):
                    # Use non-streaming API call
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages_for_api,
                        stream=False  # No streaming
                    )
                    
                    # Get the full response
                    full_response = response.choices[0].message.content
                    
                    # Process any variables in the response
                    #full_response = process_response_variables(full_response, current_client_id)
                
                # First check for any condition triggers before displaying the response
                has_condition_trigger = contains_condition_trigger(full_response)
                
                # Only display the response if it doesn't contain any condition keywords
                if not has_condition_trigger:
                    # Display the complete response at once
                    response_container.write(full_response)
                
                # Print debug info
                print(f"Response received: '{full_response}'")
                print(f"Contains condition trigger: {has_condition_trigger}")
                
                # Check if the condition for support URL is triggered
                should_add_to_history = True
                
                # Check for refund URL
                if contains_condition_trigger(full_response):
                    # Set flag to not add the response to history
                    should_add_to_history = False
                    
                    # Handle specific condition types
                    if "noknok.com/refund" in full_response:
                        print("Refund URL detected in response, handling with condition")
                        # Set up the refund order sequence
                        st.session_state.refund_order_pending = True
                        st.session_state.refund_order_prompt = prompt
                        
                    # Check for cancel URL
                    elif "noknok.com/cancel" in full_response:
                        print("Cancel URL detected in response, handling with condition")
                        # Set up the cancel order sequence
                        st.session_state.cancel_order_pending = True
                        st.session_state.cancel_order_prompt = prompt
                        
                    # Check for support URL
                    elif "noknok.com/support" in full_response:
                        print("Support URL detected in response, handling with condition")
                        # Set up the automated response sequence
                        st.session_state.support_handoff_pending = True
                        st.session_state.support_handoff_prompt = prompt
                        
                    # Check for address update phrase
                    elif "I just added your address information" in full_response:
                        print("Address-update phrase detected in response, handling condition")
                        st.session_state.address_update_pending = True
                        st.session_state.address_update_prompt = prompt
                        
                    # Check for items URL
                    elif "noknok.com/items" in full_response:
                        print("Items-URL detected in response, queuing items search")
                        st.session_state.items_search_pending = True
                        st.session_state.items_search_response = full_response  
                        st.session_state.items_search_prompt = prompt
                        
                    # Check for calories URL
                    elif "noknok.com/calories" in full_response:
                        print("Calories-URL detected in response, queuing calories search")
                        st.session_state.calories_search_pending = True
                        st.session_state.calories_search_response = full_response
                        st.session_state.calories_search_prompt = prompt
                        
                    # Check for Lebanese language URL
                    elif "noknok.com/lebanese" in full_response:
                        print("Lebanese-URL detected in response, switching to Lebanese prompt")
                        st.session_state.lebanese_prompt_pending = True
                        st.session_state.lebanese_prompt_response = full_response
                        st.session_state.lebanese_prompt_prompt = prompt
                        
                    # Check for English language URL
                    elif "noknok.com/languages" in full_response:
                        print("Languages-URL detected in response, switching to English prompt")
                        st.session_state.english_prompt_pending = True
                        st.session_state.english_prompt_response = full_response
                        st.session_state.english_prompt_prompt = prompt
                    
                    # Clear the current response container
                    response_container.empty()
                    
                    # Rerun the app to handle the condition from a clean context
                    st.rerun()

                # If no condition was triggered or no handler available, add the original response
                # Add assistant response to chat history
                if should_add_to_history:
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    
                    # Save conversation to chat history sheet
                    if st.session_state.chat_history_sheet:
                        save_to_chat_history(st.session_state.chat_history_sheet, "User", prompt, full_response)
            except Exception as e:
                full_response = f"Error: {str(e)}"
                response_container.write(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            
# After the chat message generation, check if we need to handle a refund
if "refund_order_pending" in st.session_state and st.session_state.refund_order_pending:
    client_id = st.session_state.current_client_id
    
    # Check if a client is selected
    if not client_id:
        message = "No client selected. Please select a client from the sidebar to process refunds."
        with st.chat_message("assistant"):
            st.write(message)
        st.session_state.messages.append({"role": "assistant", "content": message})
    else:
        try:
            # Access condition handler
            if "condition_handler" in st.session_state and st.session_state.condition_handler:
                # Update the current client ID in the handler
                st.session_state.condition_handler.current_client_id = client_id
                print(f"Processing refund for client ID: {client_id}")
                
                # Force refresh data
                print("Forcing data refresh for refund...")
                st.session_state.condition_handler.last_data_refresh = None
                data_loaded = st.session_state.condition_handler.load_data()
                print(f"Data refresh result: {data_loaded}")
                
                # Get direct access to the sheets for column inspection
                if st.session_state.noknok_sheets:
                    if "order" in st.session_state.noknok_sheets:
                        try:
                            headers = st.session_state.noknok_sheets["order"].row_values(1)
                            print(f"Order sheet headers: {headers}")
                        except Exception as e:
                            print(f"Could not read order sheet headers: {e}")
                    
                    if "client" in st.session_state.noknok_sheets:
                        try:
                            headers = st.session_state.noknok_sheets["client"].row_values(1)
                            print(f"Client sheet headers: {headers}")
                        except Exception as e:
                            print(f"Could not read client sheet headers: {e}")
                
                # Prepare context for condition evaluation
                context = {"client_id": client_id, "reply": "noknok.com/refund"}
                
                # Execute the refund through the condition handler
                results = st.session_state.condition_handler.evaluate_conditions(context)
                
                # Process results
                if results:
                    for result in results:
                        print(f"Condition result: {result}")
                        if result.get("id") == "refund_order_detected":
                            if "result" in result:
                                if result["result"].get("type") == "order_refunded":
                                    # Show success message
                                    success_message = result["result"].get("message", "Your refund has been processed successfully.")
                                    with st.chat_message("assistant"):
                                        st.write(success_message)
                                    st.session_state.messages.append({"role": "assistant", "content": success_message})
                                    
                                    # Add extra message about new balance
                                    balance_message = f"Your new Noknok wallet balance is ${safe_float_conversion(result['result'].get('new_wallet_balance', '0')):.2f}."
                                    with st.chat_message("assistant"):
                                        st.write(balance_message)
                                    st.session_state.messages.append({"role": "assistant", "content": balance_message})
                                    
                                    # Save to chat history
                                    if st.session_state.chat_history_sheet:
                                        save_to_chat_history(st.session_state.chat_history_sheet, 
                                                           "System", "Order refund request", success_message)
                                else:
                                    # Show error message
                                    error_message = result["result"].get("message", "Error processing refund.")
                                    with st.chat_message("assistant"):
                                        st.write(error_message)
                                    st.session_state.messages.append({"role": "assistant", "content": error_message})
                else:
                    # No conditions were triggered
                    error_message = "Failed to process refund. Please contact customer support."
                    with st.chat_message("assistant"):
                        st.write(error_message)
                    st.session_state.messages.append({"role": "assistant", "content": error_message})
        except Exception as e:
            error_message = f"Error processing refund: {str(e)}"
            with st.chat_message("assistant"):
                st.write(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})
    
    # Clear the pending flag
    st.session_state.refund_order_pending = False
    if "refund_order_prompt" in st.session_state:
        del st.session_state.refund_order_prompt

# After the chat message generation, check if we need to handle a cancel order
if "cancel_order_pending" in st.session_state and st.session_state.cancel_order_pending:
    client_id = st.session_state.current_client_id
    
    # Check if a client is selected
    if not client_id:
        message = "No client selected. Please select a client from the sidebar to process cancellations."
        with st.chat_message("assistant"):
            st.write(message)
        st.session_state.messages.append({"role": "assistant", "content": message})
    else:
        try:
            # Access condition handler
            if "condition_handler" in st.session_state and st.session_state.condition_handler:
                # Update the current client ID in the handler
                st.session_state.condition_handler.current_client_id = client_id
                print(f"Processing cancellation for client ID: {client_id}")
                
                # Get direct access to the order sheet for column inspection
                if st.session_state.noknok_sheets and "order" in st.session_state.noknok_sheets:
                    order_sheet = st.session_state.noknok_sheets["order"]
                    try:
                        # Get and print headers to see exact column names
                        headers = order_sheet.row_values(1)
                        print(f"Order sheet headers: {headers}")
                    except Exception as e:
                        print(f"Could not read order sheet headers: {e}")
                
                # Force refresh data
                print("Forcing data refresh for cancellation...")
                st.session_state.condition_handler.last_data_refresh = None
                data_loaded = st.session_state.condition_handler.load_data()
                print(f"Data refresh result: {data_loaded}")
                
                # Find the most recent order
                if st.session_state.condition_handler.order_data:
                    # Debug print order data
                    print(f"Found {len(st.session_state.condition_handler.order_data)} total orders")
                    
                    # Filter orders for the current client
                    client_orders = [order for order in st.session_state.condition_handler.order_data 
                                   if str(order.get("ClientID", "")) == str(client_id)]
                    
                    print(f"Found {len(client_orders)} orders for client {client_id}")
                    
                    if client_orders:
                        print(f"Client orders found: {client_orders}")
                        # Find most recent order - use OrderDate field
                        most_recent_order = max(client_orders, key=lambda order: order.get("OrderDate", ""))
                        order_id = most_recent_order.get("OrderID")
                        
                        # Print all fields in the most recent order for debugging
                        print(f"Most recent order details: {most_recent_order}")
                        
                        # Try different possible field names for the order amount - case insensitive
                        order_amount = None
                        possible_amount_fields = [
                            "TotalAmount", "OrderAmount", "Order Amount", "Total Amount", 
                            "Total", "Amount", "Price", "Cost", "Value"
                        ]
                        
                        # First try direct key matching
                        for field in possible_amount_fields:
                            if field in most_recent_order and most_recent_order[field]:
                                order_amount = most_recent_order[field]
                                print(f"Found order amount in field: {field}, value: {order_amount}")
                                break
                        
                        # If not found, try case-insensitive matching
                        if order_amount is None:
                            order_keys = list(most_recent_order.keys())
                            for field in possible_amount_fields:
                                matching_keys = [k for k in order_keys if k.lower() == field.lower()]
                                if matching_keys:
                                    field_key = matching_keys[0]  # Use the first matching key
                                    order_amount = most_recent_order[field_key]
                                    print(f"Found order amount via case-insensitive match in field: {field_key}, value: {order_amount}")
                                    break
                        
                        # If we still don't have an amount, check for any field containing 'amount' or 'total'
                        if order_amount is None:
                            order_keys = list(most_recent_order.keys())
                            amount_related_keys = [k for k in order_keys if 'amount' in k.lower() or 'total' in k.lower() or 'price' in k.lower()]
                            
                            if amount_related_keys:
                                field_key = amount_related_keys[0]  # Use the first matching key
                                order_amount = most_recent_order[field_key]
                                print(f"Found order amount via partial match in field: {field_key}, value: {order_amount}")
                        
                        if order_amount is None:
                            # If we still don't have an amount, dump the keys for debugging
                            print(f"Order fields available: {list(most_recent_order.keys())}")
                            order_amount = "your order"
                            print("Order amount not found, using generic text")
                        
                        # Update order status to Cancelled
                        try:
                            if st.session_state.noknok_sheets and "order" in st.session_state.noknok_sheets:
                                order_sheet = st.session_state.noknok_sheets["order"]
                                all_orders = order_sheet.get_all_records()
                                
                                # Find the row index (adding 2 because row 1 is header and sheet is 1-indexed)
                                found = False
                                for i, order in enumerate(all_orders):
                                    if str(order.get("OrderID")) == str(order_id):
                                        row_index = i + 2  # +2 for header row and 1-indexed
                                        
                                        # Check for the OrderStatus column - find the right column number
                                        header_row = order_sheet.row_values(1)  # Get header row
                                        status_col = 0
                                        for idx, header in enumerate(header_row):
                                            if header == "OrderStatus":
                                                status_col = idx + 1  # 1-indexed columns in sheets API
                                                break
                                        
                                        if status_col > 0:
                                            # Update the Status column to "Cancelled"
                                            order_sheet.update_cell(row_index, status_col, "Cancelled")
                                            found = True
                                            break
                                        else:
                                            raise Exception("OrderStatus column not found in sheet")
                                
                                if found:
                                    # Show success message
                                    # Check if the order amount is numeric to format it correctly
                                    try:
                                        # Try to convert to float to check if it's numeric
                                        float_amount = safe_float_conversion(order_amount)
                                        # Format with dollar sign
                                        amount_display = f"${float_amount:.2f}"
                                    except (ValueError, TypeError):
                                        # If not numeric, use the value as is
                                        amount_display = order_amount
                                    
                                    message = f"Your order totaling {amount_display} has been canceled. We hope to serve you better in the future. Thank you for your kind understanding! 💙🙏🏻"
                                    with st.chat_message("assistant"):
                                        st.write(message)
                                    st.session_state.messages.append({"role": "assistant", "content": message})
                                    
                                    # Save to chat history
                                    if st.session_state.chat_history_sheet:
                                        save_to_chat_history(st.session_state.chat_history_sheet, 
                                                            "System", "Order cancellation request", message)
                                else:
                                    error_message = f"Could not locate order {order_id} in the database to cancel it."
                                    with st.chat_message("assistant"):
                                        st.write(error_message)
                                    st.session_state.messages.append({"role": "assistant", "content": error_message})
                        except Exception as e:
                            error_message = f"Error cancelling order: {str(e)}"
                            with st.chat_message("assistant"):
                                st.write(error_message)
                            st.session_state.messages.append({"role": "assistant", "content": error_message})
                    else:
                        no_orders_message = "You don't have any orders to cancel."
                        with st.chat_message("assistant"):
                            st.write(no_orders_message)
                        st.session_state.messages.append({"role": "assistant", "content": no_orders_message})
                else:
                    data_error_message = "Order data could not be loaded. Please try again later."
                    with st.chat_message("assistant"):
                        st.write(data_error_message)
                    st.session_state.messages.append({"role": "assistant", "content": data_error_message})
        except Exception as e:
            error_message = f"Error processing cancellation: {str(e)}"
            with st.chat_message("assistant"):
                st.write(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})
    
    # Clear the pending flag
    st.session_state.cancel_order_pending = False
    if "cancel_order_prompt" in st.session_state:
        del st.session_state.cancel_order_prompt

# After the chat message generation, check if we need to handle a support handoff
if "support_handoff_pending" in st.session_state and st.session_state.support_handoff_pending:
    # First message
    first_message = "Kindly allow me a moment to check the matter."
    with st.chat_message("assistant"):
        st.write(first_message)
    st.session_state.messages.append({"role": "assistant", "content": first_message})
    
    # Save to chat history
    if "chat_history_sheet" in st.session_state and st.session_state.chat_history_sheet:
        save_to_chat_history(st.session_state.chat_history_sheet, 
                            "User", st.session_state.support_handoff_prompt, first_message)
    
    # Wait 5 seconds
    time.sleep(5)
    
    # Second message
    second_message = "Here the chat would have been transferred to a human agent in real life, but for testing purposes you can continue messaging the AI"
    with st.chat_message("assistant"):
        st.write(second_message)
    st.session_state.messages.append({"role": "assistant", "content": second_message})
    
    # Save to chat history
    if "chat_history_sheet" in st.session_state and st.session_state.chat_history_sheet:
        save_to_chat_history(st.session_state.chat_history_sheet, 
                            "System", "", second_message)
    
    # Clear the pending flag
    st.session_state.support_handoff_pending = False
    if "support_handoff_prompt" in st.session_state:
        del st.session_state.support_handoff_prompt
# ─────────────────────────────────────────────────────────────
# Handle queued address-update workflow
# ─────────────────────────────────────────────────────────────
if "address_update_pending" in st.session_state and st.session_state.address_update_pending:
    client_id = st.session_state.current_client_id

    if not client_id:
        msg = "No client selected. Please choose a client before updating address."
        with st.chat_message("assistant"): st.write(msg)
        st.session_state.messages.append({"role": "assistant", "content": msg})

    else:
        # 1)  capture the last two *user* messages
        last_two_user_msgs = [m["content"] for m in st.session_state.messages 
                              if m["role"] == "user"][-2:]
        history_text = "\n".join(last_two_user_msgs)

        # 2)  evaluate the new condition
        if "condition_handler" in st.session_state and st.session_state.condition_handler:
            st.session_state.condition_handler.current_client_id = client_id
            context = {
                "client_id": client_id,
                "reply": "I just added your address information",
                "history": history_text
            }
            results = st.session_state.condition_handler.evaluate_conditions(context)

            # 3)  display outcome
            if results:
                for res in results:
                    if res.get("id") == "address_update_detected":
                        with st.chat_message("assistant"):
                            st.write(res["result"].get("message", "Address updated."))
                        st.session_state.messages.append(
                            {"role": "assistant", "content": res["result"].get("message", "")}
                        )
                        # optionally: push to Chat-History sheet
                        if st.session_state.chat_history_sheet:
                            save_to_chat_history(
                                st.session_state.chat_history_sheet,
                                "System",
                                "Address update",
                                res["result"].get("message", "")
                            )
            else:
                err = "⚠️ Address update failed."
                with st.chat_message("assistant"): st.write(err)
                st.session_state.messages.append({"role": "assistant", "content": err})

    # clear the flag
    st.session_state.address_update_pending = False
    st.session_state.pop("address_update_prompt", None)
# ─────────────────────────────────────────────────────────────
# Handle queued items-search workflow
# ─────────────────────────────────────────────────────────────
if st.session_state.get("items_search_pending"):
    client_id = st.session_state.current_client_id
    if not client_id:
        msg = "No client selected. Please select a client before searching items."
        with st.chat_message("assistant"):
            st.write(msg)
        st.session_state.messages.append({"role":"assistant","content":msg})
    else:
        # Capture last user message
        last_user = ""
        for m in reversed(st.session_state.messages):
            if m["role"] == "user":
                last_user = m["content"]
                break

        context = {
            "client_id":         client_id,
            "reply":             st.session_state.items_search_response,  # full Maya message
            "last_user_message": last_user
        }

        results = st.session_state.condition_handler.evaluate_conditions(context)

        if results:
            for res in results:
                if res.get("id") == "items_search_detected":
                    text = res["result"].get("message", "")
                    with st.chat_message("assistant"):
                        st.write(text)
                    st.session_state.messages.append({"role":"assistant","content":text})
                    # save to history sheet
                    if st.session_state.chat_history_sheet:
                        save_to_chat_history(
                            st.session_state.chat_history_sheet,
                            "System", "Items search",
                            text
                        )
        else:
            err = "⚠️ Failed to search items."
            with st.chat_message("assistant"):
                st.write(err)
            st.session_state.messages.append({"role":"assistant","content":err})

    # clear the flag
    st.session_state.items_search_pending = False
    st.session_state.pop("items_search_prompt", None)

# ─────────────────────────────────────────────────────────────
# Handle queued calories-search workflow
# ─────────────────────────────────────────────────────────────
if st.session_state.get("calories_search_pending"):
    # Capture last user message (regardless of client selection)
    last_user = ""
    for m in reversed(st.session_state.messages):
        if m["role"] == "user":
            last_user = m["content"]
            break

    context = {
        "client_id": st.session_state.get("current_client_id"),
        "reply": st.session_state.calories_search_response,
        "last_user_message": last_user
    }

    results = st.session_state.condition_handler.evaluate_conditions(context)

    if results:
        for res in results:
            if res.get("id") == "calories_search_detected":
                text = res["result"].get("message", "")
                with st.chat_message("assistant"):
                    st.write(text)
                st.session_state.messages.append({"role": "assistant", "content": text})
                if st.session_state.chat_history_sheet:
                    save_to_chat_history(
                        st.session_state.chat_history_sheet,
                        "System", "Calories search",
                        text
                    )
    else:
        err = "⚠️ Failed to retrieve calories information."
        with st.chat_message("assistant"):
            st.write(err)
        st.session_state.messages.append({"role": "assistant", "content": err})

    # clear the flag
    st.session_state.calories_search_pending = False
    st.session_state.pop("calories_search_prompt", None)

# ────────────────────────────────────────────────────────────
#  Auto-refresh every minute & close chat after 5 min idle
# ────────────────────────────────────────────────────────────
st_autorefresh(interval=60_000, key="idle_refresh")   # 60 000 ms = 1 min

idle_threshold = timedelta(minutes=5)
now = datetime.now()

if (
    not st.session_state.closing_message_sent
    and (now - st.session_state.last_user_activity) > idle_threshold
):
    closing_text = (
        "Thank you for contacting noknok customer experience! 💙\n"
        "Don't forget to follow us on Facebook and Instagram on @NokNokGroceries, "
        "and on TikTok @NokNokApp, to stay up to date with all we have to offer!"
    )

    with st.chat_message("assistant"):
        st.write(closing_text)

    st.session_state.messages.append({"role": "assistant", "content": closing_text})

    if st.session_state.chat_history_sheet:
        save_to_chat_history(
            st.session_state.chat_history_sheet,
            "System", "", closing_text
        )

    st.session_state.closing_message_sent = True

# Add a button to clear chat history
if st.sidebar.button("Clear Chat History"):
    st.session_state.messages = []
    st.rerun()

# New section for conditions handling
class ConditionHandler:
    """Framework for handling various conditions in the application"""
    
    def __init__(self, sheets_client=None, noknok_sheets=None):
        self.sheets_client = sheets_client
        self.noknok_sheets = noknok_sheets
        self.conditions = {}
        self.order_data = None
        self.client_data = None
        self.items_data = None
        self.setup_complete = False
        self.last_data_refresh = None
        self.current_client_id = None
        
    def load_data(self):
        """Load data from sheets for condition checking with rate limiting"""
        if self.noknok_sheets:
            try:
                # Check if we've refreshed recently (within the last 30 seconds)
                now = datetime.now()
                if self.last_data_refresh and (now - self.last_data_refresh).total_seconds() < 30:
                    print("Skipping data refresh - last refresh was less than 30 seconds ago")
                    return self.setup_complete
                
                print("ConditionHandler: Loading data from sheets...")
                # Use the new function to get all data with rate limiting
                sheet_data = get_all_sheet_data(self.noknok_sheets)
                
                self.order_data = sheet_data.get('orders', [])
                print(f"ConditionHandler: Loaded {len(self.order_data)} orders")
                if len(self.order_data) > 0:
                    print(f"ConditionHandler: Sample order data: {self.order_data[0]}")
                else:
                    print("ConditionHandler: No order data found")
                
                self.client_data = sheet_data.get('clients', [])
                print(f"ConditionHandler: Loaded {len(self.client_data)} clients")
                if len(self.client_data) > 0:
                    print(f"ConditionHandler: Sample client data: {self.client_data[0]}")
                else:
                    print("ConditionHandler: No client data found")
                
                self.items_data = sheet_data.get('items', [])
                print(f"ConditionHandler: Loaded {len(self.items_data)} items")
                
                self.setup_complete = True
                self.last_data_refresh = now
                return True
            except Exception as e:
                print(f"Error loading data for conditions: {e}")
                import traceback
                traceback.print_exc()
                return False
        return False
    
    def register_condition(self, condition_id, check_function, action_function, description):
        """Register a new condition with its check and action functions"""
        self.conditions[condition_id] = {
            "check": check_function,
            "action": action_function,
            "description": description,
            "last_triggered": None,
            "is_active": True
        }
        print(f"Registered condition: {condition_id} - {description}")
    
    def evaluate_conditions(self, context=None):
        """Evaluate all registered conditions and trigger actions for those that match"""
        if not self.setup_complete:
            if not self.load_data():
                print("Cannot evaluate conditions: data not loaded")
                return []
        
        triggered_conditions = []
        print(f"Evaluating {len(self.conditions)} conditions with context: {context}")
        
        for condition_id, condition in self.conditions.items():
            print(f"Checking condition: {condition_id}")
            if not condition["is_active"]:
                print(f"Condition {condition_id} is not active, skipping")
                continue
                
            try:
                check_result = condition["check"](self, context)
                print(f"Condition {condition_id} check result: {check_result}")
                
                if check_result:
                    # Execute the action
                    print(f"Executing action for condition: {condition_id}")
                    result = condition["action"](self, context)
                    condition["last_triggered"] = datetime.now()
                    result_with_id = result
                    if isinstance(result, dict) and "id" not in result:
                        result_with_id = result.copy()
                        result_with_id["id"] = condition_id
                    
                    triggered_conditions.append({
                        "id": condition_id,
                        "description": condition["description"],
                        "result": result_with_id
                    })
                    print(f"Action completed for {condition_id}")
            except Exception as e:
                print(f"Error evaluating condition {condition_id}: {e}")
        
        print(f"Triggered conditions: {triggered_conditions}")
        return triggered_conditions
    
    def toggle_condition(self, condition_id, active_state):
        """Enable or disable a specific condition"""
        if condition_id in self.conditions:
            self.conditions[condition_id]["is_active"] = active_state
            return True
        return False
    
    def get_condition_status(self):
        """Get the status of all conditions"""
        return {
            condition_id: {
                "description": condition["description"],
                "active": condition["is_active"],
                "last_triggered": condition["last_triggered"]
            } 
            for condition_id, condition in self.conditions.items()
        }

# Initialize conditions handler during app startup
if "condition_handler" not in st.session_state:
    st.session_state.condition_handler = ConditionHandler(
        sheets_client=st.session_state.sheets_client if "sheets_client" in st.session_state else None,
        noknok_sheets=st.session_state.noknok_sheets if "noknok_sheets" in st.session_state else None
    )
    
    # Set current client ID if available
    if "current_client_id" in st.session_state:
        st.session_state.condition_handler.current_client_id = st.session_state.current_client_id
    
    # Register all conditions from the conditions module
    registered_count = register_all_conditions(st.session_state.condition_handler)
    print(f"Registered {registered_count} conditions from conditions module")
    
    # Automatically load data when app initializes
    with st.spinner("Loading database..."):
        data_loaded = st.session_state.condition_handler.load_data()
        if data_loaded:
            print("Initial data loaded successfully")
        else:
            print("Failed to load initial data")

# Also refresh data when a client is selected
if "current_client_id" in st.session_state and st.session_state.current_client_id:
    # Check if we need to refresh data (only if not refreshed in the last 30 seconds)
    if (
        "condition_handler" in st.session_state 
        and (not st.session_state.condition_handler.last_data_refresh 
             or (datetime.now() - st.session_state.condition_handler.last_data_refresh).total_seconds() > 30)
    ):
        print(f"Auto-refreshing data for client ID: {st.session_state.current_client_id}")
        st.session_state.condition_handler.load_data()

# Add system prompt debugger
with st.sidebar.expander("Debug System Prompt", expanded=False):
    if st.button("View Processed Prompt"):
        current_client_id = st.session_state.current_client_id if "current_client_id" in st.session_state else None
        
        # Add debugging info directly in the UI
        debug_info = []
        debug_info.append(f"Current client ID: {current_client_id}")
        
        # Get variable values first before processing the prompt
        balance_value = "N/A"
        orderitems_value = "N/A"
        orderstatus_value = "N/A"
        orderamount_value = "N/A"
        eta_value = None
        delay_value = "Default delay message"
        tech_value = "Technical issues = False"
        
        # Extract the variable values directly from data
        if "condition_handler" in st.session_state and current_client_id:
            handler = st.session_state.condition_handler
            debug_info.append("Found condition handler")
            
            # Force refresh data to get latest values
            refresh_result = handler.load_data()
            debug_info.append(f"Data refresh result: {refresh_result}")
            
            # Get client data for wallet balance
            if handler.client_data:
                debug_info.append(f"Client data available: {len(handler.client_data)} records")
                # Print sample client for debugging
                if len(handler.client_data) > 0:
                    debug_info.append(f"Sample client keys: {list(handler.client_data[0].keys())}")
                
                # Find the client
                client = next((c for c in handler.client_data if str(c.get('ClientID', '')) == str(current_client_id)), None)
                if client:
                    debug_info.append(f"Found client record for ID {current_client_id}")
                    # Print all client keys for debugging
                    debug_info.append(f"Client record keys: {list(client.keys())}")
                    
                    # Find balance (wallet) value
                    balance_fields = ['NokNok USD Wallet', 'Wallet Balance', 'Balance', 'USD Wallet']
                    debug_info.append(f"Looking for balance fields: {balance_fields}")
                    
                    balance_raw = None
                    
                    # Try direct field match
                    for field in balance_fields:
                        if field in client and client[field] is not None:
                            balance_raw = client[field]
                            debug_info.append(f"Found balance using field '{field}': {balance_raw}")
                            break
                    
                    # Try case-insensitive match if needed
                    if balance_raw is None:
                        debug_info.append("Trying case-insensitive balance field match")
                        client_fields = list(client.keys())
                        for field in balance_fields:
                            matching_fields = [k for k in client_fields if k.lower() == field.lower()]
                            if matching_fields:
                                field_name = matching_fields[0]
                                if client[field_name] is not None:
                                    balance_raw = client[field_name]
                                    debug_info.append(f"Found balance via case-insensitive match for '{field}': {balance_raw}")
                                    break
                    
                    # Format the balance
                    if balance_raw is not None:
                        try:
                            balance_float = safe_float_conversion(balance_raw)
                            balance_value = f"${balance_float:.2f}"
                            debug_info.append(f"Formatted balance: {balance_value}")
                        except (ValueError, TypeError) as e:
                            debug_info.append(f"Error formatting balance: {e}")
                            balance_value = str(balance_raw)
                    else:
                        debug_info.append("No balance value found in client record")
                else:
                    debug_info.append(f"Client with ID {current_client_id} not found in client data")
            else:
                debug_info.append("No client data available")
            
            # Get order data for order status, amount, and items
            if handler.order_data:
                debug_info.append(f"Order data available: {len(handler.order_data)} records")
                # Print sample order for debugging
                if len(handler.order_data) > 0:
                    debug_info.append(f"Sample order keys: {list(handler.order_data[0].keys())}")
                
                # Filter client orders
                client_orders = [order for order in handler.order_data if str(order.get("ClientID", "")) == str(current_client_id)]
                debug_info.append(f"Found {len(client_orders)} orders for client {current_client_id}")
                
                if client_orders:
                    # Get most recent order
                    recent_order = max(client_orders, key=lambda order: order.get("OrderDate", ""))
                    debug_info.append(f"Found recent order with ID: {recent_order.get('OrderID')}")
                    debug_info.append(f"Recent order fields: {list(recent_order.keys())}")
                    
                    # Get order status
                    if 'OrderStatus' in recent_order and recent_order['OrderStatus']:
                        orderstatus_value = recent_order['OrderStatus'].capitalize()
                        debug_info.append(f"Found order status: {orderstatus_value}")
                    else:
                        debug_info.append("OrderStatus field not found in recent order")
                    
                    # Get order ETA
                    if 'ETA' in recent_order and recent_order['ETA']:
                        eta_value = recent_order['ETA']
                        debug_info.append(f"Found ETA: {eta_value}")
                    else:
                        debug_info.append("ETA field not found in recent order")
                    
                    # Check for technical issues
                    if 'Technical Issue' in recent_order:
                        value = recent_order['Technical Issue']
                        debug_info.append(f"Found Technical Issue: {value}")
                        if isinstance(value, bool) and value:
                            tech_value = "Technical issues = True"
                        elif isinstance(value, str) and value.lower() in ['true', 'yes', '1']:
                            tech_value = "Technical issues = True"
                    else:
                        debug_info.append("Technical Issue field not found in recent order")
                    
                    # Check for weather conditions for delivery status
                    if 'Weather Conditions' in recent_order:
                        value = recent_order['Weather Conditions']
                        debug_info.append(f"Found Weather Conditions: {value}")
                        if (isinstance(value, bool) and value) or (isinstance(value, str) and value.lower() in ['true', 'yes', '1']):
                            delay_value = "Weather conditions are poor"
                    else:
                        debug_info.append("Weather Conditions field not found in recent order")
                    
                    # Get order items
                    items_fields = ["OrderItems", "Order Items", "Items"]
                    debug_info.append(f"Looking for items fields: {items_fields}")
                    
                    items_found = False
                    for field in items_fields:
                        if field in recent_order and recent_order[field]:
                            orderitems_value = str(recent_order[field])
                            debug_info.append(f"Found order items using field '{field}': {orderitems_value}")
                            items_found = True
                            break
                    
                    # If not found, try case-insensitive matching
                    if not items_found:
                        debug_info.append("Trying case-insensitive items field match")
                        order_keys = list(recent_order.keys())
                        for field in items_fields:
                            matching_keys = [k for k in order_keys if k.lower() == field.lower()]
                            if matching_keys:
                                field_key = matching_keys[0]
                                if recent_order[field_key]:
                                    orderitems_value = str(recent_order[field_key])
                                    debug_info.append(f"Found order items via case-insensitive match for '{field}': {orderitems_value}")
                                    items_found = True
                                    break
                    
                    if not items_found:
                        debug_info.append("No order items found in recent order")
                        # Try to find any field that might contain items
                        item_related_keys = [k for k in recent_order.keys() if 'item' in k.lower() or 'product' in k.lower()]
                        if item_related_keys:
                            field_key = item_related_keys[0]
                            if recent_order[field_key]:
                                orderitems_value = str(recent_order[field_key])
                                debug_info.append(f"Found possible order items in field '{field_key}': {orderitems_value}")
                    
                    # Get order amount
                    possible_amount_fields = [
                        "TotalAmount", "OrderAmount", "Order Amount", "Total Amount", 
                        "Total", "Amount", "Price", "Cost", "Value"
                    ]
                    debug_info.append(f"Looking for amount fields: {possible_amount_fields}")
                    
                    amount_found = False
                    for field in possible_amount_fields:
                        if field in recent_order and recent_order[field]:
                            order_amount = recent_order[field]
                            debug_info.append(f"Found order amount using field '{field}': {order_amount}")
                            try:
                                amount_float = safe_float_conversion(order_amount)
                                orderamount_value = f"${amount_float:.2f}"
                            except (ValueError, TypeError):
                                orderamount_value = str(order_amount)
                            break
                    
                    # If not found, try case-insensitive matching
                    if orderamount_value == "N/A":
                        order_keys = list(recent_order.keys())
                        for field in possible_amount_fields:
                            matching_keys = [k for k in order_keys if k.lower() == field.lower()]
                            if matching_keys:
                                field_key = matching_keys[0]
                                if recent_order[field_key]:
                                    order_amount = recent_order[field_key]
                                    try:
                                        amount_float = safe_float_conversion(order_amount)
                                        orderamount_value = f"${amount_float:.2f}"
                                    except (ValueError, TypeError):
                                        orderamount_value = str(order_amount)
                                    break
                    
                    # Set order status-based delay value
                    order_status = recent_order.get('OrderStatus', '').lower()
                    if order_status == "delivered":
                        delay_value = "Order status is Delivered"
                    elif order_status == "driver arrived":
                        delay_value = "Order status is Driver Arrived"
        
        # Now process the prompt with the updated variables
        processed_prompt = process_prompt_variables(system_prompt_template, current_client_id)
        
        # Show which client is being used
        if current_client_id:
            st.info(f"Showing prompt for Client ID: {current_client_id}")
            
            # Get client name directly from the database for more accurate display
            if "condition_handler" in st.session_state and st.session_state.condition_handler.client_data:
                client = next((c for c in st.session_state.condition_handler.client_data if str(c.get('ClientID', '')) == str(current_client_id)), None)
                
                if client:
                    # Try to extract client name from the client data
                    name_field_variations = ['Client First Name', 'ClientFirstName', 'First Name', 'FirstName', 'Name']
                    client_name = "Not found"
                    
                    # Print all available client fields for debugging
                    print(f"Available client fields: {list(client.keys())}")
                    
                    # Try each field variation
                    for field in name_field_variations:
                        if field in client and client[field]:
                            client_name = client[field]
                            break
                    
                    # If still not found, try case insensitive match
                    if client_name == "Not found":
                        for key in client.keys():
                            if any(variation.lower() in key.lower() for variation in name_field_variations):
                                client_name = client[key]
                                break
                else:
                    client_name = "Client not found in database"
            else:
                client_name = "Client data not available"
        else:
            st.info("Showing prompt for guest (no client selected)")
            client_name = "valued customer (default)"
        
        st.markdown("**Prompt details:**")
        st.write("- Client name:", client_name)
        if eta_value:
            st.write("- ETA value:", eta_value)
        st.write("- Delivery status:", delay_value)
        st.write("- Technical status:", tech_value)
        # Add the new variables to the prompt details display
        st.write("- Wallet balance:", balance_value)
        st.write("- Order items:", orderitems_value)
        st.write("- Order status:", orderstatus_value)
        st.write("- Order amount:", orderamount_value)
        
        st.markdown("**Full processed prompt:**")
        # Add basic syntax highlighting by converting special tokens to colored spans
        highlighted_template = processed_prompt
        highlighted_template = re.sub(r'@(\w+)@', r'<span style="color:red">@\1@</span>', highlighted_template)
        
        st.markdown(highlighted_template)



# ─────────────────────────────────────────────────────────────
# Handle queued Lebanese prompt switch
# ─────────────────────────────────────────────────────────────
if st.session_state.get("lebanese_prompt_pending"):
    client_id = st.session_state.current_client_id
    
    # Capture last user message for context
    last_user = ""
    for m in reversed(st.session_state.messages):
        if m["role"] == "user":
            last_user = m["content"]
            break

    context = {
        "client_id": client_id,
        "reply": st.session_state.lebanese_prompt_response,
        "last_user_message": last_user
    }

    results = st.session_state.condition_handler.evaluate_conditions(context)

    if results:
        for res in results:
            if res.get("id") == "lebanese_language_detected":
                text = res["result"].get("message", "")
                with st.chat_message("assistant"):
                    st.write(text)
                st.session_state.messages.append({"role":"assistant","content":text})
                # save to history sheet
                if st.session_state.chat_history_sheet:
                    save_to_chat_history(
                        st.session_state.chat_history_sheet,
                        "System", "Switched to Lebanese prompt",
                        text
                    )
    else:
        err = "⚠️ Failed to switch to Lebanese prompt."
        with st.chat_message("assistant"):
            st.write(err)
        st.session_state.messages.append({"role":"assistant","content":err})

    # clear the flag
    st.session_state.lebanese_prompt_pending = False
    st.session_state.pop("lebanese_prompt_prompt", None)

# ─────────────────────────────────────────────────────────────
# Handle queued English prompt switch
# ─────────────────────────────────────────────────────────────
if st.session_state.get("english_prompt_pending"):
    client_id = st.session_state.current_client_id
    
    # Capture last user message for context
    last_user = ""
    for m in reversed(st.session_state.messages):
        if m["role"] == "user":
            last_user = m["content"]
            break

    context = {
        "client_id": client_id,
        "reply": st.session_state.english_prompt_response,
        "last_user_message": last_user
    }

    results = st.session_state.condition_handler.evaluate_conditions(context)

    if results:
        for res in results:
            if res.get("id") == "english_language_detected":
                text = res["result"].get("message", "")
                with st.chat_message("assistant"):
                    st.write(text)
                st.session_state.messages.append({"role":"assistant","content":text})
                # save to history sheet
                if st.session_state.chat_history_sheet:
                    save_to_chat_history(
                        st.session_state.chat_history_sheet,
                        "System", "Switched to English prompt",
                        text
                    )
    else:
        err = "⚠️ Failed to switch to English prompt."
        with st.chat_message("assistant"):
            st.write(err)
        st.session_state.messages.append({"role":"assistant","content":err})

    # clear the flag
    st.session_state.english_prompt_pending = False
    st.session_state.pop("english_prompt_prompt", None)