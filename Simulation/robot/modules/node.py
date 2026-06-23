ID_DELTA = {"N": 10, "S": -10, "E": 1, "W": -1}
OPPOSITE_DIRECTION = {"N": "S", "S": "N", "E": "W", "W": "E"}
OBSTACLE_ATTR = {"N": "N_obstacle", "W": "W_obstacle", "E": "E_obstacle", "S": "S_obstacle"}
DIRECTION_DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}


def id_from_xy(x, y):
    return y * 10 + x


def xy_from_id(node_id):
    return node_id % 10, node_id // 10


def is_valid_coord(x, y, width, height):
    return 0 <= x < width and 0 <= y < height


'''
Đặc tả Edge:
[Edge này dùng cho cả simulation và robot thật]
1. Là điểm nối giữa 2 node, kế thừa thành 2 cạnh là NS_edge và WE_edge, nếu đang đứng ở một node nhìn lên 
   hướng N mà thấy cạnh đó bị chặn (NS_edge thì suy ra được thuộc tính của nó là N_obstacle = 1) và suy được node ở hướng N của node đó
   có thuộc tính S_obstacle = 1, tương tự với các hướng khác.
2. Hai node được liên kết, có 2 loại là NS và WE, cho hai hướng của map lưới. 
   - Chúng ta sẽ có quy luật, một node biến id, thì node hướng N của của nó là id + 10, 
   node hướng S của nó là id - 10, node hướng W của nó là id - 1, node hướng E của nó là id + 1.
   - Từ quy luật trên, có thể tự động xét liên kết giữa các node
   - quy luật phụ, các địa chỉ có số x hoặc y âm hoặc vượt quá kích thước map thì không tồn tại node đó.

[Robot memory — map chuẩn trong memory của robot, không liên quan tới map simulation]
'''


# class Edge:
#     def __init__(self, node1, node2, isBlock=False):
#         self.node1 = node1
#         self.node2 = node2
#         self.isBlock = isBlock

#     def set_block(self, mode):
#         self.isBlock = mode

#     def get_block(self):
#         return self.isBlock

#     def has_node(self, node):
#         return node is self.node1 or node is self.node2

#     def get_neighbor(self, node, direction):
#         raise NotImplementedError


# class NS_edge(Edge):
#     """Cạnh nối 2 node theo hướng Bắc - Nam."""

#     def __init__(self, N_node, S_node, isBlock=False):
#         if N_node.id != S_node.id + ID_DELTA["N"]:
#             raise ValueError("NS_edge: N_node.id phải = S_node.id + 10")
#         super().__init__(N_node, S_node, isBlock)
#         self.N_node = N_node
#         self.S_node = S_node

#     def get_neighbor(self, node, direction):
#         if node is self.S_node and direction == "N":
#             return self.N_node
#         if node is self.N_node and direction == "S":
#             return self.S_node
#         return None


# class WE_edge(Edge):
#     """Cạnh nối 2 node theo hướng Tây - Đông."""

#     def __init__(self, W_node, E_node, isBlock=False):
#         if E_node.id != W_node.id + ID_DELTA["E"]:
#             raise ValueError("WE_edge: E_node.id phải = W_node.id + 1")
#         super().__init__(W_node, E_node, isBlock)
#         self.W_node = W_node
#         self.E_node = E_node

#     def get_neighbor(self, node, direction):
#         if node is self.W_node and direction == "E":
#             return self.E_node
#         if node is self.E_node and direction == "W":
#             return self.W_node
#         return None


class Node:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.id = y*10 + x # quy luật của id sẽ là số x hợp số y, vậy thì khi đi lên sẽ là +10 , xuống -10, sang trái -1, sang phải +1
        self.N_obstacle = 0 # cập nhập từ edge NS trên
        self.W_obstacle = 0
        self.E_obstacle = 0
        self.S_obstacle = 0

    def neighbor_id(self, direction):
        return self.id + ID_DELTA[direction]

    def neighbor_xy(self, direction):
        dx, dy = DIRECTION_DELTA[direction]
        return self.x + dx, self.y + dy

    def get_obstacle(self, direction):
        return getattr(self, OBSTACLE_ATTR[direction])

    def _set_obstacle(self, direction, value):
        setattr(self, OBSTACLE_ATTR[direction], 1 if value else 0)

    def update_obs(self, direction, is_blocked, neighbor=None):
        """Cập nhật obstacle theo hướng map khi robot nhìn thấy cạnh bị chặn."""
        self._set_obstacle(direction, is_blocked)
        if neighbor is not None:
            neighbor._set_obstacle(OPPOSITE_DIRECTION[direction], is_blocked)

    def perceive(self, direction, is_blocked, edge):
        """Nhìn direction, cập nhật isBlock của edge và obstacle trên node memory."""
        if edge is None or not edge.has_node(self):
            return False
        neighbor = edge.get_neighbor(self, direction)
        if neighbor is None:
            return False
        edge.set_block(is_blocked)
        self.update_obs(direction, is_blocked, neighbor)
        return True


class RobotMap:
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

    def auto_link(self):
        """Tự tạo NS_edge và WE_edge giữa các node liền kề theo quy luật id."""
        for node in list(self.nodes.values()):
            n_neighbor = self.get_neighbor(node, "N")
            if n_neighbor and not self.get_edge_between(node, n_neighbor):
                self.add_ns_edge(n_neighbor, node)

            e_neighbor = self.get_neighbor(node, "E")
            if e_neighbor and not self.get_edge_between(node, e_neighbor):
                self.add_we_edge(node, e_neighbor)
