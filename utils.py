# import pandas as pd
# import jdatetime, requests
# import json, pytz
# import numpy as np
# from aautils.functions import *
# from aautils.classes import *
# from aautils.ewi_functions import *
# import warnings
# import finpy_tse
# import psycopg2

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# import finpy_tse as fpy
import sqlalchemy
from sqlalchemy import create_engine
import jdatetime
from datetime import date
from datetime import datetime

def connent_db(database_name, server_name, port):
    connection_string = (
        f'mssql+pyodbc://{server_name}:{port}/'
        f'{database_name}?driver=SQL+Server&trusted_connection=yes'
    )
    engine = create_engine(connection_string)
    con = engine.raw_connection()
    cur = con.cursor()
    return con, cur, engine

def read_from_db(query=None, database_name = 'General', server_name = '10.1.17.7', port = 1433):
    # Build the connection using the modified function
    con, cur, engine = connent_db(database_name, server_name, port)
            
    # Use Pandas to execute the query and fetch the results into a DataFrame
    df = pd.read_sql_query(query, con)

    # Close the connection
    con.close()
    
    return df

def run_query_and_get_result(query, db_info):
    conn = psycopg2.connect(**db_info)
    result_df = pd.read_sql_query(query, conn)
    conn.close()
    return result_df


def greg_to_jalali(miladi_text):
    import jdatetime
    return str(jdatetime.date.fromgregorian(day=int(miladi_text[-2:]) ,month=int(miladi_text[5:7]),year=int(miladi_text[:4])))

def calculate_n_day_return_and_var(df, n, confidence_level):
    """
    Calculate n-day returns and Value at Risk (VaR) given a dataframe with daily returns.

    Parameters:
    df (pd.DataFrame): A dataframe containing a 'return' column with daily returns.
    n (int): Number of days over which to calculate the return.
    confidence_level (float): Confidence level for VaR (e.g., 0.95 for 95%).

    Returns:
    float: n-day return as a percentage.
    float: Value at Risk (VaR) for the n-day period as a percentage.
    """
    
    # Check if n is valid
    if n <= 0:
        raise ValueError("n must be a positive integer.")

    # Calculate the VaR for n-day returns
    # We can use the normal distribution assumption to estimate VaR
    if len(df) < n:
        raise ValueError("Not enough data to calculate n-day returns.")
    
    # Calculate n-day returns series for VaR computation
    n_day_returns_series = (df['return']).rolling(window=n).apply(np.prod, raw=True) - 1
    
    # Calculate VaR at the specified confidence level
    var = np.percentile(n_day_returns_series.dropna(), (1 - confidence_level) * 100)

    return var * 100  # Return as percentages


def max_drawdown(df, cumulative_column):
    """
    Calculate the maximum drawdown of a portfolio given a dataframe with a cumulative return column.

    Parameters:
    df (pd.DataFrame): A dataframe containing a 'cumulative' column with cumulative returns.

    Returns:
    float: The maximum drawdown value as a percentage.
    """
    
    # Ensure the 'cumulative' column is sorted and convert to a series
    cumulative_returns = df[cumulative_column]
    
    # Calculate the running maximum
    running_max = cumulative_returns.cummax()
    
    # Calculate the drawdowns
    drawdowns = (cumulative_returns - running_max) / running_max
    
    # Calculate and return maximum drawdown
    max_drawdown_value = drawdowns.min()
    
    return max_drawdown_value

def sharpe_ratio(df, portfolio_return_column, risk_free_rate_column):
    """
    Calculate the Sharpe Ratio of a portfolio given a dataframe with daily returns and risk-free rate.

    Parameters:
    df (pd.DataFrame): A dataframe containing 'return' column with daily returns and 'hami' column with daily risk-free rates.
    risk_free_rate_annual (float): Annual risk-free rate as a decimal. Default is 0.

    Returns:
    float: The Sharpe ratio of the portfolio.
    """

    # Calculate excess daily returns
    df['excess_return'] = df[portfolio_return_column] - df[risk_free_rate_column]
    
    # Calculate the average excess return and standard deviation of the excess returns
    average_excess_return = df['excess_return'].mean()
    excess_return_std = df['excess_return'].std()

    # Calculate the Sharpe Ratio
    if excess_return_std == 0:
        return np.nan  # To avoid division by zero
    
    sharpe_ratio_value = average_excess_return / excess_return_std

    # Annualizing the Sharpe Ratio (since we are using daily returns)
    sharpe_ratio_annualized = sharpe_ratio_value * np.sqrt(252)  # 252 trading days in a year

    return sharpe_ratio_annualized

