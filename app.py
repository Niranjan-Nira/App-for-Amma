import streamlit as st
import pandas as pd
from datetime import date
from streamlit_gsheets import GSheetsConnection

# Set up page configuration for better mobile viewing
st.set_page_config(page_title="Daily Collection Tracker", layout="centered", initial_sidebar_state="collapsed")

# The fields we need to collect based on the form
FIELDS = [
    "NPH BR", "NPH RR", "PHH BR", "PHH RR", "AAY BR", "OAP BR",
    "SUGAR", "TD", "OIL", "WHEAT", "AAY SUGAR"
]

# Initialize connection
# The secrets (Service Account JSON & spreadsheet URL) must be in .streamlit/secrets.toml
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # Read the data from Sheet1. 
        # Using ttl=0 to always get the freshest data when writing/reading
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        # If the sheet is empty, or doesn't have our Date column yet
        if df.empty or "Date" not in df.columns:
            return pd.DataFrame(columns=["Date"] + FIELDS)
            
        # Drop any completely empty rows that Google Sheets sometimes reads
        df = df.dropna(how='all') 
        return df
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        st.info("Make sure you've shared your Google Sheet with the Service Account email and set up .streamlit/secrets.toml!")
        return pd.DataFrame(columns=["Date"] + FIELDS)

def save_entry(date_val, entries):
    df = load_data()
    
    # Format current date as a string
    date_str = date_val.strftime("%Y-%m-%d")
    
    # Prepare the new row
    row_dict = {"Date": date_str}
    row_dict.update(entries)
    
    new_df = pd.DataFrame([row_dict])
    
    # If date exists, replace it, otherwise append
    if not df.empty and "Date" in df.columns and date_str in df["Date"].values:
        df = df[df["Date"] != date_str]
        
    # Append the new row to the dataframe
    df = pd.concat([df, new_df], ignore_index=True)
    
    # Update the Google Sheet
    conn.update(worksheet="Sheet1", data=df)
    
    # Clear cache so the next read sees the fresh data
    st.cache_data.clear()
    
    return True

# --- UI Setup ---
st.title("📊 Daily Collection Tracker")

# Use tabs to organize the app
tab1, tab2 = st.tabs(["📝 Daily Entry", "📈 Monthly Totals"])

with tab1:
    st.header("New Daily Entry")
    st.write("Enter the collection quantities for today.")
    
    # Form for daily entry
    with st.form("collection_form"):
        # Select Date
        entry_date = st.date_input("Date", date.today())
        
        st.subheader("Items")
        entries = {}
        
        # Create input fields dynamically
        for field in FIELDS:
            entries[field] = st.number_input(field, min_value=0.0, step=1.0, format="%f")
            
        submit_button = st.form_submit_button(label="Submit Entry")
        
        if submit_button:
            with st.spinner("Saving to Google Sheets..."):
                save_entry(entry_date, entries)
            st.success(f"Successfully saved entry for {entry_date.strftime('%Y-%m-%d')} to Google Sheets!")

with tab2:
    st.header("Monthly Overview")
    
    with st.spinner("Loading data from Google Sheets..."):
        df = load_data()
    
    if df.empty:
        st.info("No data available yet or unable to connect to Google Sheets.")
    else:
        # Ensure Date is datetime type
        df['Date'] = pd.to_datetime(df['Date'])
        
        # Get unique months to filter
        df['Month'] = df['Date'].dt.strftime('%B %Y')
        available_months = df['Month'].unique()
        
        selected_month = st.selectbox("Select Month", available_months)
        
        # Filter data for selected month
        monthly_data = df[df['Month'] == selected_month].copy()
        
        if not monthly_data.empty:
            st.subheader(f"Totals for {selected_month}")
            
            # Extract only the numerical fields for summation (excluding Date and Month)
            try:
                # Convert our fields to numeric just in case reading from Sheets made them strings
                for field in FIELDS:
                    monthly_data[field] = pd.to_numeric(monthly_data[field], errors='coerce').fillna(0)
                    
                totals = monthly_data[FIELDS].sum()
                
                # Display metrics nicely
                col1, col2 = st.columns(2)
                
                # Split items into two columns visually
                half = len(FIELDS) // 2 + 1
                for i, field in enumerate(FIELDS):
                    if i < half:
                        with col1:
                            st.metric(label=field, value=f"{totals[field]:.2f}")
                    else:
                        with col2:
                            st.metric(label=field, value=f"{totals[field]:.2f}")
                            
                st.divider()
                st.write("### All daily entries for this month")
                st.dataframe(monthly_data.drop(columns=['Month']), use_container_width=True)
                
                # Provide CSV download button for Excel
                csv = df.drop(columns=['Month']).to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download All Data for Excel (CSV)",
                    data=csv,
                    file_name="all_collection_data_from_sheets.csv",
                    mime="text/csv",
                )
            except Exception as e:
                st.error("There was an issue processing the numerical data from the sheet. Make sure all entries in the sheet are numbers.")
