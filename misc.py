########
# Libraries
########     
import openai
import mysql.connector
import os
import time
import pydub
import tempfile
import re
from datetime import datetime, date, timedelta

########
# Setup General
######## 
directory_path = os.getcwd()
mysql_hostname = 'localhost'
# OpenAI Token
openai.api_key = "your-openai-api-key"

########
# Setup Selenium
########
driver_location = directory_path+'/chrome/chromedriver'
binary_location = directory_path+'/chrome/opt/google/chrome/google-chrome'

WAIT_TIME = 10

options = Options()
options = webdriver.ChromeOptions()
options.binary_location = binary_location
options.add_argument("user-data-dir="+directory_path+"/chrome/userdata")

driver = webdriver.Chrome(executable_path=driver_location, options=options)

class User:
    def __init__(self, user_id):
        self.user_id = user_id
        self.user_mysql_username = 'user_' + self.user_id
        self.user_mysql_password = 'user_PWD_' + self.user_id
        self.user_mysql_DB = 'user_DB_' + self.user_id

        self.chrome_user_data_dir = directory_path+'/chrome/userdata'+ self.user_id

        self.cnx = mysql.connector.connect(user=self.user_mysql_username, password=self.user_mysql_password, host=mysql_hostname)
        self.cursor = self.cnx.cursor()
        self.cursor.execute("CREATE DATABASE IF NOT EXISTS {}".format(self.user_mysql_DB))
        self.cursor.execute("USE {}".format(self.user_mysql_DB))
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_setup (
                id INT AUTO_INCREMENT PRIMARY KEY,
                status VARCHAR(255),
                mode VARCHAR(255),
                time_scheduler DATETIME
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_info (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(30),
                birthday DATE,
                address_city VARCHAR(255),
                country CHAR(10),
                phone_number VARCHAR(18)
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_contacts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(30),
                relationship CHAR(25),
                username VARCHAR(75),
                birthday DATE,
                address_city VARCHAR(255),
                country CHAR(10),
                phone_number VARCHAR(18)
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INT AUTO_INCREMENT PRIMARY KEY,
                chat_id VARCHAR(255),
                msg_id VARCHAR(255),
                msg_from VARCHAR(255),
                msg_datetime DATETIME,
                msg_type VARCHAR(255),
                msg_src_media VARCHAR(255),
                msg_text TEXT,
                msg_ref VARCHAR(255),
                modded BOOLEAN,
                queque BOOLEAN
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats_summary (
                id INT AUTO_INCREMENT PRIMARY KEY,
                chat_id VARCHAR(255),
                start_time DATETIME,
                end_time DATETIME
            )
        """)
        self.cursor.close()
        self.cnx.close()

    ######## Function to select the database assigned to a certain user and get userX setup ########
    def get_user_SETUP(self):
        self.cnx = mysql.connector.connect(user=self.user_mysql_username, password=self.user_mysql_password, host=mysql_hostname, database=self.user_mysql_DB)
        self.cursor = self.cnx.cursor()
        query = "SELECT status, mode, time_scheduler FROM user_setup"
        self.cursor.execute(query)
        row = self.cursor.fetchone()

        status = row[0]
        mode = row[1]
        time_scheduler = row[2]

        self.cursor.close()
        return self.chrome_user_data_dir, status, mode, time_scheduler
    
    ######## Function to select the database assigned to a certain user and get userX info ########
    def get_user_INFO(self):
        today = date.today()
        self.cnx = mysql.connector.connect(user=self.user_mysql_username, password=self.user_mysql_password, host=mysql_hostname, database=self.user_mysql_DB)
        self.cursor = self.cnx.cursor()
        query = "SELECT name, birthday, address_city, country, phone_number FROM user_contacts"
        self.cursor.execute(query)
        row = self.cursor.fetchone()

        name = row[0]
        birthday = row[1]
        city = row[2]
        country = row[3]
        phone_number = row[4]

        self.cursor.close()

        # convert the string in a datetime object
        data_birthday = datetime.strptime(birthday, '%Y-%m-%d')
        age = today.year - data_birthday.year - ((today.month, today.day) < (data_birthday.month, data_birthday.day))

        return name, birthday, age, city, country, phone_number
    
    ######## Function get contactX info ########
    def get_contact_INFO(self, username):
        today = date.today()
        self.cnx = mysql.connector.connect(user=self.user_mysql_username, password=self.user_mysql_password, host=mysql_hostname, database=self.user_mysql_DB)
        self.cursor = self.cnx.cursor()
        query = "SELECT name, relationship, birthday, address_city, country, phone_number FROM user_contacts WHERE username = %s"
        self.cursor.execute(query, (username,))
        row = self.cursor.fetchone()
        
        name = row[0]
        relationship = row[1]
        birthday = row[2]
        city = row[3]
        country = row[4]
        phone_number = row[5]

        self.cursor.close()

        # convert the string in a datetime object
        data_birthday = datetime.strptime(birthday, '%Y-%m-%d')
        age = today.year - data_birthday.year - ((today.month, today.day) < (data_birthday.month, data_birthday.day))

        return name, relationship, birthday, age, city, country, phone_number

######## Fuction to save an element in the user DB ########
# Usage:
#       msg_query = {'chat_id': chat_id, 'msg_id': msg_id, 'msg_from': msg_from, 'msg_datetime': msg_datetime, 'msg_type': msg_type, 'msg_src_media': msg_src_media, 'msg_text': msg_text, 'msg_ref': msg_ref}
#       save_data(msg_query, user)
#   OR
#       save_data('table_name', {'field1': 'value1', 'field2': 'value2'}, user)
#
def save_data(table_name, data_query, user):
    # get the user mysql database connection
    cnx = user.get_user_SETUP()

    cursor = cnx.cursor()
    
    # query define
    columns = ", ".join(data_query.keys())
    values = ", ".join(['%s'] * len(data_query))
    query = "INSERT INTO {} ({}) VALUES ({})".format(table_name, columns, values)
    
    # prepare data query for saving
    data_values = tuple(data_query.values())
    
    # execute the query
    cursor.execute(query, data_values)
    
    # commit changes and close the connection
    cnx.commit()
    cursor.close()
    cnx.close()

######## Fuction to process chat messages with OpenAI and save the summary
# Usage:
#       
#       
def process_chat_messages(chat_id):
    # set up variables for message processing
    last_modded_time = None
    last_message_time = None
    messages_to_process = []
    messages_processed = 0

    # get cursor object to execute MySQL queries
    cnx = user.get_user_SETUP()
    cursor = cnx.cursor()

    # loop through chat messages until no more messages to process last_message_time
    while True:
        # get last modded time from database
        cursor.execute("SELECT MAX(datetime) FROM chats WHERE modded=1 AND chat_id=%s", (chat_id,))
        result = cursor.fetchone()
        last_modded_time = result[0] if result[0] else datetime.min

        # get last message time from database
        cursor.execute("SELECT MAX(datetime) FROM chats")
        result = cursor.fetchone()
        last_message_time = result[0] if result[0] else datetime.min

        # if last message time is less than two hours from last modded time, add to messages to process
        if last_message_time - last_modded_time < timedelta(hours=2):
            cursor.execute("SELECT message FROM chats WHERE datetime > %s AND datetime <= %s AND chat_id=%s", (last_modded_time, last_message_time, chat_id))
            results = cursor.fetchall()
            messages_to_process += [result[0] for result in results]
        else:
            # if no more messages to process, break out of loop
            break

    # if there are less than 100 messages to process, do not process
    if len(messages_to_process) < 100:
        return

    # divide messages to process into groups of 100
    message_groups = [messages_to_process[i:i+100] for i in range(0, len(messages_to_process), 100)]

    # process each group of messages with OpenAI and save results to database
    for i, message_group in enumerate(message_groups):
        # join messages into single string
        message_text = "\n".join(message_group)

        # generate summary with OpenAI GPT-3
        summary = openai.Completion.create(
            engine="davinci",
            prompt=message_text,
            max_tokens=500,
            n=1,
            stop=None,
            temperature=0.5,
        ).choices[0].text

        # get datetime of first and last messages in group
        first_message_time = last_modded_time + timedelta(hours=2) if i == 0 else last_message_time
        last_message_time = last_message_time

        # insert summary and metadata into database
        summary_data = {
            "chat_id": chat_id,
            "summary": summary,
            "start_time": first_message_time,
            "end_time": last_message_time
        }
        save_data("chat_summary", summary_data, user)

        # update modded field in user_chat table for messages in group
        cursor.execute("UPDATE chats SET modded=1 WHERE datetime > %s AND datetime <= %s AND chat_id=%s", (first_message_time, last_message_time, chat_id))
        cnx.commit()

        # increment messages_processed counter
        messages_processed += len(message_group)

    # print status message
    #print(f"{messages_processed} messages processed")

######## Fuction to translate audio message in text ########
# Usage:
#       a = audio_to_text('audio.ogg')
#       print(a)
#
def audio_to_text(audio_in):
    # Audio format for input
    AUDIO_FORMAT = 'ogg'
    # Check if audio file exists
    if not os.path.isfile(audio_in):
        return "error"

    try:
        # Load audio file using pydub library
        audio = pydub.AudioSegment.from_file(audio_in, format=AUDIO_FORMAT)

        # Create a temporary file and save the audio file in WAV format to the temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            wav_filename = f.name
            audio.export(wav_filename, format='wav')

        # Send transcription request to OpenAI API using the temporary file
        with open(wav_filename, 'rb') as f:
            response = openai.Audio.transcribe("whisper-1", f)

        # Extract text from the response
        transcription_text = response["text"]

        return transcription_text

    except (pydub.exceptions.CouldntDecodeError, openai.Error) as e:
        #print(f"Error during audio processing: {e}")
        return "error"

    finally:
        # Delete the temporary file
        if os.path.isfile(wav_filename):
            os.remove(wav_filename)

######## Fuction to generate a response for a message ########
# Usage:
#       response = generate_response(contact_name="Mario Rossi", contact_relationship="friend", contact_birthday="01/01/1900", contact_chat_summary="last messages summary, including relevant informations", chat_latest_msg="last message", chat_msg_to_reply="the message you want reply to")
#       print(response)
#
def generate_response(contact_username):
    # contact_chat_summary, chat_latest_msg, chat_msg_to_reply

    user_name, user_birthday, user_age, user_city, user_country, user_phone_number = user.get_user_INFO()
    contact_name, contact_relationship, contact_birthday, contact_age, contact_city, contact_country, contact_phone_number = user.get_contact_INFO(contact_username)

    # Create OpenAI prompt
    prompt = f"Your name is {user_name}, you are {user_age} years old and you live in {user_city}. You are currently chatting with {contact_name},"
    if contact_relationship:
        prompt += f" a {contact_relationship} of yours"
    if contact_birthday:
        prompt += f" who has a birthday on {contact_birthday}"
    if contact_chat_summary:
        prompt += f". So far, you and {contact_name} have been discussing several matters, including {contact_chat_summary}"
    if chat_latest_msg:
        prompt += f". These are the last 50 messages you have exchanged: {chat_latest_msg}"
    prompt += f". With this available knowledge and being aware of the nature of your relationship with this person, set a suitable tone and reply to this message: '{chat_msg_to_reply}'"


    # Configuring Text Generation Request to OpenAI
    completions = openai.Completion.create(engine="davinci", prompt=prompt, max_tokens=50, n=1,stop=None,temperature=0.6)

    # Mining the response generated by OpenAI and format it
    response = completions.choices[0].text
    response = re.sub('[^0-9a-zA-Z\n\.\?,!]+', ' ', response)
    response = response.strip()

    return response


################################################################################################################

# create a User test object for the current user
user = User('280')
# get the user's setup values
chrome_user_data_dir, status, mode, time_scheduler = user.get_user_SETUP()
# use the values as needed
print(chrome_user_data_dir, status, mode, time_scheduler)

# create a message query
#msg_query = {'chat_id': chat_id, 'msg_id': msg_id, 'msg_from': msg_from, 'msg_datetime': msg_datetime, 'msg_type': msg_type, 'msg_src_media': msg_src_media, 'msg_text': msg_text}

# save the message for the current user
#save_data(msg_query, user)

######## START
driver.maximize_window()
driver.get('https://web.whatsapp.com/')
wait = WebDriverWait(driver, 600)
wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="app"]/div/div/div[3]/header/div[2]/div/span/div[3]/div/span')))


"""
template Save message
//// Messaggio
msg_query = {'chat_id': chat_id, 'msg_id': msg_id, 'msg_from': msg_from, 'msg_datetime': msg_datetime, 'msg_type': msg_type, 'msg_src_media': msg_src_media, 'msg_text': msg_text,}
save_msg(msg_query)


>>>> DB USER XXXXXXX
---chats
ID
chat_id
msg_id (row)
msg_from (in/out)
msg_datetime
msg_type
msg_src_media
msg_src_description !!!!!!
msg_text (media, text, link..)
msg_ref
queque (added/confirmed) !!!!!! to be managed when saving if automatic reply is active for this chat (or all of them)

---queque_list
ID
id_msg (ID CHAT)
status
//add message to reply to
//after x seconds, starts the automatic reply process which replies if no other messages have been sent after that message
// as soon as you reply, delete messages from the queque_list and update queque status from ‘chats’
---subscription
history (+/- and detail)

--- setup
chrome_user_data_dir
status (off/on/time)
mode (reply all/selected/save_only)
time_scheduler

###############################
"""
