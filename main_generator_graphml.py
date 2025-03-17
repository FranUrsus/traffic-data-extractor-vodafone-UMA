import osmnx as ox
import osmnx.bearing
from shapely.geometry.polygon import Polygon

from utils.utils_geojson import get_geojson_corners_coordinates


def generate_graph():
    # Define el área del Soho Málaga
    nombre = 'soho_malaga_7'

    puntos_ = [
        (36.717128201133136, -4.4270463127215836),
        (36.718842, -4.419519),
        (36.712883, -4.418099),
        (36.710143, -4.426427)
    ]

    puntos = [(x[1], x[0]) for x in puntos_]
    poligono = Polygon(puntos)
    # Descarga el grafo de la red de calles
    G = ox.graph_from_polygon(poligono, network_type="drive")

    # Guarda el grafo en formato GraphML
    ox.save_graphml(G, f"{nombre}.graphml")

def add_bearing():
    g = ox.load_graphml('zonas/soho/soho.graphml')
    g = osmnx.bearing.add_edge_bearings(g)
    ox.save_graphml(g, "soho.graphml")



def generate_tiles():
    # https://a.tile.openstreetmap.org/16/31962/25574.png
    corners_tile_soho1 = get_geojson_corners_coordinates(31962, 25575, 16, format='lnglat')
    for x, y in zip(['corners_0', 'corners_1', 'corners_2', 'corners_3'], corners_tile_soho1[:4]):
        print(f'"{x}": {y},')


if __name__ == '__main__':
    generate_tiles()