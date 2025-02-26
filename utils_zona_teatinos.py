def handle_jimenez_fraud(graph, node_1_id, node_2_id, filename, info):
    nearest_edge = graph.edges[node_1_id, node_2_id, 0]

    if node_1_id == 2094195157 and node_2_id == 2094195159:
        nearest_edge = graph.edges[418336300, 418336304, 0]
        extra_edge_info = graph.edges[418336304, 418336308, 0]
        extra_edge_info["dates"][filename] = info

    if node_1_id == 2094195165 and node_2_id == 3152120576:
        nearest_edge = graph.edges[418336289, 4943984606, 0]

        extra_edge_info = graph.edges[4943984604, 3152120577, 0]
        extra_edge_info["dates"][filename] = info

        extra_edge_info = graph.edges[3152120577, 418336292, 0]
        extra_edge_info["dates"][filename] = info

    if node_1_id == 2094195153 and node_2_id == 2094195155:
        nearest_edge = graph.edges[418336308, 2094195150, 0]

    if node_1_id == 2614757891 and node_2_id == 2094195161:
        nearest_edge = graph.edges[250962361, 2614757893, 0]

        extra_edge_info = graph.edges[2614757893, 5625095808, 0]
        extra_edge_info["dates"][filename] = info

        extra_edge_info = graph.edges[5625095808, 418336300, 0]
        extra_edge_info["dates"][filename] = info

    if node_1_id == 2094195161 and node_2_id == 2874546302:
        nearest_edge = graph.edges[2874546303, 250962361, 0]

    return nearest_edge
