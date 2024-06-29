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
import asyncio
import aiohttp
from datetime import datetime, timedelta
import csv
import io
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

async def retrieve_rid_data(rid, timeout=10):
    async with aiohttp.ClientSession() as session:
        storage_url = "https://api.crawlbase.com/storage"
        storage_params = {
            "token": crawlbase_key,
            "rid": rid
        }
        
        if not storage_params["rid"]:
            raise ValueError("No RID found in initial response")

        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=timeout)
        sleep_time = 1

        while datetime.now() < end_time:
            try:
                async with session.get(storage_url, params=storage_params) as response:
                    response.raise_for_status()
                    data = await response.json(content_type=None)
                    
                    if data:
                        linkedin_scraped_obj = {
                            "name": data["title"],
                            "profile_url": data["profileUrl"],
                            "headline": data["headline"],
                            "position": data["positionInfo"]["company"],
                            "school": data["educationInfo"]["school"],
                            "summary": data["summary"]
                        }
                        return linkedin_scraped_obj
                    else:
                        # If data is empty, treat it as a "not found" and continue retrying
                        raise aiohttp.ClientResponseError(response.request_info, response.history, status=404)
                    
            except aiohttp.ClientResponseError as e:
                if e.status == 404:
                    remaining_time = (end_time - datetime.now()).total_seconds()
                    if remaining_time <= 0:
                        break
                    
                    print(f"404 Not Found, retrying, RID: {rid}. Time left: {remaining_time:.2f} seconds")
                    await asyncio.sleep(min(sleep_time, remaining_time))
                    sleep_time = min(sleep_time * 2, 60, remaining_time)  # Cap sleep time
                else:
                    print(f"HTTP error occurred, status {e.status}, exception: {e}")
                    return None
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                return None

        print(f"Failed to retrieve data for RID: {rid} after {timeout} minutes")
        return None

