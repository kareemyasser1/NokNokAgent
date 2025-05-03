HEAD

HEAD
# NokNokAgent
NokNok Chatbot

>>>>>>> f8e1000
# NokNok AI Assistant

A Streamlit application that provides an AI assistant for the NokNok e-commerce/delivery system, powered by OpenAI's GPT-4o and GPT-4o-research models.

## Features

- Interactive chat interface for querying NokNok database information
- Integration with Google Sheets to access real-time order, client, and inventory data
- AI responses powered by OpenAI's GPT-4o and GPT-4o-research models
- Chat history saved to Google Sheets for record-keeping
- Real-time database statistics displayed in sidebar

## Database Structure

The application connects to the [NokNok Database](https://docs.google.com/spreadsheets/d/12rCspNRPXyuiJpF_4keonsa1UenwHVOdr8ixpZHnfwI/edit?usp=sharing) with the following structure:

1. **Order**: Contains order information including OrderID, ClientID, Order Date and time, OrderStatus, and more
2. **Client**: Contains client information including ClientID, Client Gender, Client First Name, Client Last Name, and more
3. **Items**: Contains product information including ProductID, Product Name, Price, Category, and stock status

## Setup

1. Clone this repository
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```
4. Set up Google Sheets API access:
   - Create a service account in Google Cloud Console
   - Download the credentials JSON file and save it as `credentials.json` in the project directory
   - OR set the credentials as an environment variable:
   ```
   GOOGLE_CREDENTIALS={"type": "service_account", ... }
   ```
5. Share your Google Sheets with the service account email

## Usage

Run the application with:

```
streamlit run app.py
```

Then:
1. Select your preferred AI model (GPT-4o or GPT-4o-research)
2. Ask questions about orders, clients, or inventory
3. View real-time database statistics in the sidebar
4. Clear chat history using the button in the sidebar when needed

## Requirements

- Python 3.8+
- Streamlit
- OpenAI API key
- Google Sheets API credentials
- Internet connection for API access

## Models

- **GPT-4o**: The standard GPT-4o model, optimized for general-purpose AI chat
<<<<<<< HEAD
- **GPT-4o-research**: A research-focused variant of GPT-4o with enhanced capabilities for academic and research queries 
=======
- **GPT-4o-research**: A research-focused variant of GPT-4o with enhanced capabilities for academic and research queries 
>>>>>>> 8c1ac79 (Initial commit)
>>>>>>> f8e1000
