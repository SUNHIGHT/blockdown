class GameBoard:
        def __init__(self):
            self.board = [[' ']*10 for _ in range(20)]  # 10x20の空のボード 
    
        def display_board(self):
            for row in self.board:
                print(''.join(row))
    
        def update_board(self, block):
            x, y = block.position
            self.board[y][x] = '#'   # ブロックを#で示す
    