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
                print(f"Attempting to retrieve data for RID: {rid}")
                async with session.get(storage_url, params=storage_params) as response:
                    print(f"Response status: {response.status}")
                    if response.status == 404:
                        print(f"404 Not Found for RID: {rid}. Data not ready yet.")
                    else:
                        response.raise_for_status()
                        data = await response.json(content_type=None)

                        if data and all(key in data for key in ["title", "profileUrl", "headline", "positionInfo", "educationInfo", "summary"]):
                            linkedin_scraped_obj = {
                                "name": data["title"],
                                "profile_url": data["profileUrl"],
                                "headline": data["headline"],
                                "position": data["positionInfo"]["company"],
                                "school": data["educationInfo"]["school"],
                                "summary": data["summary"]
                            }
                            print(f"Successfully retrieved data for RID: {rid}")
                            return linkedin_scraped_obj
                        else:
                            print(f"Incomplete data received for RID: {rid}. Retrying...")

            except aiohttp.ClientResponseError as e:
                print(f"ClientResponseError occurred, status {e.status}, exception: {e}")
                if e.status != 404:
                    return None
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                return None

            remaining_time = (end_time - datetime.now()).total_seconds()
            if remaining_time <= 0:
                break
            
            print(f"Retrying, RID: {rid}. Time left: {remaining_time:.2f} seconds")
            await asyncio.sleep(min(sleep_time, remaining_time))
            sleep_time = min(sleep_time * 2, 60)  # Cap sleep time at 60 seconds

        print(f"Timeout reached for RID: {rid}")
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
            # Existing jobs
            rids_url = "https://api.crawlbase.com/storage/rids"
            rids_params = {
                "token": crawlbase_key,
                "limit": "100"
            }
            
            print("Getting list of rids")
            async with session.get(rids_url, params=rids_params) as rids_response:
                rids_response.raise_for_status()
                rids_data = await rids_response.json()
                rids = rids_data["rids"]
            
            print("Start parallel processing of rids")
            start_time = time.time()

            # Create a ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=10) as executor:
                # Create a list of futures
                futures = [
                    asyncio.wrap_future(
                        executor.submit(process_rid, rid, profile_link)
                    )
                    for rid in rids
                ]

                # Process futures as they complete
                for future in asyncio.as_completed(futures):
                    result = await future
                    if result:
                        end_time = time.time()
                        print(f"RID retrieval time: {end_time - start_time} seconds, RID storage size: {len(rids)}")
                        return result  # Return immediately when a match is found
            
            print("No match found in existing RIDs")
        except aiohttp.ClientError as e:
            print(f"Request error occurred: {e}")
        except KeyError as e:
            print(f"Key error in response data: {e}")
        except json.JSONDecodeError as e:
            print(f"JSON error: {e}")

        async with session.get(async_url, params=params) as response:
            print("Query is not cached, getting new RID")
            response.raise_for_status()
            async_response = await response.json()

        result = await retrieve_rid_data(async_response["rid"])
        if result:
            return result
        else:
            print("retrieve_rid_data on new RID failed")
            return None


def process_rid(rid, profile_link):
    print(f"Checking rid {rid}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        linkedin_data = loop.run_until_complete(retrieve_rid_data(rid))
        if linkedin_data and linkedin_data["profile_url"] in profile_link:
            print(f'Match found: {linkedin_data["profile_url"]}')
            return linkedin_data
    finally:
        loop.close()
    return None

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

   dossier = process_profile(first_name, last_name, company_name)
    
   if dossier:
       return jsonify({'output': dossier})
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