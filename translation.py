import copy
import json
import logging
import os
from datetime import datetime

import geojson
import osmnx as ox
import shapely
from shapely.geometry import Point, LineString

from mongo.entity import Graph
from mongo.repository import RepositorioGraph, RepositorioGraphSoho
from utils.utils import are_opposite_bearings, get_neighbours_edges, normalize, skip_feature, \
    get_cardinal_direction_from_bearing
from utils.utils_geojson import create_linestring_geojson
from utils.utils_zona_teatinos import handle_jimenez_fraud


########################################################################################################################
#                                         TRANSLATION FUNCTIONS
########################################################################################################################


def translate_file_pairs_into_geojson(dirname, outmin, outmax):
    """ Translate a file from the given directory into a GeoJSON object
    this function is called by 'translate_all_files_pairs' function to translate all the files in the given directory
    Args:
        dirname: The directory where the file is located
        outmin: The minimum coordinates of the output (to normalize)
        outmax: The maximum coordinates of the output (to normalize)
    Returns:
        A GeoJSON object with the coordinates of the file"""

    translation = {
        "type": "FeatureCollection",
        "features": []}

    with (open(dirname) as file):
        json_coordinates = json.load(file)
        feature_id = 0
        for feature in json_coordinates["Traffic flow"]["features"]:
            coordinates = feature["geometry"]["coordinates"]

            # Skip points
            if feature["geometry"]["type"] == "Point":
                print("\t Skipping point")
                continue

            if feature["geometry"]["type"] == "LineString":
                coordinates = [coordinates]

            for line in coordinates:
                # TODO: REVISAR DE DONDE VIENE EL 4095
                for point_number in range(len(line) - 1):
                    next_pair = [
                        [
                            normalize(line[point_number][0], 4095, 0, outmin[0], outmax[0]),
                            normalize(line[point_number][1], 4095, 0, outmin[1], outmax[1])
                        ],
                        [
                            normalize(line[point_number + 1][0], 4095, 0, outmin[0], outmax[0]),
                            normalize(line[point_number + 1][1], 4095, 0, outmin[1], outmax[1])

                        ]
                    ]
                    feature_properties = {**feature["properties"], "feature_id": feature_id}
                    feature_id += 1
                    translation["features"].append(create_linestring_geojson(next_pair, feature_properties))

    return translation


def __generate_lists_coordiantes_and_neares_edges(data, graph):
    middle_coordinates_lat, middle_coordinates_lon = [], []
    coordinates_lat, coordinates_lon = [], []
    # Get from every feature (pair of points) the middle point
    for feature in data["features"]:

        if skip_feature(feature):
            continue

        coordinates = feature["geometry"]["coordinates"]

        point_1_lat, point_1_lon = coordinates[0][1], coordinates[0][0]
        point_2_lat, point_2_lon = coordinates[1][1], coordinates[1][0]

        coordinates_lon.append(point_1_lon)
        coordinates_lat.append(point_1_lat)

        coordinates_lat.append(point_2_lat)
        coordinates_lon.append(point_2_lon)

        middle_coordinates_lat.append((point_1_lat + point_2_lat) / 2)
        middle_coordinates_lon.append((point_1_lon + point_2_lon) / 2)
    nearest_edges_and_distance_list = ox.distance.nearest_edges(graph, middle_coordinates_lon, middle_coordinates_lat,
                                                                return_dist=True)
    return coordinates_lat, coordinates_lon, nearest_edges_and_distance_list


########################################################################################################################
#                                         ADD INFORMATION (NUMBER OF SPLITS)
########################################################################################################################

