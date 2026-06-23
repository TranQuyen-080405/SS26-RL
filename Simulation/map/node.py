ID_DELTA = {"N": 10, "S": -10, "E": 1, "W": -1}
DIRECTION_DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}


def id_from_xy(x, y):
    return y * 10 + x


def xy_from_id(node_id):
    return node_id % 10, node_id // 10


def is_valid_coord(x, y, width, height):
    return 0 <= x < width and 0 <= y < height


'''
Đặc tả map simulation (thay cho map thật):
- Node: ô trên lưới, có id theo quy luật y*10 + x.
- Edge: cạnh nối 2 node, có isBlock (ground truth vật lý).
- NS_edge / WE_edge: hai loại cạnh theo hướng lưới.
'''


class Edge:
    def __init__(self, node1, node2, isBlock=False):
        self.node1 = node1
        self.node2 = node2
        self.isBlock = isBlock
    
    def set_block(self, mode):
        self.isBlock = mode

    def get_block(self):
        return self.isBlock

    def has_node(self, node):
        return node is self.node1 or node is self.node2

    def get_neighbor(self, node, direction):
        raise NotImplementedError


class NS_edge(Edge):
    """Cạnh nối 2 node theo hướng Bắc - Nam."""

    def __init__(self, N_node, S_node, isBlock=False):
        if N_node.id != S_node.id + ID_DELTA["N"]:
            raise ValueError("NS_edge: N_node.id phải = S_node.id + 10")
        super().__init__(N_node, S_node, isBlock)
        self.N_node = N_node
        self.S_node = S_node

    def get_neighbor(self, node, direction):
        if node is self.S_node and direction == "N":
            return self.N_node
        if node is self.N_node and direction == "S":
            return self.S_node
        return None


class WE_edge(Edge):
    """Cạnh nối 2 node theo hướng Tây - Đông."""

    def __init__(self, W_node, E_node, isBlock=False):
        if E_node.id != W_node.id + ID_DELTA["E"]:
            raise ValueError("WE_edge: E_node.id phải = W_node.id + 1")
        super().__init__(W_node, E_node, isBlock)
        self.W_node = W_node
        self.E_node = E_node

    def get_neighbor(self, node, direction):
        if node is self.W_node and direction == "E":
            return self.E_node
        if node is self.E_node and direction == "W":
            return self.W_node
        return None


class Node:
    def __init__(self, x, y):
        self.id = y*10 + x # quy luật của id sẽ là số x hợp số y, vậy thì khi đi lên sẽ là +10 , xuống -10, sang trái -1, sang phải +1
        self.x = x
        self.y = y

    def neighbor_id(self, direction):
        return self.id + ID_DELTA[direction]

    def neighbor_xy(self, direction):
        dx, dy = DIRECTION_DELTA[direction]
        return self.x + dx, self.y + dy
