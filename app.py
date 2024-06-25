
from flask import Flask, request, jsonify
from flask_cors import CORS  # Import CORS
from dotenv import load_dotenv
import re
from bs4 import BeautifulSoup
import sys
import os
import requests
import json
import logging
import argparse
from openai import OpenAI
import time

load_dotenv()
app = Flask(__name__)
CORS(app)

serper_api_key = os.getenv("SERP_API_KEY")
hunter_io_key = os.getenv("HUNTER_IO_KEY")
crawlbase_key = os.getenv("CRAWLBASE_KEY")

client = OpenAI()

system_instruction = """
    You will receive <input> on a lead and use it to synthesize a <bio_object>. 

    The <bio_object> is based on the following <format>:

    <format>
    {{
        "name" : "",
        "company" : "",
        "bio" : "",
        "email" : "",
        "phone" : "",
    }}
    </format>

    Using the aforementioned instructions, you will process the user <input> provided below.

    When you return output, only return it as defined in <format>.
"""

system_instruction_v2 = """
    You will receive detailed information on a lead. Your task is to synthesize this information into a concise bio. Follow these guidelines:

    Conciseness: Keep the bio brief and focused solely on the provided information.
    Completeness: Use all the information given. Do not leave out any details provided.
    No Qualitative Judgments: Describe the lead without adding any qualitative or subjective assessments.
    Handling Incomplete Information: If the lead's role or other details are not fully specified, do not mention or indicate the absence of this information. The bio should not acknowledge missing details.
    Example Format: "Foo Bar has an undergraduate degree and currently focuses on slime at Nick."
    Ensure the bio contains only the factual data provided, with no extrapolation or mention of any missing information.
"""

