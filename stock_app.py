import streamlit as st
from datetime import datetime, timedelta
import re
import pandas as pd
import yfinance as yf
import requests

# --- HELPER FUNCTIONS ---
def parse_user_date_input(date_str_input, date_name="date"):
    formats_to_try = ['%d-%m-%y', '%d-%m-%Y']
    dt_obj = None
    for fmt in formats_to_try:
        try: dt_obj = datetime.strptime(date_str_input, fmt); break
        except ValueError: continue
    if dt_obj is None: return None, None
    return dt_obj.strftime('%Y-%m-%d'), dt_obj.strftime('%d-%m-%Y')

def get_date_range_from_period_keyword(period_keyword_ui_label, custom_start_date_obj=None, custom_end_date_obj=None):
    today = datetime.today()
    s_yf, s_fn, e_yf, e_fn = None, None, None, None
    period_keyword_map_to_code = {
        "1 Year": "1y", "2 Years": "2y", "3 Years": "3y", "5 Years": "5y", "Max": "max", "Custom Range": "custom"
    }
    period_code = period_keyword_map_to_code.get(period_keyword_ui_label)

    if period_code == "custom":
        if custom_start_date_obj and custom_end_date_obj:
            if custom_end_date_obj < custom_start_date_obj:
                st.sidebar.error("Custom end date cannot be before start.")
                return None, None, None, None
            s_yf = custom_start_date_obj.strftime('%Y-%m-%d'); s_fn = custom_start_date_obj.strftime('%d-%m-%Y')
            e_yf = custom_end_date_obj.strftime('%Y-%m-%d'); e_fn = custom_end_date_obj.strftime('%d-%m-%Y')
            return s_yf, s_fn, e_yf, e_fn
        else:
            st.sidebar.error("Custom start or end date missing."); return None, None, None, None
    elif period_code:
        e_yf = today.strftime('%Y-%m-%d'); e_fn = today.strftime('%d-%m-%Y')
        start_date_obj_calc = None
        if period_code == '1y': start_date_obj_calc = today - timedelta(days=365)
        elif period_code == '2y': start_date_obj_calc = today - timedelta(days=365*2)
        elif period_code == '3y': start_date_obj_calc = today - timedelta(days=365*3)
        elif period_code == '5y': start_date_obj_calc = today - timedelta(days=365*5)
        elif period_code == 'max': s_yf = None; s_fn = "inception"; return s_yf, s_fn, e_yf, e_fn
        if start_date_obj_calc:
            s_yf = start_date_obj_calc.strftime('%Y-%m-%d'); s_fn = start_date_obj_calc.strftime('%d-%m-%Y')
            return s_yf, s_fn, e_yf, e_fn
    st.sidebar.error(f"Unknown date period: {period_keyword_ui_label}"); return None, None, None, None

def sanitize_filename(name):
    if not name: return "unknown_company"
    name = re.sub(r'[<>:"/\\|?*]', '_', name); name = re.sub(r'\s+', '_', name)
    return name.strip('_')

def search_yahoo_for_tickers(search_query, result_count=20): # Added result_count parameter
    """Searches Yahoo Finance for tickers and returns a list of potential matches."""
    if not search_query: return []
    # Try to request more results, though API might still limit
    search_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={search_query}&count={result_count}"
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; StreamlitStockApp/1.0)'}
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get('quotes', []) # This is the list from Yahoo
        # st.write(f"DEBUG: Yahoo API returned {len(results)} quotes.") # For debugging if needed

        formatted_results = []
        for item in results: # Process all items returned by Yahoo
            name = item.get('longname', item.get('shortname', 'N/A'))
            symbol = item.get('symbol', 'N/A')
            exchange = item.get('exchDisp', item.get('exchange', 'N/A'))
            if symbol != 'N/A' and name != 'N/A':
                display_text = f"{symbol} - {name} ({exchange})"
                formatted_results.append({'display': display_text, 'symbol': symbol})
        return formatted_results
    except requests.exceptions.RequestException as e: st.error(f"Ticker search HTTP error: {e}"); return []
    except ValueError: st.error("Error parsing ticker search results (JSON)."); return []
    except Exception as e: st.error(f"Unexpected error in ticker search: {e}"); return []
# --- END OF HELPER FUNCTIONS ---

