import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import re                # ← already present? add if missing
import time              # we’ll sleep 3 s
from openai import OpenAI, OpenAIError

# CONDITION CHECK FUNCTIONS
def check_support_url_in_reply(handler, context=None):
    """Check if the GPT reply contains noknok.com/support which requires human agent handoff"""
    # The context should contain the reply text to check
    if not context or 'reply' not in context:
        print("Support URL check - No context or reply provided")
        return False
    
    # Check if the support URL is in the reply
    reply_text = context['reply']
    result = "noknok.com/support" in reply_text
    print(f"Support URL check - Reply contains support URL: {result}")
    return result

# ACTION FUNCTIONS
def action_human_agent_handoff(handler, context=None):
    """Handle GPT replies that need human agent intervention"""
    try:
        # First message to display
        message1 = "Kindly allow me a moment to check the matter."
        
        # Second message to display
        message2 = "Here the chat would have been transferred to a human agent in real life, but for testing purposes you can continue messaging the AI"
        
        # Instead of directly writing to the UI, we'll use streamlit session state to store these messages
        # The app.py file will handle displaying them properly
        result = {
            "id": "support_url_handoff",
            "message": "Human agent handoff sequence completed",
            "original_reply_contained": "noknok.com/support",
            "action_taken": "Queued transition messages",
            "replacement_messages": [
                {"content": message1, "delay": 0},
                {"content": message2, "delay": 5}
            ]
        }
        
        print(f"Queued replacement messages: {result}")
        return result
    except Exception as e:
        print(f"Error in human agent handoff action: {e}")
        return {
            "id": "support_url_handoff",
            "error": str(e),
            "message": "Failed to process human agent handoff"
        }
# ────────────────────────────────────────────────────────────────
# Address-update condition
# When the bot says:  "I just added your address information"
# ────────────────────────────────────────────────────────────────

def check_address_update_in_response(handler, context):
    """Return True iff the assistant's reply contains the trigger sentence."""
    return context and "reply" in context and \
           "I just added your address information" in context["reply"]


def handle_address_update(handler, context):
    """
    1. Pull the client's most recent order → current address
    2. Build one-shot prompt (current-address + last-two user messages)
    3. Ask GPT to return ONLY the new address
    4. Over-write the address column in the Order sheet
    5. Return a dict describing what happened (or an error)
    """
    try:
        # 0) Pre-conditions
        client_id = getattr(handler, "current_client_id", None)
        if not client_id:
            return {"type": "error", "message": "No client selected for address update"}

        if not handler.order_data:
            return {"type": "error", "message": "Order data unavailable"}

        # 1)  locate latest order for that client
        client_orders = [o for o in handler.order_data
                         if str(o.get("ClientID", "")) == str(client_id)]
        if not client_orders:
            return {"type": "error",
                    "message": f"No orders found for client {client_id}"}

        most_recent = max(client_orders, key=lambda o: o.get("OrderDate", ""))
        order_id = most_recent.get("OrderID", "N/A")

        # 2)  fetch current address (tolerate several header names)
        address_fields = ["Delivery Address", "Address", "DeliveryAddress",
                          "Client Address", "Shipping Address"]
        current_address = None
        for f in address_fields:
            if f in most_recent and most_recent[f]:
                current_address = most_recent[f]
                address_field_used = f
                break
        if current_address is None:
            return {"type": "error",
                    "message": "Could not locate address field in the order"}

        # 3)  compose prompt
        history_text = context.get("history", "")
        prompt_template = (
            "I will now give you a chat history of a client looking to ammend/edit "
            "his current address, your job is to return the new address and nothing "
            "else based on his previous address + new additions.\n\n"
            "Here's his current address: @address@\n"
            "Here's the chat history: @history@"
        )
        one_shot_prompt = prompt_template.replace("@address@", current_address) \
                                         .replace("@history@", history_text)

        # 4)  ask GPT (synch; small request, no streaming)
        from openai import OpenAI, OpenAIError
        import os
        try:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            gpt_resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": one_shot_prompt}],
                stream=False
            )
            new_address = gpt_resp.choices[0].message.content.strip()
        except OpenAIError as e:
            return {"type": "error", "message": f"OpenAI API error: {e}"}

        if not new_address:
            return {"type": "error", "message": "Empty address returned from GPT"}

        # 5)  write back to Google Sheets
        try:
            if handler.noknok_sheets and "order" in handler.noknok_sheets:
                order_sheet = handler.noknok_sheets["order"]
                all_orders = order_sheet.get_all_records()
                for idx, row in enumerate(all_orders):
                    if str(row.get("OrderID")) == str(order_id):
                        row_index = idx + 2          # +2 => header + 1-based
                        header_row = order_sheet.row_values(1)
                        col = header_row.index(address_field_used) + 1
                        order_sheet.update_cell(row_index, col, new_address)
                        break
        except Exception as e:
            return {"type": "error",
                    "message": f"Failed to update sheet: {e}"}

        # 6)  success payload for the Streamlit layer
        return {
            "type":       "address_updated",
            "order_id":   order_id,
            "old":        current_address,
            "new":        new_address,
            "message":    f"✅ Your delivery address has been updated to:\n\n{new_address}"
        }

    except Exception as e:
        return {"type": "error", "message": f"Unexpected error: {e}"} 

