import csv
import io
import os
import uuid
import json
from datetime import datetime, timedelta

import pandas as pd

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

# For PythonAnywhere, use a writable directory
if 'PYTHONANYWHERE_DOMAIN' in os.environ:
    # This is the directory where PythonAnywhere allows writing
    username = os.path.basename(os.path.expanduser('~'))
    CACHE_DIR = f'/tmp/{username}_app_cache'
else:
    # Local development
    CACHE_DIR = os.path.join(BASE_DIR, 'cache')

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Set cache expiry time
CACHE_EXPIRY = timedelta(hours=1)  # Cache files for 1 hour

# app = Flask(__name__)
app = Flask(__name__, static_folder='static')
app.config['JSON_SORT_KEYS'] = False
app.config['SECRET_KEY'] = 'your-secure-secret-key'  # Use a fixed key, not os.urandom
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

def cleanup_cache():
    """Remove expired files from cache directory"""
    now = datetime.now()
    for filename in os.listdir(CACHE_DIR):
        if filename.endswith('.json'):
            metadata_path = os.path.join(CACHE_DIR, filename)
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)

                expiry_time = datetime.fromisoformat(metadata.get('expiry', '2000-01-01'))
                if now > expiry_time:
                    # Remove the metadata file
                    os.remove(metadata_path)

                    # Remove the corresponding data file if it exists
                    data_path = os.path.join(CACHE_DIR, metadata.get('data_file', ''))
                    if os.path.exists(data_path):
                        os.remove(data_path)
            except Exception as e:
                print(f"Error cleaning up cache: {e}")

def get_or_create_field(file=None, file_buffer=None, **kwargs):
    """
    Get an existing Field object from session or create a new one,
    using filesystem-based caching
    """
    print("Entering get_or_create_field...")
    cleanup_cache()  # Clean up expired files

    # If we have a file or file_buffer, create a new Field object
    if file is not None or file_buffer is not None:
        if file is not None:
            print(f"File provided: {file.filename if hasattr(file, 'filename') else 'No filename'}")
            file_content = file.read()
            buffer = io.BytesIO(file_content)
        else:
            print("File buffer provided")
            buffer = file_buffer
            # Get the content for caching
            buffer.seek(0)
            file_content = buffer.read()
            buffer.seek(0)

        print(f"File content size: {len(file_content)} bytes")

        try:
            # Create Field instance
            field = Field(buffer, **kwargs)
            print("Field object created")

            field.clean_data()
            print("clean_data completed")

            # Generate unique ID for this file
            file_id = str(uuid.uuid4())

            # Save the actual file content to disk
            data_filename = f"{file_id}.data"
            data_path = os.path.join(CACHE_DIR, data_filename)
            with open(data_path, 'wb') as f:
                f.write(file_content)

            # Save metadata
            metadata = {
                'data_file': data_filename,
                'expiry': (datetime.now() + CACHE_EXPIRY).isoformat(),
                'kwargs': kwargs
            }

            metadata_path = os.path.join(CACHE_DIR, f"{file_id}.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)

            # Store only the ID in session
            session['file_id'] = file_id
            print(f"File ID {file_id} stored in session")

            return field
        except Exception as e:
            print(f"Error creating Field: {e}")
            import traceback
            print(traceback.format_exc())
            raise

    # No file provided, try to get from filesystem cache
    elif 'file_id' in session:
        file_id = session['file_id']
        print(f"No file provided, retrieving from cache with ID: {file_id}")

        try:
            # Check if metadata file exists
            metadata_path = os.path.join(CACHE_DIR, f"{file_id}.json")
            if not os.path.exists(metadata_path):
                print(f"No metadata file found for ID: {file_id}")
                return None

            # Load metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            # Check if data file exists
            data_filename = metadata.get('data_file')
            data_path = os.path.join(CACHE_DIR, data_filename)
            if not os.path.exists(data_path):
                print(f"No data file found: {data_filename}")
                return None

            # Load file content
            with open(data_path, 'rb') as f:
                file_content = f.read()

            # Update expiry time
            metadata['expiry'] = (datetime.now() + CACHE_EXPIRY).isoformat()
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)

            # Merge cached kwargs with provided kwargs
            cached_kwargs = metadata.get('kwargs', {})
            merged_kwargs = {**cached_kwargs, **kwargs}

            # Create Field instance
            buffer = io.BytesIO(file_content)
            field = Field(buffer, **merged_kwargs)
            print("Field object created from cached data")

            field.clean_data()
            print("clean_data completed")

            return field
        except Exception as e:
            print(f"Error retrieving Field from cache: {e}")
            import traceback
            print(traceback.format_exc())
            # Continue to return None

    print("No file provided and no valid cache data available")
    return None

