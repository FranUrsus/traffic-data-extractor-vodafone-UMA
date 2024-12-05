import json
import os
import copy
import networkx as nx
import osmnx as ox
import geojson
from shapely.geometry import Point, LineString
from datetime import datetime
import mapfunctions.constants as const
import mapfunctions.mongo as mongo
import mapfunctions.mongo_dates as mongo_dates


########################################################################################################################
#                                         TRADUCTION FUNCTIONS
########################################################################################################################


def translate_all_files_pairs(dirname_input, outmin, outmax, dirname_output):
    """ Translate all the files in the given directory into GeoJSON objects
    Args:
        dirname_input: The directory where the files are located
        outmin: The minimum coordinates of the input (to normalize)
        outmax: The maximum coordinates of the input (to normalize)
        dirname_output: The directory where the output files will be saved"""

    number_of_files = 0
    # Open each file in the "./json_data" folder
    for filename in os.listdir(f"{dirname_input}"):
        if not filename.endswith(".json"):
            continue

        number_of_files += 1

        with open(f"{dirname_output}/{filename}", "w") as output_file:
            output_file.write(
                json.dumps(
                    translate_file_pairs_into_geojson(dirname_input, filename, outmin, outmax)
                )
            )
            print(f"File '{filename}' translated and saved on '{dirname_output}'")


def translate_file_pairs_into_geojson(dirname, filename, outmin, outmax):
    """ Translate a file from the given directory into a GeoJSON object
    this function is called by 'translate_all_files_pairs' function to translate all the files in the given directory
    Args:
        dirname: The directory where the file is located
        filename: The name of the file
        outmin: The minimum coordinates of the input (to normalize)
        outmax: The maximum coordinates of the input (to normalize)
    Returns:
        A GeoJSON object with the coordinates of the file"""

    translation = {
        "type": "FeatureCollection",
        "features": []}

    with (open(f"{dirname}/{filename}") as file):
        json_coordinates = json.load(file)
        feature_id = 0
        for feature in json_coordinates["features"]:
            coordinates = feature["geometry"]["coordinates"]

            # Skip points
            if feature["geometry"]["type"] == "Point":
                print("\t Skipping point")
                continue

            for line in coordinates:
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


def normalize(x, in_min, in_max, out_min, out_max):
    """ Normalize a value from one range to another
    Args:
        x: The value to normalize
        in_min: The minimum value of the input range
        in_max: The maximum value of the input range
        out_min: The minimum value of the output range
        out_max: The maximum value of the output range
    Returns:
        The normalized value"""

    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


########################################################################################################################
#                                         MIX THE TILES
########################################################################################################################


def mix_tiles_from_two_folder(folder_names):
    """ Mix the files from the first two folders into the third one
    Args:
        folder_names: A list with the names of the folders"""

    for file in os.listdir(f"{folder_names[0]}"):
        with open(f"{folder_names[0]}/{file}") as file1:
            json1 = json.load(file1)

            if file in os.listdir(f"{folder_names[1]}"):
                with open(f"{folder_names[1]}/{file}") as file2:
                    json2 = json.load(file2)

                    json1["features"].extend(json2["features"])

                with open(f"{folder_names[2]}/{file}", "w") as output_file:
                    output_file.write(json.dumps(json1))
                    print(f"File '{file}' mixed and saved on '{folder_names[2]}'")


########################################################################################################################
#                                         ADD INFORMATION (NUMBER OF SPLITS)
########################################################################################################################

def add_info_to_folder(folder_input, folder_output, graph,
                       error_management=False,
                       print_distant_edges=False,
                       splits=15):
    """ Add information to all the files in the given folder (splits, nearest edge, etc.)
    Args:
        folder_input: The folder where the files are located
        folder_output: The folder where the output files will be saved
        graph: The graph to use to get the nearest edges
        error_management: A boolean to indicate if the error management is enabled
        print_distant_edges: A boolean to indicate if the distant edges should be printed"""

    for filename in os.listdir(folder_input):
        if filename.endswith(".json"):
            print(f"Adding information to {filename}")
            add_info_to_file(filename, folder_input, folder_output, graph,
                             error_management=error_management,
                             print_distant_edges=print_distant_edges,
                             splits=splits)


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

    with open(f"{folder_input}/{filename}") as f:
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
            length = point1.distance(point2) * 100000
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
                feature["properties"]["nearest_edlge_reverse"] = not nearest_edge["reversed"]
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

        json.dump(res, open(f"{folder_output}/{filename}", "w"))


def get_cardinal_direction_from_bearing(bearing):
    """ Get the cardinal direction from a bearing
    Args:
        bearing: The bearing in degrees
    Returns:
        A string with the cardinal direction"""

    points = ["north", "north east", "east", "south east", "south", "south west", "west", "north west"]

    bearing = bearing % 360
    bearing = int(bearing / 45)  # values 0 to 7
    return points[bearing]


########################################################################################################################
#                                         SPLIT THE FEATURES
########################################################################################################################


def split_features_from_folder(folder_input, folder_output):
    # Read the files in the folder
    for filename in os.listdir(f"{folder_input}"):
        with open(f"{folder_input}/{filename}") as f:
            split_data = split_features(f)

        with open(f"{folder_output}/{filename}", "w") as output_file:
            geojson.dump(split_data, output_file)

        print(f"File '{filename}' splitted and saved on '{folder_output}'")


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


def skip_feature(feature):
    """ Check if the feature should be skipped
    Args:
        feature: The feature to check
    Returns:
        A boolean indicating if the feature should be skipped"""

    if "geometry" not in feature.keys():
        return True
    if "coordinates" not in feature["geometry"].keys():
        return True
    if len(feature["geometry"]["coordinates"]) != 2:
        return True

    return False


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
#                                         ADD TRAFFIC LEVEL TO THE GRAPG
########################################################################################################################


