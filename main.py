import pygame
import sys

pygame.init()

screen = pygame.display.set_mode((640, 480))
pygame.display.set_caption("X Server Test - pygame")

running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill((30, 30, 30))

    font = pygame.font.SysFont(None, 36)
    text = font.render("X Server funktioniert!", True, (200, 200, 200))
    screen.blit(text, (120, 200))

    pygame.display.flip()

pygame.quit()
sys.exit()