# CONDITION REGISTRY
CONDITIONS_REGISTRY = {
    "support_url_handoff": {
        "check": check_support_url_in_reply,
        "action": action_human_agent_handoff,
        "description": "Detect support URL in reply and handoff to human agent"
    }
}
# ───────────────────────────────────────────────────────────────
# Items-search condition  ●  Triggered by "noknok.com/items"
# ───────────────────────────────────────────────────────────────
def check_items_url_in_response(handler, context):
    return context and "reply" in context and "noknok.com/items" in context["reply"]


def handle_items_search(handler, context):
    """
    1) extract item between quotes before noknok.com/items
    2) write it to cell G2, wait, read JSON from H2
    3) build specialised prompt and ask GPT
    4) return the assistant answer or error dict
    """
    try:
        # ── sanity: need client’s latest user message (history) in context
        history_text = context.get("history", "").strip()
        reply_text   = context.get("reply", "")

        # 1) extract item name in quotes
        #   supports "..." or “...”
        # 1) Extract item name (supports "..." and “...”)
       # 1) Extract item name (only plain quotes "..." and message must contain noknok.com/items)
        if "noknok.com/items" in reply_text:
            m = re.search(r'"([^"]+)"', reply_text)
            if not m:
                return {"type": "error", "message": "Could not extract item name in quotes"}
            item_name = m.group(1).strip()
        else:
            return {"type": "error", "message": "No noknok.com/items URL found in reply"}

        # 2) Write item to F2 on the Items sheet
        items_ws = handler.noknok_sheets.get("items")
        if items_ws is None:
            return {"type": "error", "message": "‘Items’ worksheet not found"}

        items_ws.update("F2", [[item_name]])  # write the search term
        print(f"Wrote '{item_name}' to Items!F2")


        # wait 3 seconds for formula / script to fill H2
        time.sleep(3)
        json_results = target_sheet.acell("G2").value or ""
        print(f"Items!G2 -> {json_results[:60]}…")
       

        # 3) compose prompt
        prompt_template = (
            "<Purpose> You will act as an assistant that helps users find "
            "information about items in our NokNok database based on search results. </Purpose>\n"
            "<Search Results Format>\n"
            "You will receive:\n"
            "-A user question about an item\n"
            "-The top 5 search results from our database in JSON format\n"
            "-Each result contains: item name, price (in usd), stock availability (true/false), "
            "and distance (relevance measure)\n"
            "</Search Results Format>\n\n"
            "User inquiry: @history@\n"
            "Search results: @json@\n\n"
            "Now, please answer the user's query based on these search results. "
            "You are talking with the user directly and everything you say will be received by him. "
            "Don't explain your reasoning just answer directly now."
        )
        user_prompt = prompt_template.replace("@history@", history_text)\
                                     .replace("@json@", json_results)

        # 4) ask GPT
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        gpt_resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": user_prompt}],
            stream=False
        )
        answer = gpt_resp.choices[0].message.content.strip()

        return {
            "type": "items_answer",
            "message": answer
        }

    except OpenAIError as e:
        return {"type": "error", "message": f"OpenAI error: {e}"}
    except Exception as e:
        return {"type": "error", "message": f"Unexpected error: {e}"}

# Function to register all conditions with a handler
def register_all_conditions(handler):
    """Register all conditions with the provided handler"""
    registered_count = 0
    
    # Support condition - detects support URL and provides custom response
    handler.register_condition(
        "support_url_detected",
        check_support_url_in_response,
        handle_support_request,
        "Support URL detected in response"
    )
    registered_count += 1
    
    # Cancel order condition - detects cancel URL and cancels the customer's last order
    handler.register_condition(
        "cancel_order_detected",
        check_cancel_url_in_response,
        handle_order_cancellation,
        "Cancel URL detected in response"
    )
    registered_count += 1
    
    # Refund order condition - detects refund URL and refunds to customer's wallet
    handler.register_condition(
        "refund_order_detected",
        check_refund_url_in_response,
        handle_order_refund,
        "Refund URL detected in response"
    )
    registered_count += 1
        # Address update condition
    handler.register_condition(
        "address_update_detected",
        check_address_update_in_response,
        handle_address_update,
        "Assistant indicated it updated the customer address"
    )
    registered_count += 1
   # Items search condition
    handler.register_condition(
        "items_search_detected",
        check_items_url_in_response,
        handle_items_search,
        "Extract item, fetch JSON from sheet, answer user"
    )
    registered_count += 1

    return registered_count

