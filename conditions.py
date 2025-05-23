import pandas as pd
from datetime import datetime, timedelta
import time
import streamlit as st
from openai import OpenAI, OpenAIError
import json
import re

# Helper function to safely convert string amounts to float
def safe_float_conversion(amount_str):
    """
    Safely convert a string amount to float by removing currency symbols.
    Returns a float value or 0 if conversion fails.
    """
    if amount_str is None:
        return 0
    
    if isinstance(amount_str, (int, float)):
        return float(amount_str)
    
    # Remove currency symbols and whitespace
    cleaned_str = str(amount_str).strip()
    cleaned_str = re.sub(r'[$₹£€¥]', '', cleaned_str)
    cleaned_str = cleaned_str.replace(',', '')
    
    try:
        return float(cleaned_str)
    except (ValueError, TypeError):
        print(f"Warning: Could not convert '{amount_str}' to float")
        return 0

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
        
        # Generate a third message - a summary for the human agent
        summary_prompt = """Summarize the following conversation between an AI assistant and a customer on our grocery delivery app. Focus only on:

1. Customer's name (if mentioned in the conversation)
2. Customer's main inquiry/issue (in 1-2 sentences)
3. Key details provided by the customer (order number, specific products, delivery time, etc.)
4. Solutions already attempted by the AI assistant
5. Reason for escalation to human agent

Format the summary in bullet points and keep it under 100 words. This summary will be shown to the human agent handling the escalation.

Conversation:
"""
        
        # Get conversation history from context
        conversation_history = context.get("history", "")
        
        # Call OpenAI to generate the summary
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            summary_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": summary_prompt + conversation_history}],
                temperature=0.7,
                stream=False
            )
            message3 = summary_response.choices[0].message.content.strip()
        except Exception as e:
            message3 = f"Error generating conversation summary: {str(e)}"
            print(f"Error generating summary: {e}")
        
        # Instead of directly writing to the UI, we'll use streamlit session state to store these messages
        # The app.py file will handle displaying them properly
        result = {
            "id": "support_url_handoff",
            "message": "Human agent handoff sequence completed",
            "original_reply_contained": "noknok.com/support",
            "action_taken": "Queued transition messages",
            "replacement_messages": [
                {"content": message1, "delay": 0},
                {"content": message2, "delay": 5},
                {"content": "Dear Agent, Please find the conversation Summary below to help you with assisting the customer:\n " + message3, "delay": 8}
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
            client = OpenAI(api_key= st.secrets["OPENAI_API_KEY"])
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

def check_items_url_in_response(handler, context):
    """Trigger when the assistant's reply contains noknok.com/items."""
    return bool(
        context
        and "reply" in context
        and "noknok.com/items" in context["reply"]
    )

def handle_items_request(handler, context):
    """
    1. Ask GPT to extract the quoted item name from the assistant reply.
    2. Write it to F2 (col 6,row 2) of the 'Items' sheet.
    3. Wait 3 s, then read G2 (col 7,row 2) as JSON results.
    4. Build the one-shot prompt (injecting last 4 messages + that JSON).
    5. Ask GPT for the final item answer.
    6. Return the answer as 'message'.
    """
    try:
        # 1) Ensure a client is selected
        # client_id = getattr(handler, "current_client_id", None)
        # if not client_id:x
        #      return {"type":"error","message":"No client selected for item lookup"}

        reply = context["reply"]
        
        # 2) Extract item-name using regex instead of GPT
        try:
            import re
            # Pattern to find text between double curly braces
            pattern = r'\{\{(.*?)\}\}'
            matches = re.findall(pattern, reply)
            
            if matches and len(matches) > 0:
                item_name = matches[0].strip()
                print(f"Extracted item name using regex: {item_name}")
            else:
                # Fallback to the old method of looking for quoted text if no double braces found
                quote_pattern = r'"([^"]*)"'
                quote_matches = re.findall(quote_pattern, reply)
                if quote_matches and len(quote_matches) > 0:
                    item_name = quote_matches[0].strip()
                    print(f"Extracted item name using quote regex fallback: {item_name}")
                else:
                    return {"type":"error","message":"Could not extract any item name from the assistant's reply"}
            
            if not item_name:
                return {"type":"error","message":"Could not extract any item name from the assistant's reply"}
                
        except Exception as e:
            return {"type":"error","message":f"Item extraction error: {str(e)}"}

        # 3) Write item_name → F2, wait, then read JSON from G2
        items_sheet = handler.noknok_sheets.get("items")
        if not items_sheet:
            return {"type":"error","message":"Items sheet not available"}
        items_sheet.update_cell(2, 6, item_name)   # F2
        time.sleep(3)
        json_results = items_sheet.cell(2, 7).value or ""  # G2

        # 4) Build the one-shot prompt
        # Get the last 4 messages from context instead of just the last user message
        full_history = context.get("history", "")
        
        # Split history by message delimiter to get last 4 messages
        # This approach depends on how messages are formatted in the history
        # Assuming each message is on a new line or has some delimiter
        if not full_history.strip():
            # If history is empty, try to use the last user message
            last_user_message = context.get("last_user_message", "")
            if last_user_message.strip():
                messages = [last_user_message]
            else:
                messages = []
        else:
            messages = full_history.split("\n\n")  # Adjust the delimiter based on actual format
            
        last_4_messages = "\n\n".join(messages[-4:] if len(messages) >= 4 else messages)
        
        template = """
<Purpose> You will act as an assistant that helps users find information about items in our NokNok database based on search results. </Purpose>
<Search Results Format> 
You will receive:
-A user question about an item along with the chat history that preceeded it
-The top 5 search results from our database in JSON format
-Each result contains: item name, price (in usd), stock availability (true/false), and distance (relevance measure)
</Search Results Format> 

When a clear match is found:

Directly answer the user's specific question about the item
If they asked about price: Provide the price information
If they asked about availability: Provide stock availability information
If item is out of stock: Reply verbatim with: "Unfortunately we ran out of [item name]. We are doing our best in terms of stock availability. However, due to the current situation, there are some shortages from the suppliers themselves. Please bear with us, we are replenishing every 2 days!". 

When multiple relevant matches exist:

Ask the user to clarify which specific item they're referring to.
Do this only once. When the user specify which item exactly they mean, then answer based on that item's information (like in the case of "a clear match is found") above.

When no relevant match exists:

Say: "Unfortunately, NokNok doesn't provide [item name] yet. Is there any other item I can help you with?"

Important Note: Never mention the "distance" value to users. This is only for internal relevance assessment.
Important Note 2: when there's a clear winner, even if the rest of the search results are a bit relevant, don't ask which item they're referring to. Only consider the multiple relevant matches when you genuinely can't tell which item it is.

Here's your input
User inquiry: <history> @history@ </history>
Search results: <json> @json@ </json>

Now, answer the user's query based on these search results and chat history. You are talking with the user directly and everything you say will be received by him. Don't explain your reasoning just answer directly now. 
"""
        one_shot = (
            template
            .replace("@history@", last_4_messages)
            .replace("@json@", json_results)
        )

        # 5) Final GPT call for item answer
        try:
            client = OpenAI(api_key= st.secrets["OPENAI_API_KEY"])
            final_resp = client.chat.completions.create(
                model="o4-mini",
                messages=[{"role":"user","content":one_shot}],
                temperature=1,
                stream=False
            )
            answer = final_resp.choices[0].message.content.strip()
        except OpenAIError as e:
            return {"type":"error","message":f"OpenAI final call error: {e}"}

        # 6) Return to app.py for display
        return {"type":"items_searched","message":answer}

    except Exception as e:
        return {"type":"error","message":f"Unexpected error: {e}"}

# ─────────────────────────────────────────────────────────────
# Calories URL condition
# Triggered when assistant reply contains noknok.com/calories
# ─────────────────────────────────────────────────────────────

def check_calories_url_in_response(handler, context):
    """Return True iff the assistant's reply contains noknok.com/calories"""
    return bool(context and "reply" in context and "noknok.com/calories" in context["reply"])


def handle_calories_request(handler, context):
    """Run external GPT search workflow for calories and return best answer."""
    try:
        # Extract the last user message so we can build the search prompt
        last_user_msg = context.get("last_user_message", "")

        # Build the one-shot prompt
        prompt_template = (
            "You are an expert in calories searching, you will receive a message from the user requesting to search the internet for calories. You must first start by searching the website of Carrefour Lebanon to find the relevant details. Now if you can't find it in Carrefour Lebanon, search then Carrefour UAE, Egypt and other Carrefour websites. Only if you can't find the item anywhere in any carrefour website, only then search in different websites. Remember, you are talking directly with the user, so don't explain your reasoning, just answer the user question. NEVER EXPLAIN YOUR REASONING. REMEMBER TO ALWAYS ALWAYS SEARCH CARREFOUR WEBSITES FIRST.\n\n"
            "For each query, return your findings in this JSON format:\n"
            "{\n"
            "  \"carrefourlebanonanswer\": \"A conversational response about what was found on Carrefour Lebanon website or 'Missing' if not found\",\n"
            "  \"carrefourforeignanswer\": \"A conversational response about what was found on other Carrefour websites (UAE, Egypt, etc.) or 'Missing' if not found\",\n"
            "  \"otheranswer\": \"A conversational response about what was found on non-Carrefour websites or 'Missing' if not found\"\n"
            "}\n"
            "But keep your answers a bit short, DON'T mention the website, only add the link. DO NOT SAY \"According to Carrefour Lebanon\" or \"In carrefour UAE\" and such, just state how many calories something has and put the source link.\n\n"
            "In the source link, put the extension of the full link of the item (the exact page you got the calories from, and not just the general link of the website. \n"
            "Here's the user question: @history@"
        )
        prompt = prompt_template.replace("@history@", last_user_msg)

        # Call OpenAI (synchronous, no streaming)
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            gpt_resp = client.chat.completions.create(
                model="gpt-4o",  # Using same model family as elsewhere
                messages=[{"role": "user", "content": prompt}],
                stream=False
            )
            raw_answer = gpt_resp.choices[0].message.content.strip()
        except OpenAIError as e:
            return {"type": "error", "message": f"OpenAI API error: {e}"}

        # Attempt to parse JSON from the answer.
        try:
            parsed = json.loads(raw_answer)
        except json.JSONDecodeError:
            # Try to locate JSON braces in the response
            try:
                first = raw_answer.find('{')
                last = raw_answer.rfind('}')
                parsed = json.loads(raw_answer[first:last+1]) if first != -1 and last != -1 else {}
            except Exception:
                parsed = {}

        carrefour_lb = parsed.get("carrefourlebanonanswer", "").lower() if parsed.get("carrefourlebanonanswer") else ""
        carrefour_foreign = parsed.get("carrefourforeignanswer", "").lower() if parsed.get("carrefourforeignanswer") else ""
        other = parsed.get("otheranswer", "").lower() if parsed.get("otheranswer") else ""

        # Decide which answer to send back
        if carrefour_lb and carrefour_lb != "missing":
            final_msg = carrefour_lb
        elif carrefour_foreign and carrefour_foreign != "missing":
            final_msg = carrefour_foreign
        elif other and other != "missing":
            final_msg = other
        else:
            final_msg = "We couldn't find the calorie content for this item, can you please describe it again?"

        return {"type": "calories_searched", "message": final_msg}

    except Exception as e:
        return {"type": "error", "message": f"Unexpected error: {e}"}

# ─────────────────────────────────────────────────────────────
# Lebanese URL condition
# Triggered when assistant reply contains noknok.com/lebanese
# ─────────────────────────────────────────────────────────────

def check_lebanese_url_in_response(handler, context):
    """Return True iff the assistant's reply contains noknok.com/lebanese"""
    if context and "reply" in context:
        return "noknok.com/lebanese" in context["reply"]
    return False


def handle_lebanese_prompt_switch(handler, context):
    """Switch the system prompt to LebanesePrompt.txt"""
    try:
        # Read the Lebanese prompt file
        try:
            with open('LebanesePrompt.txt', 'r', encoding='utf-8') as file:
                lebanese_prompt = file.read()
                if not lebanese_prompt:
                    return {"type": "error", "message": "Lebanese prompt file is empty"}
        except Exception as e:
            return {"type": "error", "message": f"Failed to read Lebanese prompt file: {e}"}
        
        # Store the Lebanese prompt in the session state for app.py to use
        import streamlit as st
        st.session_state.system_prompt_template = lebanese_prompt
        st.session_state.current_prompt_language = "lebanese"
        
        # Print the entire context for debugging
        print("Lebanese Switch - Full context:", context)
        
        # Extract the last 4 messages from the history
        full_history = context.get("history", "")
        print("Lebanese Switch - Full history:", full_history)
        
        # Get the last user message if history is empty
        last_message = context.get("last_user_message", "")
        print("Lebanese Switch - Last user message:", last_message)
        
        # If history is empty but we have a last message, use that
        if not full_history and last_message:
            user_context = last_message
            print("Using last_user_message instead of empty history")
        else:
            # Try multiple ways to split the history 
            if "\n\n" in full_history:
                messages = full_history.split("\n\n")
            elif "\n" in full_history:
                messages = full_history.split("\n")
            else:
                # Just use the whole history as one message if can't split
                messages = [full_history]
                
            last_4_messages = messages[-4:] if len(messages) >= 4 else messages
            user_context = "\n\n".join(last_4_messages)
        
        print("Lebanese Switch - Final user_context:", user_context)
        
        # If still empty, provide a default context
        if not user_context.strip():
            user_context = "Hello, I'm switching to Lebanese mode. How can I help you?"
            print("Using default context because user_context is empty")
        
        # Generate a response to the last messages using the new Lebanese prompt
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            
            # Prepare messages for the API call
            prompt_with_instruction = f"{lebanese_prompt}"
            
            api_messages = [
                {"role": "system", "content": prompt_with_instruction},
                {"role": "user", "content": user_context}
            ]
            
            # Call the API
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=api_messages,
                stream=False
            )
            
            # Get the response
            lebanese_response = response.choices[0].message.content.strip()
            
            # Return only the response to the context
            return {
                "type": "prompt_response",
                "language": "lebanese",
                "message": lebanese_response
            }
            
        except Exception as e:
            print(f"Error in Lebanese response generation: {e}")
            # If GPT call fails, return an error
            return {
                "type": "error",
                "message": f"Failed to generate response in Lebanese mode: {str(e)}"
            }
    
    except Exception as e:
        print(f"Unexpected error in Lebanese switch: {e}")
        return {"type": "error", "message": f"Unexpected error: {e}"}

# ─────────────────────────────────────────────────────────────
# Languages URL condition
# Triggered when assistant reply contains noknok.com/languages
# ─────────────────────────────────────────────────────────────

def check_languages_url_in_response(handler, context):
    """Return True iff the assistant's reply contains noknok.com/languages"""
    if context and "reply" in context:
        return "noknok.com/languages" in context["reply"]
    return False


def handle_english_prompt_switch(handler, context):
    """Switch the system prompt to EnglishPrompt.txt"""
    try:
        # Read the English prompt file
        try:
            with open('EnglishPrompt.txt', 'r', encoding='utf-8') as file:
                english_prompt = file.read()
                if not english_prompt:
                    return {"type": "error", "message": "English prompt file is empty"}
        except Exception as e:
            return {"type": "error", "message": f"Failed to read English prompt file: {e}"}
        
        # Store the English prompt in the session state for app.py to use
        import streamlit as st
        st.session_state.system_prompt_template = english_prompt
        st.session_state.current_prompt_language = "english"
        
        # Print the entire context for debugging
        print("English Switch - Full context:", context)
        
        # Extract the last 4 messages from the history
        full_history = context.get("history", "")
        print("English Switch - Full history:", full_history)
        
        # Get the last user message if history is empty
        last_message = context.get("last_user_message", "")
        print("English Switch - Last user message:", last_message)
        
        # If history is empty but we have a last message, use that
        if not full_history and last_message:
            user_context = last_message
            print("Using last_user_message instead of empty history")
        else:
            # Try multiple ways to split the history 
            if "\n\n" in full_history:
                messages = full_history.split("\n\n")
            elif "\n" in full_history:
                messages = full_history.split("\n")
            else:
                # Just use the whole history as one message if can't split
                messages = [full_history]
                
            last_4_messages = messages[-4:] if len(messages) >= 4 else messages
            user_context = "\n\n".join(last_4_messages)
        
        print("English Switch - Final user_context:", user_context)
        
        # If still empty, provide a default context
        if not user_context.strip():
            user_context = "Hello, I'm switching to English mode. How can I help you?"
            print("Using default context because user_context is empty")
        
        # Generate a response to the last messages using the new English prompt
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            
            # Prepare messages for the API call
            prompt_with_instruction = f"{english_prompt}"
            
            api_messages = [
                {"role": "system", "content": prompt_with_instruction},
                {"role": "user", "content": user_context}
            ]
            
            # Call the API
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=api_messages,
                stream=False
            )
            
            # Get the response
            english_response = response.choices[0].message.content.strip()
            
            # Return the response with the correct format to be handled by app.py
            return {
                "type": "prompt_response",
                "language": "english",
                "message": english_response
            }
            
        except Exception as e:
            print(f"Error in English response generation: {e}")
            # If GPT call fails, return an error
            return {
                "type": "error",
                "message": f"Failed to generate response in English mode: {str(e)}"
            }
    
    except Exception as e:
        print(f"Unexpected error in English switch: {e}")
        return {"type": "error", "message": f"Unexpected error: {e}"}