def main():
    st.set_page_config(page_title="Stock Downloader", layout="wide", initial_sidebar_state="expanded")
    st.title("📈 Stock Data Downloader")
    st.markdown("---")

    default_values = {
        'criteria_submitted': False, 'processed_criteria': {}, 'fetched_data_df': None,
        'ui_company_search_query': "", 'ui_ticker_search_results_list_of_dicts': [],
        'ui_selected_ticker_display_option': None, 'ui_selected_date_period': "1 Year",
        'ui_custom_start_date': datetime.today() - timedelta(days=365),
        'ui_custom_end_date': datetime.today(),
        'ui_selected_data_type_label': "Historical Prices (OHLCV)",
        'ui_selected_interval_label': "Daily"
    }
    for key, value in default_values.items():
        if key not in st.session_state: st.session_state[key] = value

    with st.sidebar:
        # CHANGED: Expander is now always expanded by default, user can collapse.
        # Or remove the expander altogether if you prefer inputs to always be visible.
        with st.expander("📊 **Step 1: Input Criteria**", expanded=True):
            st.session_state.ui_company_search_query = st.text_input(
                "Search Company Name or Ticker:", value=st.session_state.ui_company_search_query,
                key="company_search_widget", placeholder="e.g., Apple or AAPL"
            )
            if st.button("🔍 Search Tickers", key="search_ticker_btn", use_container_width=True):
                if st.session_state.ui_company_search_query:
                    with st.spinner("Searching..."):
                        # Pass a higher count to try and get more results
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
                        max_value=datetime.today(), key="custom_start_date_widget"
                    )
                with c2:
                    st.session_state.ui_custom_end_date = st.date_input(
                        "End Date:", value=st.session_state.ui_custom_end_date,
                        max_value=datetime.today(), min_value=st.session_state.ui_custom_start_date,
                        key="custom_end_date_widget"
                    )

            data_type_options_map = {"Historical Prices (OHLCV)": "1", "Dividends": "2", "Stock Splits": "3", "Capital Gains": "4"}
            data_type_labels = list(data_type_options_map.keys())
            try: default_dt_idx = data_type_labels.index(st.session_state.ui_selected_data_type_label)
            except ValueError: default_dt_idx = 0
            st.session_state.ui_selected_data_type_label = st.selectbox("📈 Select Data Type:", options=data_type_labels, index=default_dt_idx, key="data_type_widget")
            selected_data_type_code = data_type_options_map[st.session_state.ui_selected_data_type_label]

            selected_interval_code_ui = None
            if selected_data_type_code == "1":
                interval_options_map = {"Daily": "d", "Weekly": "w", "Monthly": "m"}
                interval_labels = list(interval_options_map.keys())
                try: default_interval_idx = interval_labels.index(st.session_state.ui_selected_interval_label)
                except ValueError: default_interval_idx = 0
                st.session_state.ui_selected_interval_label = st.selectbox("📊 Select Interval:", options=interval_labels, index=default_interval_idx, key="interval_widget")
                selected_interval_code_ui = interval_options_map[st.session_state.ui_selected_interval_label]

            if st.button("✅ Set Criteria", key="set_criteria_button", use_container_width=True, type="primary"):
                valid_inputs = True; temp_criteria = {}
                actual_ticker_symbol = None
                selected_display_opt = st.session_state.ui_selected_ticker_display_option
                if selected_display_opt and selected_display_opt != "-- Select a Ticker --":
                    for res_dict in st.session_state.ui_ticker_search_results_list_of_dicts:
                        if res_dict['display'] == selected_display_opt: actual_ticker_symbol = res_dict['symbol']; break
                    if not actual_ticker_symbol: st.error("Error retrieving selected ticker symbol."); valid_inputs = False
                elif st.session_state.ui_company_search_query:
                     st.warning(f"No ticker selected. Using '{st.session_state.ui_company_search_query.upper()}' as direct ticker.")
                     actual_ticker_symbol = st.session_state.ui_company_search_query.upper()
                else: st.error("Please select or enter a ticker."); valid_inputs = False
                if actual_ticker_symbol: temp_criteria['ticker'] = actual_ticker_symbol
                else: valid_inputs = False

                s_yf, s_fn, e_yf, e_fn = get_date_range_from_period_keyword(
                    st.session_state.ui_selected_date_period,
                    st.session_state.ui_custom_start_date if st.session_state.ui_selected_date_period == "Custom Range" else None,
                    st.session_state.ui_custom_end_date if st.session_state.ui_selected_date_period == "Custom Range" else None)
                if s_yf is None and st.session_state.ui_selected_date_period not in ["Max", "Custom Range"]:
                    st.error("Date processing failed."); valid_inputs = False
                elif st.session_state.ui_selected_date_period == "Custom Range" and (s_yf is None or e_yf is None): valid_inputs = False
                else: temp_criteria.update({'start_date_yf':s_yf, 'start_date_filename':s_fn, 'end_date_yf':e_yf, 'end_date_filename':e_fn})

                if valid_inputs:
                    temp_criteria['data_type_code'] = selected_data_type_code
                    suffix_map = {'1': "historical_prices", '2': "dividends", '3': "stock_splits", '4': "capital_gains"}
                    temp_criteria['base_file_description_suffix'] = suffix_map.get(selected_data_type_code, "data")
                    if selected_data_type_code == "1" and selected_interval_code_ui:
                        interval_map_yf = {'d': ('1d', "daily"), 'w': ('1wk', "weekly"), 'm': ('1mo', "monthly")}
                        yf_interval, interval_desc = interval_map_yf[selected_interval_code_ui]
                        temp_criteria.update({'interval_yf': yf_interval, 'interval_desc': interval_desc})
                        temp_criteria['base_file_description_suffix'] = f"historical_prices_{interval_desc}"
                    st.session_state.processed_criteria = temp_criteria
                    st.session_state.criteria_submitted = True; st.session_state.fetched_data_df = None
                    st.success("Criteria Set!")
                    st.rerun()
        
        st.markdown("---")
        if st.button("🔄 Reset All Inputs", key="reset_all_button_sidebar", use_container_width=True):
            for key_to_reset in default_values: st.session_state[key_to_reset] = default_values[key_to_reset]
            st.rerun()

    # --- Main Page Display ---
    if not st.session_state.criteria_submitted:
        st.info("👋 Welcome! Please set your data download criteria using the sidebar.")
        # ... (Instructions)
    else:
        st.subheader("📋 Current Criteria")
        crit_display = st.session_state.processed_criteria
        col1, col2, col3 = st.columns(3) # Use 3 columns for better spacing
        with col1: st.metric(label="Ticker", value=crit_display.get('ticker', 'N/A'))
        with col2: st.metric(label="Data Type", value=crit_display.get('base_file_description_suffix', 'N/A').replace("_", " ").title())
        if crit_display.get('interval_yf'):
             with col3: st.metric(label="Interval", value=crit_display.get('interval_desc', 'N/A').title())
        
        st.markdown(f"**Date Range (for Yahoo Finance):** `{crit_display.get('start_date_yf', 'Max')}` to `{crit_display.get('end_date_yf', 'Today')}`")
        st.markdown("---")

        if st.button("🚀 Fetch Data", key="fetch_data_button", use_container_width=True, type="primary"):
            st.session_state.fetched_data_df = None; crit = st.session_state.processed_criteria
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
                    
                    final_data_to_show = None # This will hold the data after filtering
                    if raw_fetched_data is not None and not raw_fetched_data.empty:
                        if crit.get('data_type_code') == "1": final_data_to_show = raw_fetched_data # yf.download handles dates
                        else: # Manual filtering for non-OHLCV
                            temp_data_filter = raw_fetched_data.copy()
                            s_yf_filter, e_yf_filter = crit.get('start_date_yf'), crit.get('end_date_yf')
                            if isinstance(temp_data_filter.index, pd.DatetimeIndex):
                                idx_naive = temp_data_filter.index.tz_localize(None).date if temp_data_filter.index.tz is not None else temp_data_filter.index.date
                                if s_yf_filter: temp_data_filter = temp_data_filter[idx_naive >= pd.to_datetime(s_yf_filter).date()]
                                if not temp_data_filter.empty and e_yf_filter:
                                    idx_naive_end = temp_data_filter.index.tz_localize(None).date if temp_data_filter.index.tz is not None else temp_data_filter.index.date
                                    temp_data_filter = temp_data_filter[idx_naive_end <= pd.to_datetime(e_yf_filter).date()]
                                final_data_to_show = temp_data_filter
                            elif isinstance(temp_data_filter, pd.DataFrame) and 'Date' in temp_data_filter.columns: # e.g. Capital Gains
                                temp_data_filter['Date'] = pd.to_datetime(temp_data_filter['Date']).dt.tz_localize(None)
                                mask = pd.Series(True, index=temp_data_filter.index)
                                if s_yf_filter: mask &= (temp_data_filter['Date'] >= pd.to_datetime(s_yf_filter))
                                if e_yf_filter: mask &= (temp_data_filter['Date'] <= pd.to_datetime(e_yf_filter))
                                final_data_to_show = temp_data_filter.loc[mask]
                            else: final_data_to_show = raw_fetched_data # Fallback if format is unexpected
                    
                    if final_data_to_show is not None and not final_data_to_show.empty:
                        if isinstance(final_data_to_show, pd.Series):
                            final_data_to_show = final_data_to_show.to_frame(name=crit.get("base_file_description_suffix", "Data"))
                        st.session_state.fetched_data_df = final_data_to_show
                        st.success("✅ Data fetched successfully!")
                    elif final_data_to_show is not None and final_data_to_show.empty: # Empty after filtering
                        st.info("ℹ️ No data found for the given criteria after filtering (or data was originally empty).")
                    else: # raw_fetched_data was None or empty
                        st.warning("⚠️ Could not fetch data or no data available from the source for this ticker/period.")
                except Exception as e:
                    st.error(f"❌ Error during data fetching: {e}")
                    # import traceback; st.text(traceback.format_exc()) # For more detailed debug
            st.rerun()

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
    
    st.markdown("---")
    st.caption("Built with [Streamlit](https://streamlit.io) & [yfinance](https://pypi.org/project/yfinance/) by Aarush")

if __name__ == '__main__':
    main()