def add_info_to_file(filename, folder_input, folder_output, graph,
                     error_management=False,
                     print_distant_edges=False,
                     splits=15):
    """ Add information to the given file (splits, nearest edge, etc.)
    Args:
        filename: The name of the file
        folder_input: The folder where the file is located
        folder_output: The folder where the output file will be saved
        graph: The graph to use to get the nearest edges
        error_management: A boolean to indicate if the error management is enabled
        print_distant_edges: A boolean to indicate if the distant edges should be printed
        splits: The amount of splits to use"""

    with open(f"{folder_input}/{filename}.pbf.json") as f:
        data = geojson.load(f)

    middle_coordinates_lat = []
    middle_coordinates_lon = []

    coordinates_lat = []
    coordinates_lon = []

    new_features = []
    i = 0
    for feature in data["features"]:

        if skip_feature(feature):
            continue

        i += 1

        coordinates = feature["geometry"]["coordinates"]

        # We add the length of the edge to the total length
        point1 = Point(coordinates[0][1], coordinates[0][0])
        point2 = Point(coordinates[1][1], coordinates[1][0])

        length = point1.distance(point2) * 100_000
        feature["properties"]["length"] = length

        coordinates_lat.append(point1.x)
        coordinates_lat.append(point2.x)

        coordinates_lon.append(point1.y)
        coordinates_lon.append(point2.y)

        # Get the middle of both points
        middle_point = ((point1.x + point2.x) / 2, (point1.y + point2.y) / 2)
        middle_coordinates_lon.append(middle_point[1])
        middle_coordinates_lat.append(middle_point[0])

    nearest_edges_and_distance_list = ox.distance.nearest_edges(graph, middle_coordinates_lon,
                                                                middle_coordinates_lat, return_dist=True)

    if len(nearest_edges_and_distance_list[0]) != i:
        raise ValueError("ERROR: Different number of features and nearest edges")

    nearest_edges_list = nearest_edges_and_distance_list[0]
    nearest_distance_list = nearest_edges_and_distance_list[1]

    j = 0
    for feature in data["features"]:

        if skip_feature(feature):
            continue

        nearest_edge_id = nearest_edges_list[j]
        feature["properties"]["error"] = ""
        distance_in_meters = nearest_distance_list[j] * 100000

        if distance_in_meters > 10:
            feature["properties"]["error"] = "Very distant from the nearest edge"

            if print_distant_edges:
                print(
                    f"Feature {j} (edge{nearest_edge_id}) is very distant from the nearest edge: "
                    f"{distance_in_meters} meters -> {[middle_coordinates_lat[j], middle_coordinates_lon[j]]}")

            j += 1
            continue

        nearest_edge = graph.edges[nearest_edge_id]

        bearing_api_edge = ox.bearing.calculate_bearing(coordinates_lat[j * 2], coordinates_lon[j * 2],
                                                        coordinates_lat[j * 2 + 1], coordinates_lon[j * 2 + 1])

        # Check if the direction is reversed or not
        if are_opposite_bearings(nearest_edge["bearing"], bearing_api_edge, tolerance=45):
            feature["properties"]["nearest_edge_reverse"] = not nearest_edge["reversed"]
        else:
            feature["properties"]["nearest_edge_reverse"] = nearest_edge["reversed"]

        # Once we know the nearest edge, we check if the API edge needs to be split
        amount_splits = round(feature["properties"]["length"] / splits)

        if 'junction' in nearest_edge.keys() and nearest_edge["junction"] == "roundabout":
            feature["properties"]["splits"] = 0
            feature["properties"]["junction"] = nearest_edge["junction"]
        else:
            feature["properties"]["splits"] = amount_splits

        feature["properties"]["aiming"] = get_cardinal_direction_from_bearing(bearing_api_edge)
        feature["properties"]["api_bearing"] = bearing_api_edge

        j += 1

        new_features.append(feature)

    res = {
        "type": "FeatureCollection",
        # "features": data["features"]
        "features": new_features

    }

    json.dump(res, open(f"{folder_output}/{filename}.pbf.json", "w"))


########################################################################################################################
#                                         SPLIT THE FEATURES
########################################################################################################################


def split_features(geojson_file,
                   print_if_more_splits_than=-1):
    data = geojson.load(geojson_file)
    new_features = []
    # Split the features
    for feature in data['features']:
        if skip_feature(feature):
            continue

        # Split each feature into segments
        amount_of_splits = feature['properties']['splits']

        if amount_of_splits < 2:
            new_features.append(feature)
            continue
        else:

            if 0 < print_if_more_splits_than < amount_of_splits:
                print("More than 10 splits -> ", amount_of_splits)

            # Get the coordinates of the original feature
            coordinates = feature['geometry']['coordinates']
            line = LineString(coordinates)

            geometries = split_line_with_two_points_in_parts(line, amount_of_splits, format_geojson=False)

            for geometry in geometries:
                # Get the properties of the original feature
                new_feature = copy.deepcopy(feature)
                new_feature['geometry'] = geometry
                new_feature['properties']['splits'] = -1

                new_features.append(new_feature)

    data['features'] = new_features
    return data


