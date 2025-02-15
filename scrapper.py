import json
import os
import time

import math

import geojson
import requests
from datetime import datetime
from dotenv import load_dotenv
import mapbox_vector_tile

from incidents_scrapper_utils import get_save_upload_traffic_incidents
from translation import save_in_mongo, get_neighbours_edges, split_features, add_info_to_file, \
    add_traffic_level_from_file, translate_file_pairs_into_geojson
import constants as const
import osmnx as ox

load_dotenv()
api_key = os.getenv("TOMTOM_API_KEY")


#######################################################################################################################

#######################################################################################################################

def pbf_to_json(filename, current_datetime):
    with open(filename, "rb") as file:
        data = file.read()

    geojson = mapbox_vector_tile.decode(data)

    with open(filename + ".json", "w") as file:
        json.dump(geojson, file, indent=4)
    save_log("OK: Translation saved on file", current_datetime)


#######################################################################################################################

#######################################################################################################################

def get_tiles(tomtom_url, current_datetime, folder_name):
    try:
        response = requests.get(tomtom_url)
        # Verify if the request was successful
        if response.status_code == 200:
            save_pbf_to_json(response.content, current_datetime, folder_name)
        else:
            raise Exception(f"ERROR on request with code: {response.status_code}")
    except Exception as e:
        # Save error on Log
        save_log(str(e), current_datetime)


def save_pbf_to_json(response, current_datetime, folder_name):
    filename = f"{folder_name}/{current_datetime}.pbf"

    # Write response to file
    with open(filename, "wb") as output_file:
        output_file.write(response)
        save_log("Response saved on file", current_datetime)

    pbf_to_json(filename, current_datetime)


def save_json_to_mongo(datetime_tile, graph, neighbours_dictionary, tiles_string, graph_area):
    # Translate both tiles files
    for tile_string in tiles_string:
        dir_output = f"cache/translation/{tile_string}"
        dir_input = f"data/{tile_string}/{datetime_tile}.pbf.json"

        # Ensure the output directory exists
        os.makedirs(dir_output, exist_ok=True)

        with open(f"{dir_output}/{datetime_tile}.pbf.json", "w") as output_file:
            if tile_string == "tile1":
                outmin = const.OUTMIN_TILE1
                outmax = const.OUTMAX_TILE1
            elif tile_string == "tile2":
                outmin = const.OUTMIN_TILE2
                outmax = const.OUTMAX_TILE2
            elif tile_string == "tile_sojo_1":
                outmin = const.OUTMIN_TILE1_SOHO
                outmax = const.OUTMAX_TILE1_SOHO
            elif tile_string == "tile_sojo_2":
                outmin = const.OUTMIN_TILE2_SOHO
                outmax = const.OUTMAX_TILE2_SOHO
            elif tile_string == "tile_sojo_3":
                outmin = const.OUTMIN_TILE3_SOHO
                outmax = const.OUTMAX_TILE3_SOHO
            elif tile_string == "tile_sojo_4":
                outmin = const.OUTMIN_TILE4_SOHO
                outmax = const.OUTMAX_TILE4_SOHO

            output_file.write(
                json.dumps(
                    translate_file_pairs_into_geojson(dir_input, outmin, outmax)
                )
            )

    print(f"{datetime_tile}: Files translated and saved on 'cache/translation'")

    # Mix the files from the first two folders into the third one
    files_dirs = []
    dir_output = f"cache/mixed/{datetime_tile}.pbf.json"
    mixed_json = {"type": "FeatureCollection", "features": []}
    for tile_string in tiles_string:
        files_dirs.append(f"cache/translation/{tile_string}/{datetime_tile}.pbf.json")

    for file_dir in files_dirs:
        with open(file_dir) as file:
            json_data = json.load(file)
            mixed_json["features"].extend(json_data["features"])

    # Ensure the output directory exists
    os.makedirs("cache/mixed", exist_ok=True)

    with open(dir_output, "w") as output_file:
        output_file.write(json.dumps(mixed_json))

    print(f"{datetime_tile}: Files mixed and saved on 'cache/mixed'")

    # Add information to all the files in the given folder (splits, nearest edge, etc.)
    dir_input = "cache/mixed"
    dir_output = "cache/informed"
    os.makedirs(dir_output, exist_ok=True)
    add_info_to_file(datetime_tile, dir_input, dir_output, graph, splits=15)

    print(f"{datetime_tile}: Files informed and saved on 'cache/informed'")

    # Split the features from the given folder
    dir_input = "cache/informed"
    dir_output = "cache/splitted"
    os.makedirs(dir_output, exist_ok=True)
    with open(f"{dir_input}/{datetime_tile}.pbf.json") as f:
        split_data = split_features(f)

    with open(f"{dir_output}/{datetime_tile}.pbf.json", "w") as output_file:
        geojson.dump(split_data, output_file)

    print(f"File '{datetime_tile}' splitted and saved on '{dir_output}'", datetime_tile)

    print(f"{datetime_tile}: Files splitted and saved on 'cache/splitted'")

    # Add the traffic level to the edges from a folder
    dir_input = dir_output
    with open(f"{dir_input}/{datetime_tile}.pbf.json") as f:
        graph = add_traffic_level_from_file(graph, f, datetime_tile,
                                            neighbours_dictionary=neighbours_dictionary,
                                            precision=3)

    print(f"{datetime_tile}: Traffic level added to the graph")

    # Save the traffic level and additional info in dates collection in MongoDB
    # TODO: si en un futuro se cambia a una maquina en la nube (con acceso a ficheros locales para la cache)
    # TODO: lo único que habría que cambiar sería la ruta de la base de datos de MongoDB
    save_in_mongo(datetime_tile, graph, graph_area)

    print(f"{datetime_tile}: Data saved in MongoDB")

    # Delete the files
    dirs = ["cache/translation/tile1", "cache/translation/tile2", "cache/mixed", "cache/informed",
            "cache/splitted"]
    for directory in dirs:
        for filename in os.listdir(directory):
            os.remove(f"{directory}/{filename}")

    print(f"{datetime_tile}: Cached Files deleted")


