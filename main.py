from flask import Flask, render_template, request, send_file, jsonify, session
import csv
import io
from io import BytesIO
from io import StringIO
import random
import openai
import os
import traceback
import logging
import faker

app = Flask(__name__)

# Set your OpenAI API key
openai.api_key = os.environ['OPENAIDEMO']
openai.api_key = os.getenv('OPENAIDEMO')
if not openai.api_key:
    raise ValueError("OPENAIDEMO environment variable is not set. Please set it in the Secrets tab.")

print(f"API Key set: {'Yes' if openai.api_key else 'No'}")
print(f"API Key length: {len(openai.api_key) if openai.api_key else 0}")

def extract_python_code(response):
    lines = response.split('\n')
    code_lines = []
    in_code_block = False
    for line in lines:
        if line.strip().startswith('```python'):
            in_code_block = True
            continue
        elif line.strip() == '```' and in_code_block:
            in_code_block = False
            continue
        if in_code_block:
            code_lines.append(line)
    return '\n'.join(code_lines)

def generate_python_code(scenario, num_columns):
    prompt = f"""
    Create a Python function named 'generate_random_data' that generates random data for the following business scenario:
    {scenario}
    
    The function should:
    1. Take a 'num_rows' parameter
    2. Generate exactly {num_columns} columns of data
    3. Return a list of dictionaries, where each dictionary represents a row of data
    4. Include appropriate field names and data types for the scenario
    5. Use the random module to generate data
    
    Provide ONLY the Python code for the function, enclosed in triple backticks, without any additional explanation.
    """
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a Python code generator. Respond only with the requested Python code, enclosed in triple backticks."},
                {"role": "user", "content": prompt}
            ]
        )
        full_response = response.choices[0].message.content
        return extract_python_code(full_response)
    except Exception as e:
        logging.error(f"Error in generating code: {str(e)}")
        return None

logging.basicConfig(level=logging.DEBUG)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        logging.info(f"Received POST request with scenario: {request.form['scenario']}")
        try:
            scenario = request.form['scenario']
            num_rows = int(request.form['num_rows'])
            num_columns = int(request.form['num_columns'])
            logging.info(f"Received request: scenario='{scenario}', num_rows={num_rows}")
            generated_code = generate_python_code(scenario, num_columns)
            logging.debug(f"Generated code: {generated_code}")
            if generated_code and isinstance(generated_code, str):
                try:
                    exec(generated_code, globals())
                    if 'generate_random_data' not in globals():
                        raise NameError("The function 'generate_random_data' was not defined.")
                    # Check if this is a preview request
                    if 'preview' in request.form:
                        preview_data = globals().get('generate_random_data', lambda num_rows: [])(5)  # Generate 5 rows for preview
                        return jsonify({'success': True, 'preview': preview_data})
                    # If not a preview, generate full data set
                    data = globals().get('generate_random_data', lambda num_rows: [])(num_rows)
                    logging.info(f"Generated {len(data)} rows of data")
                    output = StringIO()
                    writer = csv.DictWriter(output, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
                    output.seek(0)
                    return send_file(io.BytesIO(output.getvalue().encode()), 
                                     mimetype='text/csv',
                                     as_attachment=True,
                                     download_name='data_scenario.csv')
                except Exception as e:
                    logging.error(f"Error in executing generated code: {str(e)}")
                    logging.error(traceback.format_exc())
                    return jsonify({'error': f'Error in executing generated code: {str(e)}'}), 500
            else:
                logging.error("Failed to generate code")
                return jsonify({'error': 'Failed to generate code'}), 500
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Unexpected error: {str(e)}'}), 500
    else:
        # For GET requests, retrieve the selected scenario from the session
        selected_scenario = session.get('selected_scenario', '')
        return render_template('index.html', scenario=selected_scenario)


@app.route('/scenario-browser')
def scenario_browser():
    return render_template('scenario_browser.html')
@app.route('/set-scenario', methods=['POST'])
def set_scenario():
    data = request.json
    scenario = data.get('scenario')
    # Store the scenario in session
    session['selected_scenario'] = scenario
    return jsonify({"success": True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)