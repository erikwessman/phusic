import argparse
import math
import sys
import time
from asyncio import Event
from typing import Optional

import pygame

import util as util
from config_cop import patrol
from config_manager import ConfigManager
from constants import KEYBIND_FULLSCREEN
from dataobjects.config_schema import ConfigSchema
from linked_list import Node


class Game:
    FPS = 20
    cm: ConfigManager

    # Transition
    TOTAL_FADE_STEPS = 255
    TRANSITION_DURATION_SECONDS = 5
    FADE_STEPS = TOTAL_FADE_STEPS / float(TRANSITION_DURATION_SECONDS * FPS)

    # Drawing
    FONT_SIZE = 42
    INITIAL_WINDOW_SIZE = (1280, 720)
    LOGICAL_SIZE = (2560, 1440)
    logical_surface = pygame.Surface(LOGICAL_SIZE)

    # State
    running = True
    fade_step = 0
    is_fading = False
    is_fullscreen = True
    phase_started_at: float = 0

    def __init__(self, config: ConfigSchema):
        self.cm = ConfigManager(config)
        pygame.font.init()
        pygame.mixer.pre_init(44100, -16, 1, 512)
        pygame.mixer.init()

        self.__screen = pygame.display.set_mode(
            self.INITIAL_WINDOW_SIZE, pygame.RESIZABLE
        )

        self.font = pygame.font.Font(self.cm.get_font(), self.FONT_SIZE)
        pygame.display.set_caption("Phusic")

    def run(self) -> None:
        clock = pygame.time.Clock()
        self.cm.load_assets()

        fake_progress = 0
        while self.cm.status()["loading"]:
            load = self.cm.status()["latest_load"]
            fake_progress += 0.02
            self._draw_loading_screen(f"Loading: {load}", fake_progress % 1)
            self._render()
            time.sleep(0.01)

        res = self.cm.get_assets()
        self.phases = res["phases"]
        self.sfx = res["sfx"]

        start_phase = next(
            phase for phase in self.phases if phase.unique_id == config.start_phase
        )
        if not start_phase:
            raise ValueError("Start phase not found")

        self.linked_list = util.create_linked_list(start_phase, self.phases)
        self.curr_phase = self.linked_list.head
        self.next_phase = Node(None)

        self._initial_phase()

        # Main loop
        while self.running:
            self._handle_events()
            self._draw_phase()
            self._render()
            clock.tick(self.FPS)

        pygame.quit()
        sys.exit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)

        # Automatic phase change
        if self.curr_phase.value.duration is None:
            return

        time_in_phase = time.time() - self.phase_started_at
        if time_in_phase > self.curr_phase.value.duration:
            self._change_phase(self.curr_phase.next)

    def _handle_keydown(self, event: Event) -> None:
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
                exit(0)

        for phase in self.phases:
            if phase.key is not None and event.key == getattr(pygame, phase.key):
                ending_node = Node(phase)
                self._change_phase(ending_node)

        for sfx in self.sfx:
            if event.key == sfx.key:
                sfx.sound.play()

    def _toggle_fullscreen(self) -> None:
        self.is_fullscreen = not self.is_fullscreen

        if self.is_fullscreen:
            self.__screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.__screen = pygame.display.set_mode(
                self.INITIAL_WINDOW_SIZE, pygame.RESIZABLE
            )

    def _initial_phase(self) -> None:
        phase = self.curr_phase.value
        phase.sound.set_volume(1.0)
        phase.sound.play(-1)
        phase.background = pygame.transform.scale(phase.background, self.LOGICAL_SIZE)
        self.phase_started_at = time.time()

    def _change_phase(self, phase_node: Optional[Node]) -> None:
        if self.is_fading:
            return

        if not phase_node:
            return

        self.is_fading = True
        self.fade_step = 0
        self.next_phase = phase_node

        phase = phase_node.value
        phase.sound.set_volume(0.0)
        phase.sound.play(-1)
        phase.background = pygame.transform.scale(phase.background, self.LOGICAL_SIZE)
        self.phase_started_at = time.time()

    def _set_phase(self, phase_node: Optional[Node]) -> None:
        """Update the current phase without fading"""
        if not phase_node:
            return

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
        self.phase_started_at = time.time()

    def _draw_phase(self) -> None:
        curr_phase = self.curr_phase.value
        next_phase = self.next_phase.value

        text_margin = 32
        clock_margin = 64

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
            phase_position = (
                text_margin,
                self.LOGICAL_SIZE[1] - self.FONT_SIZE - text_margin,
            )

            surface = self._draw_text_with_outline(curr_phase.name, phase_position)

            # Draw time
            self._draw_text_with_outline(
                util.get_local_time(),
                (surface.get_width() + clock_margin, phase_position[1]),
                opacity=0.6,
            )

        pygame.display.flip()

    def _draw_text_with_outline(
        self, text, position, outline_width: int = 2, opacity: int = 1
    ) -> pygame.Surface:
        """
        Draws text on a pygame surface with an outline effect.

        Returns:
        - pygame.Surface: The surface with the text (including its outline) drawn on it.
        """
        x, y = position

        for dx, dy in [
            (ow, oh)
            for ow in range(-outline_width, outline_width + 1)
            for oh in range(-outline_width, outline_width + 1)
            if ow != 0 or oh != 0
        ]:
            text_surface = self.font.render(text, True, (0, 0, 0))
            text_surface = text_surface.convert_alpha()
            text_surface.set_alpha(opacity * 255)
            self.logical_surface.blit(text_surface, (x + dx, y + dy))

        text_surface = self.font.render(text, True, (255, 255, 255))
        text_surface = text_surface.convert_alpha()
        text_surface.set_alpha(opacity * 255)
        self.logical_surface.blit(text_surface, position)

        return text_surface

    def _draw_loading_screen(self, text: str, progress: float) -> None:
        self.logical_surface.fill((0, 0, 0))

        # Draw text
        text_surface = self.font.render(text, True, (255, 255, 255))
        center_width = self.LOGICAL_SIZE[0] // 2
        center_height = self.LOGICAL_SIZE[1] // 2
        text_rect = text_surface.get_rect(center=(center_width, center_height - 50))
        self.logical_surface.blit(text_surface, text_rect)

        circle_radius = 10
        movement_width = 200
        circle_x_start = center_width - movement_width // 2
        circle_y = center_height + 10 + circle_radius

        progress_modulo = progress % 1.0
        oscillation = math.sin(progress_modulo * math.pi * 2)
        circle_x = (
            circle_x_start
            + (movement_width // 2)
            + (oscillation * (movement_width // 2 - circle_radius))
        )

        pygame.draw.circle(
            self.logical_surface,
            (255, 255, 255),
            (int(circle_x), circle_y),
            circle_radius,
        )

    def _render(self) -> None:
        window_size = pygame.display.get_surface().get_size()
        logical_aspect_ratio = self.LOGICAL_SIZE[0] / self.LOGICAL_SIZE[1]
        window_aspect_ratio = window_size[0] / window_size[1]

        if logical_aspect_ratio > window_aspect_ratio:
            new_width = window_size[0]
            new_height = int(new_width / logical_aspect_ratio)
        else:
            new_height = window_size[1]
            new_width = int(new_height * logical_aspect_ratio)

        scaled_surface = pygame.transform.smoothscale(
            self.logical_surface, (new_width, new_height)
        )

        x_position = (window_size[0] - new_width) // 2
        y_position = (window_size[1] - new_height) // 2

        self.__screen.fill((0, 0, 0))
        self.__screen.blit(scaled_surface, (x_position, y_position))
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
    patrol()
    config = ConfigManager.parse_schema(args.config)

    # Write controls
    util.generate_controls_file(config)

    game = Game(config)
    game.run()