# Support URL condition
def check_support_url_in_response(handler, context):
    """Check if the bot's reply contains the support URL"""
    if context and "reply" in context:
        return "noknok.com/support" in context["reply"]
    return False

def handle_support_request(handler, context):
    """Handle a support request by providing a specific response sequence"""
    return {
        "type": "support_handoff",
        "message": "Customer needs support assistance"
    }

# Cancel order condition
def check_cancel_url_in_response(handler, context):
    """Check if the bot's reply contains the cancel URL"""
    if context and "reply" in context:
        return "noknok.com/cancel" in context["reply"]
    return False

# Refund order condition
def check_refund_url_in_response(handler, context):
    """Check if the bot's reply contains the refund URL"""
    if context and "reply" in context:
        return "noknok.com/refund" in context["reply"]
    return False

def handle_order_cancellation(handler, context):
    """Handle an order cancellation by updating the order status and providing a response"""
    # Make sure we have the current client ID
    if not hasattr(handler, "current_client_id") or not handler.current_client_id:
        return {
            "type": "error",
            "message": "No client selected for cancellation"
        }
    
    client_id = handler.current_client_id
    
    # Find the most recent order for this client
    if not handler.order_data:
        return {
            "type": "error",
            "message": "Order data not available"
        }
    
    # Filter orders for the current client and find the most recent one
    client_orders = [order for order in handler.order_data if str(order.get("ClientID", "")) == str(client_id)]
    
    if not client_orders:
        return {
            "type": "error",
            "message": f"No orders found for client ID {client_id}"
        }
    
    # Find the most recent order by date
    most_recent_order = max(client_orders, key=lambda order: order.get("OrderDate", ""))
    order_id = most_recent_order.get("OrderID")
    order_amount = most_recent_order.get("TotalAmount", 0)
    
    # Update the order status to Cancelled in the sheet
    try:
        # Find the row index of the order
        if handler.noknok_sheets and "order" in handler.noknok_sheets:
            order_sheet = handler.noknok_sheets["order"]
            all_orders = order_sheet.get_all_records()
            
            # Find the row index (adding 2 because row 1 is header and sheet is 1-indexed)
            for i, order in enumerate(all_orders):
                if str(order.get("OrderID")) == str(order_id):
                    row_index = i + 2  # +2 for header row and 1-indexed
                    
                    # Update the Status column to "Cancelled"
                    order_sheet.update_cell(row_index, 5, "Cancelled")  # Assuming Status is column E (5)
                    break
        
        # Prepare the confirmation message
        confirmation_message = f"Your order totaling {order_amount}$ has been canceled. We hope to serve you better in the future. Thank you for your kind understanding! 💙🙏🏻"
        
        return {
            "type": "order_cancelled",
            "order_id": order_id,
            "client_id": client_id,
            "amount": order_amount,
            "message": confirmation_message
        }
    
    except Exception as e:
        return {
            "type": "error",
            "message": f"Error cancelling order: {str(e)}"
        }