# A function that simulates the outcomes of investments, given required information

def simulator(df, start_date, initial_investment, increase_rate, horizon_days, asset_weights):
    # Keep data related to after the start of simulation
    df = df[df.jalali >= start_date]
    df = df.head(horizon_days)
    
    # If the days for which we have data is less than the horizon, then we cannot simulate the transactions
    if len(df) != horizon_days:
        return [np.nan, np.nan, np.nan]
    
    # Add columns with None values for the value of each fund in the portfolio
    df['pishtaz_value'] = None
    df['ayar_value'] = None
    df['hami_value'] = None
    
    # Add a column for keeping cash inflows to the portfolio
    df['inflow'] = 0
    df.reset_index(drop = True, inplace = True)
    
    # One the first day, the initial investment cash is divided among asset classes
    df.loc[0, 'pishtaz_value'] = initial_investment * asset_weights[0]
    df.loc[0, 'ayar_value'] = initial_investment * asset_weights[1]
    df.loc[0, 'hami_value'] = initial_investment * asset_weights[2]
    
    last_inflow_date = start_date
    last_inflow = initial_investment
    for i in range(1, df.shape[0]):
        df.loc[i, 'pishtaz_value'] = df.loc[i-1, 'pishtaz_value'] * df.loc[i, 'pishtaz']
        df.loc[i, 'ayar_value'] = df.loc[i-1, 'ayar_value'] * df.loc[i, 'ayar']
        df.loc[i, 'hami_value'] = df.loc[i-1, 'hami_value'] * df.loc[i, 'hami']

        # For the beginning of each month, we have cash inflows
        if df.loc[i, 'jalali'].endswith('-01'):
            
            # In each new Jalali year, increase the amount of monthly investments, given the predetermined rate.
            if df.loc[i, 'jalali'][:4] != last_inflow_date[:4]:
                last_inflow = last_inflow * (1 + increase_rate)

            df.loc[i, 'inflow'] = last_inflow

            df.loc[i, 'pishtaz_value'] = df.loc[i, 'pishtaz_value'] + last_inflow * asset_weights[0]
            df.loc[i, 'ayar_value'] = df.loc[i, 'ayar_value'] + last_inflow * asset_weights[1]
            df.loc[i, 'hami_value'] = df.loc[i, 'hami_value'] + last_inflow * asset_weights[2]

            last_inflow_date = df.loc[i, 'jalali']
    
    # The value of portfolio, is equal to the summation of the values of all asset classes.
    df['portfolio'] = df['pishtaz_value'] + df['ayar_value'] + df['hami_value']
    
    # Calculate the daily returns, adjusting cash flows' effect
    df['return'] = 1
    for i in range(1, df.shape[0]):
        df.loc[i, 'return'] = (df.loc[i, 'portfolio'] - df.loc[i, 'inflow']) / df.loc[i-1, 'portfolio']
    df['cumulative'] = df['return'].cumprod()
    
    # Calculate return and risk metrics using defined funcitons
    cumulative_return = df['return'].prod() - 1
    cagr = (df['return'].prod()) ** (1 / (horizon_days / 365)) - 1
    max_dd = max_drawdown(df, 'cumulative')
    sharpe = sharpe_ratio(df, 'return', 'hami')
    var = calculate_n_day_return_and_var(df, n = 10, confidence_level = 0.95)
    
    return [cumulative_return, cagr, max_dd, sharpe, var]

# A similar simulator function. This one returns the whole dataframe to be used for visualizations

