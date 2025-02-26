from datetime import datetime

from mongo_manager import ObjetoMongoAbstract


def _clean_edges_info(graph):
    """ Remove the extra info from the graph
    Args:
        graph: The graph to remove the extra info
    Returns:
        The graph with the extra info removed"""
    clean_keys = ('dates', 'lanes', 'oneway', 'bearing', 'speed_kph', 'maxspeed', 'length',
                  'geometry', 'ref', 'service', 'junction', 'reversed', 'travel_time')
    for u, v, data in graph.edges(data=True):
        data['traffic_level'] = data['most_recent']['traffic_level']
        data['api_data'] = data['most_recent']['api_data']
        try:
            maxspeed = float(data.get('maxspeed', 0))  # Usa 0 si no existe
            traffic_level = float(data.get('traffic_level', 1))  # Usa 1 si no existe
            data['current_speed'] = maxspeed * traffic_level
        except ValueError:
            data['current_speed'] = 0  # Valor por defecto si la conversión falla
        for key in clean_keys:
            data.pop(key, None)
    return graph


class Graph(ObjetoMongoAbstract):

    def __init__(self, filename, datetime,
                 hour_minute_string, hour_int,
                 minute_int, day_of_week, hour_float,
                 links, automated, _id=None, **kwargs):
        super().__init__(_id=_id, **kwargs)
        self.filename = filename
        self.datetime = datetime
        self.hour_minute_string = hour_minute_string
        self.hour_int = hour_int
        self.minute_int = minute_int
        self.day_of_week = day_of_week
        self.hour_float = hour_float
        self.automated = automated
        self.links = links

    def __str__(self):
        return f'{self.datetime}: {self.links} '

    @classmethod
    def generate_graph(cls, graph, filename: str):
        """ Remove the extra info from the graph before saving it to the database
        Args:
            graph: The graph to remove the extra info
            filename: The filename of the date to remove the extra info
        Returns:
            The graph with the extra info removed"""
        import networkx as nx

        # Copy graph to avoid modifying the original graph
        graph_copy = graph.copy()

        graph_copy = _clean_edges_info(graph_copy)

        graph_to_dictionary = nx.node_link_data(graph_copy, edges="links")

        graph_to_dictionary.pop('graph', None)
        graph_to_dictionary.pop('directed', None)
        graph_to_dictionary.pop('multigraph', None)
        graph_to_dictionary.pop('nodes', None)

        graph_to_dictionary['filename'] = filename
        graph_to_dictionary["datetime"] = datetime.strptime(filename.split(".")[0], "%Y_%m_%d_%H_%M_%S")
        graph_to_dictionary["hour_minute_string"] = graph_to_dictionary["datetime"].strftime("%H:%M")
        graph_to_dictionary["hour_int"] = graph_to_dictionary["datetime"].hour
        graph_to_dictionary["minute_int"] = graph_to_dictionary["datetime"].minute
        graph_to_dictionary["day_of_week"] = graph_to_dictionary["datetime"].strftime("%A")

        graph_to_dictionary["hour_float"] = graph_to_dictionary["hour_int"] + (graph_to_dictionary["minute_int"] / 60.0)

        graph_to_dictionary["automated"] = True

        return cls(**graph_to_dictionary)
