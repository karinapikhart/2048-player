# I've wanted for a long time to make a script that solves a fairly algorithmic
# puzzle, hopefully better than I can
# that way, i dont have to waste time solving the puzzles
# and i come out of it with a defined algorithm for the right/best/good
# way to solve, instead of having to rethink the algorithm
# every time i do the puzzle
# using my new selenium skills, i realized 2048 may be a good fit!

# wins were that i quickly implemented a tracer bullet
# first just learning how to slide pieces around without paying any attention to optimized choice
# then implementing some preference for move choice
# doing good quick testing of mini pieces of code in the python console instead of having to rerun a big script every time, as it grew
# then working on some algorithmic improvements
# then trying to get smarter about logging and data visualization to give more insights and speed up algorithm design

# TODO - store score values and plot them, versus move number
# TODO - implement machine learning!

#####################
## IMPORT PACKAGES ##
#####################

import sys
import requests
from lxml import etree, html
import getpass
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import selenium.common.exceptions
import random
import math
import pprint
import numpy
import csv


####################
## DEFINE GLOBALS ##
####################

WEBSITE = 'https://gabrielecirulli.github.io/2048/'
GRID_SIZE = 4
MOVES = ['DOWN', 'UP', 'LEFT', 'RIGHT']
ALGORITHM = 4
AUTO_PLAY = True
LOG_FILE_NAME = '2048-MoveLog-' + time.strftime('%Y%m%d-%H%M%S') + '.csv'
LOG_FILE_PATH = '/tmp/' + LOG_FILE_NAME
LOG_HEADER = ['move_num'
    , 'move'
    , 'is_selected_move'
    , 'total_score'
    , 'emptiness_score'
    , 'x_com_score'
    , 'y_com_score'
    , 'combine_biggies_score'
    , 'best_future_score'
    , 'current_board'
    , 'resulting_board']

######################
## DEFINE FUNCTIONS ##
######################

def launch_website(browser):
    print 'Opening page: ' + WEBSITE
    browser.get(WEBSITE)
    return

def observe_board(browser):
    board_state = {}
    elems = browser.find_elements_by_css_selector('div.tile')
    for elem in elems:
        data = elem.get_attribute('class').split(' ')
        value = data[1].split('-')[1]
        position = data[2].split('position-')[1]
        board_state[position] = value
    return board_state

def get_board_matrix(board_state):
    board_matrix = numpy.array([[0]*GRID_SIZE,[0]*GRID_SIZE,[0]*GRID_SIZE,[0]*GRID_SIZE])

    for position in board_state.keys():
        y = int(position.split('-')[0]) - 1
        x = int(position.split('-')[1]) - 1
        value = board_state[position]
        board_matrix[x, y] = value

    return board_matrix

def choose_move(board, last_board, last_move, algo_num, move_num):

    # zeroeth algorithm: always choose 'DOWN'
    if algo_num == 0:
        selected_move = 'DOWN'

    # first algorithm: totally random
    # scores: 1492, 452, 836, 316
    if algo_num == 1:
        moves = ['DOWN', 'UP', 'LEFT', 'RIGHT']
        selected_move = random.choice(moves)

    # second algorithm: always choose up first, left next, right next, down last
    # scores: 1892, 3488, 2804, 3452
    # subject feedback: looks a lot like me playing when i watch it! cool!
    # but can't seem to get to 2048. needs to be smarter!
    elif algo_num == 2:
        ordered_move_preference = ['UP', 'LEFT', 'RIGHT', 'DOWN']
        if not numpy.array_equal(last_board, board):
            selected_move = ordered_move_preference[0]
        else:
            last_index = ordered_move_preference.index(last_move)
            selected_move = ordered_move_preference[last_index + 1]

    # third algorithm: weight the choices, and then choose weighted random
    # scores: 808
    # not as good as algo 2!
    elif algo_num == 3:
        weights = {'DOWN': 10
                   , 'LEFT': 8
                   , 'RIGHT': 6
                   , 'UP' : 1}

        move_choices = []
        for move in weights.keys():
            for i in range(weights[move]):
                move_choices.append(move)

        selected_move = random.choice(move_choices)

    # try to make this as much like my personal algorithm when I play as possible
    # configs: 1, 1
    # scores: 5672, 4136, 3416, 3968
    # configs: 1, 10, 0, 1
    # scores: 11144, 3124, 3620, 3900
    # max tile: 1024!!
    elif algo_num == 4:
        best_score = -10000000 # TODO - may need to fix this... a little hacky, but i saw it done at kiva. otherwise we may hit the selected_move = None issue!
        selected_move = None
        moves_to_log = []
        for move in MOVES:
            #print 'evaluating', move
            potential_new_board = get_potential_new_board(move, board)

            # if the move doesn't do anything, skip it
            if numpy.array_equal(board, potential_new_board):
                #print 'move has no effect. skipping scoring.'
                continue

            #print potential_new_board
            move_score, log_data = score_board(potential_new_board)
            if move_score > best_score:
                selected_move = move
                best_score = move_score

            log_data['move_num'] = move_num
            log_data['current_board'] = board
            log_data['move'] = move
            log_data['resulting_board'] = potential_new_board
            moves_to_log.append(log_data)

        for entry in moves_to_log:
            if entry['move'] == selected_move:
                entry['is_selected_move'] = 1
            else:
                entry['is_selected_move'] = 0

            log(entry)

    return selected_move

