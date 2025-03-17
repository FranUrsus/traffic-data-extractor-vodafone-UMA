import json
import os
import time
import logging

from utils.utils_pbf import extract_tile_pbf_from_url

import geojson
from datetime import datetime
from dotenv import load_dotenv
from translation import save_in_mongo, get_neighbours_edges, split_features, add_info_to_file, \
    add_traffic_level_from_file, translate_file_pairs_into_geojson
import osmnx as ox

load_dotenv()
api_key = os.getenv("TOMTOM_API_KEY")


def extract_tiles_pbf_tomtom(selected_zones: dict, message_datetime: str):
    for zone in selected_zones.values():
        for tile in zone['tiles']:
            url = f"https://api.tomtom.com/traffic/map/4/tile/flow/relative/{tile['zoom']}/{tile['x']}/{tile['y']}.pbf?key={api_key}"
            folder_name = f"data/{tile['name']}/"
            dir_path = os.path.dirname(folder_name)
            extract_tile_pbf_from_url(url, message_datetime, dir_path)


def save_json_to_mongo(datetime_str: str, zonas_dict: dict, graph_area: str):
    graph = zonas_dict[graph_area]['graph']
    neighbours_dictionary = zonas_dict[graph_area]['neightbours']
    tiles = zonas_dict[graph_area]['tiles']
    # Translate both tiles files
    for tile in tiles:
        dir_output = f"cache/translation/{tile['name']}"
        dir_input = f"data/{tile['name']}/{datetime_str}.pbf.json"

        # Ensure the output directory exists
        os.makedirs(dir_output, exist_ok=True)

        outmin = (tile['corners_2'][0], tile['corners_0'][1])
        outmax = (tile['corners_0'][0], tile['corners_1'][1])

        with open(f"{dir_output}/{datetime_str}.pbf.json", "w") as output_file:
            output_file.write(
                json.dumps(
                    translate_file_pairs_into_geojson(dir_input, outmin, outmax)
                )
            )

    logging.info(f"Files translated and saved on 'cache/translation'")

    # Mix the files from the first two folders into the third one
    files_dirs = [f"cache/translation/{tile['name']}/{datetime_str}.pbf.json" for tile in tiles]
    dir_output = f"cache/mixed/{datetime_str}.pbf.json"
    mixed_json = {"type": "FeatureCollection", "features": []}

    for file_dir in files_dirs:
        with open(file_dir) as file:
            json_data = json.load(file)
            mixed_json["features"].extend(json_data["features"])

    # Ensure the output directory exists
    os.makedirs("cache/mixed", exist_ok=True)

    with open(dir_output, "w") as output_file:
        output_file.write(json.dumps(mixed_json))

    logging.info(f"Files mixed and saved on 'cache/mixed'")

    # Add information to all the files in the given folder (splits, nearest edge, etc.)
    dir_input = "cache/mixed"
    dir_output = "cache/informed"
    os.makedirs(dir_output, exist_ok=True)
    add_info_to_file(datetime_str, dir_input, dir_output, graph, splits=15)

    logging.info(f"Files informed and saved on 'cache/informed'")

    # Split the features from the given folder
    dir_input = "cache/informed"
    dir_output = "cache/splitted"
    os.makedirs(dir_output, exist_ok=True)
    with open(f"{dir_input}/{datetime_str}.pbf.json") as f:
        split_data = split_features(f)

    with open(f"{dir_output}/{datetime_str}.pbf.json", "w") as output_file:
        geojson.dump(split_data, output_file)

    logging.info(f"File '{datetime_str}' splitted and saved on '{dir_output}'")

    # Add the traffic level to the edges from a folder
    dir_input = dir_output
    with open(f"{dir_input}/{datetime_str}.pbf.json") as f:
        graph = add_traffic_level_from_file(graph, f, datetime_str,
                                            neighbours_dictionary=neighbours_dictionary,
                                            precision=3)

    logging.info(f"Traffic level added to the graph")

    # Save the traffic level and additional info in dates collection in MongoDB
    # TODO: si en un futuro se cambia a una maquina en la nube (con acceso a ficheros locales para la cache)
    # TODO: lo único que habría que cambiar sería la ruta de la base de datos de MongoDB
    save_in_mongo(datetime_str, graph, graph_area)

    logging.info(f"Data saved in MongoDB")

    # Delete the files
    dirs = [*[f"cache/translation/{tile['name']}" for tile in tiles],
            "cache/mixed", "cache/informed",
            "cache/splitted"]
    for directory in dirs:
        for filename in os.listdir(directory):
            os.remove(f"{directory}/{filename}")

    logging.info(f"{datetime_str}: Cached Files deleted")


if __name__ == "__main__":
    # LOGGER
    logging.basicConfig(encoding='utf-8', level=logging.INFO,
                        format='%(asctime)s %(message)s')
    file_logging = logging.FileHandler('scrapper.log')
    file_logging.setLevel(logging.INFO)
    file_logging.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logging.getLogger().addHandler(file_logging)

    # Zonas
    id_zonas = (
        'teatinos', 'soho'
    )
    zonas = {
        x: {
            'graph': ox.load_graphml(f"zonas/{x}/{x}.graphml"),
            'tiles': json.load(open(f'zonas/{x}/{x}_tiles.json', encoding='utf8', mode='r'))['tiles']
        }
        for x in id_zonas
    }

    # Create the neighbours dictionary
    logging.info("Getting the neighbours edges dictionary...")

    for x, y in zonas.items():
        graph_zona = y['graph']
        y['neightbours'] = {(u, v): get_neighbours_edges(graph_zona, u, v)
                            for u, v, data in graph_zona.edges(data=True)}
        logging.info(f"Neighbours edges dictionary loaded for {x}")

    while True:
        start_time = time.time()
        datetime_string = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

        # Get the tiles
        extract_tiles_pbf_tomtom(zonas, datetime_string)
        #
        # # Teatinos
        save_json_to_mongo(datetime_string, zonas, "teatinos")
        #
        # # Soho
        save_json_to_mongo(datetime_string, zonas, "soho")
        exit(-1)

        # Calculate elapsed time and sleep for the remaining time to complete 15 minutes
        elapsed_time = time.time() - start_time
        time.sleep(max(0.0, 900 - elapsed_time))
