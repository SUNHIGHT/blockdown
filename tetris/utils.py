# utils.py
import pygame

def draw_text(screen, text, size, x, y):
    font = pygame.font.Font(pygame.font.get_default_font(), size)
    text_surface = font.render(text, True, (255, 255, 255))
    text_rect = text_surface.get_rect()
    text_rect.midtop = (x, y)
    screen.blit(text_surface, text_rect)
