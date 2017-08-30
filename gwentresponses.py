# coding=UTF-8

"""Main module of the gwent 2 subreddit Heroes Responses Bot.

The main body of the script is running in this file. The comments are loaded from the subreddit
and the script checks if the comment is a response from gwent 2. If it is, a proper comment is
prepared. The comment is posted as a reply to the original post on Reddit.

Proper logging is provided - saved to 2 files as standard output and errors.
"""

import traceback
import os
from datetime import datetime, date
import sqlite3
import logging
from logging.handlers import TimedRotatingFileHandler
import prawcore
import gwent_responses_account as account
import gwent_responses_properties as properties
from responses_wiki import gwent_wiki_parser as parser

__author__ = 'Jonarzz'


SCRIPT_DIR = os.path.dirname(__file__)

RESPONSES_DB_CONN = sqlite3.connect(os.path.join(SCRIPT_DIR, 'responses.db'))
RESPONSES_DB_CURSOR = RESPONSES_DB_CONN.cursor()
COMMENTS_DB_CONN = sqlite3.connect(os.path.join(SCRIPT_DIR, 'comments.db'), detect_types=sqlite3.PARSE_DECLTYPES)
COMMENTS_DB_CURSOR = COMMENTS_DB_CONN.cursor()

logger = logging.getLogger("Rotating Log")
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler(properties.LOG_FILENAME,
                                   when='H',
                                   interval=12,
                                   backupCount=5)
logger.addHandler(handler)


def add_flair_specific_response(comment, heroes_dict, response):
    """ Will probably never use this crap, but in case /r/Gwent ends up goin that route I'll leave it."""
    RESPONSES_DB_CURSOR.execute("SELECT id, img_dir FROM heroes WHERE css=?", [comment.author_flair_css_class])
    hero_id_img = RESPONSES_DB_CURSOR.fetchone()
    if hero_id_img:
        RESPONSES_DB_CURSOR.execute("SELECT link FROM responses WHERE response=? AND hero_id=?", [response, hero_id_img[0]])
        link = RESPONSES_DB_CURSOR.fetchone()
        if link:
            comment.reply(create_reply(link[0], heroes_dict, comment.body, hero_id_img[1]))
            save_comment_id(comment.id, do_log=True)
            return True


def add_shitty_wizard_response(comment, heroes_dict, response):
    """ Leftover function from the dota bot, but I honestly have no clue what it does."""
    RESPONSES_DB_CURSOR.execute("SELECT link, hero_id FROM responses WHERE response=? AND hero IS NOT NULL ORDER BY RANDOM() LIMIT 1;", [response])
    link_and_hero_id = RESPONSES_DB_CURSOR.fetchone()
    RESPONSES_DB_CURSOR.execute("SELECT img_dir FROM heroes WHERE id=?", [link_and_hero_id[1]])
    img_dir = RESPONSES_DB_CURSOR.fetchone()[0]
    comment.reply(create_reply(link_and_hero_id[0], heroes_dict, comment.body, img_dir))
    save_comment_id(comment.id, do_log=True)


def add_regular_response(comment, heroes_dict, response):
    """ Function that adds responses before adding them to comments."""
    #RESPONSES_DB_CURSOR.execute("SELECT link, hero_id FROM responses WHERE response=? AND hero IS NOT NULL ORDER BY hero_id DESC, RANDOM() LIMIT 1", [response])
    RESPONSES_DB_CURSOR.execute("SELECT link, hero FROM responses WHERE stripped=? AND hero IS NOT NULL ORDER BY hero_id DESC, RANDOM() LIMIT 1", [response])
    link_and_hero_id = RESPONSES_DB_CURSOR.fetchone()
    if link_and_hero_id:
        #RESPONSES_DB_CURSOR.execute("SELECT img_dir FROM heroes WHERE id=?", [link_and_hero_id[1]])
        #img_dir = RESPONSES_DB_CURSOR.fetchone()
        #if img_dir:
        #    comment.reply(create_reply(link_and_hero_id[0], heroes_dict, comment.body, img=img_dir[0]))
        #    log("Added: " + comment.id)
        #else:
        #    comment.reply(create_reply(link_and_hero_id[0], heroes_dict, comment.body))
        #    log("Added: " + comment.id)
        comment.reply(create_reply(link_and_hero_id[0], heroes_dict, comment.body))
        log("Added: " + comment.id)


def prepare_specific_responses():
    """ Not really used"""
    output_dict = {}
    output_dict["shitty wizard"] = add_shitty_wizard_response
    return output_dict


SPECIFIC_RESPONSES_DICT = prepare_specific_responses()


