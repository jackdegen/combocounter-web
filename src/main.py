from flask import Flask, render_template, request, jsonify
import pandas as pd
import io

app = Flask(__name__)

def your_algorithm(df):
    # Your existing algorithm here
    # This is where you'll put your DataFrame processing code
    return df  # Return processed results

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
        
        # Check if file is empty
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        # Check file extension
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Please upload a CSV file'}), 400
            
        # Read the file into a DataFrame
        df = pd.read_csv(file.stream)
        
        # Process the DataFrame using your algorithm
        result = your_algorithm(df)
        
        # Convert results to JSON
        return jsonify({
            'success': True,
            'result': result.to_json(orient='records')
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
