#!/usr/bin/env python3
# An attempt to make a small game like Tetris Attack using curses and Python

import curses, argparse, random, time, math

# Key to press to pause the game.
PAUSE = "p"

# Key to press to select a panel.
SELECT = "s"

# Constant representing directions on how to play the game that can be
# displayed in a window in-game.
DIRECTIONS = "Move(arrows), Select({})\nPause({})".format(SELECT, PAUSE)

# Directions to display when select mode is on.
SELECT_ON = DIRECTIONS + ", Select ON"

# Constant text to show that the game is paused and how to unpause.
PAUSE_TEXT = "Paused\nUnpause = {}".format(PAUSE)

# Number of adjacent symbols of the same type required to make a match
# (i.e. %%% or &&& for a MIN_MATCH of 2).
MIN_MATCH = 2

# Maximum height (as a fraction of the total height) that the stack is
# allowed to be at the start of the game.
MAX_INIT_HEIGHT = 0.75

# Base number of panels that, when raised to SPEED_UP_EXP, determines when
# the speed will increase.
BASE_PANEL_THRESH = 6

# Exponent used to raise the BASE_PANEL_THRESH * speed to in order to determine
# the total number of panels that need to be cleared in order to increase the
# speed.
SPEED_UP_EXP = 1.5

# The number of seconds that the stack takes to advance at speed = 1
BASE_ADV_SPEED = 5.0

# Exponent to raise the number of panels eliminated at one time to in order
# to calculate the score.
ELIM_SCORE_EXP = 2

# Multiplier used to increase the score of chain eliminations caused by
# previous eliminations.
CHAIN_MULT = 1.5

# Default symbol set used by the game.
DEFAULT_SYMBOLS = ('!','@','#','$','%')

# Default length for a new game.
DEFAULT_LENGTH = 60

# Default width for a new game.
DEFAULT_WIDTH = 12