def split_line_with_two_points_in_parts(line, parts, format_geojson=False):
    # Check if the argument is LineString
    if not isinstance(line, LineString):
        raise ValueError("Input line should be a shapely LineString")

    # Check if the line has two points
    if len(list(line.coords)) != 2:
        raise ValueError("Line should have two points")

    coords = list(line.coords)
    first_point = Point(coords[0])
    last_point = Point(coords[1])

    line_length = line.length

    # Get the step to split the line
    step = line_length / parts

    # Initialize the list of the new lines
    current_step = 0

    # Initialize the current line
    current_line = [first_point]

    # Iterate over the line
    while current_step + step < line_length:
        # Get the point in the current step
        new_point = line.interpolate(current_step + step)
        # Add the point to the current line
        current_line.append(new_point)
        # Update the current step
        current_step += step

    # Add the last point of the line
    current_line.append(last_point)

    # Split the line into lines with two points
    pairs_points_lines = []
    for i in range(len(current_line) - 1):
        pairs_points_lines.append((LineString([current_line[i], current_line[i + 1]])))

    if format_geojson:
        # print([shapely.to_geojson(line) for line in pairs_points_lines])
        return [shapely.to_geojson(line) for line in pairs_points_lines]

    return pairs_points_lines


########################################################################################################################
#                                         ADD TRAFFIC LEVEL TO THE GRAPH
########################################################################################################################


def add_traffic_level_from_folder(graph, folder, neighbours_dictionary, precision=6, save_each_graph_mongo=False, ):
    """ Add the traffic level to the edges from a folder
    Args:
        :param graph: The graph to add the traffic level
        :param folder: The folder with the traffic level
        :param save_each_graph_mongo: flag to indicate if the graph should be saved in the database
        :param precision: The precision to check the traffic level of the interpolations
        :param neighbours_dictionary: dictionary with the neighbours of the edges
    Returns:
        The graph with the traffic level added"""

    for filename in os.listdir(f"{folder}"):
        with open(f"{folder}/{filename}") as datafile:
            graph = add_traffic_level_from_file(graph, datafile, filename,
                                                neighbours_dictionary=neighbours_dictionary,
                                                precision=precision)
            print(f"Added traffic level from {filename}\n\n")

    if save_each_graph_mongo:
        for filename in os.listdir(f"{folder}"):
            repo = RepositorioGraph()
            graph_object = Graph.generate_graph(graph, filename)
            repo.insert_one(graph_object)
            print(f"Saved graph with traffic level from {filename} to MongoDB\n\n")

    return graph


def add_traffic_level_from_file(graph, datafile, filename, neighbours_dictionary=None, fill_empty_edges=True,
                                precision=6):
    """ Add the traffic level to the edges from a file, and add the traffic level to the edges that are empty
    Args:
        graph: The graph to add the traffic level
        datafile: The file with the traffic level
        filename: The filename of the file
        fill_empty_edges: A boolean to indicate if the empty edges should be filled
        neighbours_dictionary: The dictionary with the neighbours of the edges
        precision: The precision to check the traffic level of the interpolations
    Returns:
        The graph with the traffic level added"""

    for u, v, edge_data in graph.edges(data=True):
        edge_data["most_recent"] = {'traffic_level': None, 'api_data': False, 'date': filename}

    data = geojson.load(datafile)

    coordinates_lat, coordinates_lon, nearest_edges_and_distance_list = __generate_lists_coordiantes_and_neares_edges(
        data, graph)

    if len(nearest_edges_and_distance_list[0]) != len(coordinates_lat) / 2:
        raise ValueError("ERROR: Different number of features and nearest edges")

    nearest_edges_list = nearest_edges_and_distance_list[0]
    # nearest_distance_list = nearest_edges_and_distance_list[1]

    # Iteration over the features (easiest way to keep the order)
    j = 0
    for feature in data["features"]:
        if skip_feature(feature):
            continue

        info = {'traffic_level': feature["properties"]["traffic_level"], 'api_data': True, 'date': filename}

        nearest_edge_id = nearest_edges_list[j]

        # We assume that the nearest edge is the correct one (reversed or not)
        node_1_id = nearest_edge_id[0]
        node_2_id = nearest_edge_id[1]
        # Then, we check if the road is reversed, if so, we invert the order of the edge's nodes
        bearing_api_edge = ox.bearing.calculate_bearing(coordinates_lat[j * 2], coordinates_lon[j * 2],
                                                        coordinates_lat[j * 2 + 1], coordinates_lon[j * 2 + 1])

        nearest_edge = graph.edges[node_1_id, node_2_id, 0]

        if not nearest_edge["oneway"] and are_opposite_bearings(nearest_edge["bearing"], bearing_api_edge):
            nearest_edge = graph.edges[node_2_id, node_1_id, 0]

        # Handle Jimenez Fraud Way (API edge is reversed)
        if nearest_edge["osmid"] == 199419587 and are_opposite_bearings(nearest_edge["bearing"], bearing_api_edge):
            nearest_edge = handle_jimenez_fraud(graph, node_1_id, node_2_id, filename, info)

        # Add traffic level
        nearest_edge["most_recent"] = info

        j += 1

    if fill_empty_edges:
        interpolate_traffic_level(graph, filename, neighbours_dictionary=neighbours_dictionary, precision=precision)

    return graph


