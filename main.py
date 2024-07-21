"""
WhatsApp Web Automation with Python and Selenium

Description:
This project leverages Python and Selenium to automate interactions with WhatsApp Web. By integrating OpenAI's artificial intelligence, 
it aims to automatically respond to chat messages based on specific contexts and user settings. 
The current version focuses on extracting and classifying chat messages. Future updates will include function optimizations 
and saving messages and configurations to a database.

Repository: https://github.com/Jersk/Whatsapp-Web-Automation-Python-AI

License:
This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
For more details, see the LICENSE file in the repository or visit https://creativecommons.org/licenses/by-nc/4.0/

Important Note:
WhatsApp's policy prohibits the use of automated systems and spam. This is an experimental project and is not intended for spamming purposes. 
Use it responsibly. The author does not take any responsibility for the misuse of this project.
"""

import time
import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
import os
import re
import hashlib
import json
import traceback

########
# Constants
########
CHAT_NAME = "Mario Rossi"  # Use the full name of the chat, including any spaces
WAIT_TIME = 30  # Wait time for page elements
MESSAGES_FILE = 'messages.json'  # Path to the messages file
DEFAULT_MONTHS_TO_EXTRACT = 1  # Default months to extract if no messages file exists
MAX_SCROLL_ATTEMPTS = 10

# Language configuration
LANGUAGE = 'italian'  # Set the desired language here
LANG_DICT = {
    'italian': {
        'days': {'DOMENICA': 6, 'LUNEDÌ': 0, 'MARTEDÌ': 1, 'MERCOLEDÌ': 2, 'GIOVEDÌ': 3, 'VENERDÌ': 4, 'SABATO': 5},
        'today': 'OGGI',
        'yesterday': 'IERI',
        'open_image': 'Apri immagine'
    }
}

current_date = None  # Track the current date globally

########
# Configure Chrome driver
########
directory_path = os.getcwd()
driver_location = os.path.join(directory_path, 'chrome', 'chromedriver')
binary_location = os.path.join(directory_path, 'chrome', 'chrome')
options = Options()
options.binary_location = binary_location
options.add_argument("user-data-dir=" + os.path.join(directory_path, 'chrome', 'userdata'))

########
# Start browser
########
service = webdriver.chrome.service.Service(driver_location)
browser = webdriver.Chrome(service=service, options=options)
browser.maximize_window()
browser.get('https://web.whatsapp.com/')

# Wait for page to load
wait = WebDriverWait(browser, 600)
wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="app"]/div/div/div[3]/header/div[2]/div/span/div[3]/div/span')))

########
# Function Definitions
########

def generate_message_id(message_data):
    """
    Generate a unique ID for each message based on its content.
    """
    content = json.dumps(message_data, sort_keys=True)
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def save_message_data(message_data, file_path=MESSAGES_FILE):
    """
    Save message data to a JSON file, creating it if it doesn't exist.
    """
    data = []
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
    data.append(message_data)
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)
    print(f"Message saved: {message_data['id']}")  # Debug message to confirm saving

def load_messages(file_path=MESSAGES_FILE):
    """
    Load messages from a JSON file, return an empty list if file does not exist.
    """
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                return json.load(file)
    except Exception as e:
        print(f"Error while loading messages: {e}")
    return []

def get_last_saved_message():
    """
    Retrieve the last saved message from the JSON file, return None if no messages.
    """
    messages = load_messages()
    if messages:
        return messages[-1]
    return None

def search_contact(contact_name):
    """
    Search for the contact using the WhatsApp Web search bar.
    """
    try:
        search_box = WebDriverWait(browser, WAIT_TIME).until(
            EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]'))
        )
        search_box.clear()
        time.sleep(1)
        search_box.send_keys(contact_name)
        time.sleep(5)
        
        contact = WebDriverWait(browser, WAIT_TIME).until(
            EC.presence_of_element_located((By.XPATH, f'//span[@title="{contact_name}"]'))
        )
        print(f"Found contact: {contact_name}")
        return contact
    except Exception as e:
        print(f"Error finding contact: {e}")
        return None