# Default starting speed for a new game.
DEFAULT_SPEED = 1

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

    # Stop before reaching the top of the window.
    cutoff = MAX_INIT_HEIGHT * self.length

    # Get the number of symbols. This number is also used as a value unto itself
    # to signify an empty space.
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
              
              if l >= MIN_MATCH:
                matches = [self.stack[x][w] for x in range(l - MIN_MATCH, l) if self.stack[x][w] == self.symbols[sym]]
                if len(matches) < MIN_MATCH:
                  bad_row = False
              else:
                bad_row = False
              
              if w >= MIN_MATCH:
                matches = [self.stack[l][y] for y in range(w - MIN_MATCH, w) if self.stack[l][y] == self.symbols[sym]]
                if len(matches) < MIN_MATCH:
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
    """Advances the stack by adding an additional line of symbols to the rear."""
    
    row = []
    for w in range(self.width):
      sym = self.symbols[self.rng.randint(0, len(self.symbols) - 1)]

      # Ensure that there are not inter-row matches.
      if w >= MIN_MATCH:
        bad_sym = True
        while bad_sym:
          matches = [row[y] for y in range(w - MIN_MATCH, w) if row[y] == sym]
          if len(matches) >= MIN_MATCH:
            sym = self.symbols[self.rng.randint(0, len(self.symbols) - 1)]
          else:
            bad_sym = False

      row.append(sym)
    
    del self.stack[self.length - 1]
    self.stack.insert(0, row)
    self.last_up = time.monotonic()

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

  def game_over(self):
    """Check the last column of the stack to see if it has hit the end of the
    screen, thus causing a game over."""

    game_over = False
    for idy in range(self.width):
      if self.stack[self.length - 1][idy] != '':
        game_over = True
        break

    return game_over

  def advance_ready(self):
    """Determine if the stack should be advanced or not based on the 
    monotonic (float) time of the last advance and the current speed
    at which the stack should advance. Returns a Boolean."""
    
    if time.monotonic() - self.last_up >= BASE_ADV_SPEED/math.log2(self.spd + 1):
      return True
    else:
      return False
  
  def swap_panel(self, old_x, old_y, new_x, new_y):
    """Move a panel from its location at old_x, old_y to the new location at
    new_x, new_y. Any existing panel at this location will be moved to the old
    location. Triggers a check_stack to see if the move eliminates any characters,
    and returns the results of the check."""

    old = self.stack[old_x][old_y]
    self.stack[old_x][old_y] = self.stack[new_x][new_y]
    self.stack[new_x][new_y] = old

    return self.check_stack()

  def update_stack(self):
    """Update the stack, if applicable. Returns a Boolean indicating whether or
    not the game is over."""
    
    game_over = False
    if self.advance_ready():
      self.advance_stack()
      (elims, score) = self.check_stack()
      game_over = self.game_over()
      self.print_stack()
    
    return (elims, score, game_over)
  
  def compact(self):
    """Compact the stack by making all pieces with a space below them fall into
    the lowest possible spot. Returns a Boolean representing whether the stack
    was compacted at all or not."""

    compacted = False
    for idx in range(1, self.length):
      for idy, elem in enumerate(self.stack[idx]):
        if elem != '':
          # Check all spaces below the current element. If there are any, drop
          # it to the lowest empty space reachable.
          down = idx - 1
          while down >= 0 and self.stack[down][idy] == '':
            self.stack[down][idy] = elem
            self.stack[down + 1][idy] = ''
            compacted = True
            down -= 1
    return compacted

  def check_stack(self):
    """Check the stack to determine if any panels need to be removed or have
    their locations updated. Returns the number of panels eliminated and the
    score received for said eliminations."""

    marked = set()

    for idx, row in enumerate(self.stack):
      for idy, elem in enumerate(row):
        same_down = 0
        same_right = 0
        if elem == '':
          continue # Nothing to do with an empty.
        if idx < self.length - MIN_MATCH:
          right = idx + 1
          while right < self.length and self.stack[right][idy] == elem:
            same_right += 1
            right += 1
        if idy < self.width - MIN_MATCH:
          down = idy + 1
          while down < self.width and self.stack[idx][down] == elem:
            same_down += 1
            down += 1

        if same_down >= MIN_MATCH or same_right >= MIN_MATCH:
          # Eliminate one for the element. It could have some above or below
          # that need to be accounted for.
          marked.add((idx, idy))

          if same_down >= MIN_MATCH:
            # Offset in the range since 0 is the main element at idx, idy.
            for y in range(1, same_down + 1):
              marked.add((idx, idy + y))
          if same_right >= MIN_MATCH:
            for x in range(1, same_right + 1):
              marked.add((idx + x, idy))

    elim = len(marked)
    for idx, idy in marked:
      self.stack[idx][idy] = ''

    compacted = self.compact()

    comp_elims = 0
    comp_score = 0
    # Check for new eliminations that can result from a compaction.
    if compacted:
      comp_elims, comp_score = self.check_stack()

    # Eliminations are just the total panels eliminated, no extras needed to
    # calculate.
    total_elims = elim + comp_elims

    # Score is calculated as the square of eliminations, plus the double of
    # the compaction score so that eliminating more panels in a chain yields
    # a higher score.
    if elim > 0:
      total_score = round(elim**ELIM_SCORE_EXP + CHAIN_MULT * comp_score)
    # If no eliminations were made this time, then a panel may have been moved
    # into an empty space rather potentially starting a chain.
    else:
      total_score = comp_score

    return (total_elims, total_score)

  def pause(self):
    """Pause the stack's advance. This must be called along with 
    stopping calls to update_stack because advance_ready works using a
    monotonic clock that won't pause, so a diff between the current
    monotonic time and the last update needs to be recorded."""
    
    self.pause_diff = time.monotonic() - self.last_up

    # Clears the screen so the player can't pause to figure out their next move.
    self.stack_win.clear()
    self.stack_win.refresh()
    
  def unpause(self):
    """Unpause the stack advance by setting the last time an advance occured
    to the current monotonic time minus the pause_diff. This prevents the stack
    from advancing immediately because the time between advances would have
    passed while the game was paused."""
    
    self.last_up = time.monotonic() - self.pause_diff
    self.print_stack()

class CursedCursor:
  """Class abstracting cursor handling."""

  def __init__(self, offset_x, offset_y, max_x, max_y):
    self.px = 0
    self.py = 0
    self.offset_x = offset_x
    self.offset_y = offset_y

    self.max_x = max_x
    self.max_y = max_y

    self.refresh = True
    self.select = False

  def move(self, dx, dy):
    """Move the cursor by the increment dx, dy within the limits provided in
    lim_x, lim_y. Sets the refresh flag to true. Returns whether the cursor
    will move."""

    new_x = self.px + dx
    new_y = self.py + dy
    if new_x >= self.max_x:
      new_x = self.max_x - 1
    elif new_x < 0:
      new_x = 0

    if new_y >= self.max_y:
      new_y = self.max_y - 1
    elif new_y < 0:
      new_y = 0

    moved = self.px != new_x or self.py != new_y
    self.px = new_x
    self.py = new_y

    self.refresh = True

    return moved

  def render(self, win):
    """Render the cursor in the given window. Resets the refresh flag to False."""

    if self.select:
      curses.curs_set(2)
    else:
      curses.curs_set(1)
    win.move(self.py + self.offset_y, self.px + self.offset_x)
    self.refresh = False

