import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from osgeo import gdal
from incidents_scrapper_utils import get_save_upload_traffic_incidents
from translation import translate_all_files_pairs, mix_tiles_from_two_folder, add_info_to_folder, \
    split_features_from_folder, add_traffic_level_from_folder, save_in_mongo, delete_files
import constants as const
import osmnx as ox

load_dotenv()
api_key = os.getenv("TOMTOM_API_KEY")


#######################################################################################################################

#######################################################################################################################

def pbf_to_json(filename, current_datetime):
    ds = gdal.OpenEx(filename, gdal.OF_VECTOR)
    gdal.VectorTranslate(filename + ".json", ds)
    gdal.VectorTranslate("dump_file_cache.json", ds)

    save_log("OK: Translation saved on file", current_datetime)


#######################################################################################################################

#######################################################################################################################

def get_tiles(tomtom_url, current_datetime, folder_name, graph, neighbours_dictionary):
    try:
        response = requests.get(tomtom_url)
        # Verify if the request was successful
        if response.status_code == 200:
            save_pbf_to_json(response.content, current_datetime, folder_name, graph, neighbours_dictionary)
        else:
            raise Exception(f"ERROR on request with code: {response.status_code}")
    except Exception as e:
        # Save error on Log
        save_log(str(e), current_datetime)


def save_pbf_to_json(response, current_datetime, folder_name, graph, neighbours_dictionary):
    filename = f"{folder_name}/{current_datetime}.pbf"

    # Write response to file
    with open(filename, "wb") as output_file:
        output_file.write(response)
        save_log("Response saved on file", current_datetime)

    pbf_to_json(filename, current_datetime)


def save_json_to_mongo(filename, current_datetime, graph, neighbours_dictionary):
    # AUTOMATICALLY SAVE IT INTO MONGO

    # Translate both tiles files
    translate_all_files_pairs("data/tile1", const.OUTMIN_TILE1, const.OUTMAX_TILE1, "output_pairs/tile1")
    translate_all_files_pairs("data/tile1", const.OUTMIN_TILE2, const.OUTMAX_TILE2, "output_pairs/tile2")

    # Mix the files from the first two folders into the third one
    mix_tiles_from_two_folder(["output_pairs/tile1", "output_pairs/tile2", "output_pairs/mixed"])

    # Add information to all the files in the given folder (splits, nearest edge, etc.)
    add_info_to_folder("output_pairs/mixed", "output_add_info/mixed", graph, splits=15)

    # Split the features from the given folder
    split_features_from_folder("output_add_info/mixed", "output_split/mixed")

    # Add the traffic level to the edges from a folder
    add_traffic_level_from_folder(graph, "output_split/mixed", neighbours_dictionary, precision=3, save_each_graph_mongo=True)

    # Save the dates in MongoDB
    save_in_mongo()

    # Delete the files
    delete_files()


def save_log(log, current_datetime):
    log_file = "logs.txt"

    # Write log file
    with open(log_file, "a") as archivo:
        archivo.write(f"[{current_datetime}]: {log}\n")


#######################################################################################################################

#######################################################################################################################


def get_tiles_pbf_and_save_json(message_datetime, graph, neighbours_dictionary, z=14):
    x1 = 7988
    y1 = 6393

    x2 = 7988
    y2 = 6392

    url1 = f"https://api.tomtom.com/traffic/map/4/tile/flow/relative/{z}/{x1}/{y1}.pbf?key={api_key}"
    url2 = f"https://api.tomtom.com/traffic/map/4/tile/flow/relative/{z}/{x2}/{y2}.pbf?key={api_key}"

    folder_name_1 = "./data/tile1"
    folder_name_2 = "./data/tile2"

    get_tiles(url1, message_datetime, folder_name_1, graph, neighbours_dictionary)
    get_tiles(url2, message_datetime, folder_name_2, graph, neighbours_dictionary)


if __name__ == "__main__":
    # Open graph from file
    graph = ox.load_graphml("base_graph.graphml")

    # TODO: Get the neighbours dictionary from a saved file.
    print("Getting the neighbours edges dictionary...")
    neighbours_dictionary = {}
    for u, v, data in graph.edges(data=True):
        neighbours_dictionary[(u, v)] = get_neighbours_edges(graph, u, v)

    while True:
        current_datetime = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

        # Get the tiles
        get_tiles_pbf_and_save_json(current_datetime, graph, neighbours_dictionary)
        save_json_to_mongo(current_datetime, graph, neighbours_dictionary)

        # Get the traffic incidents
        get_save_upload_traffic_incidents(current_datetime, log_func=save_log, update_csv=False)

        # 15 minutes
        time.sleep(900)