def get_chat_container(browser, last_message_text=None, last_message_datetime=None):
    """
    Open the chat with the specified contact and scroll to the last saved message.
    """
    try:
        print(f"Trying to open chat with {CHAT_NAME}")
        contact = search_contact(CHAT_NAME)
        if contact:
            contact.click()
            time.sleep(2)  # Wait for messages to load

            messages = scroll_to_top(last_message_text, last_message_datetime)
            if last_message_text and last_message_datetime:
                start_index = -1
                for i, message in enumerate(messages):
                    message_text = get_message_text(message)
                    message_datetime, _ = extract_and_update_datetime(message)
                    print(f"Checking message {i}: text='{message_text}', datetime='{message_datetime}'")  # Debug print
                    if message_text == last_message_text and message_datetime == last_message_datetime:
                        start_index = i + 1
                        break
                    if message_datetime and message_datetime > last_message_datetime:
                        start_index = i
                        break
                if start_index != -1:
                    return messages[start_index:]
                else:
                    print("Last message not found or datetime exceeded.")  # Debug print
                    return []
            return messages
        else:
            print(f"Contact {CHAT_NAME} not found.")
            return []
    except Exception as e:
        print(f"Error while trying to open chat and scroll: {e}")
        print(traceback.format_exc())
        return []

def scroll_to_top(last_message_text=None, last_message_datetime=None):
    """
    Scroll to the top of the messages to find the last saved message.
    """
    sync_paused_xpath = '//span[@data-icon="alert-sync-paused"]'
    sync_in_progress_xpath = '//span[@data-icon="sync-in-progress"]'
    max_retries = 5
    retries = 0
    no_new_messages_count = 0
    max_no_new_messages = 5
    reached_start_date = False
    scroll_attempts = 0

    while scroll_attempts < MAX_SCROLL_ATTEMPTS:
        messages = browser.find_elements(By.CSS_SELECTOR, '.message-in, .message-out, ._amjw._amk1._aotl')
        if not messages:
            print("No messages found, continuing to scroll...")
            continue

        browser.execute_script("arguments[0].scrollIntoView(true);", messages[0])
        time.sleep(2)
        new_messages = browser.find_elements(By.CSS_SELECTOR, '.message-in, .message-out, ._amjw._amk1._aotl')

        if last_message_text and last_message_datetime:
            if any(get_message_text(message) == last_message_text for message in messages):
                break
        else:
            if len(new_messages) == len(messages):
                no_new_messages_count += 1
                if no_new_messages_count >= max_no_new_messages:
                    try:
                        sync_paused = browser.find_element(By.XPATH, sync_paused_xpath)
                        if sync_paused:
                            print("Chat sync is paused. Waiting for 1 minute and retrying...")
                            time.sleep(60)
                            retries += 1
                            if retries >= max_retries:
                                print("Sync paused error persists after multiple retries.")
                                raise Exception("Sync paused error persists.")
                            no_new_messages_count = 0  # Reset count after retry
                            continue  # Retry after waiting
                    except NoSuchElementException:
                        pass
                    
                    try:
                        sync_in_progress = browser.find_element(By.XPATH, sync_in_progress_xpath)
                        if sync_in_progress:
                            print("Chat is synchronizing. Waiting for it to finish...")
                            time.sleep(10)  # Adjust this sleep time if necessary
                            no_new_messages_count = 0  # Reset count after waiting
                            continue
                    except NoSuchElementException:
                        pass

                    print("Reached the beginning of the chat without finding the start date.")
                    break
                else:
                    print("No new messages found, waiting for more messages to load...")
                    time.sleep(2)  # Wait a bit longer to allow more messages to load
                    continue  # Check again after waiting

            for message in messages:
                message_datetime, _ = extract_and_update_datetime(message)
                print(f"Scrolling - message datetime: {message_datetime}")  # Debug print
                if message_datetime and last_message_datetime and message_datetime <= last_message_datetime:
                    reached_start_date = True
                    break
            
            if reached_start_date:
                break  # Break if start date has been reached

        scroll_attempts += 1

    return messages

def get_message_type(message):
    """
    Determine the type of message.
    """
    incoming_message = message.get_attribute('innerHTML')
    if "_akbu _akbw" in incoming_message:
        return 'Deleted'
    if "msg-video" in incoming_message and 'copyable-text' in incoming_message:
        return 'Video and text together'
    if "msg-video" in incoming_message:
        return 'Video'
    elif LANG_DICT[LANGUAGE]['open_image'] in incoming_message and 'copyable-text' in incoming_message:
        return 'Image and text together'
    elif 'selectable-text copyable-text' in incoming_message:
        return 'Referred Text' if message.find_elements(By.CLASS_NAME, '_1hl2r') else 'Text'
    elif LANG_DICT[LANGUAGE]['open_image'] in incoming_message and not 'copyable-text' in incoming_message:
        return 'Image'
    elif 'role="slider"' in incoming_message:
        return 'Voice'
    elif 'data-testid="video-content"' in incoming_message:
        return 'Video'
    elif '_1-lf9 _4OiJG _18q-J' in incoming_message:
        return 'File'
    else:
        return None

