import base64
import csv
import io
import os
import pickle
import random
import uuid

import pandas as pd

from datetime import datetime, timedelta

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
    session # Storing field instance rather than having to recreate each time
)

# Local
from combocounter import ComboCounter
from field import Field
from processing import ProcessDraftKingsFile

from __info import PLAYER_COLUMNS

# Near the top of app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'max-entries')

HIDDEN = [
    # 'jdeegs99',
    # 'moklovin'
]

app = Flask(__name__, static_folder='static')
app.config['JSON_SORT_KEYS'] = False
app.config['SECRET_KEY'] = os.urandom(24)  # For session encryption
app.config['SESSION_TYPE'] = 'filesystem'  # Optional: use filesystem instead of cookies

# Simple cache for file data with expiration
FILE_CACHE = {}
CACHE_EXPIRY = timedelta(minutes=30)  # Cache files for 30 minutes

def cleanup_cache():
    """Remove expired files from cache"""
    now = datetime.now()
    expired_keys = [k for k, v in FILE_CACHE.items() if now > v.get('expiry', now)]
    for key in expired_keys:
        del FILE_CACHE[key]

def get_or_create_field(file=None, **kwargs):
    """
    Get an existing Field object from session or create a new one
    """
    print("Entering get_or_create_field...")
    cleanup_cache()  # Clean up expired files
    
    # If we have a file, always create a new Field object
    if file is not None:
        print(f"File provided: {file.filename if hasattr(file, 'filename') else 'No filename'}")
        
        # Create a new Field object
        file_content = file.read()
        print(f"Read file content, size: {len(file_content)} bytes")
        
        # Attempt to validate file content by reading first few lines
        file_buffer = io.BytesIO(file_content)
        try:
            # Try reading the first few lines to validate
            df_peek = pd.read_csv(file_buffer, nrows=5)
            print(f"Peek at file: {df_peek.shape}, columns: {df_peek.columns.tolist()}")
            # Reset buffer position
            file_buffer.seek(0)
        except Exception as e:
            print(f"Error peeking at file: {e}")
        
        file_buffer = io.BytesIO(file_content)
        print("Created fresh file buffer")
        
        try:
            # Create Field instance
            field = Field(file_buffer, **kwargs)
            print("Field object created")
            
            field.clean_data()
            print("clean_data completed")
            
            # Generate unique ID and store file in cache
            file_id = str(uuid.uuid4())
            FILE_CACHE[file_id] = {
                'content': file_content,
                'expiry': datetime.now() + CACHE_EXPIRY,
                'kwargs': kwargs
            }
            
            # Store only the ID in session
            session['file_id'] = file_id
            print("File ID stored in session")
            
            return field
        except Exception as e:
            print(f"Error creating Field: {e}")
            import traceback
            print(traceback.format_exc())
            raise
            
    # No file provided, try to get from cache
    elif 'file_id' in session and session['file_id'] in FILE_CACHE:
        file_id = session['file_id']
        print(f"No file provided, retrieving from cache with ID: {file_id}")
        
        try:
            # Get from cache
            cache_entry = FILE_CACHE[file_id]
            file_content = cache_entry['content']
            cached_kwargs = cache_entry.get('kwargs', {})
            
            # Update expiry time
            FILE_CACHE[file_id]['expiry'] = datetime.now() + CACHE_EXPIRY
            
            print(f"Retrieved file content from cache: {len(file_content)} bytes")
            
            # Merge cached kwargs with provided kwargs
            merged_kwargs = {**cached_kwargs, **kwargs}
            
            file_buffer = io.BytesIO(file_content)
            print("Created file buffer from cached data")
            
            # Create Field instance from cached file content
            field = Field(file_buffer, **merged_kwargs)
            print("Field object created from cached data")
            
            field.clean_data()
            print("clean_data completed")
            
            return field
        except Exception as e:
            print(f"Error retrieving Field from cache: {e}")
            import traceback
            print(traceback.format_exc())
            # Remove invalid cache entry
            if file_id in FILE_CACHE:
                del FILE_CACHE[file_id]
            # Continue to return None
    
    print("No file provided and no valid cache data available")
    return None

def adjust_key(key) -> str:
    """
    Since JSON does not allow dict keys to be tuples, this function will adjust the key to work
    Do not type hint as "str|tuple[str,...]" -> causes compatibility
    """
    return key if isinstance(key, str) else '-'.join(key)

