import streamlit as st
import os
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from openai import OpenAI
import time
import threading
import re
# Import our conditions module
from conditions import register_all_conditions
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import base64

# Load environment variables
load_dotenv()

# Set up OpenAI API key
#api_key = st.secrets["OPENAI_API_KEY"]
api_key = st.secrets["OPENAI_API_KEY"]

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

# Initialize system prompt directly from prompt.txt
try:
    with open('prompt.txt', 'r', encoding='utf-8') as file:
        system_prompt_template = file.read()
        print(f"Successfully loaded prompt.txt with {len(system_prompt_template)} characters")
        if len(system_prompt_template) == 0:
            raise ValueError("Empty system prompt file")
except Exception as e:
    print(f"Error loading prompt.txt: {e}")
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

# Function to replace prompt variables
def process_prompt_variables(prompt_template, client_id=None):
    """Replace variables in prompt template with actual values based on client data and conditions"""
    # Initialize variables with default values
    client_name = "valued customer"
    eta_message = "noknok is committed to delivering your order within the advised estimated time of delivery mentioned upon placing the order. The average delivery time is 15 mins."
    order_delay_message = "Your order has been delayed due to an unusual rush at the branch. We apologize for the inconvenience caused and thank you for your patience and understanding. 🙏"
    technical_message = "Everything seems to be working on our end. I'll connect you to our tech team right away so they can assist you further."
    order_eta_message = "noknok is committed to delivering your order within the advised estimated time of delivery mentioned upon placing the order. The average delivery time is 15 mins."
    eta_value = None
    
    try:
        if "condition_handler" in st.session_state and st.session_state.condition_handler:
            handler = st.session_state.condition_handler
            
            # Get client data for @clientName@
            if client_id and handler.client_data:
                client = next((c for c in handler.client_data if str(c.get('ClientID')) == str(client_id)), None)
                if client:
                    # Try to get client first name with exact field matching
                    if 'Client First Name' in client and client['Client First Name']:
                        client_name = client['Client First Name']
                        print(f"Found client name: {client_name}")
            
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
                        eta_message = f"You can expect to receive your order by {eta_value}."
                    else:
                        eta_message = "noknok is committed to delivering your order within the advised estimated time of delivery mentioned upon placing the order. The average delivery time is 15 mins."
                    
                    # @OrderETA@ - Similar to @ETA@ but with different wording
                    if is_ongoing and eta_value:
                        order_eta_message = f"You can expect to receive your order by {eta_value}."
                    else:
                        order_eta_message = "noknok is committed to delivering your order within the advised estimated time of delivery mentioned upon placing the order. The average delivery time is 15 mins."
                    
                    # @OrderDelay@ - EXACTLY according to specification
                    if order_status == "delivered":
                        order_delay_message = "It appears that the order was delivered. Could you please double-check? It's possible the driver may have handed it to someone else by mistake. Let me know what you find and we'll sort it out right away. 💙"
                    elif order_status == "driver arrived":
                        order_delay_message = "The driver has arrived. Could you kindly check?"
                    elif weather_conditions:
                        order_delay_message = "Unfortunately, we are facing some difficulty in delivering your order due to the poor weather conditions. We appreciate your patience until our drivers are able to reach your location successfully. Thank you for choosing noknok! 💙🙏🏻"
                    else:
                        # Default case
                        if eta_value:
                            order_delay_message = f"Your order has been delayed due to an unusual rush at the branch. You can expect to receive your order by {eta_value}. We apologize for the inconvenience caused and thank you for your patience and understanding. 🙏"
                        else:
                            order_delay_message = "Your order has been delayed due to an unusual rush at the branch. We apologize for the inconvenience caused and thank you for your patience and understanding. 🙏"
                    
                    # @Technical@ - Based on technical issues flag
                    if technical_issues:
                        technical_message = "We're currently facing some difficulties. We should be back and running in no time. Your patience is much appreciated. 💙"
                    else:
                        technical_message = "Everything seems to be working on our end. I'll connect you to our tech team right away so they can assist you further."
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
    
    return prompt

