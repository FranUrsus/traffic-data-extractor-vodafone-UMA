# import osmnx as ox
#
# # Define el área del Soho Málaga
# place_name = "Soho, Málaga, España"
# place_name = "Ensanche Centro, Málaga, España"
# nombre = 'soho_malaga'
# nombre = 'ensanche_malaga'
#
# # Descarga el grafo de la red de calles
# G = ox.graph_from_place(place_name, network_type="drive")
#
# # Guarda el grafo en formato GraphML
# ox.save_graphml(G, f"{nombre}.graphml")