import pygame
import sys
from pathlib import Path
from super_mario_pygamece.game import PygameMario
from super_mario_pygamece.paths import ProjectPaths

def simulate_game():
    # Setup paths
    project_root = Path("/mnt/f/C++_Projects/Super_Mario_PYGAMECE")
    paths = ProjectPaths(project_root)
    
    # Initialize game
    game = PygameMario(level_path=None, paths=paths, audio_enabled=False)
    
    print("Simulation started: Logging gameplay events...")
    
    # Simulate 30 seconds at 60 FPS = 1800 frames
    for frame in range(1800):
        # Log status every 100 frames
        if frame % 100 == 0:
            print(f"[Frame {frame}] Player Pos: ({game.world.player.pos.x:.1f}, {game.world.player.pos.y:.1f}) | State: {game.world.state.value}")
        
        # Log events
        events = game.world.pop_events()
        for event in events:
            print(f"[Event] {event.upper()}")
            
        # Simulate simple behavior
        # Simple auto-jump
        jump_pressed = (frame % 300 == 0)
        
        # Update game
        keys = {} # Dummy key states
        game.world.update(keys, jump_pressed, False, False, 1/60.0)
        
    print("Simulation finished.")

if __name__ == "__main__":
    simulate_game()
