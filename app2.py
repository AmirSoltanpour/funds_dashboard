import dash
from dash import dcc, html, Input, Output, State
from flask import Flask
import pandas as pd
from utils import fetch_fund_names, read_from_db, simulator3

# Create a Flask server
server = Flask(__name__)
# Create a Dash application
app = dash.Dash(__name__, server=server)

# Load fund names and their RegNums as a DataFrame at app startup
funds_df = fetch_fund_names()  # Returns a DataFrame with 'NameFa' and 'RegNum'
fund_names = funds_df['NameFa'].tolist()  # List of fund names
reg_nums = funds_df['RegNum'].tolist()  # List of registration numbers

# Create a mapping from fund names to their registration numbers
name_to_regnum = dict(zip(fund_names, reg_nums))

# App layout
app.layout = html.Div(style={'padding': '20px', 'font-family': 'IranSans', 'direction': 'rtl'}, children=[
    html.H1("داشبورد شبیه‌سازی سرمایه‌گذاری", style={'text-align': 'center'}),
    
    html.Div([
        html.Label("نام صندوق‌ها:"),
        dcc.Dropdown(
            id='fund-dropdown',
            options=[{'label': name, 'value': name} for name in fund_names],
            multi=True,  # Allow multiple selections
            placeholder='صندوق‌ها را انتخاب کنید...'
        ),
    ], style={'margin-bottom': '10px'}),
    
    html.Div([
        html.Label("وزن برای صندوق‌های انتخابی (درصد):"),
        dcc.Input(
            id='weight-input',
            type='text',  # Keep the input type as text
            placeholder='وزن‌ها را وارد کنید (مثال: 20, 30, 50)...',
            style={'text-align': 'right'}
        ),
        html.Button('اضافه کردن وزن', id='add-weights-button', n_clicks=0),
    ], style={'margin-bottom': '10px'}),
    
    html.Div(id='weights-output', style={'margin-top': '10px'}),  # Display the entered weights
    dcc.Store(id='weights-store'),  # Store weights in a dcc.Store component
    dcc.Store(id='fund-weights-store'),  # Store fund weights dictionary

    # New input fields for user-defined parameters
    html.Div([
        html.Label("تاریخ شروع (yyyy-mm-dd):"),
        dcc.Input(id='start-date', type='text', value='1398-05-04', style={'text-align': 'right'}),
    ], style={'margin-bottom': '10px'}),
    
    html.Div([
        html.Label("تاریخ پایان (yyyy-mm-dd):"),
        dcc.Input(id='end-date', type='text', value='1400-12-10', style={'text-align': 'right'}),
    ], style={'margin-bottom': '10px'}),
    
    html.Div([
        html.Label("نرخ افزایش سالانه (%):"),
        dcc.Input(id='increase-rate', type='number', value=20, step=0.1, style={'text-align': 'right'}),
    ], style={'margin-bottom': '10px'}),
    
    html.Div([
        html.Label("سرمایه اولیه:"),
        dcc.Input(id='initial-investment', type='number', value=1000, style={'text-align': 'right'}),
    ], style={'margin-bottom': '10px'}),

    html.Div([
        html.Button('اجرای شبیه‌سازی', id='run-simulation', n_clicks=0),
    ], style={'margin-bottom': '20px'}),
    
    dcc.Graph(id='cumulative-graph'),
    dcc.Graph(id='portfolio-graph'),

    html.Div(
        id='risk-measures',
        style={
            'margin-top': '20px',
            'font-size': '16px',
            'width': '60%',
            'margin-left': 'auto',
            'margin-right': '600px',
            'text-align': 'right'
        }
    ),
])

# Callback for adding weights
@app.callback(
    Output('weights-output', 'children'),
    Output('weight-input', 'value'),  # Clear the input after adding
    Output('weights-store', 'data'),  # Output to store weights
    Output('fund-weights-store', 'data'),  # Store fund-weights dictionary
    Input('add-weights-button', 'n_clicks'),
    Input('weight-input', 'value'),
    State('fund-dropdown', 'value'),
    State('weights-store', 'data'),  # Get current weights from store
)
def add_weights(n_clicks, weight_values, selected_funds, weights):
    if n_clicks > 0:
        if selected_funds and weight_values:
            try:
                # Split the input string into a list and convert to floats
                weights = [float(weight.strip()) for weight in weight_values.split(',')]
                # Check that the number of weights matches the selected funds
                if len(weights) != len(selected_funds):
                    return f"خطا: تعداد وزن‌ها با تعداد صندوق‌های انتخاب شده مطابقت ندارد. (تعداد صندوق‌ها: {len(selected_funds)}, تعداد وزن‌ها: {len(weights)})", weight_values, None, None
                # Check that the weights sum to 100
                if sum(weights) != 100:
                    return "خطا: مجموع وزن‌ها باید برابر با 100 درصد باشد.", weight_values, None, None
                # Create a dictionary of the fund weights
                fund_weights_dict = dict(zip(selected_funds, weights))
                reg_num_weights_dict = {name_to_regnum[fund]: weight for fund, weight in fund_weights_dict.items()}  # Replace names with RegNums
                # Log the dictionary of fund weights with RegNums
                print(f"Dictionary of Fund Weights (RegNum): {reg_num_weights_dict}")  # Print to console
                # Store valid weights and dictionary
                return f"وزن‌های فعلی: {weights}, (تعداد: {len(weights)})", "", weights, reg_num_weights_dict  # Clear input after appending
            except ValueError:
                return "لطفاً مقادیر عددی صحیح وارد کنید.", weight_values, None, None  # Handle invalid input
        else:
            return "لطفاً صندوق‌ها و وزن‌ها را وارد کنید.", weight_values, None, None  # Prompt for valid input
    return "", weight_values, weights, None  # Maintain current weights if no new weight added