def get_message_text(message):
    """
    Extract the text of the message.
    """
    text = ""
    try:
        message_html = message.find_element(By.CSS_SELECTOR, 'span.copyable-text').get_attribute("innerHTML")
        for img in message.find_elements(By.TAG_NAME, "img"):
            alt = img.get_attribute("alt")
            message_html = message_html.replace(str(img.get_attribute("outerHTML")), alt)
        text = re.sub(r'<[^>]+>', '', message_html)
    except NoSuchElementException:
        print("No text found in message.")
    except StaleElementReferenceException:
        print("Stale element reference exception while getting message text.")
    except Exception as e:
        print(f"Error while getting message text: {e}")
    return text

def extract_and_update_datetime(message):
    """
    Extract the datetime and update the global current_date variable based on the message content.
    """
    global current_date
    dt = None
    time = None
    try:
        raw_fromdata = message.find_element(By.CSS_SELECTOR, 'div.copyable-text').get_attribute('data-pre-plain-text')
        date_time = raw_fromdata.split('] ')[0][1:]
        date_str, time_str = date_time.split(', ')
        dt = datetime.datetime.strptime(date_time, '%H:%M, %d/%m/%Y')
        current_date = dt.date()
        time = dt.strftime("%H:%M")
        print(f"Extracted from data-pre-plain-text: dt={dt}, current_date={current_date}, time={time}")  # Debug print
    except NoSuchElementException:
        print("No date/time element found.")
    except StaleElementReferenceException:
        print("Stale element reference exception while extracting date and time.")
    except Exception as e:
        print(f"Error while extracting date and time from data-pre-plain-text: {e}")

    try:
        if '_amjw _amk1 _aotl' in message.get_attribute('class'):
            date_text = message.find_element(By.CSS_SELECTOR, 'span._ao3e').text
            if '/' in date_text:
                current_date = datetime.datetime.strptime(date_text, '%d/%m/%Y').date()
                print(f"Updated current_date to {current_date} based on date text")  # Debug print
            elif date_text in [LANG_DICT[LANGUAGE]['today'], LANG_DICT[LANGUAGE]['yesterday']]:
                if date_text == LANG_DICT[LANGUAGE]['today']:
                    current_date = datetime.date.today()
                elif date_text == LANG_DICT[LANGUAGE]['yesterday']:
                    current_date = datetime.date.today() - datetime.timedelta(days=1)
                print(f"Updated current_date to {current_date} based on text '{date_text}'")  # Debug print
            else:
                day_map = LANG_DICT[LANGUAGE]['days']
                desired_day = day_map[date_text]
                today = datetime.date.today()
                current_day = today.weekday()
                days_difference = current_day - desired_day
                if days_difference < 0:
                    days_difference += 7
                current_date = today - datetime.timedelta(days=days_difference)
                print(f"Updated current_date to {current_date} based on day '{date_text}'")  # Debug print
    except NoSuchElementException:
        print("No date text element found.")
    except StaleElementReferenceException:
        print("Stale element reference exception while updating current date.")
    except Exception as e:
        print(f"Error while updating current date: {e}")

    try:
        # Additional attempt to extract time
        time_element = message.find_element(By.XPATH, ".//span[contains(@class, 'x1c4vz4f') and contains(@class, 'x2lah0s')]")
        time_str = time_element.get_attribute('innerText') or time_element.get_attribute('textContent')
        print(f"Found time from specific class 1: {time_str}")
        if not time:
            time = time_str
    except NoSuchElementException:
        print("No time element found.")
    except StaleElementReferenceException:
        print("Stale element reference exception while extracting time.")
    except Exception as e:
        print(f"Error while extracting time from specific class: {e}")

    try:
        # Additional attempt to extract time
        time_element = message.find_element(By.XPATH, ".//span[contains(@class, 'x1rg5ohu') and contains(@class, 'x16dsc37')]")
        time_str = time_element.get_attribute('innerText') or time_element.get_attribute('textContent')
        print(f"Found time from specific class 2: {time_str}")
        if not time:
            time = time_str
    except NoSuchElementException:
        print("No time element found.")
    except StaleElementReferenceException:
        print("Stale element reference exception while extracting time.")
    except Exception as e:
        print(f"Error while extracting time from specific class: {e}")

    if current_date and time:
        try:
            dt = datetime.datetime.combine(current_date, datetime.datetime.strptime(time, "%H:%M").time())
            print(f"Combined datetime: {dt}")
        except Exception as e:
            print(f"Error combining date and time into datetime: {e}")

    print(f"Final extracted datetime: {dt}, current_date: {current_date}, time: {time}")  # Debug print
    return dt, time

