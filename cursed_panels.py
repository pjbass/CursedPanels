#!/usr/bin/env python3
# An attempt to make a small game like Tetris Attack using curses and Python

import curses, argparse, random, time

class PanelStack:
  """Class abstracting the stack of panels used in the game."""
  
  def __init__(self, rate, symbols, length, width, start_x, start_y):
    
    self.spd = rate
    self.symbols = symbols
    self.rng = random.Random()
    self.length = length
    self.width = width
    self.stack_win = curses.newwin(width, length, start_y, start_x)
    self.pause_diff = 0.0
    self.last_up = time.monotonic()
    self.build_initial_stack()
    
  def build_initial_stack(self):
    """Build the initial stack based on the symbols provided, the RNG,
    the lenght of the stack, and the width of the stack."""
    
    self.stack = []
    cutoff = 0.75 * self.length # Stop at 3/4 of the length so there are no panels beyond that.
    nsym = len(self.symbols)
    
    for l in range(self.length):
      
      self.stack.append([])
      for w in range(self.width):
        if l > 0:
          if self.stack[l - 1][w] == '' or l >= cutoff:
            self.stack[l].append('')
            continue
          else:
            
            # Try to prevent symbols being placed that would result in an
            # immediate match on either rows or columns.
            bad_row = True
            bad_col = True
            while bad_row or bad_col:
              sym = self.rng.randint(0, nsym)
              
              if sym == nsym: # Going to be blank, which is always OK.
                break
              
              if l > 1:
                if self.stack[l - 1][w] != self.symbols[sym] or self.stack[l - 2][w] != self.symbols[sym]:
                  bad_row = False
              else:
                bad_row = False
              
              if w > 1:
                if self.stack[l][w - 1] != self.symbols[sym] or self.stack[l][w - 2] != self.symbols[sym]:
                  bad_col = False
              else:
                bad_col = False
            
        else:
          sym = self.rng.randint(0, nsym)
        
        if sym == nsym:
          self.stack[l].append('') # Length will be considered an empty.
        else:
          self.stack[l].append(self.symbols[sym])
          
  def advance_stack(self):
    """Advances the stack by adding an additional line of symbols to the rear.
    Returns a Boolean representing whether the game is over or not."""
    
    row = []
    game_over = False
    for w in range(self.width):
      row.append(self.symbols[self.rng.randint(0, len(self.symbols) - 1)])
      
      # While prepping the new row, check if the new last row will have a symbol hit the top
      if self.stack[self.length - 2][w] != '':
        game_over = True
    
    del self.stack[self.length - 1]
    self.stack.insert(0, row)
    self.last_up = time.monotonic()
    
    return game_over

  def print_stack(self):
    """Print the stack line by line."""
    
    self.stack_win.clear()
    for idx, row in enumerate(self.stack):
      for idy, elem in enumerate(row):
        try:
          if elem != '':
            self.stack_win.addch(idy, idx, elem)
          elif idx == self.length - 1:
            self.stack_win.addch(idy, idx, '|')
        except curses.error:
          pass # This is apparently a spurious error caused by the cursor
               # being placed outside of the window when writing to the 
               # lower right corner of a window.
    
    self.stack_win.refresh()

  def advance_ready(self):
    """Determine if the stack should be advanced or not based on the 
    monotonic (float) time of the last advance and the current speed
    at which the stack should advance. Returns a Boolean."""
    
    if time.monotonic() - self.last_up >= 1.0/(0.5*self.spd):
      return True
    else:
      return False
  
  def update_stack(self):
    """Update the stack, if applicable. Returns a Boolean indicating whether or
    not the game is over."""
    
    game_over = False
    if self.advance_ready():
      game_over = self.advance_stack()
      self.print_stack()
    
    return game_over
  
  def pause(self):
    """Pause the stack's advance. This must be called along with 
    stopping calls to update_stack because advance_ready works using a
    monotonic clock that won't pause, so a diff between the current
    monotonic time and the last update needs to be recorded."""
    
    self.pause_diff = time.monotonic() - self.last_up
    
  def unpause(self):
    """Unpause the stack advance by setting the last time an advance occured
    to the current monotonic time minus the pause_diff. This prevents the stack
    from advancing immediately because the time between advances would have
    passed while the game was paused."""
    
    self.last_up = time.monotonic() - self.pause_diff
          

