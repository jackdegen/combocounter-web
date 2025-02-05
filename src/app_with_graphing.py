import io
import pandas as pd

# Making matplotlib work in web format
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.style.use('fivethirtyeight')

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file
)
# Local
from combocounter import ComboCounter
from __info import PLAYER_COLUMNS

app = Flask(__name__)
# Do NOT want to sort JSON keys
app.json.sort_keys = False

def adjust_key(key: str|tuple[str,...]) -> str:
    """
    Since JSON does not allow dict keys to be tuples, this function will adjust the key to work
    """
    return key if isinstance(key, str) else '-'.join(key)

def graph_exposures(counts_dict: dict[str,int], N: int):
    """
    Graph exposures given counts of each player/combos of players
    """
    exposure_data = {
        'name': list(counts_dict.keys()),
        'exposure (%)': [100 * count_ / N for count_ in counts_dict.values()]
    }

    df = pd.DataFrame(exposure_data).set_index('name').sort_values('exposure (%)', ascending=True)

    print("Starting plot creation...")
    print(f"DataFrame shape: {df.shape}")
    
    plt.clf()
    plt.close('all')

    fig = plt.figure(figsize=(90, 60))
    print(f"Figure size in inches: {fig.get_size_inches()}")
    
    ax = fig.add_subplot(111)

    # Create plot
   #plt.figure(figsize=(20,12))
    df.plot.barh(ax=ax)
   #plt.title('Exposures:')
    plt.tight_layout()

    # Save plot to temporary buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    plt.close(fig)# Free the memory
    buf.seek(0)

    return buf
    

def run_ComboCounter(
    df: pd.DataFrame,
    option: int, # Option for combination length --> TODO: Decide/standardize naming for this option (<-- example of issue)
    sport: str,
    mode: str,
    num_results: int
) -> dict[str,int]:
    """
    Runs the combocounter code
    Need to validate/clean data first though
        - Reading from a csv treates a tuple of strings as a single string
    """
    # TODO: make some templates for different sports 
    # columns = [f'G{n+1}' for n in range(6)]
    columns = PLAYER_COLUMNS[sport][mode]
    print(columns)

    # sanitize_columns#
    if columns[-1] not in list(df.columns):
        # Assumes desired columns are starting subset of all columns
        df = (df
              .loc[:, list(df.columns)[:len(columns)]]
              .set_axis(columns, axis=1)
              )

    lineups = tuple(df[columns].apply(tuple, axis=1))

    # # JSON does not allow tuple keys to be dumped
    cc = ComboCounter(lineups, k=5)
    cc.run()
    counts = {
        level: dict(sorted(
            {adjust_key(k): v for k,v in innerdict.items()}.items(),
            key=lambda item: item[1],
            reverse=True
        ))
        for level, innerdict in cc.counts().items()
    }

    #return graph_exposures(counts[combo_len], df.shape[0])


    return dict([item for item in counts[option].items()][:{1: 100}.get(option, 50)])
    # return lineups[0]
    # return cc.counts()
    # return df.to_dict(orient='records')
    
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_file():
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']

        option = int(request.form.get('option', '1'))
        sport = str(request.form.get('sport', 'PGA'))
        mode = str(request.form.get('mode', 'classic')).lower()
        
        
        
        # Check if file is empty
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        # Check file extension
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Please upload a CSV file'}), 400
            
        # Read the file into a DataFrame
        df = pd.read_csv(file.stream)
    
        # return send_file(
        #     run_ComboCounter(df, option),
        #     mimetype='image/png'
        # )
    
        # Process the DataFrame using your algorithm
        result = run_ComboCounter(df, option, sport, mode)
        
        # Return the results directly since they're already in a JSON-serializable format
        return jsonify({
            'success': True,
            'result': result,
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