def handle_order_refund(handler, context):
    """Handle an order refund by adding the amount to the client's wallet"""
    # Make sure we have the current client ID
    if not hasattr(handler, "current_client_id") or not handler.current_client_id:
        return {
            "type": "error",
            "message": "No client selected for refund"
        }
    
    client_id = handler.current_client_id
    
    # Find the most recent order for this client
    if not handler.order_data:
        return {
            "type": "error",
            "message": "Order data not available"
        }
    
    # Filter orders for the current client and find the most recent one
    client_orders = [order for order in handler.order_data if str(order.get("ClientID", "")) == str(client_id)]
    
    if not client_orders:
        return {
            "type": "error",
            "message": f"No orders found for client ID {client_id}"
        }
    
    # Find the most recent order by date
    most_recent_order = max(client_orders, key=lambda order: order.get("OrderDate", ""))
    order_id = most_recent_order.get("OrderID")
    
    # Find the order amount using the same approach as in app.py
    order_amount = None
    possible_amount_fields = [
        "TotalAmount", "OrderAmount", "Order Amount", "Total Amount", 
        "Total", "Amount", "Price", "Cost", "Value"
    ]
    
    # Try direct key matching
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
        return {
            "type": "error",
            "message": "Could not determine order amount for refund"
        }
    
    try:
        # Convert order amount to float for calculation
        float_amount = float(order_amount)
    except (ValueError, TypeError):
        return {
            "type": "error",
            "message": f"Invalid order amount format: {order_amount}"
        }
    
    # Find the client to update their wallet
    if not handler.client_data:
        return {
            "type": "error",
            "message": "Client data not available"
        }
    
    client_data = next((c for c in handler.client_data if str(c.get('ClientID')) == str(client_id)), None)
    if not client_data:
        return {
            "type": "error",
            "message": f"Client ID {client_id} not found in client data"
        }
    
    # Find the wallet field in client data
    wallet_amount = None
    wallet_field = None
    possible_wallet_fields = ["NokNok USD Wallet", "Wallet", "Balance", "USD Wallet", "Account Balance"]
    
    # Try direct match
    for field in possible_wallet_fields:
        if field in client_data and client_data[field] is not None:
            wallet_field = field
            wallet_amount = client_data[field]
            print(f"Found wallet in field: {field}, current value: {wallet_amount}")
            break
    
    # Try case insensitive
    if wallet_amount is None:
        client_keys = list(client_data.keys())
        for field in possible_wallet_fields:
            matching_keys = [k for k in client_keys if k.lower() == field.lower()]
            if matching_keys:
                wallet_field = matching_keys[0]
                wallet_amount = client_data[wallet_field]
                print(f"Found wallet via case-insensitive match in field: {wallet_field}, value: {wallet_amount}")
                break
    
    # Try partial match
    if wallet_amount is None:
        client_keys = list(client_data.keys())
        wallet_related_keys = [k for k in client_keys if 'wallet' in k.lower() or 'balance' in k.lower() or 'usd' in k.lower()]
        if wallet_related_keys:
            wallet_field = wallet_related_keys[0]
            wallet_amount = client_data[wallet_field]
            print(f"Found wallet via partial match in field: {wallet_field}, value: {wallet_amount}")
    
    if wallet_amount is None or wallet_field is None:
        return {
            "type": "error",
            "message": "Could not find wallet field in client data"
        }
    
    try:
        # Convert wallet amount to float for calculation
        float_wallet = float(wallet_amount) if wallet_amount else 0
    except (ValueError, TypeError):
        float_wallet = 0
    
    # Calculate new wallet amount
    new_wallet_amount = float_wallet + float_amount
    
    try:
        # Update the client's wallet
        if handler.noknok_sheets and "client" in handler.noknok_sheets:
            client_sheet = handler.noknok_sheets["client"]
            all_clients = client_sheet.get_all_records()
            
            # Find the client row
            found = False
            for i, client in enumerate(all_clients):
                if str(client.get("ClientID", "")) == str(client_id):
                    row_index = i + 2  # +2 for header row and 1-indexed
                    
                    # Find the wallet column
                    header_row = client_sheet.row_values(1)  # Get header row
                    wallet_col = 0
                    for idx, header in enumerate(header_row):
                        if header == wallet_field:
                            wallet_col = idx + 1  # 1-indexed columns in sheets API
                            break
                    
                    if wallet_col > 0:
                        # Update the wallet amount
                        client_sheet.update_cell(row_index, wallet_col, new_wallet_amount)
                        found = True
                        break
                    else:
                        raise Exception(f"Wallet column '{wallet_field}' not found in sheet")
            
            if not found:
                return {
                    "type": "error",
                    "message": f"Could not locate client {client_id} in the database to update wallet"
                }
            
            # Update the order status to Refunded
            try:
                if "order" in handler.noknok_sheets:
                    order_sheet = handler.noknok_sheets["order"]
                    all_orders = order_sheet.get_all_records()
                    
                    # Find the order row
                    order_found = False
                    for i, order in enumerate(all_orders):
                        if str(order.get("OrderID")) == str(order_id):
                            row_index = i + 2  # +2 for header row and 1-indexed
                            
                            # Find the status column
                            header_row = order_sheet.row_values(1)  # Get header row
                            status_col = 0
                            for idx, header in enumerate(header_row):
                                if header.lower() in ["orderstatus", "status", "order status"]:
                                    status_col = idx + 1  # 1-indexed columns in sheets API
                                    break
                            
                            if status_col > 0:
                                # Update status to Refunded
                                order_sheet.update_cell(row_index, status_col, "Refunded")
                                order_found = True
                                break
                    
                    if not order_found:
                        print(f"Warning: Could not update order {order_id} status to Refunded")
            except Exception as e:
                print(f"Error updating order status: {e}")
            
            # Format the amount for message
            try:
                amount_display = f"${float_amount}"
            except:
                amount_display = str(order_amount)
            
            # Return success with refund details
            return {
                "type": "order_refunded",
                "order_id": order_id,
                "client_id": client_id,
                "amount": amount_display,
                "new_wallet_balance": f"${new_wallet_amount}",
                "message": f"Your order totaling {amount_display} has been refunded to your noknok wallet. We hope to serve you better in the future. Thank you for your kind understanding! 💙🙏🏻"
            }
        else:
            return {
                "type": "error",
                "message": "Client sheet not available"
            }
    except Exception as e:
        return {
            "type": "error",
            "message": f"Error processing refund: {str(e)}"
        } 