def add_traffic_level_from_folder(graph, folder, neighbours_dictionary, precision=6, save_each_graph_mongo=False, ):
    """ Add the traffic level to the edges from a folder
    Args:
        graph: The graph to add the traffic level
        folder: The folder with the traffic level
        precision: The precision to check the traffic level of the interpolations
        save_each_graph_mongo: A boolean to indicate if the graph should be saved in the database
    Returns:
        The graph with the traffic level added"""

    if save_each_graph_mongo:
        db = get_database("TFG")
        col = db["graphs"]

    for filename in os.listdir(f"{folder}"):
        with open(f"{folder}/{filename}") as datafile:
            graph = add_traffic_level_from_file(graph, datafile, filename,
                                                neighbours_dictionary=neighbours_dictionary,
                                                precision=precision)
            print(f"Added traffic level from {filename}\n\n")

    if save_each_graph_mongo:
        # for i in range(1, 100): # TODO: Delete this for, when it's really executed. This was for a test of speed
        for filename in os.listdir(f"{folder}"):
            graph_to_dictionary = __prepare_graph_date_before_saving_mongo(graph, filename)
            insert_data(col, graph_to_dictionary)
            print(f"Saved graph with traffic level from {filename} to MongoDB\n\n")

    return graph


def __prepare_graph_date_before_saving_mongo(graph, filename):
    """ Remove the extra info from the graph before saving it to the database
    Args:
        graph: The graph to remove the extra info
        filename: The filename of the date to remove the extra info
    Returns:
        The graph with the extra info removed"""

    # Copy graph to avoid modifying the original graph
    graph_copy = graph.copy()

    graph_copy = __clean_edges_info(graph_copy, filename)

    graph_to_dictionary = nx.node_link_data(graph_copy)
    del graph_to_dictionary['graph']
    del graph_to_dictionary['directed']
    del graph_to_dictionary['multigraph']
    del graph_to_dictionary['nodes']

    graph_to_dictionary['filename'] = filename
    graph_to_dictionary["datetime"] = datetime.strptime(filename.split(".")[0], "%Y_%m_%d_%H_%M_%S")
    graph_to_dictionary["hour_minute_string"] = graph_to_dictionary["datetime"].strftime("%H:%M")
    graph_to_dictionary["hour_int"] = graph_to_dictionary["datetime"].hour
    graph_to_dictionary["minute_int"] = graph_to_dictionary["datetime"].minute
    graph_to_dictionary["day_of_week"] = graph_to_dictionary["datetime"].strftime("%A")

    # Calculamos el valor flotante de la hora
    graph_to_dictionary["hour_float"] = graph_to_dictionary["hour_int"] + (graph_to_dictionary["minute_int"] / 60.0)

    return graph_to_dictionary


def __clean_edges_info(graph, filename):
    """ Remove the extra info from the graph
    Args:
        graph: The graph to remove the extra info
    Returns:
        The graph with the extra info removed"""

    for u, v, data in graph.edges(data=True):
        data['traffic_level'] = data['dates'][filename]['traffic_level']
        data['api_data'] = data['dates'][filename]['api_data']
        data['current_speed'] = float(data['maxspeed']) * float(data['traffic_level'])

        if 'dates' in data:
            del data['dates']
        if 'lanes' in data:
            del data['lanes']
        if 'oneway' in data:
            del data['oneway']
        if 'bearing' in data:
            del data['bearing']
        if 'speed_kph' in data:
            del data['speed_kph']
        if 'maxspeed' in data:
            del data['maxspeed']
        if 'length' in data:
            del data['length']
        if 'geometry' in data:
            del data['geometry']
        if 'ref' in data:
            del data['ref']
        if 'service' in data:
            del data['service']
        if 'junction' in data:
            del data['junction']
        if 'reversed' in data:
            del data['reversed']
        if 'travel_time' in data:
            del data['travel_time']

    return graph


def get_neighbours_edges(graph, node1, node2):
    """ Get the neighbours edges of the nodes
    Args:
        graph: The graph to get the neighbours edges
        node1: The first node
        node2: The second node"""
    neighbours_edges = []

    for u, v, data in graph.edges(data=True):
        if u == node1 or v == node1 or u == node2 or v == node2:
            neighbours_edges.append((u, v))

    neighbours_edges.remove((node1, node2))

    try:
        # Don't consider the reverse way of the edge, if it exists
        neighbours_edges.remove((node2, node1))
    except ValueError:
        pass

    return neighbours_edges


########################################################################################################################
#                                         SAVE TRAFFIC LEVEL IN MONGO
########################################################################################################################

def save_in_mongo():
    mixed_tiles_path = "output_split/mixed"
    available_files_info = mongo_dates.get_files_dictionary_from_folder(mixed_tiles_path)
    mongo.insert_multiple_data(mongo.get_database()["dates"], available_files_info)


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


########################################################################################################################
#                                         DELETE FILES
########################################################################################################################


def delete_files():
    print("Deleting files\n\n")
    dirs = ["data/tile1", "data/tile2", "output_pairs/tile1", "output_pairs/tile2", "output_pairs/mixed", "output_add_info/mixed", "output_split/mixed"]

    for directory in dirs:
        for filename in os.listdir(directory):
            os.remove(f"{directory}/{filename}")


if __name__ == "__main__":
    # Open graph from file
    graph = ox.load_graphml("graph_output/traffic_15files_reduced")

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
    add_traffic_level_from_folder(graph, "output_split/mixed", precision=3, save_each_graph_mongo=True)

    # Save the dates in MongoDB
    save_in_mongo()

    # Delete the files
    delete_files()
