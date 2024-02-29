import argparse
import sys
import time

import pygame

import util as util
from config_parser import ConfigParser
from constants import KEYBIND_FULLSCREEN
from dataobjects.config import ConfigSchema
from linked_list import Node


class Game:
    FPS = 20

    # Transition
    TOTAL_FADE_STEPS = 255
    TRANSITION_DURATION_SECONDS = 5
    FADE_STEPS = TOTAL_FADE_STEPS / float(TRANSITION_DURATION_SECONDS * FPS)

    # Drawing
    FONT_SIZE = 42
    FONT_COLOR = (255, 255, 255)
    INITIAL_WINDOW_SIZE = (1280, 720)
    LOGICAL_SIZE = (2048, 1080)
    logical_surface = pygame.Surface(LOGICAL_SIZE)

    _running = True

    def __init__(self, config: ConfigSchema):
        pygame.font.init()
        pygame.mixer.init()

        # Window
        self.__screen = pygame.display.set_mode(
            self.INITIAL_WINDOW_SIZE, pygame.RESIZABLE
        )
        self.font = pygame.font.Font(config.font, self.FONT_SIZE)
        pygame.display.set_caption("Phusic")

        # Load stuff
        getter = ConfigParser()

        start_time = time.time()
        res = getter.get_assets(config)
        end_time = time.time()

        print(f"Execution time: {end_time - start_time} seconds")

        self.phases = res["phases"]
        self.endings = res["endings"]
        self.sfx = res["sfx"]

        # Setup state
        self.fade_step = 0
        self.is_fading = False
        self.is_fullscreen = True

        self.linked_list = util.create_linked_list(self.phases)
        self.curr_phase = self.linked_list.head
        self.next_phase = Node(None)

    def run(self) -> None:
        clock = pygame.time.Clock()
        self._initial_phase()

        while self._running:
            self._handle_events()
            self._draw_phase()
            self._render()
            clock.tick(self.FPS)

        pygame.quit()
        sys.exit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == getattr(pygame, KEYBIND_FULLSCREEN):
                    self._toggle_fullscreen()

                if event.key == pygame.K_LEFT:
                    self._change_phase(self.curr_phase.prev)

                if event.key == pygame.K_RIGHT or event.key == pygame.K_SPACE:
                    self._change_phase(self.curr_phase.next)

                if pygame.key.get_mods() & pygame.KMOD_CTRL:
                    if event.key == pygame.K_LEFT:
                        self._set_phase(self.curr_phase.prev)
                    elif event.key == pygame.K_RIGHT:
                        self._set_phase(self.curr_phase.next)
                    elif event.key == pygame.K_c:
                        print("Shutting down")
                        exit(0)

                for ending in self.endings:
                    if event.key == ending.key:
                        ending_node = Node(ending)
                        self._change_phase(ending_node)

                for sfx in self.sfx:
                    if event.key == sfx.key:
                        sfx.sound.play()

    def _toggle_fullscreen(self) -> None:
        self.is_fullscreen = not self.is_fullscreen

        if self.is_fullscreen:
            self.logical_surface = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.logical_surface = pygame.display.set_mode(self.LOGICAL_SIZE)

    def _initial_phase(self) -> None:
        phase = self.curr_phase.value
        phase.sound.set_volume(1.0)
        phase.sound.play(-1)
        phase.background = pygame.transform.scale(phase.background, self.LOGICAL_SIZE)

    def _change_phase(self, phase_node: Node) -> None:
        if self.is_fading:
            return

        if not phase_node:
            if not self.linked_list.head:
                print("Linked list is empty")
                exit(1)

            print("No next phase, reverting back to start...")
            phase_node = self.linked_list.head

        self.is_fading = True
        self.fade_step = 0
        self.next_phase = phase_node

        phase = phase_node.value
        phase.sound.set_volume(0.0)
        phase.sound.play(-1)
        phase.background = pygame.transform.scale(phase.background, self.LOGICAL_SIZE)

    def _set_phase(self, phase_node: Node) -> None:
        """Update the current phase without fading"""
        if self.next_phase.value:
            self.next_phase.value.sound.stop()
        self.curr_phase.value.sound.stop()
        self.is_fading = False
        self.fade_step = 0

        phase = phase_node.value
        phase.sound.set_volume(1.0)
        phase.sound.play(-1)
        phase.background = pygame.transform.scale(phase.background, self.LOGICAL_SIZE)

        self.curr_phase = phase_node

    def _draw_phase(self) -> None:
        curr_phase = self.curr_phase.value
        next_phase = self.next_phase.value

        if self.is_fading:
            # Handle fade background
            alpha = int(self.fade_step * (255 / self.TOTAL_FADE_STEPS))
            next_phase.background.set_alpha(alpha)
            self.logical_surface.blit(curr_phase.background, (0, 0))
            self.logical_surface.blit(next_phase.background, (0, 0))

            # Handle fade sound
            new_volume = alpha / 255.0
            next_phase.sound.set_volume(new_volume)
            curr_phase.sound.set_volume(1.0 - new_volume)

            self.fade_step += self.FADE_STEPS

            if self.fade_step > self.TOTAL_FADE_STEPS:
                self.is_fading = False
                curr_phase.sound.stop()
                self.curr_phase = self.next_phase
        else:
            self.logical_surface.blit(curr_phase.background, (0, 0))

            # Draw phase name
            phase_position = (20, self.LOGICAL_SIZE[1] - 10 - self.FONT_SIZE)
            self._draw_text_with_outline(curr_phase.name, phase_position)

        # Draw current time
        curr_time = util.get_local_time()
        time_position = (
            self.LOGICAL_SIZE[0] - self.FONT_SIZE - 55,
            self.LOGICAL_SIZE[1] - 10 - self.FONT_SIZE,
        )
        self._draw_text_with_outline(curr_time, time_position)

        pygame.display.flip()

    def _draw_text_with_outline(self, text, position, outline_width: int = 2) -> None:
        x, y = position

        for dx, dy in [
            (ow, oh)
            for ow in range(-outline_width, outline_width + 1)
            for oh in range(-outline_width, outline_width + 1)
            if ow != 0 or oh != 0
        ]:
            text_surface = self.font.render(text, True, (0, 0, 0))
            self.logical_surface.blit(text_surface, (x + dx, y + dy))

        text_surface = self.font.render(text, True, self.FONT_COLOR)
        self.logical_surface.blit(text_surface, position)

    def _draw_loading_screen(self, text: str, progress: float) -> None:
        self.logical_surface.fill((0, 0, 0))

        # Draw text
        text_surface = self.font.render(text, True, (255, 255, 255))
        center_width = self.LOGICAL_SIZE[0] // 2
        center_height = self.LOGICAL_SIZE[1] // 2
        text_rect = text_surface.get_rect(center=(center_width, center_height - 50))
        self.logical_surface.blit(text_surface, text_rect)

        # Draw progress bar
        progress_bar_width = 200
        progress_bar_height = 20
        progress_bar_x = center_width - progress_bar_width // 2
        progress_bar_y = center_height + 10
        progress_fill = progress * progress_bar_width

        # Draw progress bar background
        pygame.draw.rect(
            self.logical_surface,
            (255, 255, 255),
            (progress_bar_x, progress_bar_y, progress_bar_width, progress_bar_height),
            1,
        )
        # Fill the progress bar
        if progress_fill > 0:
            pygame.draw.rect(
                self.logical_surface,
                (255, 255, 255),
                (progress_bar_x, progress_bar_y, progress_fill, progress_bar_height),
            )

        self._render()

    def _render(self) -> None:
        window_size = pygame.display.get_surface().get_size()
        scaled_surface = pygame.transform.smoothscale(self.logical_surface, window_size)

        self.__screen.blit(scaled_surface, (0, 0))
        pygame.display.flip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Start the game with a configuration file."
    )
    parser.add_argument(
        "--config",
        default="configs/blood_rage.json",
        type=str,
        help="Path to configuration file",
    )
    args = parser.parse_args()

    # Validate configs
    ConfigParser.assert_valid_configs()
    config = ConfigParser.parse_schema(args.config)

    # Write controls
    util.generate_controls_file(config)

    game = Game(config)
    game.run()
