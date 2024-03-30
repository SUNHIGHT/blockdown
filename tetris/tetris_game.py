# tetris_game.py
import pygame
import random
import sys
from config import COLS, ROWS, BLOCK_SIZE, FPS, DROP_TIME,EMPTY_CELL,COLORS,TETROMINOS
from utils import draw_text

class TetrisGame:

    def __init__(self, screen):
        self.screen = screen
        self.score = 0
        self.COLORS = COLORS
        self.DROP_TIME = DROP_TIME
        self.TETROMINOS = TETROMINOS
        self.EMPTY_CELL = EMPTY_CELL
        self.COLS = COLS
        self.ROWS = ROWS
        self.BLOCK_SIZE = BLOCK_SIZE
        self.FPS = FPS
        self.field = [[self.EMPTY_CELL] * self.COLS for _ in range(self.ROWS)]
        self.screen = screen
        pygame.init()
        self.field = [[self.EMPTY_CELL] * self.COLS for _ in range(self.ROWS)]
        # self.screen = pygame.display.set_mode((self.COLS * self.BLOCK_SIZE, self.ROWS * self.BLOCK_SIZE))  # この行は削除またはコメントアウト
        self.clock = pygame.time.Clock()
        # BGMとSEのロード
        # self.bgm_path = '/Users/takanishi/ChatGPT/tetris/music/sample_music.mp3'
        # self.collision_se_path = '/Users/takanishi/ChatGPT/tetris/SE/collision_SE.mp3'
        # self.vanish_se_path = '/Users/takanishi/ChatGPT/tetris/SE/vanish_SE.mp3'
        # pygame.mixer.music.load(self.bgm_path)
        # self.collision_sound = pygame.mixer.Sound(self.collision_se_path)
        # self.vanish_sound = pygame.mixer.Sound(self.vanish_se_path)

        # 効果音の音量を最大に設定
        self.collision_sound.set_volume(1.0)  # pygameでは1.0が最大音量
        self.vanish_sound.set_volume(1.0)  # 1.5倍にはできないため、最大に設定

        # BGMの音量を0.5に設定
        pygame.mixer.music.set_volume(0.5)
        
        # BGMの再生（-1は無限ループを意味する）
        pygame.mixer.music.play(-1)

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
        # ゲームオーバー画面の表示前にBGMを停止
        pygame.mixer.music.stop()
        self.screen.fill((0, 0, 0))
        # ゲームオーバー画面のテキストを表示
        self.draw_text('Game Over', 20, self.COLS * self.BLOCK_SIZE / 2, self.ROWS * self.BLOCK_SIZE / 2)
        self.draw_text("Press 'R' to restart or 'S' to finish", 20, self.COLS * self.BLOCK_SIZE / 2, self.ROWS * self.BLOCK_SIZE / 2 + 30)

        pygame.display.update()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_f:
                        pygame.quit()
                        sys.exit()
                    if event.key == pygame.K_r:  # 's'キーで再開
                        self.reset_game()
                        return True
    
    def reset_game(self):
        self.field = [[self.EMPTY_CELL] * self.COLS for _ in range(self.ROWS)]
        self.score = 0
        self.DROP_TIME = 0.5  # 初期落下速度にリセット



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
        # ブロックが着地したときの効果音を再生
        self.collision_sound.play()

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
    
    def update_drop_speed(self):
        # スコアに応じて落下速度を更新
        if self.score < 1000:
            self.DROP_TIME = 0.5
        elif self.score < 2000:
            self.DROP_TIME = 0.45
        elif self.score < 3000:
            self.DROP_TIME = 0.4
        # 以降、スコアが高くなるごとにDROP_TIMEを小さくしていく
        else:
            self.DROP_TIME = max(0.1, self.DROP_TIME - 0.05)  # 一定の速さ以上にはならないようにする



    def remove_full_rows(self):
        new_field = [row for row in self.field if not all(cell != self.EMPTY_CELL for cell in row)]
        rows_deleted = len(self.field) - len(new_field)
        if rows_deleted > 0:
            self.score += self.calculate_score(rows_deleted)
            self.update_drop_speed()  # スコアが更新された後に落下速度を更新
            # 行が消去された時の効果音を再生
            self.vanish_sound.play()
        for _ in range(rows_deleted):
            new_field.insert(0, [self.EMPTY_CELL] * self.COLS)
        self.field = new_field

    
    def calculate_score(self, rows_deleted):
        # 行を消去することによるスコアの計算
        if rows_deleted == 1:
            return 100
        elif rows_deleted == 2:
            return 300
        elif rows_deleted == 3:
            return 500
        elif rows_deleted == 4:
            return 1000
        return 0

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
        # スコア表示位置の調整（画面の右端から30ピクセル左に寄せる）
        score_position_x = self.COLS * self.BLOCK_SIZE - 100  # 100は適宜調整してください
        self.draw_text(f"Score: {self.score}", 20, score_position_x, 10)

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