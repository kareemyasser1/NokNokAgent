import streamlit as st

# Set up the page before any other Streamlit calls
st.set_page_config(
    page_title="NokNok AI Assistant",
    page_icon="🛒",
    layout="wide",
)

# Add fixed header CSS
st.markdown('''
<style>
.fixed-header {
    position: fixed;
    top: 0;
    left: 18rem;  /* Leave space for sidebar */
    right: 0;
    background-color: white;
    z-index: 1000;
    padding: 1rem;
    display: flex;
    align-items: center;
    gap: 1.5rem;
    border-bottom: 1px solid rgba(49, 51, 63, 0.1);
}

/* Add padding to main content to prevent overlap with fixed header */
.main .block-container {
    padding-top: 7rem !important;
}

.fixed-header img {
    max-height: none !important;
    object-fit: contain;
    width: 200px;
}

.title-text {
    margin: 0;
    padding: 0;
    font-size: 2.5rem;
    font-weight: bold;
}
</style>
''', unsafe_allow_html=True)

# Load the logo image
with open("logo.png", "rb") as f:
    logo_base64 = base64.b64encode(f.read()).decode()

# Add the fixed header
st.markdown(f'''
<div class="fixed-header">
    <img src="data:image/png;base64,{logo_base64}" alt="logo">
    <h1 class="title-text">AI Assistant 🛒</h1>
</div>
''', unsafe_allow_html=True)

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
from conditions import register_all_conditions
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import base64
import streamlit.components.v1 as components  # For custom HTML (background particles)

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
                📊 Open Google Sheet
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
                                <span class="balance-value">${client_balance}</span>
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
                            </style>
                            """, unsafe_allow_html=True)
                            
                            # Sort by date (most recent first)
                            recent_orders = sorted(client_orders, key=lambda x: x.get('OrderDate', ''), reverse=True)[:3]
                            
                            # Create order HTML items with proper styling
                            order_html_items = []
                            for o in recent_orders:
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
                                        amount_display = f"${float(order_amount)}"
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
                                
                                # Create HTML for this order
                                order_id = o.get('OrderID', 'N/A')
                                order_html_items.append(f"""
                                <div class="order-item">
                                    <span class="order-id">Order #{order_id}</span>
                                    <span class="order-amount">{amount_display}</span>
                                    <span class="order-status {status_class}">{order_status}</span>
                                </div>
                                """.strip())
                            
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
        if message.get("content"):
            st.write(message["content"])
        if message.get("image_bytes"):
            st.image(message["image_bytes"])

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

if should_send:
    prompt = prompt_input or ""  # allow empty string when image-only
    st.session_state.last_user_activity = datetime.now()
    st.session_state.closing_message_sent = False
    
    # Debug info
    print(f"Should send message - prompt: '{prompt}', send_image_only: {st.session_state.get('send_image_only', False)}")

    # Read and consume any attached image
    image_bytes = st.session_state.pop("attached_image_bytes", None)
    image_mime = st.session_state.pop("attached_image_mime", "image/jpeg")
    
    # Reset the send_image_only flag for next run
    send_image_only = st.session_state.pop("send_image_only", False)
    
    # Ensure uploader will be reset on next rerun
    if image_bytes:
        st.session_state.reset_uploader = True
        print(f"Image received, size: {len(image_bytes)} bytes")
    
    if send_image_only and not image_bytes:
        # Edge-case: send button but no image (shouldn't normally happen)
        print("Warning: Send image requested but no image found")
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
        
        st.markdown("**Prompt details:**")
        st.write("- Client name:", client_name)
        if eta_value:
            st.write("- ETA value:", eta_value)
        st.write("- Delivery status:", delay_value)
        st.write("- Technical status:", tech_value)
        
        st.markdown("**Full processed prompt:**")
        # Add basic syntax highlighting by converting special tokens to colored spans
        highlighted_template = processed_prompt
        highlighted_template = re.sub(r'@(\w+)@', r'<span style="color:red">@\1@</span>', highlighted_template)
        
        st.markdown(highlighted_template) 

# Show current language indicator in sidebar
current_language = st.session_state.get("current_prompt_language", "english").capitalize()
language_emoji = "🇱🇧" if current_language.lower() == "lebanese" else "🇬🇧"
st.sidebar.markdown(f"### Current Prompt: {language_emoji} {current_language} Prompt")

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