class CursedPanels:
  """Class abstracting the logic required to run a game."""
  
  def __init__(self, rate, symbols, length, width):
    """Initialize the various elements of the game. Sets up the various game
    windows, sets the speed of the game, the symbol set, and builds the initial
    stack."""
    
    self.score = 0
    self.panels = 0
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

    self.cursor = CursedCursor(stack_begin_x, stack_begin_y, l, w)
    
    self.score_win = curses.newwin(2, 25, 0, 0)
    self.speed_win = curses.newwin(2, 25, 0, 25)
    self.status_win = curses.newwin(2, 25, 0, 50)
    
    self.stack = PanelStack(rate, symbols, l, w, stack_begin_x, stack_begin_y)
    
    # A set of variables to help determine if there was a change to something
    # and an update is needed.
    self.last_score = self.score
    self.last_spd = self.stack.spd
    
    self.mode = self.game
  
  def update_score(self):
    """Update the score window with the current score."""
    
    self.score_win.clear()
    self.score_win.addstr("Score\n{}".format(self.score))
    self.score_win.refresh()
    self.last_score = self.score
    
  def update_speed(self):
    """Update the speed window with the current stack speed."""
    
    self.speed_win.clear()
    self.speed_win.addstr("Speed\n{}".format(self.stack.spd))
    self.speed_win.refresh()
    self.last_spd = self.stack.spd
    
  def set_status(self, status=None):
    """Update the status window to display the given string. Pass None to display
    the game instructions."""
    
    self.status_win.clear()
    if status:
      self.status_win.addstr(status)
    else:
      self.status_win.addstr(DIRECTIONS)
    self.status_win.refresh()
  
  def game(self, stdscr):
    """Play the game during the event loop."""
    
    up_stack = self.stack.advance_ready()
    up_score = self.score != self.last_score
    up_spd = self.stack.spd != self.last_spd
    elims = 0

    moved = False
    old_cursor = (self.cursor.px, self.cursor.py)
    inp = stdscr.getch()
    if inp == ord(PAUSE):
      self.mode = self.pause
    elif inp == ord(SELECT):
      self.cursor.select = not self.cursor.select
      if self.cursor.select:
        self.set_status(SELECT_ON)
      else:
        self.set_status()
    elif inp == curses.KEY_LEFT:
      moved = self.cursor.move(-1, 0)
    elif inp == curses.KEY_RIGHT:
      moved = self.cursor.move(1, 0)
    elif inp == curses.KEY_UP:
      moved = self.cursor.move(0, -1)
    elif inp == curses.KEY_DOWN:
      moved = self.cursor.move(0, 1)

    if self.cursor.select and moved:
      (elims, score) =self.stack.swap_panel(
        old_cursor[0],
        old_cursor[1],
        self.cursor.px,
        self.cursor.py
      )
      self.stack.print_stack()
      self.panels += elims
      self.score += score

    if any((up_stack, up_score, up_spd, self.cursor.refresh)):
      stdscr.refresh()
    
    self.cursor.render(stdscr)
    if up_stack:
      (elims, score, game_over) = self.stack.update_stack()
      
      # Make the cursor follow the stack upward
      self.cursor.move(1, 0)

      if game_over:
        self.mode = self.game_over

      self.score += score
      
    if up_score:
      self.update_score()
    
    if up_spd:
      self.update_speed()
    
    self.panels += elims

    if self.panels > (self.stack.spd * BASE_PANEL_THRESH)**SPEED_UP_EXP:
      self.stack.spd += 1
  
  def pause(self, stdscr):
    """Pause the game."""

    stdscr.nodelay(False) # Make getch block

    self.stack.pause()

    self.set_status(PAUSE_TEXT)

    while True:
      inp = stdscr.getch()
      if inp == ord(PAUSE):
        break

    stdscr.nodelay(True)
    self.mode = self.game
    self.set_status()
    self.stack.unpause()


  def game_over(self, stdscr):
    """Game over mode."""
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
    self.set_status()
    self.stack.print_stack()
    
    try:
      while True:
        self.mode(stdscr)
    
    except KeyboardInterrupt:
      pass # This is the standard exit sequence, so nothing to do
    

def parse_opts():
  """Parses the options provided on the command line. Returns the parsed options."""
  
  parser = argparse.ArgumentParser(description='A cursed Panel de Pon clone')
  
  parser.add_argument('-r','--rate', metavar="RT", type=int, default=DEFAULT_SPEED,
                      help="Initial speed for the stack to advance at. Defaults to {}.".format(DEFAULT_SPEED))
  parser.add_argument('-s', '--symbols', metavar='SYM', type=str, nargs='+', default=DEFAULT_SYMBOLS,
                      help="Set the symbols that make up the panels")
  parser.add_argument('-l', '--length', metavar='LEN', type=int, default=DEFAULT_LENGTH,
                      help="Total length of the stack. Defaults to {} characters.".format(DEFAULT_LENGTH))
  parser.add_argument('-w', '--width', metavar="WDT", type=int, default=DEFAULT_WIDTH,
                      help="Width of the stack. Defaults to {} characters.".format(DEFAULT_WIDTH))
  
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
