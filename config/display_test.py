#!/usr/bin/env python3
"""Enhanced display test with multiple visual elements - No Audio."""
import os
import sys
import time
import math
import sdl2
import sdl2.ext
import sdl2.sdlttf

def draw_text(renderer, text, x, y, size=32):
    """Draw text on the screen."""
    sdl2.sdlttf.TTF_Init()
    font = sdl2.sdlttf.TTF_OpenFont(b"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    
    # Create white text
    color = sdl2.SDL_Color(255, 255, 255, 255)
    text_surface = sdl2.sdlttf.TTF_RenderText_Solid(font, text.encode(), color)
    text_texture = sdl2.SDL_CreateTextureFromSurface(renderer, text_surface)
    
    # Get text dimensions
    text_rect = sdl2.SDL_Rect()
    text_rect.x = x
    text_rect.y = y
    text_rect.w = text_surface.contents.w
    text_rect.h = text_surface.contents.h
    
    # Render text
    sdl2.SDL_RenderCopy(renderer, text_texture, None, text_rect)
    
    # Clean up
    sdl2.SDL_FreeSurface(text_surface)
    sdl2.SDL_DestroyTexture(text_texture)
    sdl2.sdlttf.TTF_CloseFont(font)
    sdl2.sdlttf.TTF_Quit()

def test_display():
    # Initialize SDL2 with VIDEO only, explicitly disable audio
    sdl2.SDL_SetHint(b"SDL_AUDIODRIVER", b"dummy")
    sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)
    
    # Create fullscreen window
    window = sdl2.SDL_CreateWindow(b"Enhanced Display Test",
                                 sdl2.SDL_WINDOWPOS_CENTERED,
                                 sdl2.SDL_WINDOWPOS_CENTERED,
                                 1280, 720,
                                 sdl2.SDL_WINDOW_SHOWN | sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP)
    
    if not window:
        print(f"Error creating window: {sdl2.SDL_GetError()}")
        return

    renderer = sdl2.SDL_CreateRenderer(window, -1, 
                                     sdl2.SDL_RENDERER_ACCELERATED | 
                                     sdl2.SDL_RENDERER_PRESENTVSYNC)
    
    if not renderer:
        print(f"Error creating renderer: {sdl2.SDL_GetError()}")
        sdl2.SDL_DestroyWindow(window)
        return

    try:
        running = True
        demo_state = 0
        last_update = time.time()
        
        while running:
            # Handle events
            events = sdl2.ext.get_events()
            for event in events:
                if event.type == sdl2.SDL_QUIT:
                    running = False
                    break
                elif event.type == sdl2.SDL_KEYDOWN:
                    if event.key.keysym.sym == sdl2.SDLK_q:
                        running = False
                        break
            
            current_time = time.time()
            if current_time - last_update >= 3.0:  # Change display every 3 seconds
                demo_state = (demo_state + 1) % 4
                last_update = current_time
                
                # Clear screen
                sdl2.SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255)
                sdl2.SDL_RenderClear(renderer)
                
                if demo_state == 0:
                    # Draw text
                    draw_text(renderer, "Welcome to Display Test!", 400, 300, 48)
                    
                elif demo_state == 1:
                    # Draw rectangles
                    sdl2.SDL_SetRenderDrawColor(renderer, 255, 0, 0, 255)
                    rect1 = sdl2.SDL_Rect(100, 100, 200, 150)
                    sdl2.SDL_RenderFillRect(renderer, rect1)
                    
                    sdl2.SDL_SetRenderDrawColor(renderer, 0, 255, 0, 255)
                    rect2 = sdl2.SDL_Rect(400, 100, 200, 150)
                    sdl2.SDL_RenderFillRect(renderer, rect2)
                    
                elif demo_state == 2:
                    # Draw circle (approximated with lines)
                    sdl2.SDL_SetRenderDrawColor(renderer, 0, 0, 255, 255)
                    center_x, center_y = 640, 360
                    radius = 100
                    for i in range(360):
                        angle = i * math.pi / 180
                        x = int(center_x + radius * math.cos(angle))
                        y = int(center_y + radius * math.sin(angle))
                        sdl2.SDL_RenderDrawPoint(renderer, x, y)
                        
                else:
                    # Draw pattern
                    for i in range(0, 1280, 40):
                        sdl2.SDL_SetRenderDrawColor(renderer, 
                                                  (i * 255) // 1280,
                                                  255 - ((i * 255) // 1280),
                                                  128,
                                                  255)
                        line_rect = sdl2.SDL_Rect(i, 0, 20, 720)
                        sdl2.SDL_RenderFillRect(renderer, line_rect)
                
                # Update screen
                sdl2.SDL_RenderPresent(renderer)
            
            # Small delay to prevent using too much CPU
            sdl2.SDL_Delay(16)
            
    finally:
        sdl2.SDL_DestroyRenderer(renderer)
        sdl2.SDL_DestroyWindow(window)
        sdl2.SDL_Quit()

if __name__ == "__main__":
    test_display()