def get_message_data(message):
    """
    Retrieve message data, including text, datetime, type, and unique ID.
    """
    dt, time = extract_and_update_datetime(message)
    if dt is None or time is None:
        print("Skipping message due to missing date/time.")
        return None

    message_dir = 'In' if 'message-in' in message.get_attribute('outerHTML') else 'Out'
    message_type = get_message_type(message)
    
    message_data = {
        'type': message_type,
        'message_dir': message_dir,
        'date': current_date.strftime("%d/%m/%Y") if current_date else None,
        'time': time,
        'datetime': dt.strftime("%d/%m/%Y %H:%M") if dt else None
    }

    if message_type == 'Video and text together':
        try:
            video_tag = message.find_element(By.XPATH, ".//video")
            latest_video_src = video_tag.get_attribute('src')
            text = get_message_text(message)
            message_data.update({
                'text': text,
                'video_src': latest_video_src,
            })
        except NoSuchElementException:
            print("No video element found.")
        except StaleElementReferenceException:
            print("Stale element reference exception while getting video and text together.")
        except Exception as e:
            print(f"Error while getting video and text together: {e}")

    elif message_type == 'Image and text together':
        img_tag = message.find_elements(By.XPATH, ".//img")
        latest_image_src = img_tag[-1].get_attribute('src')
        text = get_message_text(message)
        message_data.update({
            'text': text,
            'image_src': latest_image_src,
        })
    elif message_type == 'Image':
        img_tag = message.find_elements(By.XPATH, ".//img")
        latest_image_src = img_tag[-1].get_attribute('src')
        message_data.update({
            'image_src': latest_image_src,
        })
    elif message_type == 'File':
        file_tag = message.find_element(By.XPATH, ".//div[@class='_1-lf9 _4OiJG _18q-J']")
        latest_file_src = file_tag.get_attribute('data-url')
        message_data.update({
            'file_src': latest_file_src,
        })
    elif message_type == 'Referred Text':
        try:
            a = message.find_element(By.CLASS_NAME, '_1hl2r').text
            b = a.split('\n')[1:]
            time = b[-1]
            referred_msg = ''.join(map(str, b))
            reply = message.find_element(By.CLASS_NAME, '_21Ahp').text
            message_data.update({
                'referred_msg': referred_msg,
                'reply': reply,
            })
        except NoSuchElementException:
            print("No referred text element found.")
        except StaleElementReferenceException:
            print("Stale element reference exception while getting referred text.")
        except Exception as e:
            print(f"Error while getting referred text: {e}")

    elif message_type == 'Text':
        text = get_message_text(message)
        message_data.update({
            'text': text,
        })

    message_id = generate_message_id(message_data)
    message_data['id'] = message_id

    save_message_data(message_data)

    return message_data

def search_messages(last_saved_message=None, keyword=None, date_range=None, start_date=None):
    """
    Search messages up to the last saved message, with optional keyword, date range, or start date filters.
    """
    last_message_text = None
    last_message_datetime = None
    if last_saved_message:
        last_message_text = last_saved_message['text']
        last_message_datetime = datetime.datetime.strptime(last_saved_message['date'] + ' ' + last_saved_message['time'], '%d/%m/%Y %H:%M')
    else:
        if not start_date:
            start_date = datetime.datetime.today() - datetime.timedelta(days=DEFAULT_MONTHS_TO_EXTRACT * 30)

    messages = get_chat_container(browser, last_message_text, last_message_datetime)
    if not messages:
        print("No messages found.")
        return []

    filtered_messages = []
    for message in messages:
        message_data = get_message_data(message)
        if not message_data:
            continue

        if start_date:
            message_datetime = datetime.datetime.strptime(message_data['datetime'], '%d/%m/%Y %H:%M')
            if message_datetime < start_date:
                continue

        if keyword and keyword.lower() not in message_data.get('text', '').lower():
            continue

        if date_range:
            message_date = datetime.datetime.strptime(message_data['date'], '%d/%m/%Y').date()
            if not (date_range[0] <= message_date <= date_range[1]):
                continue

        filtered_messages.append(message_data)

    return filtered_messages

def main():
    """
    Main function to execute the script.
    """
    try:
        last_saved_message = get_last_saved_message()
        start_date = datetime.datetime(2024, 6, 20)
        date_range = (start_date.date(), datetime.datetime.today().date())

        filtered_messages = search_messages(last_saved_message, date_range=date_range)
        print(f'Total amount of filtered messages: {len(filtered_messages)}')
        #for i, message_data in enumerate(filtered_messages):
        #    print(f"Message {i}: {message_data['text']}")

    except Exception as e:
        print(f"Error: {e}")
        print(traceback.format_exc())
    finally:
        browser.quit()

if __name__ == "__main__":
    main()
