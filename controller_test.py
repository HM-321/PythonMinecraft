import sdl2
import sdl2.ext
import ctypes
import time

sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER)

n = sdl2.SDL_NumJoysticks()
print(f'Joysticks: {n}')

for i in range(n):
    name = sdl2.SDL_JoystickNameForIndex(i).decode()
    print(f'  {i}: {name}')

if n == 0:
    print('No joystick')
    sdl2.SDL_Quit()
    exit()

gc = sdl2.SDL_GameControllerOpen(0)
if gc:
    print(f'Opened as GameController')
else:
    joy = sdl2.SDL_JoystickOpen(0)
    print(f'Opened as Joystick')

event = sdl2.SDL_Event()
while True:
    while sdl2.SDL_PollEvent(ctypes.byref(event)):
        if event.type == sdl2.SDL_CONTROLLERBUTTONDOWN:
            print(f'Btn: {event.cbutton.button}')
        elif event.type == sdl2.SDL_CONTROLLERAXISMOTION:
            if abs(event.caxis.value) > 8000:
                print(f'Axis {event.caxis.axis}: {event.caxis.value}')
    time.sleep(0.01)