# Function to process response and replace condition-based variables
def process_response_variables(response_text, client_id=None):
    """Replace variables in the assistant's response based on client data and conditions"""
    if client_id is None or not response_text:
        return response_text
    
    # Initialize variables with default values
    eta_message = "noknok is committed to delivering your order within the advised estimated time of delivery mentioned upon placing the order. The average delivery time is 15 mins."
    delay_message = "Your order has been delayed due to an unusual rush at the branch. We apologize for the inconvenience caused and thank you for your patience and understanding. 🙏"
    technical_message = "Everything seems to be working on our end. I'll connect you to our tech team right away so they can assist you further."
    
    try:
        if "@ETA@" in response_text or "@Order Delay@" in response_text or "@Technical@" in response_text:
            if "condition_handler" in st.session_state and st.session_state.condition_handler:
                handler = st.session_state.condition_handler
                
                # Get order data for active orders
                if handler.order_data:
                    # Find client's ongoing orders (not delivered or cancelled)
                    ongoing_orders = [
                        o for o in handler.order_data 
                        if str(o.get('ClientID', '')) == str(client_id) and 
                        o.get('OrderStatus', '').lower() not in ['delivered', 'cancelled', 'canceled', 'refunded']
                    ]
                    
                    if ongoing_orders:
                        # Sort to get the most recent order
                        recent_order = max(ongoing_orders, key=lambda o: o.get('OrderDate', ''))
                        
                        # Process ETA variable
                        if "@ETA@" in response_text:
                            eta_value = None
                            for field in ["ETA", "eta", "Estimated Time of Arrival", "Delivery Time"]:
                                if field in recent_order and recent_order[field]:
                                    eta_value = recent_order[field]
                                    break
                            
                            if eta_value:
                                eta_message = f"You can expect to receive your order by {eta_value}."
                        
                        # Process Order Delay variable
                        if "@Order Delay@" in response_text:
                            order_status = None
                            for field in ["OrderStatus", "Status", "Order Status"]:
                                if field in recent_order and recent_order[field]:
                                    order_status = recent_order[field].lower()
                                    break
                            
                            weather_conditions = False
                            for field in ["Weather Conditions", "WeatherConditions", "Weather"]:
                                if field in recent_order and recent_order[field]:
                                    # Convert various formats to boolean
                                    value = recent_order[field]
                                    if isinstance(value, bool):
                                        weather_conditions = value
                                    elif isinstance(value, str) and value.lower() in ['true', 'yes', '1']:
                                        weather_conditions = True
                                    break
                            
                            if order_status == "delivered":
                                delay_message = "It appears that the order was delivered. Could you please double-check? It's possible the driver may have handed it to someone else by mistake. Let me know what you find and we'll sort it out right away. 💙"
                            elif order_status == "driver arrived":
                                delay_message = "The driver has arrived. Could you kindly check?"
                            elif weather_conditions:
                                delay_message = "Unfortunately, we are facing some difficulty in delivering your order due to the poor weather conditions. We appreciate your patience until our drivers are able to reach your location successfully. Thank you for choosing noknok! 💙🙏🏻"
                            else:
                                # Default delay message with ETA if available
                                eta_value = None
                                for field in ["ETA", "eta", "Estimated Time of Arrival", "Delivery Time"]:
                                    if field in recent_order and recent_order[field]:
                                        eta_value = recent_order[field]
                                        break
                                
                                if eta_value:
                                    delay_message = f"Your order has been delayed due to an unusual rush at the branch. You can expect to receive your order by {eta_value}. We apologize for the inconvenience caused and thank you for your patience and understanding. 🙏"
                        
                        # Process Technical variable
                        if "@Technical@" in response_text:
                            technical_issues = False
                            for field in ["Technical Issue", "TechnicalIssue", "Technical"]:
                                if field in recent_order and recent_order[field]:
                                    # Convert various formats to boolean
                                    value = recent_order[field]
                                    if isinstance(value, bool):
                                        technical_issues = value
                                    elif isinstance(value, str) and value.lower() in ['true', 'yes', '1']:
                                        technical_issues = True
                                    break
                            
                            if technical_issues:
                                technical_message = "We're currently facing some difficulties. We should be back and running in no time. Your patience is much appreciated. 💙"
    except Exception as e:
        print(f"Error processing response variables: {e}")
        import traceback
        traceback.print_exc()
    
    # Replace variables in the response text
    processed_response = response_text
    processed_response = processed_response.replace("@ETA@", eta_message)
    processed_response = processed_response.replace("@Order Delay@", delay_message)
    processed_response = processed_response.replace("@Technical@", technical_message)
    
    return processed_response