class CursedPanels:
  """Class abstracting the logic required to run a game."""
  
  def __init__(self, rate, symbols, length, width):
    """Initialize the various elements of the game. Sets up the various game
    windows, sets the speed of the game, the symbol set, and builds the initial
    stack."""
    
    self.score = 0
    self.base_spd = rate
    if length > curses.COLS:
      l = curses.COLS
    else:
      l = length
    
    if width > curses.LINES - 2:
      w = curses.LINES - 2 # To still have a place to display the score
    else:
      w = width
    
    stack_begin_x = int((curses.COLS - l)/2)
    stack_begin_y = int((curses.LINES - 2 - w)/2) + 2
    
    self.score_win = curses.newwin(2, 20, 0, 0)
    self.speed_win = curses.newwin(2, 20, 0, 20)
    self.status_win = curses.newwin(2, 20, 0, 40)
    
    self.stack = PanelStack(rate, symbols, l, w, stack_begin_x, stack_begin_y)
    
    # A set of variables to help determine if there was a change to something
    # and an update is needed.
    self.last_score = self.score
    self.last_spd = self.stack.spd
    
    self.mode = self.game
  
  def update_score(self):
    """Update the score window with the current score."""
    
    self.score_win.clear()
    self.score_win.addstr(f"Score\n{self.score}")
    self.score_win.refresh()
    self.last_score = self.score
    
  def update_speed(self):
    """Update the speed window with the current stack speed."""
    
    self.speed_win.clear()
    self.speed_win.addstr(f"Speed\n{self.stack.spd}")
    self.speed_win.refresh()
    self.last_spd = self.stack.spd
    
  def set_status(self, status=None):
    """Update the status window to display the given string. Pass None to clear
    the status window."""
    
    self.status_win.clear()
    if status:
      self.status_win.addstr(status)
    self.status_win.refresh()
  
  def game(self, stdscr):
    """Play the game during the event loop."""
    
    up_stack = self.stack.advance_ready()
    up_score = self.score != self.last_score
    up_spd = self.stack.spd != self.last_spd
    
    if any((up_stack, up_score, up_spd)):
      stdscr.refresh()
    
    if up_stack:
      game_over = self.stack.update_stack()
      
      if game_over:
        self.mode = self.game_over
      
    if up_score:
      self.update_score()
    
    if up_spd:
      self.update_speed()
    
    inp = stdscr.getch()
    if inp == ord('w'):
      time.sleep(10)
    elif inp == ord('s'):
      self.score += 1
    elif inp == ord('r'):
      self.stack.spd += 1
  
  def game_over(self, stdscr):
    """Game over mode"""
    stdscr.nodelay(False) # Make sure getch blocking.
    
    self.set_status("Game Over\nAgain (y/n)?")
    
    cont = True
    
    while cont:
      inp = stdscr.getch()
      if inp == ord('y'):
        cont = False
      elif inp == ord('n'):
        raise KeyboardInterrupt() # Since this is already handled for quitting by the main loop.
    
    stdscr.nodelay(True) # Don't want to block it anymore.
    self.reset(stdscr)
  
  def reset(self, stdscr):
    """Reset the game to play again."""
    
    self.score = 0
    self.stack.spd = self.base_spd
    self.stack.build_initial_stack()
    
    stdscr.refresh()
    self.update_score()
    self.update_speed()
    self.stack.print_stack()
    self.set_status()
    
    self.mode = self.game
  
  def game_loop(self, stdscr):
    """Run the game loop, including handling the game logic and any key events."""
    
    stdscr.clear()
    stdscr.nodelay(True) # Make sure getch is nonblocking.
    stdscr.keypad(True) # So special keys come as single keystrokes rather than sequences.
    
    stdscr.refresh()
    self.update_score()
    self.update_speed()
    self.stack.print_stack()
    
    try:
      while True:
        self.mode(stdscr)
    
    except KeyboardInterrupt:
      pass # This is the standard exit sequence, so nothing to do
    

def parse_opts():
  """Parses the options provided on the command line. Returns the parsed options."""
  
  parser = argparse.ArgumentParser(description='A cursed Panel de Pon clone')
  
  parser.add_argument('-r','--rate', metavar="RT", type=int, default=1,
                      help="Initial speed for the stack to advance at. Defaults to 1.")
  parser.add_argument('-s', '--symbols', metavar='SYM', type=str, nargs='+', default=['!','@','#','$','%'],
                      help="Set the symbols that make up the panels")
  parser.add_argument('-l', '--length', metavar='LEN', type=int, default=60,
                      help="Total length of the stack. Defaults to 60 characters.")
  parser.add_argument('-w', '--width', metavar="WDT", type=int, default=12,
                      help="Width of the stack. Defaults to 12 characters.")
  
  return parser.parse_args()      
      

def game(stdscr, opts):
  """Runs the game based on the options given"""
  
  state = CursedPanels(opts.rate, opts.symbols, opts.length, opts.width)
  state.game_loop(stdscr)

def main():
  """Main function for the program"""
  
  opts = parse_opts()
  
  curses.wrapper(game,opts)

if __name__ == "__main__":
  main()