def adjust_key(key, **kwargs) -> str:
    """
    Since JSON does not allow dict keys to be tuples, this function will adjust the key to work
    Do not type hint as "str|tuple[str,...]" -> causes compatibility
    """
    return key if isinstance(key, str) else kwargs.get('char', ', ').join(key)

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
    Potentially may need to do some file caching similar to Field if want to use
    CC on lineup sets much bigger than 150
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

        max_entries_dict = field.max_entries()
        if max_entries_dict.get('jdeegs99') is None:
            max_entries_dict['jdeegs99'] = max(max_entries_dict.values())

        # Get max entries and prepare a list for the response
        # Serializing data properly for frontend
        max_entries = sorted([
            {"contestant": str(contestant), "entries": int(count)}
            for contestant, count in max_entries_dict.items()
        ], key=lambda data_: data_["contestant"][0].lower())


        return jsonify({
            'success': True,
            'entries': max_entries
        })

    except Exception as e:
        return jsonify({'error': f"Error in analyze_max_entries: {str(e)}"}), 500


@app.route('/analyze-mme-ownership', methods=['POST'])
def analyze_mme_ownership():
    try:
        # Check if using a cached file or a new upload
        using_cached_file = False
        if 'file' not in request.files and 'file_id' in session:
            using_cached_file = True

        if not using_cached_file and ('file' not in request.files or request.files['file'].filename == ''):
            return jsonify({'error': 'No file uploaded'}), 400

        sport = str(request.form.get('sport', 'PGA'))
        mode = str(request.form.get('mode', 'classic')).lower()
        player = str(request.form.get('player', ''))

        # Get the field instance
        if using_cached_file:
            field = get_or_create_field(sport=sport, mode=mode)
        else:
            file = request.files['file']
            if not file.filename.endswith('.csv'):
                return jsonify({'error': 'Please upload a CSV file'}), 400
            field = get_or_create_field(file=file, sport=sport, mode=mode)

        # Check if field is None after attempting to get it
        if field is None:
            return jsonify({'error': 'No cached file available. Please upload a file.'}), 400

        # Get MME ownership data
        mme_ownership_data = dict(sorted(field.mme_ownership().to_dict().items(), key=lambda item: item[1], reverse=True))

        if len(player):
            # player = player.replace(', ', ',') # Ensure the .split() successful
            select_players = [name_.strip() for name_ in player.split(',')]
            mme_ownership_data = {name_: own_ for name_, own_ in mme_ownership_data.items() if name_ in select_players}

        return jsonify({
            'success': True,
            'mme_ownership': mme_ownership_data  # Changed from 'entries' to 'mme_ownership'
        })
    except Exception as e:
        import traceback
        print(traceback.format_exc())  # Add this for better debugging
        return jsonify({'error': f"Error in analyze_mme_ownership: {str(e)}"}), 500  # Fixed function name in error message


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
        player = str(request.form.get('player', ''))

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

        if len(player):
            # player = player.replace(', ', ',') # Ensure the .split() successful
            select_players = [name_.strip() for name_ in player.split(',')]
            leverage = {name_: leverage_ for name_, leverage_ in leverage.items() if name_ in select_players}

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
        return jsonify({'error': "Please ensure that you have the correct options selected. If you do have all the correct options but the error persists, please email me the issue."}), 500

if __name__ == '__main__':
    app.run(debug=True)
