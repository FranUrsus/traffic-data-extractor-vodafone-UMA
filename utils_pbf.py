import json
import logging
import os

import mapbox_vector_tile
import requests


def extract_tile_pbf_from_url(tomtom_url, current_datetime, dir_path):
    try:
        response = requests.get(tomtom_url)
        # Verify if the request was successful
        if response.status_code == 200:
            save_pbf_to_json(response.content, current_datetime, dir_path)
        else:
            raise Exception(f"ERROR on request with code: {response.status_code}")
    except Exception as e:
        # Save error on Log
        logging.error(str(e))


def save_pbf_to_json(response, current_datetime, dir_path):

    os.makedirs(dir_path, exist_ok=True)
    filename = f"{dir_path}/{current_datetime}.pbf"
    # Write response to file
    with open(filename, "wb") as output_file:
        output_file.write(response)
        logging.info(f"Saved pbf to {filename}")
    pbf_to_json(filename)


def pbf_to_json(filename):
    with open(filename, "rb") as file:
        data = file.read()

    geojson = mapbox_vector_tile.decode(data)

    with open(filename + ".json", "w") as file:
        json.dump(geojson, file, indent=4)
        logging.info(f"Saved pbf to {filename}")
