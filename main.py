import json
import os
import requests
import time

BASE_URL = "https://obd.hcraontario.ca/api/"

api_calls_made = 0
def read_json(file_path):
    """Reads and returns JSON data from a file."""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except IOError as e:
        print(f"Error reading file {file_path}: {e}")
        return None


def save_json(data, folder, filename):
    """Saves JSON data to a file in the specified folder."""
    try:
        if not os.path.exists(folder):
            os.makedirs(folder)
        with open(os.path.join(folder, f"{filename}.json"), 'w') as file:
            json.dump(data, file, indent=4)
    except IOError as e:
        print(f"Error saving file {filename}.json in folder {folder}: {e}")


def file_exists_and_not_empty(file_path):
    """Checks if a file exists and is not empty."""
    return os.path.exists(file_path) and os.path.getsize(file_path) > 0


def fetch_api_data(api, account_number):
    """Fetches data from the API for a given endpoint and account number."""
    global api_calls_made
    try:
        response = requests.get(f"{BASE_URL}{api}?id={account_number}")
        api_calls_made += 1
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data from API {api} for account {account_number}: {e}")
        raise e


def process_builder_pdos(pdo_data):
    """Processes builder PDOs data."""
    for pdo in pdo_data:
        pdo_id = pdo["TOUNIQUENUMBER"]
        pdo_file_path = os.path.join("PDO", f"{pdo_id}.json")
        if not file_exists_and_not_empty(pdo_file_path):
            print(f"Fetching PDO data for {pdo_id}")
            pdo_response_data = fetch_api_data("pdoConvictions", pdo_id)
            save_json(pdo_response_data, "PDO", pdo_id)
        else:
            print(f"PDO data for {pdo_id} already cached")


def make_api_calls(account_number, license_status):
    apis = {
        "builder": ["builderSummary", "builderPDOs", "builderConvictions",
                    "builderMembers", "builderCondoProjects", "builderConditions"],
        "umbrella": ["umbrellaSummary", "umbrellaMembers",
                     "umbrellaProperties", "umbrellaCondoProjects"]
    }

    selected_apis = apis["builder"] if license_status != "NULL/UMBRELLA" else apis["umbrella"]
    folder_name = "Umbrella" if license_status == "NULL/UMBRELLA" else "Builder"
    response_data = {}
    file_path = os.path.join(folder_name, f"{account_number}.json")
    if not file_exists_and_not_empty(file_path):
        time.sleep(2)
    fetched = False
    for api in selected_apis:
        if not file_exists_and_not_empty(file_path):
            print(f"Fetching data for API {api} for {account_number}")
            data = fetch_api_data(api, account_number)
            response_data[api] = data
            if api == "builderPDOs":
                process_builder_pdos(data)
            fetched = True
        else:
            print(f"Data for API {api} for {account_number} already cached")
            if api == "builderPDOs":
                # Ensure that individual PDOs are processed even if the builderPDOs data was previously cached
                pdo_data = read_json(file_path)["builderPDOs"]
                process_builder_pdos(pdo_data)
    if fetched:
        save_json(response_data, folder_name, account_number)


def main():
    """Main function to initiate API calls."""
    global api_calls_made
    try:
        builders = read_json("builders.json")
        if builders:
            api_calls_made = 0
            for item in builders:
                account_number = item["ACCOUNTNUMBER"]
                license_status = item["LICENSESTATUS"]
                print(f"Requesting data for account {account_number}")
                make_api_calls(account_number, license_status)
            if api_calls_made == 0:
                print("Download completed")
                exit(0)
    except KeyboardInterrupt:
        print("Process interrupted by user.")


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            pass