def interpolate_traffic_level(graph, filename, neighbours_dictionary=None, precision=6):
    """ Interpolate the traffic level of the edges with the traffic level of the neighbours that have it
    Args:
        graph: The graph to interpolate the traffic level
        filename: The filename of the date to interpolate
        precision: The precision to check the traffic level of the interpolations
        neighbours_dictionary: The dictionary with the neighbours of the edges"""

    num_iter = 0
    num_edges_interpolated = 1
    d = neighbours_dictionary
    if neighbours_dictionary is None:
        logging.info("Getting the neighbours edges...")
        d = {(u, v): get_neighbours_edges(graph, u, v) for u, v, data in graph.edges(data=True)}

    logging.info("Interpolating the traffic level...")
    while num_edges_interpolated > 0:
        num_edges_interpolated = 0
        num_iter += 1

        for u, v, data in graph.edges(data=True):
            if not data['most_recent']['api_data']:
                neighbours_edges = d[(u, v)]

                neighbour_traffic_levels = [graph.edges[edge[0], edge[1], 0]['most_recent']['traffic_level']
                                            for edge in neighbours_edges
                                            if
                                            graph.edges[edge[0], edge[1], 0]['most_recent'][
                                                'traffic_level'] is not None]

                if len(neighbour_traffic_levels) > 0:
                    new_traffic_level = sum(neighbour_traffic_levels) / len(neighbour_traffic_levels)

                    if round(new_traffic_level, precision) != round(
                            data['most_recent'].get('traffic_level', -1) if data['most_recent'].get(
                                'traffic_level', -1) is not None else -1, precision):
                        data['most_recent']['traffic_level'] = new_traffic_level
                        num_edges_interpolated += 1

        if num_iter % 50 == 0:
            print("\tIteration: ", num_iter, " - Interpolated ", num_edges_interpolated, " edges\t\tfile =", filename)


########################################################################################################################
#                                         SAVE TRAFFIC LEVEL IN MONGO
########################################################################################################################

def save_in_mongo(datetime_string, graph, graph_area):
    repo = None
    if graph_area == 'teatinos':
        repo = RepositorioGraph()
    elif graph_area == 'soho':
        repo = RepositorioGraphSoho()
    graph_object = Graph.generate_graph(graph, datetime_string)
    repo.insert_one(graph_object)


def get_files_dictionary_from_folder(path):
    # Get the list of files in the folder
    files = os.listdir(path)

    available_files = []
    # Iterate over the files in the folder
    for file in files:
        # Check if file is .pbf.json
        if not file.endswith(".json"):
            continue

        next_file = {"filename_extensions": file, "filename": file.split(".")[0],
                     "datetime": datetime.strptime(file.split(".")[0], "%Y_%m_%d_%H_%M_%S")}
        next_file["day_of_week"] = next_file["datetime"].strftime("%A")

        available_files.append(next_file)

    return available_files