async def scrape_linkedin_profiles_v2(profile_link):
    async_url = "https://api.crawlbase.com/"
    params = {
        "token": crawlbase_key,
        "scraper": "linkedin-profile",
        "async": "true",
        "url": profile_link
    }
    
    async with aiohttp.ClientSession() as session:
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
                print(f"Checking rid {rid}")
                linkedin_data = await retrieve_rid_data(rid)
                if linkedin_data:
                    print(f'Checking {linkedin_data["profile_url"]}')
                    if linkedin_data["profile_url"] in profile_link:
                        return linkedin_data
        
        except aiohttp.ClientError as e:
            print(f"Request error occurred: {e}")
            return None
        except KeyError as e:
            print(f"Key error in response data: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None

        async with session.get(async_url, params=params) as response:
            response.raise_for_status()
            async_response = await response.json()
        
        return await retrieve_rid_data(async_response["rid"])

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
        # DEBUG print(data)
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
       linkedin_data = asyncio.run(scrape_linkedin_profiles_v2(link))
       if linkedin_data:
           snippet_clean = re.sub(r'\| Learn more about .*?\.', '', snippet)
           dossier["linkedin_data"] = str(linkedin_data) + snippet_clean
           shouldQuery = True
       else:
            print("LinkedIn query failed") 
   
   if linkedin_data and linkedin_data["name"].lower() != f"{first_name} {last_name}".lower():
    split_name = linkedin_data["name"].split(" ")
    first_name = split_name[0]
    last_name = split_name[1]
    
   dossier["email"] = get_email(first_name, last_name, company_name)
   #dossier["phone"] = "555-555-5555"

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

@app.route('/generate_batch_bio', methods=['POST'])
def generate_batch_bio():
    """
    Generate bios for multiple profiles from a CSV file.
    
    Accepts a CSV file upload with either:
    1. Three columns: assumed to be first name, last name, and company, or
    2. Two columns: assumed to be full name and company.
    Processes each row to generate a bio and returns the results for all profiles.
    Logs skipped rows to a file.
    
    :return: JSON response with results or error message
    :rtype: flask.Response
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected for uploading'}), 400
    
    if file and file.filename.endswith('.csv'):
        try:
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.reader(stream)
            
            # Read the first row to determine the CSV structure
            first_row = next(csv_input, None)
            if not first_row:
                return jsonify({'error': 'CSV file is empty'}), 400
            
            column_count = len(first_row)
            if column_count not in [2, 3]:
                return jsonify({'error': 'CSV must have either 2 or 3 columns'}), 400
            
            results = []
            skipped_rows = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                
                # Process all rows, including the first one
                for index, row in enumerate(csv_input, start=1):
                    if len(row) == column_count:
                        futures.append(executor.submit(process_row, row, column_count, index))
                    else:
                        skipped_rows.append((index, row, "Incorrect number of columns"))
                
                for future in futures:
                    result, skipped = future.result()
                    if result:
                        results.append(result)
                    if skipped:
                        skipped_rows.append(skipped)
            
            # Log skipped rows
            log_skipped_rows(skipped_rows)
            
            return jsonify({'results': results, 'skipped_count': len(skipped_rows)})
        except Exception as e:
            logger.error(f"Error processing CSV: {str(e)}")
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Allowed file type is csv'}), 400

def process_row(row, column_count, row_index):
    """
    Process a single row from the CSV.
    
    :param row: A list containing the row data
    :param column_count: The number of columns in the CSV
    :param row_index: The index of the current row
    :return: Tuple (Dictionary with processed profile data or None, Tuple with skipped row info or None)
    """
    try:
        if column_count == 3:
            first_name, last_name, company_name = row
        elif column_count == 2:
            full_name, company_name = row
            name_parts = full_name.split(maxsplit=1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""
        else:
            return None, (row_index, row, "Incorrect number of columns")
        
        if not first_name or not company_name:
            return None, (row_index, row, "Missing required data (first name or company)")
        
        result = process_profile(first_name, last_name, company_name)
        return result, None
    except Exception as e:
        logger.error(f"Error processing row {row_index}: {str(e)}")
        return None, (row_index, row, f"Error: {str(e)}")

def log_skipped_rows(skipped_rows):
    """
    Log skipped rows to a file.
    
    :param skipped_rows: List of tuples containing (row_index, row_data, reason)
    """
    if not skipped_rows:
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"skipped_rows_{timestamp}.log"
    
    try:
        with open(filename, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Row Index", "Row Data", "Reason"])
            for row in skipped_rows:
                writer.writerow(row)
        logger.info(f"Skipped rows logged to {filename}")
    except Exception as e:
        logger.error(f"Error logging skipped rows: {str(e)}")

def process_profile(first_name, last_name, company_name):
    """
    Process a single profile to generate a bio.
    
    Searches for the profile, scrapes LinkedIn data if available,
    and generates a bio using the LLM.
    
    :param first_name: First name of the person
    :type first_name: str
    :param last_name: Last name of the person
    :type last_name: str
    :param company_name: Company name
    :type company_name: str
    :return: Dictionary containing bio and profile information
    :rtype: dict
    """
    # Perform search using the profile information
    results = json.loads(search(f"{first_name} {last_name} {company_name}"))
    item_arr = results["organic"]
    dossier = {
        "linkedin_data": "",
        "email": "",
        "phone": ""
    }
    isLinkedin = False
    
    # Look for LinkedIn profile in search results
    for item in item_arr:
        link = item["link"]
        snippet = item["snippet"]
        if "linkedin.com" in link:
            isLinkedin = True
            break
    
    if isLinkedin:
        # Scrape LinkedIn profile
        linkedin_data = asyncio.run(scrape_linkedin_profiles_v2(link))
        if linkedin_data:
            # Clean up snippet and add to dossier
            snippet_clean = re.sub(r'\| Learn more about .*?\.', '', snippet)
            dossier["linkedin_data"] = str(linkedin_data) + snippet_clean
            
            # Update name if it differs from input
            if linkedin_data["name"].lower() != f"{first_name} {last_name}".lower():
                split_name = linkedin_data["name"].split(" ")
                first_name = split_name[0]
                last_name = split_name[1]
            
            # Get email and generate bio
            dossier["email"] = get_email(first_name, last_name, company_name)
            response = query_llm(str(dossier["linkedin_data"]))
            output_bio = response.choices[0].message.content
            
            return {
                "name": f"{first_name} {last_name}",
                "company": company_name,
                "bio": output_bio,
                "email": dossier["email"],
                "phone": dossier["phone"]
            }
    
    # Return error if bio generation fails
    return {
        "name": f"{first_name} {last_name}",
        "company": company_name,
        "error": "Failed to generate bio"
    }

if __name__ == '__main__':
    app.run(debug=True)  # Set debug as False in production