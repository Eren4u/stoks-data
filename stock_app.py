import streamlit as st
from datetime import datetime, timedelta, date # Ensure 'date' is imported
import re
import pandas as pd
import yfinance as yf
import requests

# --- HELPER FUNCTIONS ---
def parse_user_date_input(date_str_input, date_name="date"): # Less used now with st.date_input
    formats_to_try = ['%d-%m-%y', '%d-%m-%Y']
    dt_obj = None;
    for fmt in formats_to_try:
        try: dt_obj = datetime.strptime(date_str_input, fmt); break
        except ValueError: continue
    if dt_obj is None: return None, None
    return dt_obj.strftime('%Y-%m-%d'), dt_obj.strftime('%d-%m-%Y')

def get_date_range_from_period_keyword(period_keyword_ui_label, custom_start_date_obj=None, custom_end_date_obj=None):
    today = datetime.today().date() # Use .date() for consistency with st.date_input
    s_yf, s_fn, e_yf, e_fn = None, None, None, None
    period_keyword_map_to_code = {
        "1 Year": "1y", "2 Years": "2y", "3 Years": "3y", "5 Years": "5y", "Max": "max", "Custom Range": "custom"
    }
    period_code = period_keyword_map_to_code.get(period_keyword_ui_label)

    if period_code == "custom":
        if custom_start_date_obj and custom_end_date_obj:
            # custom_start_date_obj and custom_end_date_obj are already datetime.date objects
            if custom_end_date_obj < custom_start_date_obj:
                # This error should ideally be caught by st.date_input's min_value for end_date
                st.sidebar.error("Custom end date cannot be before custom start date.")
                return None, None, None, None
            s_yf = custom_start_date_obj.strftime('%Y-%m-%d')
            s_fn = custom_start_date_obj.strftime('%d-%m-%Y')
            e_yf = custom_end_date_obj.strftime('%Y-%m-%d')
            e_fn = custom_end_date_obj.strftime('%d-%m-%Y')
            return s_yf, s_fn, e_yf, e_fn
        else:
            # This should ideally not be reached if st.date_input has default values
            st.sidebar.error("Custom start or end date is missing for 'Custom Range' selection.")
            return None, None, None, None
    elif period_code:
        e_yf = today.strftime('%Y-%m-%d')
        e_fn = today.strftime('%d-%m-%Y')
        start_date_obj_calc = None # This will be a datetime.date object
        if period_code == '1y': start_date_obj_calc = today - timedelta(days=365)
        elif period_code == '2y': start_date_obj_calc = today - timedelta(days=365*2)
        elif period_code == '3y': start_date_obj_calc = today - timedelta(days=365*3)
        elif period_code == '5y': start_date_obj_calc = today - timedelta(days=365*5)
        elif period_code == 'max':
            s_yf = None # yfinance understands None as max
            s_fn = "inception"
            return s_yf, s_fn, e_yf, e_fn
        
        if start_date_obj_calc:
            s_yf = start_date_obj_calc.strftime('%Y-%m-%d')
            s_fn = start_date_obj_calc.strftime('%d-%m-%Y')
            return s_yf, s_fn, e_yf, e_fn
            
    st.sidebar.error(f"Unknown or invalid date period processing: {period_keyword_ui_label}")
    return None, None, None, None

def sanitize_filename(name):
    if not name: return "unknown_company"
    name = re.sub(r'[<>:"/\\|?*]', '_', name); name = re.sub(r'\s+', '_', name)
    return name.strip('_')