def run_ComboCounter(
    df: pd.DataFrame,
    option: int,
    sport: str,
    mode: str,
    num_results: int,
    percents: bool
) -> dict[str,int]:
    """
    Runs the combocounter code
    Need to validate/clean data first though
        - Reading from a csv treates a tuple of strings as a single string
    """
    columns = PLAYER_COLUMNS[sport][mode]
    lineups = tuple(df[columns].apply(tuple, axis=1))

    cc = ComboCounter(lineups, k=len(columns)-1)
    cc.run()
    counts = {
        level: dict(sorted(
            {adjust_key(k): v for k,v in innerdict.items()}.items(),
            key=lambda item: item[1],
            reverse=True
        ))
        for level, innerdict in cc.counts().items()
    }

    ret = dict([item for item in counts[option].items()][:num_results])

    if percents:
        n_lineups = len(lineups)
        return {k: round(100*v/n_lineups, 2) for k,v in ret.items()}

    return ret

@app.route('/available-files')
@app.route('/available-files/<tournament>')
def get_available_files(tournament=None):
    """Return list of available files in the data directory or tournament subdirectory"""
    try:
        if tournament:
            # Use the tournament subdirectory path
            directory = os.path.join(DATA_DIR, tournament)
        else:
            # Use the default directory
            # Doesnt make sense at the moment, may cause issues if getting 0 results but everything works
            directory = DATA_DIR

        # Check if directory exists
        if not os.path.exists(directory):
            return jsonify({'error': f'Directory {directory} not found'}), 404

        # Get files and strip .csv extension
        files = sorted([
            os.path.splitext(f)[0]
            for f in os.listdir(directory)
            if all([
                f.endswith('.csv'),
                f.split('/')[-1].split('.')[0] not in HIDDEN
            ])
        ], key=lambda file_: file_.split('/')[-1][0].lower())

        return jsonify({'files': files})
    except Exception as e:
        print("Error:", str(e))  # Debug print
        return jsonify({'error': str(e)}), 500

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/field')
def field():
    return render_template('field.html')

@app.route('/analyze-field', methods=['POST'])
def analyze_field():
    try:
        # Check if using a cached file or a new upload
        using_cached_file = False
        
        if 'file' not in request.files and 'file_id' in session:
            using_cached_file = True
            
        if not using_cached_file and ('file' not in request.files or request.files['file'].filename == ''):
            return jsonify({'error': 'No file uploaded'}), 400
        
        sport = str(request.form.get('sport', 'PGA'))
        mode = str(request.form.get('mode', 'classic')).lower()
        
        # Get the field instance
        if using_cached_file:
            field = get_or_create_field(sport=sport, mode=mode)
            if field is None:
                return jsonify({'error': 'No cached file available. Please upload a file.'}), 400
        else:
            file = request.files['file']
            if not file.filename.endswith('.csv'):
                return jsonify({'error': 'Please upload a CSV file'}), 400
            field = get_or_create_field(file=file, sport=sport, mode=mode)
        
        # Get ownership data
        ownership_data = field.ownership()
        
        return jsonify({
            'success': True, 
            'analysis': ownership_data
        })
        
    except Exception as e:
        import traceback
        print("Exception in analyze_field:", str(e))
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/analyze-max-entries', methods=['POST'])
def analyze_max_entries():
    try:
        # Check if using a cached file or a new upload
        using_cached_file = False
        
        if 'file' not in request.files and 'file_id' in session:
            using_cached_file = True
            
        if not using_cached_file and ('file' not in request.files or request.files['file'].filename == ''):
            return jsonify({'error': 'No file uploaded'}), 400
        
        sport = str(request.form.get('sport', 'PGA'))
        mode = str(request.form.get('mode', 'classic')).lower()
        
        # Get the field instance
        if using_cached_file:
            field = get_or_create_field(sport=sport, mode=mode)
            if field is None:
                return jsonify({'error': 'No cached file available. Please upload a file.'}), 400
        else:
            file = request.files['file']
            if not file.filename.endswith('.csv'):
                return jsonify({'error': 'Please upload a CSV file'}), 400
            field = get_or_create_field(file=file, sport=sport, mode=mode)
        
        # Get max entries and prepare a list for the response
        # Serializing data properly for frontend
        max_entries = sorted([
            {"contestant": str(contestant), "entries": int(count)}
            for contestant, count in field.max_entries().items()
        ], key=lambda data_: data_["contestant"][0].lower())
        
        # for contestant, count in max_entries_dict.items():
        #     entries_list.append({
        #         "contestant": str(contestant), "entries": int(count)
        #     })
        
        return jsonify({
            'success': True,
            'entries': max_entries
        })
        
    except Exception as e:
        return jsonify({'error': f"Error in analyze_max_entries: {str(e)}"}), 500