def execute():
    """Main method executing the script.

    It connects to an account, loads dictionaries from proper files (declared in properties file).
    Afterwards it executes add_comments method with proper arguments passed.
    """
    reddit_account = account.get_account()

    #try:
        #sticky = reddit_account.subreddit(properties.SUBREDDIT).sticky()
    # Apparently this doesn't work, the prawcore
    #except prawcore.exceptions.NotFound:
    #    sticky = None
    sticky = None
    #log('START')

    for submission in reddit_account.subreddit(properties.SUBREDDIT).new(limit=150):
        add_comments_to_submission(submission, sticky)

    for submission in reddit_account.subreddit(properties.SUBREDDIT).hot(limit=35):
        add_comments_to_submission(submission, sticky)


def add_comments_to_submission(submission, sticky):
    """Method that adds the bot replies to the comments in the given submission."""
    if submission == sticky:
        return

    heroes_dict = parser.dictionary_from_file(properties.HEROES_FILENAME)

    add_comments(submission, heroes_dict)


def add_message_to_file(message, filename):
    """Method that appends given string message to a file with provided filename."""
    with open(filename, 'a') as file:
        file.write(str(datetime.now()) + '\n' + message + '\n')


#def log(message, error=False):
def log(message):
    """ new logger with log rotating."""
    #logger = logging.getLogger("Rotating Log")
    #logger.setLevel(logging.INFO)

    #handler = TimedRotatingFileHandler(properties.LOG_FILENAME,
                                       #when='M',
                                       #interval=5,
                                       #backupCount=5)
    #logger.addHandler(handler)
    logger.info(str(datetime.now()) + '\n' + message + '\n')
    #handler.stream.close()


#def log(message, error=False):
    #"""Method used to save messages to an proper (info/error) log file."""
    #if error:
    #    add_message_to_file(message, properties.ERROR_FILENAME)
    #else:
    #    add_message_to_file(message, properties.INFO_FILENAME)


def add_comments(submission, heroes_dict):
    """Method used to check all the comments in a submission and add replies if they are responses.

    All comments are loaded. If comment ID is in the already doone comments database, next comment
    is checked (further actions are ommited). If the comment wasn't analized before,
    it is prepared for comparision to the responses in dictionary. If the comment is not on the
    excluded responses list (loaded from properties) and if it is in the dictionary, a reply
    comment is prepared and posted.
    """
    submission.comments.replace_more(limit=None, threshold=0)
    for comment in submission.comments.list():
        COMMENTS_DB_CURSOR.execute("SELECT id FROM comments WHERE id=?", [comment.id])
        if COMMENTS_DB_CURSOR.fetchone():
            continue

        stripped_body = comment.body.replace(r".", "")
        stripped_body = stripped_body.replace(r",", "")
        stripped_body = stripped_body.replace(r"'", "")
        stripped_body = stripped_body.replace(r"’", "")

        #response = prepare_response(comment.body)
        response = prepare_response(stripped_body)
        if response in properties.EXCLUDED_RESPONSES:
            save_comment_id(comment.id)
            continue

        #if add_flair_specific_response(comment, heroes_dict, response):
            #continue

        if response in SPECIFIC_RESPONSES_DICT:
            SPECIFIC_RESPONSES_DICT[response](comment, heroes_dict, response)
            continue

        add_regular_response(comment, heroes_dict, response)
        save_comment_id(comment.id)


def save_comment_id(comment_id, do_log=False):
    """ This function is pretty important, saves the comment ID so we don't spam"""
    if do_log:
        log("Added: " + comment_id)
    COMMENTS_DB_CURSOR.execute("INSERT INTO comments VALUES (?, ?)", (comment_id, date.today()))
    COMMENTS_DB_CONN.commit()


def create_reply(response_url, heroes_dict, orignal_text, img=None):
    """Method that creates a reply in reddit-post format.

    The message consists of a link the the response, the response itself, a warning about the sound
    and an ending added from the properties file (post footer).
    """
    short_hero_name = parser.short_hero_name_from_actual_url(response_url)
    hero_name = heroes_dict[short_hero_name]
    if img:
        return (
            "[]({}): [{}]({}) (sound warning: {}){}"
            .format(img, orignal_text, response_url, hero_name, properties.COMMENT_ENDING)
            )
    #else:
    return (
        "[{}]({}) (sound warning: {}){}"
        .format(orignal_text, response_url, hero_name, properties.COMMENT_ENDING)
        )


def prepare_response(response):
    """Method used to prepare  the response.

    Dots and exclamation marks are stripped. The response is turned to lowercase.
    Multiple letters ending the response are removed (e.g. ohhh->oh).
    """
    response = response.strip(" .!").lower()

    #i = 1
    new_response = response
    # Temprarily removing this, is messing with a bunch of crap
    #try:
    #    while response[-1] == response[-1 - i]:
    #        new_response = new_response[:-1]
    #        i += 1
    #except IndexError:
    #    log("IndexError", True)

    return new_response


if __name__ == '__main__':
    while True:
        try:
            execute()
        except (KeyboardInterrupt, SystemExit):
            COMMENTS_DB_CONN.commit()
            raise
        except:
            COMMENTS_DB_CONN.commit()
            log(traceback.format_exc())