# Callback for running the simulation
@app.callback(
    Output('cumulative-graph', 'figure'),
    Output('portfolio-graph', 'figure'),
    Output('risk-measures', 'children'),
    Input('run-simulation', 'n_clicks'),
    Input('fund-dropdown', 'value'),  # Selected funds
    Input('fund-weights-store', 'data'),  # Get fund weights dictionary
    Input('start-date', 'value'),  # Start date input
    Input('end-date', 'value'),  # End date input
    Input('increase-rate', 'value'),  # Increase rate input
    Input('initial-investment', 'value'),  # Initial investment input
)
def run_simulation(n_clicks, selected_funds, fund_weights_dict, start_date, end_date, increase_rate, initial_investment):
    if n_clicks > 0 and selected_funds:
        # Check if the fund_weights_dict is populated
        if fund_weights_dict is None:
            return {}, {}, "لطفاً وزن‌ها را وارد کنید."

        # Extracting RegNums from the weights dictionary
        selected_reg_nums = list(fund_weights_dict.keys())
        
        # Execute the query using the RegNums
        data_query = f"SELECT [Date], [Return], RegNum FROM [General].[dbo].[Funds_Fact_NAV2_Historical_Revised] WHERE regnum IN ({', '.join(map(str, selected_reg_nums))})"
        
        # Fetch data from the database
        df = read_from_db(data_query)  # Assuming this returns a DataFrame

        # Run the simulation
        result = simulator3(df, fund_weights_dict, start_date=start_date, end_date=end_date, increase_rate=increase_rate/100.0, initial_investment=initial_investment)
        
        result_df = result[0]
        cumulative_return = result[1]
        cagr = result[2]
        max_dd = result[3]
        var = result[4]

        # Assuming result_df contains 'cumulative' and 'portfolio' columns with a 'Date' column
        cumulative_fig = {
            'data': [
                {'x': result_df['Date'], 'y': result_df['cumulative'], 'type': 'line', 'name': 'Cumulative'},
            ],
            'layout': {
                'title': 'بازدهی تجمعی',
                'xaxis': {'title': 'Date'},
                'yaxis': {'title': 'بازده تجمعی (%)', 'tickformat': '.0%', 'font': {'family': 'IranSans'}},
                'font': {'family': 'IranSans'}
            }
        }

        portfolio_fig = {
            'data': [
                {'x': result_df['Date'], 'y': result_df['portfolio'], 'type': 'line', 'name': 'Portfolio'},
            ],
            'layout': {
                'title': 'ارزش پرتفوی',
                'xaxis': {'title': 'Date'},
                # 'yaxis': {'title': 'Portfolio Value'},
                'font': {'family': 'IranSans'}
            }
        }

        # Prepare text for the risk measures
        risk_measures = [
            {"name": "بازده تجمعی", "value": f"{cumulative_return * 100:.2f}%"},
            {"name": "نرخ رشد مرکب سالانه", "value": f"{cagr * 100:.2f}%"},
            {"name": "ماکزیمم کاهش", "value": f"{abs(max_dd) * 100:.2f}%"},
            # {"name": "نسبت شارپ", "value": f"{sharpe:.2f}"},
            {"name": "ارزش در معرض خطر", "value": f"{abs(var):.2f}%"}
        ]

        # Convert the list to HTML lines
        risk_measures_lines = [
            html.Div(
                [html.Span(measure['name'], style={'flex': '1', 'text-align': 'right'}), 
                html.Span(measure['value'], style={'flex': '1', 'text-align': 'right'})],
                style={
                    'display': 'flex', 
                    'justify-content': 'flex-start',  # Align items to the start (left)
                    'align-items': 'flex-start', 
                    'margin-bottom': '4px'
                }
            ) for measure in risk_measures
        ]
        
        return cumulative_fig, portfolio_fig, risk_measures_lines


    return {}, {}, []  # Before running the simulation

# Start the Dash app
if __name__ == '__main__':
    app.run_server(debug=True)