@app.route('/analyze-duplicates', methods=['POST'])
def analyze_duplicates():
    try:
        # Check if using a cached file or a new upload
        using_cached_file = False
        
        if 'file' not in request.files and 'file_id' in session:
            using_cached_file = True
            
        if not using_cached_file and ('file' not in request.files or request.files['file'].filename == ''):
            return jsonify({'error': 'No file uploaded'}), 400
        
        sport = str(request.form.get('sport', 'PGA'))
        mode = str(request.form.get('mode', 'classic')).lower()
        
        # Get the field instance
        if using_cached_file:
            field = get_or_create_field(sport=sport, mode=mode)
            if field is None:
                return jsonify({'error': 'No cached file available. Please upload a file.'}), 400
        else:
            file = request.files['file']
            if not file.filename.endswith('.csv'):
                return jsonify({'error': 'Please upload a CSV file'}), 400
            field = get_or_create_field(file=file, sport=sport, mode=mode)
        
        # Get duplicates
        # dupes_df = field.duplicates()

        duplicated_lineups = sorted([
            {"lineup": ", ".join(lineup_), "entries": int(count_)}
            for lineup_, count_ in field.duplicates()['count'].items()
        ], key=lambda item: item['entries'], reverse=True)
        
        return jsonify({
            'success': True,
            'duplicates': duplicated_lineups
        })
        
    except Exception as e:
        import traceback
        print("Exception in analyze_duplicates:", str(e))
        print(traceback.format_exc())
        return jsonify({'error': f"Error in analyze_duplicates: {str(e)}"}), 500