def search(query):
    """
    Perform a search using the Serper API.

    Sends a POST request to the Serper API with the given query and prints the response text.

    :param query: The search query.
    :type query: str
    :return: The response text from the Serper API.
    :rtype: str
    """
    url = "https://google.serper.dev/search"

    payload = json.dumps({
        "q": query
    })

    headers = {
        'X-API-KEY': serper_api_key,
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    #logging.info(response.text)

    return response.text

def scrape_linkedin_profiles(url):
    
    headers = {
        "User-Agent": "rwtreter",
    }

    profile_obj = {
        "profile_name" : "",
        "description" : ""
    }

    logging.info(f"Accessing url: {url}")
    
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract profile information
        title_tag = soup.find('title')
        designation_tag = soup.find('h2')
        followers_tag = soup.find('meta', {"property": "og:description"})
        description_tag = soup.find('p', class_='break-words')

        # Check if the tags are found before calling get_text()
        name = title_tag.get_text(strip=True).split("|")[0].strip() if title_tag else "Profile Name not found"
        designation = designation_tag.get_text(strip=True) if designation_tag else "Designation not found"

        # Use regular expression to extract followers and description count
        followers_match = re.search(r'\b(\d[\d,.]*)\s+followers\b', followers_tag["content"]) if followers_tag else None
        followers_count = followers_match.group(1) if followers_match else "Followers count not found"

        description = description_tag.get_text(strip=True) if description_tag else "Description not found"

        logging.info(f"Profile Name: {name}")
        logging.info(f"Designation: {designation}")
        logging.info(f"Followers Count: {followers_count}")
        logging.info(f"Description: {description}")
        
        profile_obj["profile_name"] = name
        profile_obj["description"] = description

        return profile_obj
    else:
        logging.info(f"Error: Unable to retrieve the LinkedIn company profile. Status code: {response.status_code}")
        return None

def retrieve_rid_data(rid):
    try:
        retries = 10
        success = False
        sleep_time = 1
        while retries > 0 and not success:
            storage_url = "https://api.crawlbase.com/storage"
            storage_params = {
                "token": crawlbase_key,
                "rid": rid
            }

            if not storage_params["rid"]:
                raise ValueError("No RID found in initial response")

            try:
                storage_response = requests.get(storage_url, params=storage_params)
                storage_response.raise_for_status()
                success = True  # If response is successful, set success to True to break the loop
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logging.warning(f"404 Not Found, retrying, RID: {rid}")
                    retries -= 1
                    time.sleep(sleep_time)
                    sleep_time += 2
                else:
                    raise  # Re-raise the exception if it's not a 404 to handle it with the outer exception handler

            if success:
                data = storage_response.json()
                if data:
                    linkedin_scraped_obj = {
                        "name" : data["title"],
                        "profile_url" : data["profileUrl"],
                        "headline": data["headline"],
                        "position": data["positionInfo"]["company"],
                        "school": data["educationInfo"]["school"],
                        "summary": data["summary"]
                    }
                    return linkedin_scraped_obj
                
        if not success:
            logging.error("Failed to retrieve data after multiple retries.")
            return jsonify({"error": "Failed to retrieve data after multiple retries."}), 500

    except requests.exceptions.RequestException as e:
        logging.error(f"Request error occurred: {e}")
        return None#jsonify({"error": str(e)}), 500
    except KeyError as e:
        logging.error(f"Key error in response data: {e}")
        return None#jsonify({"error": "Key error in response data"}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None#jsonify({"error": str(e)}), 500

def scrape_linkedin_profiles_v2(profile_link):
    async_url = "https://api.crawlbase.com/"
    params = {
        "token": crawlbase_key,
        "scraper": "linkedin-profile",
        "async": "true",
        "url": profile_link
    }

    # Check if the profile is already cached
    try: 
        rids_url = "https://api.crawlbase.com/storage/rids"
        rids_params = {
            "token": crawlbase_key,
            "limit": "100"
            }
        rids_response = requests.get(rids_url, params=rids_params)
        rids_response.raise_for_status()
        
        rids_data = rids_response.json()

        rids = rids_data["rids"]
        print(rids)
        for rid in rids:
            print(f"checking rid {rid}")
            linkedin_data = retrieve_rid_data(rid)
            if linkedin_data:
                print(f'Checking {linkedin_data["profile_url"]}')
                if linkedin_data["profile_url"] in profile_link:
                    return linkedin_data
    
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error occurred: {e}")
        return None#jsonify({"error": str(e)}), 500
    except KeyError as e:
        logging.error(f"Key error in response data: {e}")
        return None#jsonify({"error": "Key error in response data"}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None#jsonify({"error": str(e)}), 500

    response = requests.get(async_url, params=params)
    response.raise_for_status()  # Check for HTTP request errors
    async_response = response.json()

    retrieve_rid_data(async_response["rid"])

def query_llm(dossier):
    response = client.chat.completions.create(
      model="gpt-4",
      messages=[
        {
          "role": "system",
          "content": system_instruction_v2
        },
        {
          "role": "user",
          "content": dossier
        }
      ],
      temperature=0.7,
      max_tokens=512,
      top_p=1
    )

    return response

def get_email(first_name, last_name, company):

    # Set up the API endpoint and parameters
    url = "https://api.hunter.io/v2/email-finder"
    params = {
        "domain": company + ".com",
        "first_name": first_name,
        "last_name": last_name,
        "api_key": hunter_io_key
    }

    try:
        # Make the API request
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes

        # Parse the JSON response
        data = response.json()
        print(data)
        # Extract the email from the response
        email = data["data"]["email"]
        return email

    except requests.exceptions.RequestException as e:
        print(f"Error occurred while making the hunter.io API request: {e}")
        return None

    except (KeyError, IndexError) as e:
        print(f"Error occurred while parsing the hunter.io API response: {e}")
        return None

@app.route('/generate_bio', methods=['POST', 'OPTIONS'])
def generate_bio():
   if request.method == 'OPTIONS':
       headers = {
           'Access-Control-Allow-Origin': '*',
           'Access-Control-Allow-Methods': 'POST',
           'Access-Control-Allow-Headers': 'Content-Type'
       }
       return ('', 204, headers)

   data = request.get_json()
   first_name = data['first']
   last_name = data['last']
   company_name = data['company']

   results = json.loads(search(f"{first_name} {last_name} {company_name}"))

   item_arr = results["organic"]
   dossier = {
       "linkedin_data": "",
       "email": "",
       "phone": ""
   }

   isLinkedin = False
   for item in item_arr:
       link = item["link"]
       snippet = item["snippet"]
       if "linkedin.com" in link:
           isLinkedin = True
           break

   shouldQuery = False
   if isLinkedin:
       linkedin_data = scrape_linkedin_profiles_v2(link)
       if linkedin_data:
           snippet_clean = re.sub(r'\| Learn more about .*?\.', '', snippet)
           dossier["linkedin_data"] = str(linkedin_data) + snippet_clean
           shouldQuery = True
       else:
            print("LinkedIn query failed") 
   
   if linkedin_data["name"].lower() != f"{first_name} {last_name}".lower():
    split_name = linkedin_data["name"].split(" ")
    first_name = split_name[0]
    last_name = split_name[1]
    
   dossier["email"] = get_email(first_name, last_name, company_name)
   dossier["phone"] = "555-555-5555"

   if shouldQuery:
       response = query_llm(str(dossier["linkedin_data"]))
       output_bio = response.choices[0].message.content

       lead_obj = {
        "bio" : output_bio,
        "email" : dossier["email"],
        "phone" : dossier["phone"]
       }

       return jsonify({'output': lead_obj})
   else:
       return jsonify({'error': 'Failed to generate bio'})

if __name__ == '__main__':
    app.run(debug=True)  # Set debug as False in production