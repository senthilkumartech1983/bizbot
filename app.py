from flask import Flask, render_template, request, redirect, url_for, session, flash
#from werkzeug.security import generate_password_hash, check_password_hash
import os
import mysql.connector # Import the MySQL connector library
from flask import Flask, request, jsonify, render_template
import os
import streamlit as st
from langchain.chains import create_sql_query_chain
from langchain_google_genai import GoogleGenerativeAI
from sqlalchemy.exc import ProgrammingError
from langchain.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain_community.utilities import SQLDatabase
from langchain.chat_models import init_chat_model
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain import hub
from langgraph.prebuilt import create_react_agent

db_uri = "mysql+mysqlconnector://sql12787708:KCcxsNAL1D@sql12.freesqldatabase.com:3306/sql12787708"

db = SQLDatabase.from_uri(db_uri)

os.environ["GOOGLE_API_KEY"] = "AIzaSyCqSJfni-2eEiFbDl8CpQrXd8Pb_VnrjPc"

# Initialize LLM
#llm = GoogleGenerativeAI(model="gemini-1.5-flash-002",google_api_key="AIzaSyCqSJfni-2eEiFbDl8CpQrXd8Pb_VnrjPc")
llm = init_chat_model('gemini-2.5-flash',model_provider='google_genai')

toolkit = SQLDatabaseToolkit(db=db,llm=llm)
tools = toolkit.get_tools()
#print(tools)

prompt_template = hub.pull('langchain-ai/sql-agent-system-prompt')
prompt_template.messages[0].pretty_print()

system_message = prompt_template.format(dialect='mysql',top_k=5)
sql_agent = create_react_agent(llm,tools,prompt=system_message)
import io
import sys
def get_sql_agent_output(sql_agent_instance, user_query):
    """
    Streams events from a SQL agent, captures the string output of each message's
    .pretty_print() method, and returns these strings as a list.

    Args:
        sql_agent_instance: An initialized SQL agent object (e.g., from LangChain).
        user_query (str): The natural language query to send to the SQL agent.

    Returns:
        list: A list of strings, where each string is the captured output
              of a message's .pretty_print() method.
    """
    print(f"Processing query: '{user_query}'")
    collected_output_strings = [] # Initialize an empty list to store strings

    for event in sql_agent_instance.stream(
        {"messages": ('user', user_query)},
        stream_mode='values'
    ):
        if 'messages' in event and len(event['messages']) > 0:
            if 10 == len(event['messages']) :
                try:
                    print(f"YES")
                    message_object = event['messages'][-1]
                    old_stdout = sys.stdout
                    redirected_output = io.StringIO()
                    sys.stdout = redirected_output

                
                # Call pretty_print() which will now write to our buffer
                    message_object.pretty_print()
                # Get the captured string value
                    captured_string = redirected_output.getvalue()
                    collected_output_strings.append(captured_string)
                finally:
                # Always restore stdout, even if an error occurs
                    sys.stdout = old_stdout
        # You could add an else here if you want to log events that don't contain messages,
        # but it won't be part of the returned list.
            else:     
                print(f"NO")
            # message_object = event['messages'][-1]

            # Create a string buffer to capture output
            

    return collected_output_strings

# Define the UserManager class to handle database interactions for users
class UserManager:
    def __init__(self, db_config):
        self.db_config = db_config

    def _get_db_connection(self):
        """Helper to establish a connection to the MySQL database."""
        try:
            conn = mysql.connector.connect(**self.db_config)
            return conn
        except mysql.connector.Error as err:
            print(f"Error connecting to MySQL: {err}")
            return None

    def _close_db_connection(self, conn, cursor=None):
        """Helper to close database cursor and connection."""
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    def validate_user(self, username, password):
        """
        Validates a user's credentials against the database.
        Returns True if credentials are valid, False otherwise.
        """
        conn = self._get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True) # Get results as dictionaries
            try:
                cursor.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
                user_record = cursor.fetchone()
                print(f"DB result for user '{username}': {user_record}")
                if user_record and user_record['password_hash'] == password:
                   return True
                else:
                   return False
            except mysql.connector.Error as err:
                print(f"Error validating user '{username}': {err}")
                return False
            finally:
                self._close_db_connection(conn, cursor)
        return False # Return False if database connection fails

# --- Flask Application Setup ---
app = Flask(__name__)
app.secret_key = os.urandom(24) # Secret key for session management

# --- MySQL Database Configuration ---
# IMPORTANT: Replace these with your actual MySQL database credentials.
# For production, these should be stored securely (e.g., environment variables).
DB_CONFIG = {
    'host': 'localhost', # Or your MySQL server IP/hostname
    'user': 'root', # Your MySQL username
    'password': '365536', # Your MySQL password
    'database': 'genainosql' # The name of your database
}

# Create an instance of UserManager
user_manager = UserManager(DB_CONFIG)

# Call setup_database when the application starts
# This ensures the table exists and default users are present
#with app.app_context():
#    user_manager.setup_database()


@app.route('/')
def index():
    """
    The root route. Checks if a user is already logged in.
    If logged in, redirects to the query; otherwise, redirects to the login page.
    """
    if 'username' in session:
        return redirect(url_for('query'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login.
    - GET request: Displays the login form.
    - POST request: Processes the submitted username and password.
    """
    if 'username' in session:
        return redirect(url_for('query'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Use the UserManager to validate credentials
        if user_manager.validate_user(username, password):
            session['username'] = username 
            flash('Login successful!', 'success') 
            return redirect(url_for('query'))
        else:
            flash('Invalid username or password.', 'danger')
            return render_template('login.html', username=username)
    
    return render_template('login.html')

@app.route('/query')
def query():
    """
    The protected query page.
    Only accessible if the user is logged in (i.e., 'username' is in the session).
    """
    if 'username' in session:
        return render_template('query.html', username=session['username'])
    else:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    """
    Handles user logout.
    Removes the 'username' from the session, effectively logging the user out.
    """
    session.pop('username', None) 
    flash('You have been logged out.', 'info') 
    return redirect(url_for('login'))

# Route to handle the data submission from the HTML form
@app.route('/process_data', methods=['POST'])
def process_data():
    if request.is_json:
        data = request.get_json()
        input1 = data.get('input1')
                # --- Your Python Logic Here ---
        # Example: Concatenate the inputs or perform a calculation
        if input1 :
            output_message = get_sql_agent_output(sql_agent,{input1})
        else:
            output_message = "Please provide input text"
        # --- End of Your Python Logic ---
              
        original_message_list = output_message
        # Access the string from the list
        message_string = original_message_list[0]
        import re
        # Use a regular expression to find the part after "Ai Message =" and leading/trailing whitespace
        # match = re.search(r"Ai Message\s*=+[\s\n]*(.*)", message_string, re.DOTALL)
        parts = message_string.split("Ai Message")
        if len(parts) > 1:
            cleaned_message = parts[1].strip("= ") # Remove leading/trailing '=' and spaces
        else:
            cleaned_message = message_string
        
        
        return jsonify(output=cleaned_message)
    else:
        return jsonify(error="Request must be JSON"), 400

if __name__ == '__main__':
    # app.run(host='0.0.0.0', port=5000, debug=True)
    app.run()