@app.route('/analyze-leverage', methods=['POST'])
def analyze_leverage():
    try:
        # Check if using a cached file or a new upload
        using_cached_file = False
        
        if 'file' not in request.files and 'file_id' in session:
            using_cached_file = True
            
        if not using_cached_file and ('file' not in request.files or request.files['file'].filename == ''):
            return jsonify({'error': 'No file uploaded'}), 400
        
        sport = str(request.form.get('sport', 'PGA'))
        mode = str(request.form.get('mode', 'classic')).lower()
        contestant = str(request.form.get('contestant', ''))
        
        # Get the field instance
        if using_cached_file:
            field = get_or_create_field(sport=sport, mode=mode)
            if field is None:
                return jsonify({'error': 'No cached file available. Please upload a file.'}), 400
        else:
            file = request.files['file']
            if not file.filename.endswith('.csv'):
                return jsonify({'error': 'Please upload a CSV file'}), 400
            field = get_or_create_field(file=file, sport=sport, mode=mode)
        
        # Get leverage data
        # df_leverage = field.leverage(contestant)
        # leverage_data = {name: float(df_leverage.loc[name, 'leverage']) for name in df_leverage.index}
        leverage = {name_: leverage_ for name_, leverage_ in field.leverage(contestant)['leverage'].items()}

        sorted_leverage = [{"player": name_, "leverage": leverage_} for name_, leverage_ in leverage.items()]
        
        return jsonify({
            'success': True,
            'contestant': contestant,
            'leverage': sorted_leverage
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/export-ownership', methods=['POST'])
def export_ownership():
    """Server-side export option if needed"""
    try:
        # Check if using a cached file or a new upload
        using_cached_file = False
        
        if 'file' not in request.files and 'file_id' in session:
            using_cached_file = True
            
        if not using_cached_file and ('file' not in request.files or request.files['file'].filename == ''):
            return jsonify({'error': 'No file uploaded'}), 400
        
        sport = str(request.form.get('sport', 'PGA'))
        mode = str(request.form.get('mode', 'classic')).lower()
        
        # Get the field instance
        if using_cached_file:
            field = get_or_create_field(sport=sport, mode=mode)
            if field is None:
                return jsonify({'error': 'No cached file available. Please upload a file.'}), 400
        else:
            file = request.files['file']
            if not file.filename.endswith('.csv'):
                return jsonify({'error': 'Please upload a CSV file'}), 400
            field = get_or_create_field(file=file, sport=sport, mode=mode)
        
        # Get ownership data
        ownership_data = field.ownership()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Player', 'Ownership %'])
        
        for player, ownership in sorted(ownership_data.items(), key=lambda x: x[1], reverse=True):
            writer.writerow([player, f"{ownership:.1f}%"])
        
        # Create response
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        output.close()
        
        return send_file(
            mem,
            as_attachment=True,
            download_name='ownership_data.csv',
            mimetype='text/csv'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/visualize-data', methods=['POST'])
def visualize_data():
    try:
        # Check if using a cached file or a new upload
        using_cached_file = False
        
        if 'file' not in request.files and 'file_id' in session:
            using_cached_file = True
            
        if not using_cached_file and ('file' not in request.files or request.files['file'].filename == ''):
            return jsonify({'error': 'No file uploaded'}), 400
        
        sport = str(request.form.get('sport', 'PGA'))
        mode = str(request.form.get('mode', 'classic')).lower()
        
        # Get the field instance
        if using_cached_file:
            field = get_or_create_field(sport=sport, mode=mode)
            if field is None:
                return jsonify({'error': 'No cached file available. Please upload a file.'}), 400
        else:
            file = request.files['file']
            if not file.filename.endswith('.csv'):
                return jsonify({'error': 'Please upload a CSV file'}), 400
            field = get_or_create_field(file=file, sport=sport, mode=mode)
        
        # Get ownership data
        ownership_data = field.ownership()
        
        # For visualization, we just return the ownership data
        # The frontend will handle the actual visualization
        return jsonify({
            'success': True,
            'visualization': ownership_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/process', methods=['POST'])
def process_file():
    try:
        data_source = request.form.get('source_type', 'upload')

        # Get file content either from upload or data directory
        if data_source == 'upload':
            if 'file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            if not file.filename.endswith('.csv'):
                return jsonify({'error': 'Please upload a CSV file'}), 400
            file_content = file.read()
        else:
            # Read from data directory
            selected_file = request.form.get('selected_file')
            tournament = request.form.get('tournament')

            if not selected_file:
                return jsonify({'error': 'No file selected from directory'}), 400

            # Build the file path
            if tournament and tournament != 'none':
                file_path = os.path.join(DATA_DIR, tournament, selected_file + '.csv')
            else:
                file_path = os.path.join(DATA_DIR, selected_file + '.csv')

            if not os.path.exists(file_path):
                return jsonify({'error': 'Selected file not found'}), 400

            with open(file_path, 'rb') as f:
                file_content = f.read()

        # Create BytesIO object for pandas to read
        file_buffer = io.BytesIO(file_content)

        option = int(request.form.get('option', '1'))
        sport = str(request.form.get('sport', 'PGA'))
        mode = str(request.form.get('mode', 'classic')).lower()
        num_results = int(request.form.get('numResults', '50'))
        percents = str(request.form.get('percents', 'No')) == 'Yes'
        is_dk_file = str(request.form.get('is_dk_file', 'No')) == 'Yes'

        # Check if it's a DK file by looking at first few columns
        try:
            check_df = pd.read_csv(file_buffer, nrows=1)
            detected_dk = any('Entry ID' in cols for cols in check_df.columns)

            # Reset buffer position after checking
            file_buffer.seek(0)

            if detected_dk != is_dk_file:
                correct_type = "DraftKings" if detected_dk else "custom"
                return jsonify({
                    'error': f'File appears to be a {correct_type} file. Please adjust the DraftKings File setting accordingly.'
                }), 400

        except Exception as e:
            # Reset buffer position on error too
            file_buffer.seek(0)
            return jsonify({'error': f'Error reading file format: {str(e)}'}), 400

        # Process with the verified file type
        # Create a new buffer to ensure it's not been consumed
        fresh_buffer = io.BytesIO(file_content)
        df = ProcessDraftKingsFile(fresh_buffer, sport, mode, is_dk_file).lineups

        result = run_ComboCounter(df, option, sport, mode, num_results, percents)

        return jsonify({
            'success': True,
            'result': result,
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())  # Print detailed error for debugging
        return jsonify({'error': str(e) + "  -->   Make sure correct options selected."}), 500

if __name__ == '__main__':
    app.run(debug=True)
