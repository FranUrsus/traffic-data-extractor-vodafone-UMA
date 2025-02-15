import osmnx as ox

# Define el área del Soho Málaga
place_name = "Soho, Málaga, España"

# Descarga el grafo de la red de calles
G = ox.graph_from_place(place_name, network_type="drive")

# Guarda el grafo en formato GraphML
ox.save_graphml(G, "soho_malaga.graphml")