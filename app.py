import dash
from dash import dcc, html, Input, Output
from flask import Flask
import pandas as pd
from utils import simulator, simulator2, store_settings_weights, load_data

# Create a Flask server
server = Flask(__name__)

# Create a Dash application
app = dash.Dash(__name__, server=server)

df = load_data()  # Load data once at app startup
df = df[df['jalali'] >= '1392-01-01']  # Filter based on the Jalali date

# Load settings from the utility function
asset_settings = store_settings_weights()

# App layout
app.layout = html.Div(style={'padding': '20px', 'font-family': 'IranSans', 'direction': 'rtl'}, children=[
    html.H1("داشبورد شبیه‌سازی سرمایه‌گذاری", style={'text-align': 'center'}),
    
    html.Div([
        html.Label("تاریخ شروع (yyyy-mm-dd):"),
        dcc.Input(id='start-date-input', type='text', value='1398-05-01', style={'text-align': 'right'}),
    ], style={'margin-bottom': '10px'}),
    
    html.Div([
        html.Label("سرمایه اولیه:"),
        dcc.Input(id='initial-investment', type='number', value=1000, style={'text-align': 'right'}),
    ], style={'margin-bottom': '10px'}),
    
    html.Div([
        html.Label("نرخ افزایش سالانه(%)"),  # Updated label to reflect percentage input
        dcc.Input(id='increase-rate', type='number', value=20, style={'text-align': 'right'}),  # Changed default value to represent percentage
    ], style={'margin-bottom': '10px'}),
    
    html.Div([
        html.Label("افق زمانی (بر حسب سال):"),
        dcc.Slider(
            id='horizon-slider',
            min=0,
            max=10,
            marks={0: '0', 1: '1', 3: '3', 10: '10'},
            value=3,
            step=None
        ),
    ], style={'margin-bottom': '10px'}),
    
    html.Div([
        html.Label("درجه ریسک (۱-۵):"),
        dcc.Dropdown(
            id='risk-degree-dropdown',
            options=[{'label': str(i), 'value': i} for i in range(1, 6)],
            value=3  # Default risk degree
        ),
    ], style={'margin-bottom': '10px'}),
    
    html.Div([
        html.Button('اجرای شبیه‌سازی', id='run-simulation', n_clicks=0),
    ], style={'margin-bottom': '20px'}),
    
    dcc.Graph(id='cumulative-graph'),
    dcc.Graph(id='portfolio-graph'),

    # Risk measures Div in app layout
    html.Div(
        id='risk-measures', 
        style={
            'margin-top': '20px', 
            'font-size': '16px', 
            'width': '60%',  # Adjust width as needed
            'margin-left': 'auto',  
            'margin-right': '600px',
            'text-align': 'right'  # Align the text to the left
        }
    ),
])

# Callback for processing the simulation and updating the risk measures text
@app.callback(
    Output('cumulative-graph', 'figure'),
    Output('portfolio-graph', 'figure'),
    Output('risk-measures', 'children'),
    Input('run-simulation', 'n_clicks'),
    Input('start-date-input', 'value'),
    Input('initial-investment', 'value'),
    Input('increase-rate', 'value'),
    Input('horizon-slider', 'value'),
    Input('risk-degree-dropdown', 'value')
)
def update_graphs(n_clicks, start_date, initial_investment, increase_rate, horizon_years, risk_degree):
    if n_clicks > 0:
        horizon_days = horizon_years * 365
        
        # Get asset weights based on risk degree and horizon
        asset_weights = asset_settings.get((risk_degree, horizon_days), [0.5, 0.3, 0.2])
        
        # Run the first simulator for risk metrics
        cumulative_return, cagr, max_dd, sharpe, var = simulator(df, start_date, initial_investment, increase_rate/100, horizon_days, asset_weights)
        
        # Run the second simulator for portfolio data
        result_df = simulator2(df, start_date, initial_investment, increase_rate/100, horizon_days, asset_weights)
        
        # Create cumulative figure
        cumulative_fig = {
            'data': [
                {'x': result_df['Date'], 'y': result_df['cumulative'], 'type': 'line', 'name': 'Cumulative'},
            ],
            'layout': {
                'title': 'بازده تجمعی',
                'yaxis': {'title': 'بازده تجمعی (%)', 'tickformat': '.0%', 'font': {'family': 'IranSans'}},
                'font': {'family': 'IranSans'}
            }
        }
        # Create portfolio figure
        portfolio_fig = {
            'data': [
                {'x': result_df['Date'], 'y': result_df['portfolio'], 'type': 'line', 'name': 'Portfolio'},
            ],
            'layout': {
                'title': 'ارزش پورتفوی',
                'font': {'family': 'IranSans'}
            }
        }
        
        # Prepare text for the risk measures
        risk_measures = [
            {"name": "بازده تجمعی", "value": f"{cumulative_return * 100:.2f}%"},
            {"name": "نرخ رشد مرکب سالانه", "value": f"{cagr * 100:.2f}%"},
            {"name": "ماکزیمم کاهش", "value": f"{abs(max_dd) * 100:.2f}%"},
            {"name": "نسبت شارپ", "value": f"{sharpe:.2f}"},
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
    
    return {}, {}, []

if __name__ == '__main__':
    app.run(debug=True)