def log(evaluated_move_details):
    log_entry = []
    for item in LOG_HEADER:
        log_entry.append(evaluated_move_details[item])

    with open(LOG_FILE_PATH, 'ab') as csvfile:
        f = csv.writer(csvfile)
        f.writerow(log_entry)

    return

# give the potential move a score. bigger score is better!
# current observations are that we are letting the anchor slip away, and aren't opportunistically combining big guys
# TODO - need to normalize these scores so that they are tunable in some sensible way
# need to make the scoring nonlinear for some of the components -- e.g. emptiness should get prioritized as real estate runs low
def score_board(board):

    # configurations!
    empty_space_weight = 1
    x_com_weight = 300
    y_com_weight = 100
    #anchor_row_protection_weight = 1 # TODO - unused
    #risk_of_wedging_weight = 1
    #next_moves_weight = 1
    combine_big_numbers_bonus = 1.2
    best_future_score_weight = 1

    # TRY TO KEEP THE BOARD EMPTY!
    empty_score = empty_space_weight * get_num_empties(board)

    # TRY TO KEEP THE NUMBERS ORGANIZED!
    x, y = get_center_of_mass(board)
    x_com_score = 1/x * x_com_weight
    y_com_score = 1/y * y_com_weight

    # TRY TO REDUCE THE NUMBER OF DUPLICATE NUMBERS, ESPECIALLY BIG NUMBERS!
    #unique = numpy.unique(board)
    combine_biggies_score = get_combine_big_numbers_score(board, combine_big_numbers_bonus)

    # PLAN AHEAD
    # score all options 3 layers down = 4 ^ 3 options = 64 options (without adding tiles)
    best_future_score = 0
    for move_1 in MOVES:
        for move_2 in MOVES:
            for move_3 in MOVES:
                future_board = get_potential_new_board(move_3, get_potential_new_board(move_2, get_potential_new_board(move_1, board)))
                future_score = 0
                # TODO - remove code duplication from in here. this function is a little recursive
                future_score += empty_space_weight * get_num_empties(future_board)
                x, y = get_center_of_mass(board)
                future_score += 1/x * x_com_weight
                future_score += 1/y * y_com_weight
                future_score += get_combine_big_numbers_score(board, combine_big_numbers_bonus)

                if future_score > best_future_score:
                    best_future_score = future_score
    best_future_score *= best_future_score_weight

    score_components = {
        'emptiness_score': empty_score
        , 'x_com_score': x_com_score
        , 'y_com_score': y_com_score
        , 'combine_biggies_score': combine_biggies_score
        , 'best_future_score': best_future_score
                        }

    score = 0
    for component in score_components.keys():
        score += score_components[component]

    score_components['total_score'] = score

    return score, score_components

def get_combine_big_numbers_score(board, bonus):
    score = 0
    for row in board:
        for element in row:
            score += element ** bonus
    return score

def get_num_empties(board):
    return GRID_SIZE * GRID_SIZE - numpy.count_nonzero(board)

def get_center_of_mass(board):
    x_weights = []
    y_weights = []
    for i in range(GRID_SIZE):
        x_weight = sum(board.transpose()[i])
        y_weight = sum(board[i])
        x_weights = x_weights + ([i+1] * x_weight)
        y_weights = y_weights + ([i+1] * y_weight)
    x_center_of_mass = numpy.mean(x_weights)
    y_center_of_mass = numpy.mean(y_weights)
    return x_center_of_mass, y_center_of_mass