# Set model to gpt-4o (removed from UI)
model = "gpt-4o"

# App title
st.title("NokNok AI Assistant")

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
st.sidebar.title("NokNok Database")

# Add refresh button as a circular arrow at the top
sheet_url = "https://docs.google.com/spreadsheets/d/12rCspNRPXyuiJpF_4keonsa1UenwHVOdr8ixpZHnfwI"
top_cols = st.sidebar.columns([1, 6, 1])
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
                
                st.success("Database refreshed!")
                # Rerun the app to show updated data
                st.rerun()

# Add open sheet button as a nice styled button
with top_cols[2]:
    st.markdown(f'''
    <a href="{sheet_url}" target="_blank">
        <div style="display: flex; justify-content: center; align-items: center;">
            <span style="font-size: 1.2rem;">📋</span>
        </div>
    </a>
    ''', unsafe_allow_html=True)

# Add last updated timestamp
if "condition_handler" in st.session_state and st.session_state.condition_handler.last_data_refresh:
    last_update = st.session_state.condition_handler.last_data_refresh.strftime("%H:%M:%S")
    st.sidebar.caption(f"Last updated: {last_update}")

# Client selection dropdown
if "current_client_id" not in st.session_state:
    st.session_state.current_client_id = None

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
        
        # Display stats
        st.sidebar.metric("Total Orders", len(orders_data))
        st.sidebar.metric("Total Clients", len(clients_data))
        st.sidebar.metric("Products In Stock", sum(1 for item in items_data if item.get("In stock") == "true"))
        
        if orders_data or clients_data or items_data:
            st.sidebar.success("✅ Connected to NokNok Database")
            db_connected = True
            
            # Add styled Google Sheet button
            st.sidebar.markdown(f'''
            <a href="{sheet_url}" target="_blank" style="display: inline-block; text-decoration: none; 
               background-color: #4285F4; color: white; padding: 8px 16px; border-radius: 4px;
               font-weight: bold; text-align: center; margin: 8px 0px; width: 100%;">
               📊 Open Google Sheet
            </a>
            ''', unsafe_allow_html=True)
            
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
                
                # Show dropdown for client selection
                selected_index = st.sidebar.selectbox(
                    "Select client to chat as:",
                    options=range(len(dropdown_labels)),
                    format_func=lambda i: dropdown_labels[i],
                    index=0  # Default to None/guest
                )
                
                selected_value = dropdown_values[selected_index]
                
                # Handle selection
                if selected_value != "none":
                    # Store client ID in session state
                    client_id = selected_value
                    st.session_state.current_client_id = client_id
                    
                    # Find the client's data to display
                    client_data = next((c for c in clients_data if str(c.get('ClientID')) == str(client_id)), None)
                    if client_data:
                        # Format name using the correct field names
                        first_name = client_data.get('Client First Name', '')
                        last_name = client_data.get('Client Last Name', '')
                        display_name = f"{first_name} {last_name}"
                            
                        # Display client info in the sidebar
                        st.sidebar.info(f"""
                        ### Client Details
                        **Name:** {display_name}
                        **Email:** {client_data.get('Client Email', 'N/A')}
                        **Gender:** {client_data.get('Client Gender', 'N/A')}
                        **Address:** {client_data.get('Client Address', 'N/A')}
                        **Balance:** ${client_data.get('NokNok USD Wallet', 0)}
                        """)
                        
                        # Show client's recent orders if available
                        client_orders = [o for o in orders_data if str(o.get('ClientID', '')) == str(client_id)]
                        if client_orders:
                            # Sort by date (most recent first)
                            recent_orders = sorted(client_orders, key=lambda x: x.get('OrderDate', ''), reverse=True)[:3]
                            
                            # Create formatted order info with proper amount handling
                            order_info_items = []
                            for o in recent_orders:
                                # Try to get order amount using the same logic as cancellation
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
                                        amount_display = f"${float(order_amount)}"
                                    else:
                                        amount_display = "(Amount not available)"
                                except (ValueError, TypeError):
                                    # If it's not convertible to float, use as is
                                    amount_display = str(order_amount)
                                
                                # Try different status field names
                                order_status = None
                                status_fields = ["OrderStatus", "Status", "Order Status", "State"]
                                
                                # Try direct matches
                                for field in status_fields:
                                    if field in o and o[field]:
                                        order_status = o[field]
                                        break
                                
                                # Try case-insensitive
                                if order_status is None:
                                    order_keys = list(o.keys())
                                    for field in status_fields:
                                        matching_keys = [k for k in order_keys if k.lower() == field.lower()]
                                        if matching_keys:
                                            field_key = matching_keys[0]
                                            order_status = o[field_key]
                                            break
                                
                                # Default if not found
                                if order_status is None:
                                    order_status = "Status unknown"
                                
                                order_info_items.append(
                                    f"• Order #{o.get('OrderID')}: {amount_display} ({order_status})"
                                )
                            
                            order_info = "\n".join(order_info_items)
                            st.sidebar.info(f"""
                            ### Recent Orders
                            {order_info}
                            """)
                else:
                    st.session_state.current_client_id = None
        else:
            st.sidebar.warning("⚠️ Connected but no data available")
    except Exception as e:
        st.sidebar.error(f"Error loading data: {e}")
        print(f"Detailed error: {e}")
