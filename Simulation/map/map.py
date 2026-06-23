from map.node import Node, NS_edge, WE_edge, is_valid_coord


class Map:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.nodes = {}
        self.nodes_by_id = {}
        self.edges = []

    def add_node(self, x, y):
        if not is_valid_coord(x, y, self.width, self.height):
            return None
        node = Node(x, y)
        self.nodes[(x, y)] = node
        self.nodes_by_id[node.id] = node
        return node

    def get_node(self, x, y):
        if not is_valid_coord(x, y, self.width, self.height):
            return None
        return self.nodes.get((x, y))

    def get_node_by_id(self, node_id):
        return self.nodes_by_id.get(node_id)

    def get_neighbor(self, node, direction):
        x, y = node.neighbor_xy(direction)
        return self.get_node(x, y)

    def add_ns_edge(self, n_node, s_node, isBlock=False):
        edge = NS_edge(n_node, s_node, isBlock)
        self.edges.append(edge)
        return edge

    def add_we_edge(self, w_node, e_node, isBlock=False):
        edge = WE_edge(w_node, e_node, isBlock)
        self.edges.append(edge)
        return edge

    def get_edge_between(self, node_a, node_b):
        if node_b is None:
            return None
        for edge in self.edges:
            if isinstance(edge, NS_edge):
                pair = {edge.N_node, edge.S_node}
            elif isinstance(edge, WE_edge):
                pair = {edge.W_node, edge.E_node}
            else:
                pair = {edge.node1, edge.node2}
            if node_a in pair and node_b in pair:
                return edge
        return None

    def get_edge_in_direction(self, node, direction):
        neighbor = self.get_neighbor(node, direction)
        return neighbor, self.get_edge_between(node, neighbor)

    def read_block(self, x, y, direction):
        """Đọc trạng thái chặn thật của cạnh theo vị trí và hướng nhìn."""
        node = self.get_node(x, y)
        if node is None:
            return False
        _, edge = self.get_edge_in_direction(node, direction)
        if edge is None:
            return False
        return edge.get_block()

    def auto_link(self):
        """Tự tạo NS_edge và WE_edge giữa các node liền kề theo quy luật id."""
        for node in list(self.nodes.values()):
            n_neighbor = self.get_neighbor(node, "N")
            if n_neighbor and not self.get_edge_between(node, n_neighbor):
                self.add_ns_edge(n_neighbor, node)

            e_neighbor = self.get_neighbor(node, "E")
            if e_neighbor and not self.get_edge_between(node, e_neighbor):
                self.add_we_edge(node, e_neighbor)
