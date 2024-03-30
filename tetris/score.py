import random
import pygame
import sys

class TetrisGame:
    COLS = 10
    ROWS = 20
    BLOCK_SIZE = 30
    COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255), (255, 0, 255)]
    TETROMINOS = {
        'I': [[1, 1, 1, 1]],
        'O': [[1, 1], [1, 1]],
        'T': [[1, 1, 1], [0, 1, 0]],
        'S': [[0, 1, 1], [1, 1, 0]],
        'Z': [[1, 1, 0], [0, 1, 1]],
        'J': [[1, 0, 0], [1, 1, 1]],
        'L': [[0, 0, 1], [1, 1, 1]]
    }
    EMPTY_CELL = 0
    FPS = 30  
    DROP_TIME = 0.5

    def __init__(self):
        pygame.init()
        self.field = [[self.EMPTY_CELL] * self.COLS for _ in range(self.ROWS)]
        self.screen = pygame.display.set_mode(
            (self.COLS * self.BLOCK_SIZE, self.ROWS * self.BLOCK_SIZE)
        )
        self.clock = pygame.time.Clock()

    def main_menu(self):
        while True:
            self.screen.fill((0, 0, 0))
            # スタート画面のテキストを表示（"Press 'S' key to start"に変更）
            self.draw_text("Press 'S' key to start", 20, self.COLS * self.BLOCK_SIZE / 2, self.ROWS * self.BLOCK_SIZE / 2)
            pygame.display.update()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_s:  # 's'キーでゲーム開始
                        return True


    def game_over_screen(self):
        self.screen.fill((0, 0, 0))
        # ゲームオーバー画面のテキストを表示
        self.draw_text('Game Over', 20, self.COLS * self.BLOCK_SIZE / 2, self.ROWS * self.BLOCK_SIZE / 2)
        self.draw_text("Press 'S' key to restart", 20, self.COLS * self.BLOCK_SIZE / 2, self.ROWS * self.BLOCK_SIZE / 2 + 30)
        pygame.display.update()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_s:  # 's'キーで再開
                        return


    def draw_text(self, text, size, x, y):
        font = pygame.font.Font(pygame.font.get_default_font(), size)
        text_surface = font.render(text, True, (255, 255, 255))
        text_rect = text_surface.get_rect()
        text_rect.midtop = (x, y)
        self.screen.blit(text_surface, text_rect)


    def create_new_block(self):
        pos_x = self.COLS // 2
        pos_y = 0
        block_color = random.choice(self.COLORS)
        block = random.choice(list(self.TETROMINOS.values())) 
        return pos_x, pos_y, block_color, block

    def add_block_to_field(self, pos_x, pos_y, block_color, block):
        for col, row in enumerate(block):
            for row_val, cell in enumerate(row):
                if cell:
                    self.field[pos_y + row_val][pos_x + col] = block_color

    def draw_block(self, x, y, block_color):
        pygame.draw.rect(
            self.screen, block_color,
            (x*self.BLOCK_SIZE, y*self.BLOCK_SIZE, self.BLOCK_SIZE-1, self.BLOCK_SIZE-1)    
        )


    def update_position(self, pos_x, delta_x):
        pos_x += delta_x
        return pos_x
    def rotate_block(self, block):
        return [list(row) for row in zip(*block[::-1])]

    def handle_user_input(self):
        delta_x = 0
        rotate = False
        fast_drop = False  # 早送りフラグを追加
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    delta_x = -1
                elif event.key == pygame.K_RIGHT:
                    delta_x = 1
                elif event.key == pygame.K_DOWN:  # 下キーで早送り
                    fast_drop = True
                elif event.key == pygame.K_RETURN:  # エンターキーで回転
                    rotate = True
        return delta_x, rotate, fast_drop



    def remove_full_rows(self):
        # 一列が全て埋まっているか確認し、埋まっていない行だけを新しいフィールドに追加
        new_field = [row for row in self.field if not all(cell != self.EMPTY_CELL for cell in row)]
        # 消去した行の数だけ上部に新しい空の行を追加
        rows_deleted = len(self.field) - len(new_field)
        for _ in range(rows_deleted):
            new_field.insert(0, [self.EMPTY_CELL for _ in range(self.COLS)])
        self.field = new_field


    def process_user_input(self, pos_x, pos_y, block, delta_x, block_color):
        if self.collision_test(pos_x + delta_x, pos_y + 1, block):
            self.add_block_to_field(pos_x, pos_y, block_color, block)
            self.remove_full_rows()
            pos_x, pos_y, block_color, block = self.create_new_block()

            if self.collision_test(pos_x, pos_y, block):
                return True, pos_x, pos_y, block_color, block
        else:
            pos_x = self.update_position(pos_x, delta_x)

        return False, pos_x, pos_y, block_color, block

    def draw_field_and_block(self, pos_x, pos_y, block_color, block):
        self.screen.fill((0, 0, 0))

    # フィールド上の既存のブロックを描画
        for y, row in enumerate(self.field):
            for x, cell in enumerate(row):
                if cell != self.EMPTY_CELL:  # cell が EMPTY_CELL でない場合、ブロックの一部
                    self.draw_block(x, y, cell)

        # 現在落下中のブロックを描画
        for c, row in enumerate(block):
            for r, val in enumerate(row):
                if val:
                    self.draw_block(pos_x + c, pos_y + r, block_color)


    def drop_block_over_time(self, pos_y, start_ticks, drop_speed):
        seconds = (pygame.time.get_ticks() - start_ticks) / 1000
        if seconds > drop_speed:  # drop_speedを使用して落下間隔を制御
            pos_y += 1
            start_ticks = pygame.time.get_ticks()
        return pos_y, start_ticks

    
    def collision_test(self, pos_x, pos_y, block):
        for col, row in enumerate(block):
            for row_val, cell in enumerate(row):
                if cell:
                    field_x = pos_x + col
                    field_y = pos_y + row_val

                    # 横軸方向の範囲外判定
                    if field_x < 0 or field_x >= self.COLS:
                        return True

                    # 縦軸方向の範囲外判定
                    if field_y >= self.ROWS:
                        return True
            
                    # ブロックとフィールドの衝突判定
                    is_collision = self.field[field_y][field_x] != self.EMPTY_CELL
                    if is_collision:
                        # 衝突が確認されたらTrueを返す
                        return True
        return False

    def game_loop(self):
        while True:  # ゲームをリスタート可能にするためのループ
            pos_x, pos_y, block_color, block = self.create_new_block()
            fast_drop = False  # fast_dropをここで初期化
            game_over = False  # ここでgame_over変数を初期化
            start_ticks = pygame.time.get_ticks()

            while not game_over:
                delta_x, rotate, fast_drop = self.handle_user_input()  # fast_dropを受け取る
                new_pos_x = self.update_position(pos_x, delta_x)
                if not self.collision_test(new_pos_x, pos_y, block):
                    pos_x = new_pos_x

                # 下キーが押された場合の早送り処理
                if fast_drop:
                    drop_speed = 0.05  # 早送り時の落下間隔を短くする
                else:
                    drop_speed = self.DROP_TIME
                pos_y, start_ticks = self.drop_block_over_time(pos_y, start_ticks, drop_speed)

                if self.collision_test(pos_x, pos_y + 1, block):
                    self.add_block_to_field(pos_x, pos_y, block_color, block)
                    self.remove_full_rows()
                    pos_x, pos_y, block_color, block = self.create_new_block()
                    if self.collision_test(pos_x, pos_y, block):
                        game_over = True

                if rotate:
                    rotated_block = self.rotate_block(block)
                    if not self.collision_test(pos_x, pos_y, rotated_block):
                        block = rotated_block

                self.draw_field_and_block(pos_x, pos_y, block_color, block)
                pygame.display.update()
                self.clock.tick(self.FPS)

            # ゲームオーバー処理
            self.game_over_screen()
            if not self.main_menu():  # ゲームオーバー後、メインメニューで「S」キーが押されなかった場合、終了
                break




if __name__ == "__main__":
    game = TetrisGame()
    if game.main_menu():  # main_menuがTrueを返したらゲームを開始
        game.game_loop()