def save_log(log, current_datetime):
    log_file = "logs.txt"

    # Write log file
    with open(log_file, "a") as archivo:
        archivo.write(f"[{current_datetime}]: {log}\n")


#######################################################################################################################

#######################################################################################################################


def get_tiles_pbf_and_save_json(message_datetime):
    celdas = [
        # Zoom 14
        ('tile1', (14, 7988, 6393)),
        ('tile2', (14, 7988, 6392)),

        # Zoom 16
        ('tile_sojo_1', (16, 31962, 25573)),
        ('tile_sojo_2', (16, 31963, 25573)),
        ('tile_sojo_3', (16, 31962, 25572)),
        ('tile_sojo_4', (16, 31963, 25572))
    ]

    for celda in celdas:
        z, x, y = celda[1]
        url = f"https://api.tomtom.com/traffic/map/4/tile/flow/relative/{z}/{x}/{y}.pbf?key={api_key}"
        folder_name = f"./data/{celda[0]}"
        get_tiles(url, message_datetime, folder_name)


if __name__ == "__main__":

    #tiles teatinos
    tiles = ["tile1", "tile2"]

    #tiles_soho
    tiles_soho = ["tile_sojo_1", "tile_sojo_2", "tile_sojo_3", "tile_sojo_4"]

    # Open graph teatinos from file
    base_graph = ox.load_graphml("base_graph.graphml")

    # Open graph SOHO from file
    base_graph_soho = ox.load_graphml("soho_malaga.graphml")


    # Create the neighbours dictionary
    print("Getting the neighbours edges dictionary...")

    # Teatinos
    neighbours_dictionary_created = {}
    for u, v, data in base_graph.edges(data=True):
        neighbours_dictionary_created[(u, v)] = get_neighbours_edges(base_graph, u, v)
    print("Neighbours edges dictionary loaded for teatinos.")

    #Soho
    neighbours_dictionary_soho_created = {}
    for u, v, data in base_graph_soho.edges(data=True):
        neighbours_dictionary_soho_created[(u, v)] = get_neighbours_edges(base_graph_soho, u, v)
    print("Neighbours edges dictionary loaded for soho.")

    while True:
        start_time = time.time()
        datetime_string = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

        # Get the tiles
        get_tiles_pbf_and_save_json(datetime_string)

        # Teatinos
        save_json_to_mongo(datetime_string, base_graph, neighbours_dictionary_created, tiles, "teatinos")

        # Soho
        save_json_to_mongo(datetime_string, base_graph_soho, neighbours_dictionary_soho_created, tiles_soho, "soho")


        # Calculate elapsed time and sleep for the remaining time to complete 15 minutes
        elapsed_time = time.time() - start_time
        time.sleep(max(0.0, 900 - elapsed_time))