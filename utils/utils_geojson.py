import math


def create_linestring_geojson(coordinates, properties):
    """ Create a GeoJSON object with a LineString geometry
    Args:
        coordinates: A list of lists of coordinates
        properties: A dictionary with the properties of the feature
    Returns:
        A GeoJSON object with a LineString geometry"""

    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates
        }
    }


def get_geojson_corners_coordinates(x_tile, y_tile, zoom, format="latlng"):
    """ Get the coordinates of the corners of a tile in the GeoJSON format
    Args:
        x_tile: The x coordinate of the tile
        y_tile: The y coordinate of the tile
        zoom: The zoom level of the tile
        format: The format of the coordinates. Choose between 'latlng' and 'lnglat'
    Returns:
         A list with the coordinates of the corners of the tile in the GeoJSON format"""

    lng_left = x_tile * 360 / (2 ** zoom) - 180
    lng_right = (x_tile + 1) * 360 / (2 ** zoom) - 180
    lat_top = math.atan(math.sinh(math.pi * (1 - 2 * y_tile / (2 ** zoom)))) * 180 / math.pi
    lat_bottom = math.atan(math.sinh(math.pi * (1 - 2 * (y_tile + 1) / (2 ** zoom)))) * 180 / math.pi

    if format == "latlng":
        return [
            [lat_top, lng_left],
            [lat_bottom, lng_left],
            [lat_bottom, lng_right],
            [lat_top, lng_right],
            [lat_top, lng_left]  # Closing coordinate
        ]
    elif format == "lnglat":
        return [
            [lng_left, lat_top],
            [lng_left, lat_bottom],
            [lng_right, lat_bottom],
            [lng_right, lat_top],
            [lng_left, lat_top]  # Closing coordinate
        ]
    else:
        raise ValueError("Invalid format. Choose 'latlng' or 'lnglat'.")


if __name__ == "__main__":

    x_tile_coords = 7988
    y_tile_coords = 6393
    zoom = 14

    geojson_coordinates_tile1 = get_geojson_corners_coordinates(x_tile_coords, y_tile_coords, zoom, format="lnglat")
    geojson_coordinates_tile2 = get_geojson_corners_coordinates(x_tile_coords, y_tile_coords - 1, zoom, format="lnglat")