def get_potential_new_board(potential_move, current_board):
    if potential_move in ('UP', 'DOWN'):
        current_board = current_board.transpose()

    new_rows = []
    for row in current_board:
        smooshed_row = []
        if potential_move in ('LEFT', 'UP'):
            smooshed_row = smoosh_row(row, 'left')
        elif potential_move in ('RIGHT', 'DOWN'):
            smooshed_row = smoosh_row(row, 'right')
        new_rows.append(smooshed_row)
    new_board = numpy.array(new_rows)

    # convert columns back to vertical
    if potential_move in ('UP', 'DOWN'):
        new_board = new_board.transpose()

    return new_board

def compress_row(row):
    compressed_lane = []
    for i in row:
        if i != 0:
            compressed_lane.append(i)
    return compressed_lane

# imagine these rows when considering smooshing - function looks good with manual testing!
# [_, _, _, _]
# [2, _, _, _]
# [2, 4, _, _]
# [2, 2, _, _]
# [2, 2, 2, _]
# [2, 2, 2, 2]
# [2, 2, 4, _]
# [2, 4, 2, _]
# [4, 2, 2, _]
# [4, 2, 2, 2]
def smoosh_row(row, direction):

    if direction == 'left':
        compressed_row = compress_row(row)
    elif direction == 'right':
        compressed_row = list(reversed(compress_row(row)))
    else:
        print 'oops. issue'
        sys.exit()

    smooshed_row = []
    i = 0
    while i <= len(compressed_row) - 1:
        # if you're on the last item,
        # it won't have a matching neighbor to smoosh with, so append it
        if i + 1 == len(compressed_row):
            smooshed_row.append(int(compressed_row[i]))
        # otherwise, if you find a matching neighbor, smoosh and skip
        elif compressed_row[i] == compressed_row[i+1]:
            smooshed_row.append(2 * int(compressed_row[i]))
            i += 1
        # otherwise, if the neighbor doesn't match, just append
        else:
            smooshed_row.append(int(compressed_row[i]))
        i += 1

    while len(smooshed_row) < GRID_SIZE:
        smooshed_row.append(0)

    if direction == 'left':
        return smooshed_row
    elif direction == 'right':
        return list(reversed(smooshed_row))
    else:
        print 'oops. issue'
        sys.exit()

def play(browser, move):
    # got stuck here with a WebDriverException - "cannot focus element" - using xpath fixed it, not sure why
    #elem = browser.find_element_by_class_name('grid-container')
    #elem = browser.find_element_by_class_name('heading')
    elem = browser.find_element_by_xpath('/html')
    #elem.send_keys(move)

    if move == 'DOWN':
        elem.send_keys(Keys.ARROW_DOWN)
    elif move == 'UP':
        elem.send_keys(Keys.ARROW_UP)
    elif move == 'LEFT':
        elem.send_keys(Keys.ARROW_LEFT)
    elif move == 'RIGHT':
        elem.send_keys(Keys.ARROW_RIGHT)
    else:
        print 'oops. something went wrong'
        sys.exit()

    return

def is_game_over(browser):
    try:
        browser.find_element_by_class_name('game-message game-over')
        return True
    except:
        return False

##########
## MAIN ##
##########

# launch the website
browser = webdriver.Chrome()
launch_website(browser)

# start a log file for moves chosen
if ALGORITHM == 4:
    with open(LOG_FILE_PATH, 'wb') as csvfile:
        f = csv.writer(csvfile)
        f.writerow(LOG_HEADER)

move_num = 1
game_over = False
last_board_matrix = numpy.array([])
last_move = 'DOWN'
while not game_over:

    # observe the board
    try:
        board_state = observe_board(browser)
    except:
        print 'too speedy? failed to get board state. try again'
        continue

    # convert board to a matrix
    board_matrix = get_board_matrix(board_state)
    print board_matrix

    # choose what move to make next
    selected_move = choose_move(board_matrix, last_board_matrix, last_move, ALGORITHM, move_num)
    print 'move chosen: ' + selected_move

    # wait for player to confirm
    if not AUTO_PLAY:
        ready = raw_input('ready to make move?')

    # make move
    play(browser, selected_move)

    # check if game is over
    # TODO - this is not working, need to come back to this because it never ends
    game_over = is_game_over(browser)

    # store last moves for next time
    last_board_matrix = board_matrix
    last_move = selected_move

    move_num += 1


# TODO
# graph the scores! visualize and learn!
# then, make a movie of the moves to see what worked/didnt to play alongside the graph?
# plot_game_stats()