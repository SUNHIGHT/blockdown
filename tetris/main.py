# main.py
import pygame
import sys
from tetris_game import TetrisGame
from config import COLS, ROWS, BLOCK_SIZE,FPS

def main():

    pygame.init()
    screen = pygame.display.set_mode((COLS * BLOCK_SIZE, ROWS * BLOCK_SIZE))
    clock = pygame.time.Clock()
    game = TetrisGame(screen)

    while True:
        game = TetrisGame(screen)
        game.main_menu()

        game_over = False

        while not game_over:
            game_over = game.game_loop()

            if game_over:
                restart = game.game_over_screen()
                if not restart:
                    break

        pygame.display.update()
        clock.tick(FPS)

if __name__ == "__main__":
    main()