else:
    st.sidebar.warning("⚠️ Database connection not available")
    st.sidebar.info("The application will still work, but without real database access.")
    # Show empty stats
    st.sidebar.metric("Total Orders", 0)
    st.sidebar.metric("Total Clients", 0)
    st.sidebar.metric("Products In Stock", 0)

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("content"):
            st.write(message["content"])
        if message.get("image_bytes"):
            st.image(message["image_bytes"])

# Bottom-bar image uploader (appears just above the chat input)
uploaded_file = st.file_uploader(
    "Attach image (optional)",
    type=["png", "jpg", "jpeg"],
    key=f"image_uploader_{st.session_state.uploader_version}"
)
if uploaded_file is not None:
    st.session_state["attached_image_bytes"] = uploaded_file.getvalue()
    st.session_state["attached_image_mime"] = uploaded_file.type or "image/jpeg"

# Inject CSS to keep uploader fixed at bottom (just above chat input)
st.markdown(
    """
    <style>
    /* Pin the file uploader */
    div[data-testid="stFileUploader"] {
        position: fixed;
        bottom: 90px;               /* slightly above chat_input */
        left: 50%;                  /* center horizontally */
        transform: translateX(-50%);
        width: calc(100% - 6rem);   /* match main block width accounting for padding */
        max-width: 46rem;           /* similar to chat_input max width */
        padding: 10px 12px 6px 12px;
        background: var(--background-color);
        border-top: 1px solid rgba(49,51,63,0.2);
        z-index: 9999;
    }

    /* Provide extra bottom padding so messages are not hidden under uploader */
    section.main.css-1v0mbdj.egzxvld2 {   /* main block container wrapper class may vary */
        padding-bottom: 150px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Optional send button to allow sending image without typing text
send_image_only = False
if st.session_state.get("attached_image_bytes"):
    send_image_only = st.button("Send image", key="send_image_btn")

# -----------------------------------------------
# Chat input & message sending
# -----------------------------------------------

prompt_input = st.chat_input("Ask about orders, clients, or inventory...")

# Determine if we should send a message this run
should_send = (prompt_input is not None) or send_image_only

if should_send:
    prompt = prompt_input or ""  # allow empty string when image-only
    st.session_state.last_user_activity = datetime.now()
    st.session_state.closing_message_sent = False

    # Read and consume any attached image
    image_bytes = st.session_state.pop("attached_image_bytes", None)
    image_mime  = st.session_state.pop("attached_image_mime", "image/jpeg")
    if send_image_only and not image_bytes:
        # Edge-case: send button but no image (shouldn't normally happen)
        send_image_only = False

    if not api_key:
        st.error("OpenAI API key is missing. Please set it in your environment variables.")
    else:
        # Add user message (with optional image) to chat history
        user_message_entry = {"role": "user", "content": prompt}
        if image_bytes:
            user_message_entry["image_bytes"] = image_bytes
            user_message_entry["mime"] = image_mime
            st.session_state.reset_uploader = True
        st.session_state.messages.append(user_message_entry)
        with st.chat_message("user"):
            if prompt:
                st.write(prompt)
            if image_bytes:
                st.image(image_bytes)

        # Generate response
        with st.chat_message("assistant"):
            response_container = st.empty()
            full_response = ""
            
            try:
                # Create OpenAI client with minimal parameters to avoid proxies error
                client = OpenAI(api_key=api_key)
                
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
                    full_response = process_response_variables(full_response, current_client_id)
                
                # Display the complete response at once
                response_container.write(full_response)
                
                # Print debug info
                print(f"Response received: '{full_response}'")
                print(f"Contains noknok.com/support: {'noknok.com/support' in full_response}")
                
                # Check if the condition for support URL is triggered
                should_add_to_history = True
                
                # Check for refund URL
                if "noknok.com/refund" in full_response:
                    print("Refund URL detected in response, handling with condition")
                    
                    # Set up the refund order sequence
                    st.session_state.refund_order_pending = True
                    st.session_state.refund_order_prompt = prompt
                    
                    # Don't add the original response to history
                    should_add_to_history = False
                    
                    # Clear the current response
                    response_container.empty()
                    
                    # Rerun the app to handle the refund from a clean context
                    st.rerun()
                
                # Check for cancel URL
                elif "noknok.com/cancel" in full_response:
                    print("Cancel URL detected in response, handling with condition")
                    
                    # Set up the cancel order sequence
                    st.session_state.cancel_order_pending = True
                    st.session_state.cancel_order_prompt = prompt
                    
                    # Don't add the original response to history
                    should_add_to_history = False
                    
                    # Clear the current response
                    response_container.empty()
                    
                    # Rerun the app to handle the cancellation from a clean context
                    st.rerun()
                
                # Check for support URL
                elif "noknok.com/support" in full_response:
                    print("Support URL detected in response, handling with condition")
                    
                    # Set up the automated response sequence to run *after* the current display
                    st.session_state.support_handoff_pending = True
                    st.session_state.support_handoff_prompt = prompt
                    
                    # Don't add the original response to history
                    should_add_to_history = False
                    
                    # Clear the current response - this will end this chat message context
                    response_container.empty()
                    
                    # Rerun the app to handle the handoff from a clean context
                    st.rerun()
                elif "I just added your address information" in full_response:
                    print("Address-update phrase detected in response, handling condition")
                    st.session_state.address_update_pending = True
                    st.session_state.address_update_prompt = prompt      # keep the user prompt
                    should_add_to_history = False
                    #response_container.empty()
                    st.rerun()
                # … existing refund/cancel/support branches …
                elif "noknok.com/items" in full_response:
                    print("Items-URL detected in response, queuing items search")
                    st.session_state.items_search_pending = True
                    st.session_state.items_search_response = full_response  
                    st.session_state.items_search_prompt = prompt
                    should_add_to_history = True
                    #response_container.empty()
                    st.rerun()
                elif "noknok.com/calories" in full_response:
                    print("Calories-URL detected in response, queuing calories search")
                    st.session_state.calories_search_pending = True
                    st.session_state.calories_search_response = full_response
                    st.session_state.calories_search_prompt = prompt
                    should_add_to_history = True
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
                                    balance_message = f"Your new Noknok wallet balance is {result['result'].get('new_wallet_balance', '0')}."
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
                                        float_amount = float(order_amount)
                                        # Format with dollar sign
                                        amount_display = f"${float_amount}"
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

# Add condition controls to sidebar
with st.sidebar.expander("Condition Controls", expanded=False):
    if st.button("Evaluate All Conditions"):
        with st.spinner("Evaluating conditions..."):
            # Pass an empty context when manually evaluating
            context = {}
            results = st.session_state.condition_handler.evaluate_conditions(context)
            if results:
                for result in results:
                    st.success(f"Triggered: {result['description']}")
                    st.json(result['result'])
            else:
                st.info("No conditions triggered")
    
    # Add refresh data button
    if st.button("Refresh Data"):
        with st.spinner("Refreshing data..."):
            success = st.session_state.condition_handler.load_data()
            if success:
                st.success("Data refreshed successfully")
            else:
                st.error("Failed to refresh data")
    
    st.write("Registered Conditions:")
    condition_status = st.session_state.condition_handler.get_condition_status()
    for cond_id, status in condition_status.items():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"{cond_id}: {status['description']}")
            if status['last_triggered']:
                st.caption(f"Last triggered: {status['last_triggered'].strftime('%Y-%m-%d %H:%M')}")
        with col2:
            if st.checkbox("Active", value=status['active'], key=f"toggle_{cond_id}"):
                st.session_state.condition_handler.toggle_condition(cond_id, True)
            else:
                st.session_state.condition_handler.toggle_condition(cond_id, False)

# Add system prompt debugger
with st.sidebar.expander("Debug System Prompt", expanded=False):
    if st.button("View Processed Prompt"):
        current_client_id = st.session_state.current_client_id if "current_client_id" in st.session_state else None
        processed_prompt = process_prompt_variables(system_prompt_template, current_client_id)
        
        # Show which client is being used
        if current_client_id:
            st.info(f"Showing prompt for Client ID: {current_client_id}")
        else:
            st.info("Showing prompt for guest (no client selected)")
        
        # Extract the replaced values from processed prompt for display
        client_name = processed_prompt.split("@clientName@")[0] if "@clientName@" in processed_prompt else "Not found"
        
        # Extract values by looking for key phrases in the processed text
        eta_value = None
        if "You can expect to receive your order by" in processed_prompt:
            eta_parts = processed_prompt.split("You can expect to receive your order by")
            if len(eta_parts) > 1:
                eta_end = eta_parts[1].find(".")
                if eta_end > 0:
                    eta_value = eta_parts[1][:eta_end]
        
        delay_value = None
        if "It appears that the order was delivered" in processed_prompt:
            delay_value = "Order status is Delivered"
        elif "The driver has arrived" in processed_prompt:
            delay_value = "Order status is Driver Arrived"
        elif "difficulty in delivering your order due to the poor weather conditions" in processed_prompt:
            delay_value = "Weather conditions are poor"
        else:
            delay_value = "Default delay message"
        
        tech_value = None
        if "We're currently facing some difficulties" in processed_prompt:
            tech_value = "Technical issues = True"
        else:
            tech_value = "Technical issues = False"
        
        # Display the extracted values in a table
        variables = {
            "clientName": "valued customer" if "@clientName@" not in system_prompt_template else 
                        ("Not found" if client_name == "Not found" else 
                         client_name if len(client_name) < 20 else client_name[:20] + "..."),
            "ETA": "Default value" if "noknok is committed to delivering" in processed_prompt else 
                   f"Specific time: {eta_value}" if eta_value else "Custom value",
            "OrderDelay": delay_value,
            "Technical": tech_value,
            "OrderETA": "Same as ETA value"
        }
        
        # Create a DataFrame for display
        df = pd.DataFrame(list(variables.items()), columns=["Variable", "Selected Value"])
        st.table(df)
        
        # Display the processed prompt
        st.subheader("Processed Prompt")
        st.code(processed_prompt, language="markdown")
        
        # Display the original template with variables highlighted
        st.subheader("Template Variables")
        highlighted_template = system_prompt_template
        highlighted_template = highlighted_template.replace("@clientName@", "**@clientName@**")
        highlighted_template = highlighted_template.replace("@ETA@", "**@ETA@**")
        highlighted_template = highlighted_template.replace("@OrderDelay@", "**@OrderDelay@**")
        highlighted_template = highlighted_template.replace("@Technical@", "**@Technical@**")
        highlighted_template = highlighted_template.replace("@OrderETA@", "**@OrderETA@**")
        
        st.markdown(highlighted_template) 