# Function to register all conditions with a handler
def register_all_conditions(handler):
    """Register all conditions with the provided handler"""
    registered_count = 0
    
    # Calories-URL condition
    handler.register_condition(
        "calories_search_detected",
        check_calories_url_in_response,
        handle_calories_request,
        "URL noknok.com/calories detected → calories web search"
    )
    registered_count += 1
    
    # English language prompt condition (via /languages URL)
    handler.register_condition(
        "english_language_detected",
        check_languages_url_in_response,
        handle_english_prompt_switch,
        "URL noknok.com/languages detected → switch to English prompt"
    )
    registered_count += 1
    
    # Lebanese language prompt condition
    handler.register_condition(
        "lebanese_language_detected",
        check_lebanese_url_in_response,
        handle_lebanese_prompt_switch,
        "URL noknok.com/lebanese detected → switch to Lebanese prompt"
    )
    registered_count += 1
    
    # Support condition - detects support URL and provides custom response
    handler.register_condition(
        "support_url_detected",
        check_support_url_in_reply,
        action_human_agent_handoff,
        "Support URL detected in response → human agent handoff"
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
    
    # Items-URL condition
    handler.register_condition(
        "items_search_detected",
        check_items_url_in_response,
        handle_items_request,
        "URL noknok.com/items detected → lookup item in sheet + GPT"
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
    # Make sure we have the current client ID
    if not hasattr(handler, "current_client_id") or not handler.current_client_id:
        return {
            "type": "error",
            "message": "No client selected for support"
        }
    
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
    
    # Check if the order is already refunded or canceled
    current_status = None
    status_fields = ["OrderStatus", "Status", "Order Status"]
    for field in status_fields:
        if field in most_recent_order and most_recent_order[field]:
            current_status = most_recent_order[field].lower()
            print(f"Found current order status for cancellation: {current_status}")
            break
    
    # If order is already refunded or canceled, don't proceed with cancellation
    if current_status in ["refunded", "cancelled", "canceled"]:
        return {
            "type": "error",
            "message": f"This order has already been {current_status}. No further action is needed."
        }
    
    # Get the order amount with safe conversion
    order_amount = most_recent_order.get("TotalAmount", 0)
    float_amount = safe_float_conversion(order_amount)
    
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
        confirmation_message = f"Your order totaling ${float_amount:.2f} has been canceled. We hope to serve you better in the future. Thank you for your kind understanding! 💙🙏🏻"
        
        return {
            "type": "order_cancelled",
            "order_id": order_id,
            "client_id": client_id,
            "amount": f"${float_amount:.2f}",
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
    
    # Check if the order is already refunded or canceled
    current_status = None
    status_fields = ["OrderStatus", "Status", "Order Status"]
    for field in status_fields:
        if field in most_recent_order and most_recent_order[field]:
            current_status = most_recent_order[field].lower()
            print(f"Found current order status: {current_status}")
            break
    
    # If order is already refunded or canceled, don't proceed with refund
    if current_status in ["refunded", "cancelled", "canceled"]:
        return {
            "type": "error",
            "message": f"This order has already been {current_status}. No further action is needed."
        }
    
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
        # Convert order amount to float for calculation using the safe method
        float_amount = safe_float_conversion(order_amount)
        if float_amount == 0 and order_amount is not None:
            return {
                "type": "error",
                "message": f"Invalid order amount format: {order_amount}"
            }
    except Exception as e:
        return {
            "type": "error",
            "message": f"Error processing order amount: {str(e)}"
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
    
    # Convert wallet amount to float using safe conversion
    float_wallet = safe_float_conversion(wallet_amount)
    
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
                amount_display = f"${float_amount:.2f}"
            except Exception as e:
                print(f"Error formatting amount: {e}")
                amount_display = str(order_amount)
            
            # Return success with refund details
            return {
                "type": "order_refunded",
                "order_id": order_id,
                "client_id": client_id,
                "amount": amount_display,
                "new_wallet_balance": f"${new_wallet_amount:.2f}",
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