def simulator2(df, start_date, initial_investment, increase_rate, horizon_days, asset_weights):
    df = df[df.jalali >= start_date]
    df = df.head(horizon_days)
    if len(df) != horizon_days:
        return [np.nan, np.nan, np.nan]
    
    df['pishtaz_value'] = None
    df['ayar_value'] = None
    df['hami_value'] = None
    df['inflow'] = 0
    df.reset_index(drop = True, inplace = True)
    
    df.loc[0, 'pishtaz_value'] = initial_investment * asset_weights[0]
    df.loc[0, 'ayar_value'] = initial_investment * asset_weights[1]
    df.loc[0, 'hami_value'] = initial_investment * asset_weights[2]
    
    last_inflow_date = start_date
    last_inflow = initial_investment
    for i in range(1, df.shape[0]):
        df.loc[i, 'pishtaz_value'] = df.loc[i-1, 'pishtaz_value'] * df.loc[i, 'pishtaz']
        df.loc[i, 'ayar_value'] = df.loc[i-1, 'ayar_value'] * df.loc[i, 'ayar']
        df.loc[i, 'hami_value'] = df.loc[i-1, 'hami_value'] * df.loc[i, 'hami']

        if df.loc[i, 'jalali'].endswith('-01'):

            if df.loc[i, 'jalali'][:4] != last_inflow_date[:4]:
                last_inflow = last_inflow * (1 + increase_rate)

            df.loc[i, 'inflow'] = last_inflow

            df.loc[i, 'pishtaz_value'] = df.loc[i, 'pishtaz_value'] + last_inflow * asset_weights[0]
            df.loc[i, 'ayar_value'] = df.loc[i, 'ayar_value'] + last_inflow * asset_weights[1]
            df.loc[i, 'hami_value'] = df.loc[i, 'hami_value'] + last_inflow * asset_weights[2]

            last_inflow_date = df.loc[i, 'jalali']
            
    df['portfolio'] = df['pishtaz_value'] + df['ayar_value'] + df['hami_value']
    df['return'] = 1
    for i in range(1, df.shape[0]):
        df.loc[i, 'return'] = (df.loc[i, 'portfolio'] - df.loc[i, 'inflow']) / df.loc[i-1, 'portfolio']
    df['cumulative'] = df['return'].cumprod() - 1
    
    return df

def load_data():
    print("🔄 Loading Features Data... (This happens only once at startup)")
    funds_df = read_from_db(mofid_funds_return_query)
    
    # Load fixed_df and set its index to datetime
    fixed_df = pd.read_excel('files/asset_classes_data.xlsx')
    fixed_df['greg_date'] = pd.to_datetime(fixed_df['greg_date'])  # Convert to datetime
    fixed_df.set_index('greg_date', inplace=True)
    fixed_df = fixed_df.pct_change() + 1

    # Pivot and rename the funds DataFrame
    funds_df = funds_df.pivot(index='Date', columns='RegNum', values='Return')
    funds_df['Date'] = pd.to_datetime(funds_df.index)  # Convert index to datetime
    funds_df.set_index('Date', inplace=True)  # Set Date as the index
    funds_df.rename(columns={10600: 'pishtaz', 11586: 'ayar', 11277: 'hami'}, inplace=True)

    # Merge the DataFrames
    df = pd.merge(fixed_df, funds_df, left_index=True, right_index=True, how='right')

    df['ayar'].fillna(df['coin'], inplace=True)
    df['hami'].fillna(df['riskfree'], inplace=True)
    
    # Keep only the relevant columns
    df = df[['pishtaz', 'ayar', 'hami']]
    df.reset_index(drop=False, inplace=True)
    df['jalali'] = df['Date'].astype(str).apply(greg_to_jalali)

    print("✅ Features Data Loaded!")
    return df

def store_settings_weights():
    settings = [
        [1, [0.1, 0,   0.9], 365],
        [2, [0.3, 0.1, 0.6], 365],
        [3, [0.6, 0.1, 0.3], 365],
        [4, [0.7, 0.2, 0.1], 365],
        [5, [0.8, 0.2, 0], 365],
        
        [1, [0.1, 0,   0.9], 365 * 3],
        [2, [0.3, 0.1, 0.6], 365 * 3],
        [3, [0.4, 0.1, 0.5], 365 * 3],
        [4, [0.5, 0.2, 0.3], 365 * 3],
        [5, [0.9, 0.1, 0], 365 * 3],
        
        [1, [0.2, 0.1, 0.7], 365 * 10],
        [2, [0.3, 0.1, 0.6], 365 * 10],
        [3, [0.5, 0.2, 0.3], 365 * 10],
        [4, [0.6, 0.2, 0.2], 365 * 10],
        [5, [0.9, 0.1, 0], 365 * 10]
    ]
    
    # Convert to DataFrame
    settings_df = pd.DataFrame(settings, columns=['risk', 'weights', 'horizon'])
    
    # Convert to a dictionary for easier lookup
    settings_dict = {}
    for _, row in settings_df.iterrows():
        settings_dict[(row['risk'], row['horizon'])] = row['weights']
    
    return settings_dict

mofid_funds_return_query = '''
SELECT RegNum,
       Date,
	   [Return]
  FROM [Funds_Fact_NAV2_Historical_Revised]
  Where regnum in (10600, 11277, 11586)
'''

all_funds_return_query = '''
SELECT a.NameFa,
       b.Date,
	   b.[Return]
  FROM [Funds_Dim_Info] a join [Funds_Fact_NAV2_Historical_Revised] b
  on a.RegNum = b.RegNum
  where a.InstituteTypeId = 6
'''