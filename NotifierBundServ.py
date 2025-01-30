import requests
import yagmail
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow logging

websites = [
    {"url": "https://www.service.bund.de/Content/DE/Ausschreibungen/Suche/Formular.html?nn=4641482&type=0&searchResult=true&view=processForm&resultsPerPage=100", "keywords": ["catering", "verpflegung", "lebensmittel", "kantin", "speise", "hotel", "essen"]},
]

# Email configuration
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MATCHES_FILE = os.path.join(SCRIPT_DIR, "matches.json")
TEXT_PARTS_FILE = "extracted_text_parts.json"

def clear_matches_file():
    """Clear the matches.json file."""
    if os.path.exists(MATCHES_FILE):
        with open(MATCHES_FILE, "w") as file:
            json.dump({}, file, indent=4)
        print(f"{MATCHES_FILE} has been cleared.")
    else:
        print(f"{MATCHES_FILE} does not exist. Creating a new empty file.")
        with open(MATCHES_FILE, "w") as file:
            json.dump({}, file, indent=4)

def load_previous_matches():
    """Load previously found matches from a file."""
    if os.path.exists(MATCHES_FILE):
        with open(MATCHES_FILE, "r") as file:
            return json.load(file)
    return {}

def save_matches(matches):
    """Save matches to a file."""
    with open(MATCHES_FILE, "w") as file:
        json.dump(matches, file, indent=4)

def save_text_parts(text_parts):
    """Save extracted text parts to a file."""
    with open(TEXT_PARTS_FILE, "w") as file:
        json.dump(text_parts, file, indent=4)

def filter_relevant_titles(extracted_data, keywords):
    """
    Search extracted titles for keywords (case insensitive) and return matches.
    """
    relevant_matches = []
    for data in extracted_data:
        text = data["title"].lower()
        date = data.get("date", "No Date")
        link = data.get("link", "No Link")
        
        if any(keyword.lower() in text for keyword in keywords):
            print(f"Relevant Match Found: {text}")
            relevant_matches.append({"title": data["title"], "date": date, "link": link})
    
    return relevant_matches

def extract_titles_with_selenium(url):
    """
    Extract titles, corresponding dates, and links directly from a dynamically rendered webpage using Selenium.
    Returns an array of dictionaries containing the title, date, and link.
    """
    extracted_data = []
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(url)
        
        WebDriverWait(driver, 5).until(lambda d: d.execute_script("return document.readyState") == "complete")

        # Handle cookies popup if necessary
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'alle akzeptieren')]"))
            ).click()
            print("Cookies popup dismissed.")
        except Exception:
            print("No cookies popup found.")

        results = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "result-list"))
        )
        print(f"Found {len(results)} result-list elements.")

        for result in results:
            try:
                links = result.find_elements(By.XPATH, ".//a")
                for link in links:
                    title = link.text.strip()
                    href = link.get_attribute("href").strip()
                    if title and href:
                        extracted_data.append({"title": title, "link": href})
                        print(f"Extracted: Title: {title}, Link: {href}")
            except Exception as e:
                print(f"Error extracting data from a result: {e}")
    except Exception as e:
        print(f"Error loading the page: {e}")
    finally:
        driver.quit()

    return extracted_data

def send_email(new_matches):
    """Send an email notification with titles, dates, and links."""
    subject = "Neue Ausschreibungen verfügbar!!"
    body = "Die folgenden neuen Übereinstimmungen wurden gefunden:\n\n"

    for match in new_matches:
        title = match.get("title", "No Title")
        date = match.get("date", "No Date")
        link = match.get("link", "No Link")
        body += f"Title: {title}\nLink: {link}\n\n"

    try:
        yag = yagmail.SMTP(EMAIL_ADDRESS, EMAIL_PASSWORD)
        yag.send("Henrik.Hemmer@flc-group.de", subject, body)
        print("Email sent!")
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():
    """Main function to check websites and send emails."""
    previous_matches = load_previous_matches()
    print("Previous Matches:", previous_matches)
    new_matches = []

    for site in websites:
        url = site["url"]
        keywords = site["keywords"]

        extracted_data = extract_titles_with_selenium(url)
        save_text_parts(extracted_data)

        matches = filter_relevant_titles(extracted_data, keywords)

        if url not in previous_matches:
            previous_matches[url] = []

        for match in matches:
            if match not in previous_matches[url]:
                new_matches.append(match)
                previous_matches[url].append(match)

    if new_matches:
        send_email(new_matches)

    save_matches(previous_matches)

if __name__ == "__main__":
    main()