def search_yahoo_for_tickers(search_query, result_count=20):
    # ... (search_yahoo_for_tickers function remains the same)
    if not search_query: return []
    search_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={search_query}&count={result_count}"
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; StreamlitStockApp/1.0)'}
    try:
        response = requests.get(search_url, headers=headers, timeout=10); response.raise_for_status()
        data = response.json(); results = data.get('quotes', [])
        formatted_results = []
        for item in results:
            name = item.get('longname', item.get('shortname', 'N/A')); symbol = item.get('symbol', 'N/A')
            exchange = item.get('exchDisp', item.get('exchange', 'N/A'))
            if symbol != 'N/A' and name != 'N/A':
                formatted_results.append({'display': f"{symbol} - {name} ({exchange})", 'symbol': symbol})
        return formatted_results
    except requests.exceptions.RequestException as e: st.error(f"Ticker search HTTP error: {e}"); return []
    except ValueError: st.error("Error parsing ticker search results (JSON)."); return []
    except Exception as e: st.error(f"Unexpected error in ticker search: {e}"); return []
# --- END OF HELPER FUNCTIONS ---

def main():
    st.set_page_config(page_title="Stock Downloader", layout="wide", initial_sidebar_state="expanded")
    st.title("📈 Stock Data Downloader")
    st.markdown("---")

    # Define a very early date for min_value of date_input
    MIN_DATE = date(1970, 1, 1) # Yahoo data often doesn't go much earlier than this for many stocks

    default_values = {
        'criteria_processed_successfully': False, 'processed_criteria': {}, 'fetched_data_df': None,
        'ui_company_search_query': "", 'ui_ticker_search_results_list_of_dicts': [],
        'ui_selected_ticker_display_option': None, 'ui_selected_date_period': "1 Year",
        # Ensure default custom dates are datetime.date objects
        'ui_custom_start_date': (datetime.today() - timedelta(days=365)).date(),
        'ui_custom_end_date': datetime.today().date(),
        'ui_selected_data_type_label': "Historical Prices (OHLCV)",
        'ui_selected_interval_label': "Daily"
    }
    for key, value in default_values.items():
        if key not in st.session_state: st.session_state[key] = value

    with st.sidebar:
        with st.expander("📊 **Step 1: Input Criteria**", expanded=True):
            # ... (Ticker search UI remains the same) ...
            st.session_state.ui_company_search_query = st.text_input(
                "Search Company Name or Ticker:", value=st.session_state.ui_company_search_query,
                key="company_search_widget", placeholder="e.g., Apple or AAPL"
            )
            if st.button("🔍 Search Tickers", key="search_ticker_btn", use_container_width=True):
                if st.session_state.ui_company_search_query:
                    with st.spinner("Searching..."):
                        st.session_state.ui_ticker_search_results_list_of_dicts = search_yahoo_for_tickers(st.session_state.ui_company_search_query, result_count=25)
                    if not st.session_state.ui_ticker_search_results_list_of_dicts: st.warning("No tickers found.")
                    st.session_state.ui_selected_ticker_display_option = None
                else: st.warning("Please enter a search query.")

            if st.session_state.ui_ticker_search_results_list_of_dicts:
                display_options = ["-- Select a Ticker --"] + [res['display'] for res in st.session_state.ui_ticker_search_results_list_of_dicts]
                current_selection_display = st.session_state.ui_selected_ticker_display_option
                current_index = 0
                if current_selection_display and current_selection_display in display_options:
                    current_index = display_options.index(current_selection_display)
                st.session_state.ui_selected_ticker_display_option = st.selectbox(
                    "Select Ticker from Results:", options=display_options, index=current_index,
                    key="ticker_select_widget", help="Format: SYMBOL - Name (Exchange)"
                )
            elif st.session_state.ui_company_search_query:
                st.info("If direct ticker entry, ensure it's correct (e.g. AAPL, MSFT.MX)")


            date_period_options = ["1 Year", "2 Years", "3 Years", "5 Years", "Max", "Custom Range"]
            st.session_state.ui_selected_date_period = st.selectbox(
                "🗓️ Select Date Period:", options=date_period_options,
                index=date_period_options.index(st.session_state.ui_selected_date_period), key="date_period_widget"
            )
            if st.session_state.ui_selected_date_period == "Custom Range":
                c1, c2 = st.columns(2)
                with c1:
                    st.session_state.ui_custom_start_date = st.date_input(
                        "Start Date:", value=st.session_state.ui_custom_start_date,
                        min_value=MIN_DATE, # MODIFIED: Set min_value
                        max_value=datetime.today().date(), # Use .date()
                        key="custom_start_date_widget"
                    )
                with c2:
                    st.session_state.ui_custom_end_date = st.date_input(
                        "End Date:", value=st.session_state.ui_custom_end_date,
                        min_value=st.session_state.ui_custom_start_date, # Dynamically set based on start
                        max_value=datetime.today().date(), # Use .date()
                        key="custom_end_date_widget"
                    )
            # ... (Data Type and Interval Selectbox UI remains the same) ...
            data_type_options_map = {"Historical Prices (OHLCV)": "1", "Dividends": "2", "Stock Splits": "3", "Capital Gains": "4"}
            data_type_labels = list(data_type_options_map.keys()); default_dt_idx = 0
            try: default_dt_idx = data_type_labels.index(st.session_state.ui_selected_data_type_label)
            except ValueError: pass
            st.session_state.ui_selected_data_type_label = st.selectbox("📈 Select Data Type:", options=data_type_labels, index=default_dt_idx, key="data_type_widget")
            selected_data_type_code = data_type_options_map[st.session_state.ui_selected_data_type_label]

            selected_interval_code_ui = None
            if selected_data_type_code == "1":
                interval_options_map = {"Daily": "d", "Weekly": "w", "Monthly": "m"}; interval_labels = list(interval_options_map.keys()); default_interval_idx = 0
                try: default_interval_idx = interval_labels.index(st.session_state.ui_selected_interval_label)
                except ValueError: pass
                st.session_state.ui_selected_interval_label = st.selectbox("📊 Select Interval:", options=interval_labels, index=default_interval_idx, key="interval_widget")
                selected_interval_code_ui = interval_options_map[st.session_state.ui_selected_interval_label]


            if st.button("📊 Process & Fetch Data", key="process_fetch_button", use_container_width=True, type="primary"):
                # ... (Criteria processing and Data Fetching logic largely remains the same) ...
                # ... (Ensure it correctly uses datetime.date objects from st.date_input for custom range) ...
                st.session_state.criteria_processed_successfully = False
                st.session_state.fetched_data_df = None

                valid_inputs = True; temp_criteria = {}
                actual_ticker_symbol = None
                selected_display_opt = st.session_state.ui_selected_ticker_display_option
                if selected_display_opt and selected_display_opt != "-- Select a Ticker --":
                    for res_dict in st.session_state.ui_ticker_search_results_list_of_dicts:
                        if res_dict['display'] == selected_display_opt: actual_ticker_symbol = res_dict['symbol']; break
                    if not actual_ticker_symbol: st.error("Error retrieving selected ticker symbol."); valid_inputs = False
                elif st.session_state.ui_company_search_query:
                     actual_ticker_symbol = st.session_state.ui_company_search_query.upper()
                     st.info(f"Attempting to use direct ticker: '{actual_ticker_symbol}'")
                else: st.error("Please select or enter a ticker."); valid_inputs = False
                if actual_ticker_symbol: temp_criteria['ticker'] = actual_ticker_symbol
                else: valid_inputs = False

                if valid_inputs: # Proceed only if ticker is resolved
                    # Pass datetime.date objects directly for custom range
                    s_yf, s_fn, e_yf, e_fn = get_date_range_from_period_keyword(
                        st.session_state.ui_selected_date_period,
                        custom_start_date_obj=st.session_state.ui_custom_start_date if st.session_state.ui_selected_date_period == "Custom Range" else None,
                        custom_end_date_obj=st.session_state.ui_custom_end_date if st.session_state.ui_selected_date_period == "Custom Range" else None
                    )
                    if s_yf is None and st.session_state.ui_selected_date_period not in ["Max", "Custom Range"]:
                        st.error("Date processing failed."); valid_inputs = False
                    elif st.session_state.ui_selected_date_period == "Custom Range" and (s_yf is None or e_yf is None):
                        # Error message is handled by get_date_range_from_period_keyword
                        valid_inputs = False
                    else: temp_criteria.update({'start_date_yf':s_yf, 'start_date_filename':s_fn, 'end_date_yf':e_yf, 'end_date_filename':e_fn})

                if valid_inputs: # Proceed only if dates are also resolved
                    temp_criteria['data_type_code'] = selected_data_type_code
                    suffix_map = {'1': "historical_prices", '2': "dividends", '3': "stock_splits", '4': "capital_gains"}
                    temp_criteria['base_file_description_suffix'] = suffix_map.get(selected_data_type_code, "data")
                    if selected_data_type_code == "1" and selected_interval_code_ui:
                        interval_map_yf = {'d': ('1d', "daily"), 'w': ('1wk', "weekly"), 'm': ('1mo', "monthly")}
                        yf_interval, interval_desc = interval_map_yf[selected_interval_code_ui]
                        temp_criteria.update({'interval_yf': yf_interval, 'interval_desc': interval_desc})
                        temp_criteria['base_file_description_suffix'] = f"historical_prices_{interval_desc}"
                    
                    st.session_state.processed_criteria = temp_criteria
                    st.session_state.criteria_processed_successfully = True
                
                if st.session_state.criteria_processed_successfully:
                    crit = st.session_state.processed_criteria
                    ticker_str = crit.get('ticker'); raw_fetched_data = None
                    with st.spinner(f"Fetching data for {ticker_str}..."):
                        try:
                            ticker_obj = yf.Ticker(ticker_str)
                            if crit.get('data_type_code') != "1" and not ticker_obj.info:
                                 st.warning(f"Could not get company info for '{ticker_str}'.")
                            
                            if crit.get('data_type_code') == "1":
                                end_date_exclusive_yf = (pd.to_datetime(crit.get('end_date_yf')) + timedelta(days=1)).strftime('%Y-%m-%d') if crit.get('end_date_yf') else None
                                raw_fetched_data = yf.download(ticker_str, start=crit.get('start_date_yf'), end=end_date_exclusive_yf,
                                                             interval=crit.get('interval_yf'), progress=False, timeout=20)
                            elif crit.get('data_type_code') == "2": raw_fetched_data = ticker_obj.dividends
                            elif crit.get('data_type_code') == "3": raw_fetched_data = ticker_obj.splits
                            elif crit.get('data_type_code') == "4": raw_fetched_data = ticker_obj.capital_gains
                            
                            final_data_to_show = None
                            if raw_fetched_data is not None and not raw_fetched_data.empty:
                                if crit.get('data_type_code') == "1": final_data_to_show = raw_fetched_data
                                else:
                                    temp_data_filter = raw_fetched_data.copy(); s_yf_filter, e_yf_filter = crit.get('start_date_yf'), crit.get('end_date_yf')
                                    if isinstance(temp_data_filter.index, pd.DatetimeIndex):
                                        idx_naive = temp_data_filter.index.tz_localize(None).date if temp_data_filter.index.tz is not None else temp_data_filter.index.date
                                        if s_yf_filter: temp_data_filter = temp_data_filter[idx_naive >= pd.to_datetime(s_yf_filter).date()]
                                        if not temp_data_filter.empty and e_yf_filter:
                                            idx_naive_end = temp_data_filter.index.tz_localize(None).date if temp_data_filter.index.tz is not None else temp_data_filter.index.date
                                            temp_data_filter = temp_data_filter[idx_naive_end <= pd.to_datetime(e_yf_filter).date()]
                                        final_data_to_show = temp_data_filter
                                    elif isinstance(temp_data_filter, pd.DataFrame) and 'Date' in temp_data_filter.columns:
                                        temp_data_filter['Date'] = pd.to_datetime(temp_data_filter['Date']).dt.tz_localize(None)
                                        mask = pd.Series(True, index=temp_data_filter.index)
                                        if s_yf_filter: mask &= (temp_data_filter['Date'] >= pd.to_datetime(s_yf_filter))
                                        if e_yf_filter: mask &= (temp_data_filter['Date'] <= pd.to_datetime(e_yf_filter))
                                        final_data_to_show = temp_data_filter.loc[mask]
                                    else: final_data_to_show = raw_fetched_data
                            
                            if final_data_to_show is not None and not final_data_to_show.empty:
                                if isinstance(final_data_to_show, pd.Series):
                                    final_data_to_show = final_data_to_show.to_frame(name=crit.get("base_file_description_suffix", "Data"))
                                st.session_state.fetched_data_df = final_data_to_show
                                st.success("✅ Data fetched successfully!")
                            elif final_data_to_show is not None and final_data_to_show.empty:
                                st.info("ℹ️ No data found for the given criteria after filtering.")
                            else: st.warning("⚠️ Could not fetch data or no data available from source.")
                        except Exception as e: st.error(f"❌ Error during data fetching: {e}")
                else:
                    if 'ticker' not in temp_criteria and not st.session_state.ui_company_search_query : st.error("Ticker selection is required.")
                    # else: st.warning("Could not fetch data as criteria setting failed. Please check inputs.") # Already handled by other errors
                
                st.rerun()

        st.markdown("---")
        if st.button("🔄 Reset All Inputs", key="reset_all_button_sidebar", use_container_width=True):
            for key_to_reset in default_values: st.session_state[key_to_reset] = default_values[key_to_reset]
            st.rerun()

    # --- Main Page Display ---
    # ... (Main page display logic remains the same, showing criteria if set, and data preview/download if fetched) ...
    if not st.session_state.criteria_processed_successfully:
        st.info("👋 Welcome! Please set your data download criteria using the sidebar.")
    else:
        st.subheader("📋 Current Criteria")
        crit_display = st.session_state.processed_criteria
        col1, col2, col3 = st.columns(3)
        with col1: st.metric(label="Ticker", value=crit_display.get('ticker', 'N/A'))
        with col2: st.metric(label="Data Type", value=crit_display.get('base_file_description_suffix', 'N/A').replace("_", " ").title())
        if crit_display.get('interval_yf'):
             with col3: st.metric(label="Interval", value=crit_display.get('interval_desc', 'N/A').title())
        st.markdown(f"**Date Range (YF):** `{crit_display.get('start_date_yf', 'Max')}` to `{crit_display.get('end_date_yf', 'Today')}`")
        st.markdown("---")

        if st.session_state.fetched_data_df is not None and not st.session_state.fetched_data_df.empty:
            st.subheader("📄 Data Preview")
            st.dataframe(st.session_state.fetched_data_df.head())
            csv_data = st.session_state.fetched_data_df.to_csv(index=True).encode('utf-8')
            crit_dl = st.session_state.processed_criteria
            fn_company = sanitize_filename(crit_dl.get("ticker", "unknown")); fn_suffix = crit_dl.get("base_file_description_suffix", "data")
            fn_start = crit_dl.get("start_date_filename", "inception"); fn_end = crit_dl.get("end_date_filename", "today")
            file_name = f"{fn_company}_{fn_suffix}_{fn_start}_to_{fn_end}.csv"
            file_name = re.sub(r'_+', '_', file_name).strip('_')
            st.download_button(label="📥 Download Data as CSV", data=csv_data, file_name=file_name, mime='text/csv', key="download_csv_button", use_container_width=True)
        elif st.session_state.criteria_processed_successfully: # Criteria were set, but fetch might have failed or found no data
             st.caption("_Data will appear here after successful fetching, or an error/info message if issues occur._")


    st.markdown("---")
    st.caption("Built with [Streamlit](https://streamlit.io) & [yfinance](https://pypi.org/project/yfinance/) by Aarush")

if __name__ == '__main__':
    main()
